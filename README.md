# SignalCatcher

SignalCatcher monitors YouTube channels, captures metadata, downloads videos and manages
diarization tasks. It uses FastAPI, PostgreSQL, SQLAlchemy/Alembic, APScheduler and yt-dlp.

## Architecture

```
main.py                  FastAPI API; receives commands and serves queries
worker.py                Dedicated scheduler; consumes durable requests
src/core/                Settings, database, logging, security and operational telemetry
src/modules/youtube/     Domain, application, infrastructure and presentation
src/modules/diarization/ Domain, application, infrastructure and presentation
alembic/                 Versioned database migrations
script/                  Maintenance commands
```

The API never starts a scheduler or runs media work with FastAPI BackgroundTasks.
Administrative requests and content changes commit in the same transaction before the
HTTP response is sent. The worker consumes coalesced requests from `job_control`.
One pending rerun per job is retained even if requests arrive during an active run.
An exclusive PostgreSQL advisory lock permits one scheduler worker per database;
API processes can be scaled separately. Scheduler definitions live in code rather than
sharing an APScheduler 3 job store between API processes.

Content is reserved with `SELECT FOR UPDATE SKIP LOCKED`. Every reservation has a unique
token and an expiration timestamp, renewed every 20 seconds in short transactions.
Final updates validate ownership and expiry, so an old executor cannot overwrite a newer
reservation. External calls run outside database transactions. Download progress checks
reservation health and aborts after loss of ownership.

## Local setup

Requirements: Python 3.10+ (Docker/CI use 3.12), uv, PostgreSQL and FFmpeg on PATH.

Copy `.env.example` to `.env` and set at least:

```dotenv
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_DATABASE=signalcatcher
DOWNLOAD_YOUTUBE_PATH=./youtube
ADMIN_API_KEY=your_long_random_key
```

Generate the administrative key locally, for example with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep `.env` untracked.

Install dependencies and apply migrations:

```sh
uv sync --frozen
uv run alembic upgrade head
```

Start the worker and API in separate terminals:

```sh
uv run python worker.py
```

```sh
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Swagger is at `http://127.0.0.1:8000/docs`. The API can serve read requests without a
worker, but `/ready` returns 503 and queued media requests wait until a worker is ready.

### Administrative access

POST, PATCH and DELETE operations under `/api/youtube` and `/api/diarization` require
`X-API-Key`, compared against `ADMIN_API_KEY`. `/metrics` requires the same key.
Reads remain available without an administrative key. Missing server configuration
returns 503 for administrative operations; a missing/incorrect request key returns 401.
Use HTTPS when accessing the API over an untrusted network.

The sibling `SignalCatcherFrontend` project lets users enter the key in **Settings**.
It stores the key for that browser tab and attaches the header to administrative calls.
Never set the key as a `VITE_*` variable or embed it in frontend source/builds.
Set `VITE_API_BASE_URL` to the API URL. The frontend **Operations** tab shows live
worker/queue/job telemetry and queues manual runs through the API.

```sh
curl -X POST http://localhost:8000/api/youtube/scheduler/jobs/youtube_extract_and_download/run \
  -H "X-API-Key: YOUR_KEY"
```

## Docker

The base stack expects PostgreSQL on the existing `signalcatcher_network` network.
Create that network if it does not exist and attach your PostgreSQL container to it.
The downloads directory must be writable by container UID/GID 1000.

```sh
docker compose up --build -d
```

The stack has three backend services:

- `migrate` applies Alembic migrations once, before either long-running service starts.
- `app` exposes the API on port 5001 and checks readiness.
- `worker` owns scheduling and media processing; its healthcheck verifies the stored heartbeat.

The Compose stack mounts `/media/eriberry/SSD_1/youtube` on the Raspberry Pi host
at `/youtube` in both API and worker containers, with `DOWNLOAD_YOUTUBE_PATH=/youtube`.
Samba continues to share the same SSD directory. The local overlay mounts `./youtube`
from the development host at `/youtube`.
`DIARIZATION_API_URL` must be reachable from the container; the default Compose value
is `http://diarization:8001`. `localhost` inside a container means that same container.

