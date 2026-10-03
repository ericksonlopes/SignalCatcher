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

