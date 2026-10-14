# DemoGraph Neo4j on Raspberry Pi / Portainer

This stack deploys the external graph database used by DemoGraph. The API, PostgreSQL
catalog and frontend continue to run in their existing stacks.
Use a Raspberry Pi with a 64-bit operating system and Docker ARM64. The official
`neo4j:5.26-community` image supports ARM64; Docker selects the host architecture.
Reserve at least 2 GB of available RAM for this configuration, in addition to other services.
This file targets Portainer Docker Standalone, not Docker Swarm.

For an SSD mounted as `fuseblk` (usually NTFS via FUSE), use the standalone
`demograph-neo4j.volumes.compose.yml` variant instead of SSD bind mounts, provided
the Docker data root resides on a writable Linux filesystem. Check on the Raspberry:

```bash
findmnt -T "$(sudo docker info --format '{{.DockerRootDir}}')" -o TARGET,FSTYPE,OPTIONS
```

The variant persists graph data, logs and import files in Docker-managed named
volumes under the Docker data root, which may be on the SD card rather than the SSD.
Extracted source files still use the existing `demograph` directory on the SSD.
Paste the entire variant into the same Portainer stack and retain its environment
variables. It initializes a separate database; it does not import or delete files
from the previous SSD data directory. If that directory holds a working database,
migrate it with an appropriate backup/restore procedure before switching storage.
Keep the stack name stable, and preserve the named volumes when redeploying.

## Deploy in Portainer

1. Open **Stacks → Add stack**, and name it `demograph-neo4j`.
2. Paste the contents of `demograph-neo4j.compose.yml` into **Web editor**.
3. Add these variables in the stack's **Environment variables** section:

   | Variable | Value |
   | --- | --- |
   | `DEMOGRAPH_NEO4J_PASSWORD` | A new strong password for the `neo4j` user |
   | `DEMOGRAPH_NEO4J_HOST` | Optional: Raspberry LAN IP or hostname, without a scheme or port; recommended for external Browser access |
   | `SIGNALCATCHER_NETWORK` | `signalcatcher_network`, or the existing backend network name |

4. Ensure that this external network exists on the selected Docker environment. The
   SignalCatcher stack already uses it. If needed, create a **bridge** network under
   **Networks → Add network** with the same name.
5. Confirm that the SSD is mounted at `/media/eriberry/SSD_1`, then deploy the stack.
   Docker creates the missing bind directories. Wait for the container to become healthy.
6. Open `http://RASPBERRY_IP:7474`, then sign in as `neo4j` with the configured password.
   Without `DEMOGRAPH_NEO4J_HOST`, the advertised address defaults to the internal
   Docker hostname `demograph-neo4j`. For a Browser client on another computer,
   enter `bolt://RASPBERRY_IP:7687` in its connection form, or set the host variable
   to the Raspberry LAN address and redeploy.

The stack stores the database under `/media/eriberry/SSD_1/demograph-neo4j/data`.
Logs and import files use sibling folders. Extracted source files remain under
`/media/eriberry/SSD_1/demograph`; they are managed by the DemoGraph API.
Ports 7474 (Browser) and 7687 (Bolt) must be available on the Raspberry.

## Connect SignalCatcher

Set these environment variables in the existing SignalCatcher stack and redeploy its API
service:

```dotenv
DEMOGRAPH_NEO4J_URI=bolt://demograph-neo4j:7687
DEMOGRAPH_NEO4J_USER=neo4j
DEMOGRAPH_NEO4J_PASSWORD=THE_SAME_PASSWORD_AS_THE_NEO4J_STACK
DEMOGRAPH_NEO4J_DATABASE=neo4j
```

The service hostname works when both stacks use the same Docker bridge network on the
same host. For a backend on a different host, use `bolt://RASPBERRY_IP:7687` instead.
The frontend receives no Neo4j credentials. Confirm Neo4j availability on the DemoGraph
screen, then start an extraction and load.