The local overlay also builds the sibling frontend and exposes API port 8000/frontend
port 3000. It requires Docker Compose 2.24.4+ for `!override`:

```sh
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build -d
```

### Upgrade from an API with an embedded scheduler

Stop the old API/scheduler before applying the new migration. After upgrading the schema,
start the dedicated worker and new API together. Do not run the old code alongside the
new worker: old jobs do not participate in the reservation protocol. Existing captured
content is preserved. Legacy `apscheduler_jobs` entries are no longer loaded; schedules
are recreated from code, while manual requests and telemetry live in `job_control`.
Do not restart the old application after this migration without reviewing compatibility.

## Content pipeline and recovery

```
STARTED -> PENDING_METADATA_EXTRACTION -> EXTRACTING_METADATA
        -> METADATA_EXTRACTED -> PENDING_DOWNLOAD -> DOWNLOADING
        -> DOWNLOADED -> COMPLETED
```

The worker checks reservations every 30 seconds, resetting only expired/orphaned
processing states. Active heartbeats are never reset. A killed download is retried from
the pending download stage; retries replace final-looking partial files left by the
storage-compatible `nopart` download mode. Reservations expire after 300 seconds by default.

Unclassified failures become `ERROR`. Retry attempts use exponential backoff from
300 seconds up to 86400 seconds and stop after 5 metadata processing attempts per cycle.
The retry queue excludes items already attempted in its current run, so one repeatedly
failing item cannot stop other eligible videos. A successful download clears the error,
retry schedule and attempt counter. Manual retry resets the counter and queues `REPROCESSING`.
Known restrictions remain classified as `MEMBERS_ONLY`, `AGE_RESTRICTED`, `PRIVATE_VIDEO`,
`COPYRIGHT_REMOVED`, `ACCOUNT_TERMINATED` or `VIDEO_REMOVED`. Upcoming premieres/lives
use `SCHEDULED` and are periodically returned to the download queue.

Deletion is asynchronous. DELETE returns 202 and sets `deletion_requested`; the content
is excluded from processing queues. The worker confines every resolved path to the
configured downloads directory, removes files idempotently and then commits `DELETED`.
Failures preserve the original state and record the error with backoff. Deletion has
its own attempt counter and stops after the configured attempt limit. Submitting DELETE
again resets that counter. Conflicting commands on an actively reserved video return 409.
The UI shows deletion pending until physical removal has been confirmed.

## Worker jobs

| Job ID | Schedule |
| --- | --- |
| `youtube_monitor_channels` | Every 30 minutes; independently of media work |
| `youtube_extract_and_download` | Every 15 minutes; metadata then downloads |
| `youtube_process_errors` | Every 30 minutes |
| `youtube_promote_scheduled` | Every 30 minutes |
| `youtube_delete_contents` | Every minute |
| `youtube_extract_metadata` | Manual only |
| `youtube_download_videos` | Manual only |

