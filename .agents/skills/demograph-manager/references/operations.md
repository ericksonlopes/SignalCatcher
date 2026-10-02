# Operations and validation

## Configuration and storage

Read `src/core/config/settings.py`, `.env.example`, `docker-compose.yml` and
`docker-compose.local.yml` for current defaults and mounts.

- `DEMOGRAPH_STORAGE_PATH`: optional override; empty derives the `demograph`
  sibling of `DOWNLOAD_YOUTUBE_PATH`.
- `DEMOGRAPH_NEO4J_URI`, `DEMOGRAPH_NEO4J_USER`, `DEMOGRAPH_NEO4J_PASSWORD`,
  `DEMOGRAPH_NEO4J_DATABASE`: external graph connection; no frontend credentials.
- Production extraction files: `/media/eriberry/SSD_1/demograph`, mounted at
  `/demograph` in the backend containers. Local overlay: `./demograph`.
- Execution starts from HTTP commands via FastAPI BackgroundTasks, returning `running`.
  No DemoGraph worker, global advisory lock or queue consumer exists. Keep the API
  active during tasks; process restarts do not automatically resume them.
- Compose includes `demograph-storage-init` and the shared migration service. The API
  depends on storage initialization. It creates the missing directory and assigns
  a root-owned mount directory to UID/GID 1000 when running as root; it does not
  recursively change existing artifacts.
- Upgrades remove the old `demograph-worker` service/container and apply catalog
  migration `da2026100202`, which drops its obsolete heartbeat table. Legacy queued
  runs can be started manually with Resume. Pending statuses remain readable for
  compatibility but new HTTP submissions never wait for a consumer.

## External Neo4j / Portainer

Read `deploy/portainer/demograph-neo4j.compose.yml` and
`deploy/portainer/README.md` for the ready-to-paste Docker Standalone stack.
Current image: `neo4j:5.26-community`, official ARM64/AMD64 image, no APOC dependency.
Verify current official image support when changing the image or Neo4j major version.

Required Portainer variable: `DEMOGRAPH_NEO4J_PASSWORD`. Optional
`DEMOGRAPH_NEO4J_HOST` defaults to `demograph-neo4j`; set it to the Raspberry LAN
address for external Browser clients, or enter the Raspberry Bolt address manually.
External bridge network defaults to `signalcatcher_network`. Same-host backend
URI is `bolt://demograph-neo4j:7687`; cross-host URI uses the Raspberry address.
Browser and Bolt ports are 7474 and 7687. Graph persistence defaults to
`/media/eriberry/SSD_1/demograph-neo4j/{data,logs,import}`, separate from extracted
files. Heap, page cache, container memory and storage root are configurable.

`NEO4J_AUTH` initializes credentials only for a new database; changing the stack
variable does not rotate the password of an existing data directory. Preserve
data volumes and existing authentication when preparing upgrades. Treat an
external schema/ingestion command as a graph write, not a read-only connectivity check.

For SSD permission failures, see the Portainer README troubleshooting section.
The image user is UID/GID `7474:7474`. Inspect the host filesystem, mount options
and directory ownership before choosing a repair. Limit any ownership changes
to this graph database's directories; NTFS/exFAT, read-only mounts and Docker
user-namespace remapping require diagnosis beyond a plain `chown`.
For the observed SSD `fuseblk` mount, a standalone alternative is
`deploy/portainer/demograph-neo4j.volumes.compose.yml`. Its named volumes live
under the Docker data root: verify that root uses a writable Linux filesystem.
This initializes a separate graph database and does not migrate old bind-mounted
data. Extraction artifacts continue on the SSD. Preserve named volumes on redeploy.

## Verification

Run from the backend root with its existing environment:

```powershell
uv run ruff check src/modules/demograph tests/test_demograph.py
uv run ruff format --check src/modules/demograph tests/test_demograph.py
uv run mypy src
uv run python -m unittest discover -s tests -p "test_demograph*.py" -v
```

For frontend changes, run `npm run lint` and `npm run build` in the frontend root.
Use the mock server for interface validation; report whether checks use fixtures
or the real backend. Build success alone does not confirm ingestion.

The test suite covers dependencies, official vote choices, full-file schemas,
encoding, cancellation, safe paths, checksum resume/tampering, pagination failures,
404 topics, retained extraction, API authorization, reversible migrations, worker
direct API execution, legacy pending-run resume and Neo4j receipt replay/newer-snapshot protection.