## Optional settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEMOGRAPH_NEO4J_HOST` | `demograph-neo4j` | Advertised hostname; use the Raspberry LAN address for external clients |
| `DEMOGRAPH_NEO4J_STORAGE` | `/media/eriberry/SSD_1/demograph-neo4j` | Persistent database directory |
| `DEMOGRAPH_NEO4J_HEAP` | `512M` | Maximum Java heap |
| `DEMOGRAPH_NEO4J_PAGECACHE` | `512M` | Graph page cache |
| `DEMOGRAPH_NEO4J_MEMORY_LIMIT` | `2g` | Total container memory limit |

Increase heap/cache for larger loads only when RAM is available. Keep the total container
limit above heap plus page cache to leave space for JVM and native allocations. Changing
`NEO4J_AUTH` initializes a new database's password; it does not change credentials on an
existing `/data` directory. Stack redeploys preserve the bind-mounted database.

References: [official Neo4j image](https://hub.docker.com/_/neo4j),
[Docker configuration](https://neo4j.com/docs/operations-manual/current/docker/configuration/),
[initial authentication](https://neo4j.com/docs/operations-manual/current/docker/introduction/).

## Permission errors on the SSD

An `AccessDeniedException` writing `/data/dbms/*_auth.ini.tmp` means the container
cannot initialize authentication on its mounted data directory. The Neo4j user
in this image has UID/GID `7474:7474`. Diagnose on the Raspberry host via SSH:

```bash
findmnt -T /media/eriberry/SSD_1 -o TARGET,SOURCE,FSTYPE,OPTIONS
ls -ldn /media/eriberry/SSD_1/demograph-neo4j/{data,data/dbms,logs}
```

For a writable Linux filesystem such as ext4, XFS or Btrfs, stop the Neo4j
container in Portainer, then repair only this database's directories:

```bash
sudo mkdir -p /media/eriberry/SSD_1/demograph-neo4j/{data,logs,import}
sudo chown -R 7474:7474 /media/eriberry/SSD_1/demograph-neo4j/{data,logs,import}
sudo chmod -R u+rwX /media/eriberry/SSD_1/demograph-neo4j/{data,logs,import}
```

Start the container again. Substitute the actual root if `DEMOGRAPH_NEO4J_STORAGE`
was overridden. Do not apply these commands to the entire SSD or unrelated module
files. For NTFS/exFAT, a read-only mount, ACLs or Docker user-namespace remapping,
first inspect the actual mount/identity configuration; host `chown` alone may not
resolve the error. Do not format the disk or remove the data directory as a repair.
# Reset all graph metadata

Deleting nodes/relationships leaves Neo4j's label/property tokens and identity
constraints in the store. On Community Edition, removing these tokens requires an
offline reset of the user database. With explicit authorization to discard the
graph, run `sudo bash reset-demograph-neo4j.sh neo4j` on the Raspberry Docker host
using [reset-demograph-neo4j.sh](reset-demograph-neo4j.sh). The argument is the
Portainer stack/Compose project name.

The script verifies a single `demograph-neo4j` service and persistent `/data` mount,
stops it, reuses its exact image without networking, checks resolved paths and removes
only `/data/databases/neo4j` and `/data/transactions/neo4j`. It restarts the container,
preserving `system` (users/passwords), extraction files and unrelated volumes.
Wait for healthy status, reconnect Neo4j Browser and verify empty nodes, labels,
property keys and constraints. The next DemoGraph load recreates its identity constraints.

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

### Party agreement analysis upgrade

Deploy backend and frontend together. This feature adds no environment variable,
SQL migration or Neo4j plugin. After Votings, Votes and Histories are loaded, run
Agreement between parties from DemoGraph's Runs tab. New loads and deletions
invalidate managed derived relationships; recalculate after changing source data.
The internal DemoGraphState revision node may remain after deleting the last
extraction. It stores no worker heartbeat or business records. See the repository
README for PoC v1 criteria, coverage limits and the analysis-key query contract.
