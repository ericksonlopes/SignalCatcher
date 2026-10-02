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
uv run python -m unittest discover -s tests -p test_demograph.py -v
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