Requests are polled every 2 seconds. Media jobs share one processing lane; requests
received during a long job remain pending. Monitoring can run alongside media processing.
The configured intervals restart from worker startup; the scheduler does not replay
missed interval ticks. Durable manual requests survive worker restarts.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/status` | API liveness |
| GET | `/ready` | Database connectivity and fresh worker heartbeat; 503 if unavailable |
| GET | `/metrics` | Administrative JSON telemetry: queue age/counts, exhausted retries, job runs/failures/duration |
| POST / GET | `/api/youtube/monitored_channels` | Register/list monitored channels |
| PATCH | `/api/youtube/monitored_channels/{id}/status` | Toggle monitoring |
| GET | `/api/youtube/channels` | Saved channels |
| POST / GET | `/api/youtube/content` | Ingest a video / list paginated content |
| POST | `/api/youtube/playlist` | Ingest a playlist |
| GET | `/api/youtube/content/status-count` | Content counts by step |
| GET | `/api/youtube/content/{external_id}/tracking` | Transition history |
| POST | `/api/youtube/content/{external_id}/retry` | Queue manual retry |
| POST | `/api/youtube/content/retry-errors` | Queue eligible error retries |
| POST | `/api/youtube/content/trigger-metadata-extraction` | Queue metadata work |
| POST | `/api/youtube/content/trigger-downloads` | Queue downloads |
| DELETE | `/api/youtube/content/{external_id}` | Queue recoverable physical deletion |
| POST | `/api/youtube/scheduler/jobs/{job_id}/run` | Queue a job by ID |
| POST | `/api/diarization/youtube/{external_id}` | Create a diarization task for completed content |
| GET | `/api/diarization/list` | List diarization tasks |
| POST | `/api/diarization/{id}/reprocess` | Requeue a diarization task |
| POST | `/api/diarization/{id}/cancel` | Cancel an eligible diarization task |

Compatibility routes under `/api/youtube/scheduler/jobs/*/execute` also enqueue work.
A 202 response acknowledges persistence of the request, not successful job completion.
Content listing includes `deletion_requested`, `attempt_count`, `next_retry_at`,
`error_info`, language and publication/creation timestamps.

## Configuration

All settings are documented in `.env.example` and validated by Pydantic Settings.

| Variable | Default / purpose |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DATABASE` | Required database connection |
| `DOWNLOAD_YOUTUBE_PATH` | Required download root |
| `ADMIN_API_KEY` | Administrative writes and telemetry; no default credential |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` |
| `PROCESSING_LEASE_SECONDS` | 300; minimum 60 |
| `MAX_PROCESSING_ATTEMPTS` | 5 |
| `RETRY_BASE_SECONDS`, `RETRY_MAX_SECONDS` | 300 / 86400 |
| `WORKER_HEARTBEAT_MAX_AGE` | 60 seconds |
| `DIARIZATION_API_URL` | `http://localhost:8001` locally |
| `DIARIZATION_CONNECT_TIMEOUT`, `DIARIZATION_READ_TIMEOUT` | 10 / 300 seconds; socket timeouts, not a total deadline |
| `FFMPEG_LOCATION` | Optional; FFmpeg is installed on PATH in Docker |
| `VOICE_MONKEY_API_TOKEN`, `VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID` | Optional notifications |
| `LIST_LOG_LEVELS` | Optional comma-separated logging levels |

Database connections validate pooled connections before reuse and have a 5-second
connection timeout and 10-second statement timeout for short database operations.

## Maintenance and static checks

```sh
uv run python -m script.delete_content VIDEO_ID
uv run python -m script.reprocess_errors
uv run python -m script.reset_stuck_states
```

These commands use the same durable queue/recovery rules as the API. They do not delete
records directly or reset active reservations.

CI requires lint, formatting, type checking and the existing API import check. No test
suite was introduced by these improvements.

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## License

This project is for personal use. Consult the author for licensing information.
## DemoGraph

DemoGraph is available in the frontend side rail. Its catalog distinguishes source files from
confirmed Neo4j loads, retains extraction versions, and exposes file schemas, bounded previews,
downloads and the observed graph schema. The first version covers current deputies, voting
events, all individual vote choices, parliamentary histories and official proposition topics.
Analytical filters and similarity calculations from the PoC are not applied.

The module separates reusable pipeline infrastructure from Câmara dataset behavior:

```text
src/modules/demograph/
  domain/
    entities/                  # Execution entity
    interfaces/                # Catalog, extraction and graph loading contracts
    rules/                     # Dataset selection and dependencies
    mapping/                   # Shared identity rules and a mapper per dataset
  application/use_cases/       # Pipeline orchestration
  infrastructure/
    models/                    # One SQLAlchemy model per table
    catalog/                   # PostgreSQL repository and serialization
    storage/                   # Files, checksums, decoding and schema observation
    extraction/
      transport.py             # Shared HTTP, pagination and durable publication
      extractor.py             # Dataset dispatch and extraction checkpoints
      annual.py                # Shared annual CSV extraction
      selection.py             # Source identifiers selected from stored files
      deputies.py              # Current deputy snapshot
      votings.py               # Annual voting events
      votes.py                 # Annual individual vote choices
      histories.py             # Parliamentary histories
      topics.py                # Voting details and proposition topics
    graph/
      loader.py                # Neo4j transactions, receipts and observed schema
      queries/                 # Cypher separated by dataset
  presentation/
    dependencies/              # Dependency injection
    dtos/                      # HTTP request validation
    routes/                    # Catalog, runs, artifacts, schema and health routers
    workers/                   # Storage initialization only; no execution worker
```

To add a dataset, declare its dependencies in `domain/rules/datasets.py`, implement its
extractor and mapper, and register them in the dispatch tables. Dataset Cypher belongs in
`infrastructure/graph/queries/`. Changes to catalog tables require an Alembic migration.

The extracted files use the same storage parent as YouTube, with a sibling directory named
`demograph`. In production Compose the host path is `/media/eriberry/SSD_1/demograph`, mounted
at `/demograph` in the API and workers. The local overlay uses `./demograph` alongside
`./youtube`. For a native process, an empty `DEMOGRAPH_STORAGE_PATH` derives this sibling from
`DOWNLOAD_YOUTUBE_PATH`; an explicit setting overrides it. The extractor creates a missing
directory automatically. Compose additionally runs `demograph-storage-init` to prepare the
bind mount and assign a root-owned mount directory to application UID/GID 1000,
without recursively changing existing files.

Configure the external Neo4j instance hosted on the Raspberry Pi/Portainer:

The ready-to-paste Portainer stack is
[`deploy/portainer/demograph-neo4j.compose.yml`](deploy/portainer/demograph-neo4j.compose.yml).
See [`deploy/portainer/README.md`](deploy/portainer/README.md) for stack variables,
persistent SSD paths, network setup and the SignalCatcher connection settings.

```dotenv
DEMOGRAPH_NEO4J_URI=bolt://RASPBERRY_IP:7687
DEMOGRAPH_NEO4J_USER=neo4j
DEMOGRAPH_NEO4J_PASSWORD=YOUR_PASSWORD
DEMOGRAPH_NEO4J_DATABASE=neo4j
```

Credentials stay in the backend. Use Neo4j 5.26 Community or compatible Neo4j 5.x; APOC is
not required. The graph database should be dedicated to DemoGraph; legacy PoC files and
graph records are not imported. Persist the external Neo4j `/data` directory in its own stack.

Install dependencies and apply the catalog migrations, then start the API:

```powershell
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Compose automatically runs migrations and prepares storage before starting the API.
DemoGraph has no dedicated worker or advisory lock: clicking Start, Resume, Load or
Refresh schema begins a background task in the API immediately. The response returns
`running`, while catalog progress remains available. Extraction and catalog browsing
work without Neo4j; only loads and graph schema refresh need its connection.
The existing YouTube worker remains independent. When upgrading an existing Portainer
stack, remove its old `demograph-worker` service/container and update backend and frontend.
Legacy pending executions can be started explicitly with Resume; nothing drains a queue.

In **Runs**, select datasets and a date interval, then choose extract-only or extract-and-load.
The interval is inclusive and applies to voting dates across every organ in the annual source
files. Deputies are the current snapshot and histories retain the records returned by the source.
Dependencies are included automatically. Annual CSV artifacts retain their full source coverage;
catalog file counts must not be interpreted as counts of loaded votes. Load counters distinguish
out-of-period, duplicate, invalid and processed records, including per-dataset counters.

Files are published atomically beneath `<storage>/<extraction-id>/<dataset>/`, with SHA-256,
source URL, collection time, encoding and extractor version in PostgreSQL. JSON artifacts retain
the source envelope and pagination links. A 404 topic resource is explicitly cataloged as
unavailable, with an issue. Current deputy lists use `pagina`/`itens`, while deputy
histories and proposition topics are requested without those unsupported parameters;
these endpoints return their complete collections. A 404 topic resource does not mean
the proposition has no topics. Successful extraction
files survive load failures and can be loaded separately. No automatic file deletion occurs.

To remove data, open a version in the DemoGraph catalog and click **Delete extraction**.
The confirmation identifies the entire extraction: all its datasets/files, its related
load runs and corresponding graph data. `DELETE /api/demograph/extractions/{id}` uses
the administrative API key. Active executions must finish (or finish cancellation) first.
The deletion runs directly in the API, without a worker or advisory lock.

Neo4j batches now retain their mapped rows and source metadata. Deleting a version
replays the remaining confirmed batches in snapshot order in one Neo4j transaction,
restoring older shared records instead of deleting records required by other versions.
Foreign relationships and the nodes they protect remain intact. This reconstruction
can take time on large graphs; do not start another graph operation during deletion.
Older receipts are recovered from their original checksum-verified files before mutation;
missing or modified files abort deletion without changing the graph.

Graph deletion commits before filesystem removal. Only the selected UUID directory
under DemoGraph storage is removed (including unfinished downloads), followed by its
catalog artifacts, issues and runs. A filesystem/Neo4j failure keeps the catalog entry
as **Deletion pending**; click **Retry deletion** after correcting the problem. Retrying
also recovers an interrupted deletion and skips graph work already confirmed. Refresh
the graph schema if its observation failed after deletion. No SQL migration is required
for this feature; deploy the updated backend and frontend together.

Executions and artifacts remain cataloged in PostgreSQL, while processing runs as a
background task owned by the API request. There is no global execution lock and no
separate consumer process. Keep the API running while an extraction/load is active;
restarts do not automatically resume interrupted tasks. Cancellation is checked between
streamed chunks, pages and batches. Resume reuses completed artifacts after verifying
their checksums.
Each Neo4j batch stores a receipt in the same transaction as its data, so a lost PostgreSQL
checkpoint does not duplicate writes. Load errors can leave confirmed batches in the graph;
the execution remains failed/partial until resumed. Older source snapshots do not replace
newer observed attributes. File schemas are derived during complete reads; CSV inferred types
are separate from the actual textual representation. Graph schemas inspect stored data and
actual relationship endpoints, without inventing possible label combinations. Schema refresh
failure preserves the confirmed load and flags the cached graph schema as stale.

All endpoints are under `/api/demograph`. Writes use the existing `X-API-Key` administrative
contract. Run lists and extraction versions are paginated; file previews are limited to 50 rows.
The frontend's development server provides matching in-memory DemoGraph mocks. Point
`VITE_API_BASE_URL` at the backend for real data, or at the local frontend server for fixtures.

Tests (the HTTP tests use the project's `httpx2` development dependency):

```powershell
uv run python -m unittest discover -s tests -p test_demograph.py -v
docker compose -p signalcatcher-demograph-test -f tests/integration/demograph-compose.yml up -d --wait
docker compose -p signalcatcher-demograph-test -f tests/integration/demograph-compose.yml port postgres 5432
docker compose -p signalcatcher-demograph-test -f tests/integration/demograph-compose.yml port neo4j 7687
# Use the ports reported above; these credentials belong only to disposable test databases.
$env:DEMOGRAPH_TEST_SQL_URL='postgresql+psycopg2://demograph_test:demograph_test_only@127.0.0.1:POSTGRES_PORT/demograph_test'
$env:DEMOGRAPH_TEST_NEO4J_URI='bolt://127.0.0.1:NEO4J_PORT'
$env:DEMOGRAPH_TEST_NEO4J_PASSWORD='demograph_test_only'
uv run python -m unittest discover -s tests -p test_demograph.py -v
docker compose -p signalcatcher-demograph-test -f tests/integration/demograph-compose.yml down
```

The integration suite creates and drops DemoGraph tables and clears the graph in the explicitly
configured test databases. Never point these test variables at production or the PoC instance.

### Parallel DemoGraph extraction

Propositions and topics use bounded parallel HTTP extraction. Set
`DEMOGRAPH_HTTP_CONCURRENCY=4` (default; allowed 1 through 8, per extraction);
`1` processes resources sequentially. Voting details finish before deduplicated
proposition-topic requests start. Each thread owns and closes its HTTP session.
Progress reports `resources_phase` (`voting_details` or `proposition_topics`) and
completed/total resources for the current phase. Files remain individually
checksummed and reusable on explicit Resume. Cancellation or failure stops new
admissions and joins in-flight requests before reporting the terminal status.
HTTP 429/transient retries use bounded backoff and honor Retry-After (seconds or
HTTP date, capped at 120 seconds per delay). Cancellation is cooperative; an
in-flight HTTP request can wait for the configured network timeout. This runs
inside the API's manual task; it adds no execution service or global run lock.
Short local synchronization protects catalog updates and directory creation
between the threads; network requests and file downloads run concurrently.


### Party voting agreement (PoC method)

In **DemoGraph → Runs → Agreement between parties**, choose dates and click
**Calculate agreement**. This executes immediately inside the API against the
current managed Neo4j graph; it does not download data. Load **Votings, Votes and
Histories** first. Topics and current-deputy affiliations are not used by this metric.
The form defaults to 1 Yes/No participant per party and 30 shared disputed votings.
Use 2023-02-01 through 2026-09-30 to produce
`majority_sim_nao_v1:2023-02-01:2026-09-30:1:30` for the existing PoC query.

The port preserves the PoC v1 criteria: Plenary, legislature 57, explicit roll-call
or Yes/No tally evidence without symbolic-voting wording, at least 100 valid binary
votes before historical resolution. Party affiliation is the last legislature-57
history entry at or before each vote; unresolved histories are excluded, without
falling back to the current party. Abstention, obstruction and other non-binary
choices remain ingested but do not enter this metric. Party ties are excluded from
comparisons. Disputed votings have a minority of at least 10% of historically
resolved Yes/No votes. Every comparable voting has the same weight. The metric is
agreement of recorded majorities, not an ideology or attendance score.

Creates `SimilarityAnalysis`, `(Party)-[:VOTING_POSITION]->(Voting)` and
`(Party)-[:VOTING_SIMILARITY]->(Party)`. Relations expose `analysis_key`,
`agreement`, `common_votes`, `disputed_agreement`, `disputed_common_votes`,
`profile_similarity` and sample status. All compared pairs are stored; apply the
minimum shared-disputed count when querying. A completed calculation can have
zero eligible pairs; inspect the period coverage, exclusions and included counts
in run details. Available first/last voting dates are observed bounds, not proof
that all intermediate dates or source records were loaded. No data is invented
for gaps in the graph.

`POST /api/demograph/analyses/party-similarity` accepts
`{"start":"2023-02-01","end":"2026-09-30","min_party_votes":1,"min_common":30}`,
requires the administrative API key and returns a run id with HTTP 202. Cancel and
Resume use the normal run endpoints. The run operation is `analysis`; it creates
no extraction version or source file. The confirmed report is stored in
`progress.analysis`; `analysis_complete` indicates graph publication. Schema
refresh follows publication. No PostgreSQL migration or APOC installation is needed.

Publication atomically replaces the same analysis key, preserves raw vote choices
and current affiliations, and rolls back all changes on cancellation/failure.
A source revision detects loading that overlaps computation; retry after it finishes.
Every new committed load batch or extraction deletion removes managed derived
edges and invalidates analysis metadata. Recalculate explicitly after changing data.
The revision is maintained in an internal `DemoGraphState` node, excluded from the
business schema. It can remain after deleting the last extraction; it is not an
extracted voting or worker. Normal deletion still removes all corresponding votes,
files and catalog entries. External writes outside DemoGraph do not advance the
revision; recalculate after manually changing graph data.