By default tests use isolated SQLite and HTTP fixtures; PostgreSQL coexistence and
Neo4j integration cases require explicit test environment variables. **The suite
drops its catalog tables and deletes every node in the supplied graph database.**
Never point `DEMOGRAPH_TEST_SQL_URL` or `DEMOGRAPH_TEST_NEO4J_URI` at production
or the legacy PoC. Use `tests/integration/demograph-compose.yml` with a dedicated
Compose project; get random host ports with `docker compose ... port`, then set
`DEMOGRAPH_TEST_SQL_URL`, `DEMOGRAPH_TEST_NEO4J_URI` and
`DEMOGRAPH_TEST_NEO4J_PASSWORD` to those disposable services. See the repository
README DemoGraph section for full commands. Stop only the test project you created.

Validate Compose syntax with `docker compose -f <file> config --quiet`, using
dummy values for required interpolation variables. Do not print resolved config
containing real credentials. A successful config check does not prove Raspberry
deployment, external network existence or available memory.

## Extraction deletion

Deploy backend and frontend together; this feature needs no SQL migration. Deletion
is manual per version, including all files/datasets and associated load runs. Finish
active executions first. Keep the API alive while the synchronous request reconstructs
remaining Neo4j batches in one transaction. Foreign edges and their nodes survive.
Large graphs require time/memory for reconstruction.

Legacy receipts are recovered from verified original artifacts before changing the
graph. If recovery fails, retain files and catalog, repair the source artifacts and
retry. `delete_failed` and an interrupted `deleting` stage can both be resumed through
the same DELETE endpoint/button. A successful graph checkpoint prevents repeated
graph work when physical directory removal needs retry. Schema observation failure
requires manual Refresh schema after successful removal. Never purge the SQL catalog
before Neo4j and files have been handled.

Deletion tests cover authorization, active runs, path isolation, files/catalog removal,
graph and filesystem failures, retry checkpoints, interrupted deletion, preserving
other versions, legacy tamper checks, restoration of shared snapshots and foreign
relationship protection. Integration tests use only disposable PostgreSQL/Neo4j.

## Full reset and metadata

Normal extraction deletion removes data but Neo4j label/property tokens remain in
the store. Community 5.26 needs an offline user-database reset to clear those tokens.
With explicit user authorization, use `deploy/portainer/reset-demograph-neo4j.sh`
on the Raspberry Docker host; the argument is the stack/project name (currently
`neo4j`). Verify the installed image, `/data` persistence and resolved directories.
The script stops the selected service and deletes only its `neo4j` store and
transaction log directories, preserving `system` authentication and extracted files.
Reconnection must confirm zero labels/property keys/constraints, not merely zero nodes.
This procedure was verified in a disposable container with a persistent volume.

Graph operation admission uses short serializable SQL transactions to prevent
starting a load while deletion is being admitted; no worker/advisory lock is added.
DemoGraph frontend preserves endpoint conflict reasons and translates deletion errors.
HTTP integration verifies starting a pipeline and deleting its files/catalog/graph;
PostgreSQL integration verifies overlapping start/delete cannot both be admitted.

## Parallel topic extraction

Set `DEMOGRAPH_HTTP_CONCURRENCY=4` in backend environment (default; range 1..8,
per extraction; use 1 for sequential requests). Recreate the API container to apply
configuration/code updates. No SQL migration or Neo4j stack change is required.
Voting details finish before deduplicated topic requests. Own sessions are closed
when pools finish. Cancellation/failure joins running requests; network timeouts can
delay termination. Registered artifacts remain reusable. Retry-After seconds/date
are honored up to 120 seconds per retry. Resource phase/counts appear in PT/EN UI.
Tests use HTTP fixtures with barriers to prove four simultaneous requests, own
sessions, deduplication, joined cancellation/failure, retained files and 429 backoff.

## Party analysis operations

Deploy API/frontend together; no SQL migration, configuration or Neo4j plugin change.
Load Votings, Votes and Histories, then manually calculate party agreement from Runs.
Dates and minima form the PoC-compatible key. The computation uses the currently
loaded graph, not a chosen extraction version or guaranteed complete source coverage.
Review exclusions and observed date bounds. New loads/deletions remove old derived
relations; rerun explicitly. A revision conflict requires retry after loading finishes.
Cancellation/failure rolls back publication; an earlier committed result is preserved.
Report source_revision records provenance; DemoGraphState is an internal persistent
revision node. External/manual graph writes do not advance it.

Use `test_demograph*.py` to include the separate pure algorithm suite. Integration
verifies a known party score with the original query, idempotence, atomic cancelled
publication, invalidation/stale revision rejection and deletion. All graph tests use
only dedicated disposable databases; do not initiate production analysis as a test.
