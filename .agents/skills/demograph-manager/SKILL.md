---
name: demograph-manager
description: >-
  Maintain, extend and debug the DemoGraph module in SignalCatcher, including
  Camara extraction, durable artifacts, PostgreSQL catalog, Neo4j loading,
  React catalog/schema screens and Raspberry Pi Portainer configuration.
  Use for requests about DemoGraph; ordinary YouTube ingestion belongs to youtube-manager.
---

# DemoGraph Manager

Work within the user's requested change. DemoGraph is a manual pipeline:
**extract official source data -> publish durable files -> load Neo4j**.
Clicking Start, Resume, Load or Refresh schema dispatches the task immediately
through FastAPI BackgroundTasks. Do not add a queue consumer, global advisory lock
or separate DemoGraph worker unless the user explicitly requests that architecture.
The catalog tracks both extracted versions and confirmed loads. Extraction works
without Neo4j. Current scope is Camara dos Deputados; the legacy PoC is a reference,
not an automatic source of files, graph records or analytical filtering.

## Find the implementation

Backend root: the SignalCatcher repository containing this skill. Frontend root:
its sibling `SignalCatcherFrontend`. The sibling `DemoGraph` repository contains
the PoC. Resolve paths from the workspace instead of assuming a user's home path.
Read the applicable repository instructions before editing.

Read [references/module-map.md](references/module-map.md) for affected backend
packages, frontend contracts, database tables and endpoints. Read
[references/operations.md](references/operations.md) when changing persistence,
API background execution, deployment or tests. Check actual source before relying on this map.

## Preserve architecture

- Keep domain entities, interfaces, dataset rules and mapping free of infrastructure
  dependencies. Application use cases orchestrate domain contracts; infrastructure
  implements them; presentation validates requests and wires dependencies.
- Preserve the granular folders. Each ORM table has its own file under
  `infrastructure/models/`. Each dataset has an extractor, mapper and graph query
  in the appropriate package. Shared transport, storage and schema observation stay
  reusable. HTTP routes, DTOs, dependency injection and storage initialization stay separate. DemoGraph has no execution worker.
- Export ORM models through `infrastructure/models/__init__.py` for Alembic discovery.
  Keep the shared `src.core.database.connector.Base`; add migrations when database
  structure changes. Use absolute `src.` imports, and update runtime module commands
  when moving bootstrap entrypoints.

## Pipeline invariants

- `votes` and `topics` require `votings`. Histories without votes include current
  deputies. Preserve dependency ordering from `domain/rules/datasets.py`.
- Annual CSVs retain full source coverage. The inclusive date interval filters graph
  loads by voting dates, not saved CSV contents. Deputies represent the current
  snapshot; histories retain the official historical records.
- Preserve all official vote choices, including abstention and obstruction. PoC v1 similarity is available as an explicitly requested manual analysis;
  its filters apply only to derived metrics, never raw ingestion.
- Default artifact storage is a sibling of `DOWNLOAD_YOUTUBE_PATH` named `demograph`.
  Create missing directories automatically. Registered paths stay within this root.
  Keep `.gitignore` storage rules anchored at the repository root so they cannot
  hide `src/modules/demograph/`.
- Publish files atomically, then register checksum, origin, time, encoding, counts
  and observed fields. Verify registered checksums on resume and before loading.
  Preserve complete JSON envelopes, pagination-loop detection, bounded transient
  retries and cooperative cancellation during streaming and batches.
- Respect endpoint-specific collection contracts: current deputies accept
  `pagina`/`itens`; deputy histories and proposition topics reject those parameters.
  Their extractors call the shared transport with `pagination=False`, retaining the
  complete response and registered checkpoint. Do not infer pagination from an
  array-shaped response or silently suppress HTTP 400.
- A 404 proposition-topic response is an explicit unavailable resource with an
  issue, not evidence that the proposition has no themes. Do not delete known graph
  theme relations based on an unavailable response.
- Retain successful extraction after load failure. Cancellation and failures can
  leave confirmed graph batches; expose that state instead of claiming rollback.
- Store Neo4j batch receipts in the same transaction as writes. Preserve replay
  semantics after a lost catalog checkpoint and prevent older source snapshots
  from overwriting newer observed attributes and relations.
- File schemas describe complete files; inferred CSV types are separate from
  textual source types. Graph schemas describe stored nodes, properties and actual
  relationship endpoints. A schema refresh failure retains a confirmed load and
  marks the cached graph schema stale.
- Catalog totals distinguish source records from processed, rejected, duplicate
  and outside-period records, including per-dataset load counters and last confirmed
  ingestion. Preserve pagination and the 50-record preview limit.
- Keep credentials in backend configuration. Writes use the existing administrative
  API-key dependency. Public errors must not expose driver credentials or payloads.

## Parallel topic extraction

`DEMOGRAPH_HTTP_CONCURRENCY` defaults to 4 and accepts 1 through 8 per extraction.
Only voting details and deduplicated proposition topics run in bounded thread pools;
keep dataset ordering and complete the first phase before starting the second.
Each thread owns its HTTP session. Preserve cancellation, bounded submission,
joining running tasks on failure/cancel, session cleanup and artifact reuse.
Local thread synchronization protects SQL catalog updates and directory creation;
it is not a global run/advisory lock. Keep downloads outside that synchronization.
Progress includes phase, completed and total resources. Honor bounded Retry-After
backoff, preserve 404 issues and never add pagination parameters to topic requests.

## Explicit extraction deletion

The catalog offers deletion per extraction version, including all its datasets/files
and associated load runs. `DELETE /api/demograph/extractions/{id}` runs synchronously
in the API with the existing administrative API-key dependency and a frontend
confirmation. Active executions must finish or complete cancellation first. There
is still no DemoGraph worker or advisory lock.

Preserve the recoverable sequence: validate the UUID directory and registered paths,
commit graph deletion, checkpoint `graph_deleted`, remove only that extraction
folder (including partial downloads), then remove its SQL catalog entries and refresh
schema. Failures retain `delete_failed`; explicit retry resumes it and interrupted
`deleting` stages. Never allow a load/resume to reuse an extraction pending deletion.

Batch receipts retain mapped rows and metadata. Graph deletion replays all remaining
confirmed batches in snapshot/path/batch order in a single transaction, restoring
shared records and retaining foreign relationships and connected nodes. Legacy
receipts need checksum-verified source files for recovery before mutation. Missing
legacy files must abort without modifying the graph. Reconstructing large graphs
can take time and memory; avoid overlapping graph operations during deletion. Do not
replace this with blanket `DETACH DELETE` or filesystem removal outside the UUID root.
Operation admission uses short serializable SQL transactions; retain specific PT/EN
conflict reasons instead of masking all HTTP 409 responses. For an explicitly requested
full reset of Neo4j metadata, follow the offline procedure in the operations reference
and `deploy/portainer/reset-demograph-neo4j.sh`; it requires Docker-host access and
preserves the system/authentication database.

## Implement a change

For a new dataset, trace the dependency resolver, extractor dispatch, mapper dispatch,
graph query dispatch, catalog seed/migration, HTTP contracts, frontend types, labels,
selection form and mock server. Change the parts required by the actual dataset;
do not silently treat an unknown dataset as topics. Verify the relevant official
Camara API/CSV contract when changing source integration.

For frontend changes, update the actual API contract, typed payloads, Portuguese and
English translations, and matching development mocks together. Use the user's
chosen data source; an in-memory mock success is not proof of a real Neo4j ingestion.

For diagnosis, inspect the run's stage, progress, issues, checkpoints, artifact
availability/checksum, API availability and Neo4j health before choosing a retry.
Avoid restarting unrelated YouTube services to resolve a DemoGraph issue.

Validate the behavior affected by the change with the existing tests and relevant
type/lint/build checks. Integration tests must use disposable databases, as described
in the operations reference. Creating a deployment file does not authorize applying
it to Portainer, running production migrations or initiating a bulk extraction.

## Mandatory Living Documentation Policy

Update this skill and its relevant references alongside changes to the module's
architecture, contracts, dataset semantics, persistence, commands or operational
invariants. Update the repository DemoGraph README and Portainer documentation when
their instructions change. Describe the final implementation and verification;
do not preserve abandoned approaches as current architecture.

## Party agreement analysis

The user requested incorporation of PoC `majority_sim_nao_v1`. Preserve the domain
algorithm in `domain/analysis/party_similarity.py`, analyzer port and graph adapter.
The standalone `analysis` run reads managed Neo4j votings/votes/histories, writes
positions/similarity atomically, then refreshes schema. It does not extract or use
current affiliations. Preserve exact date/minimum analysis keys and original PoC
selection (Plenary, legislature 57, nominal evidence, 100 binary votes before history
resolution, party majorities without ties, 10% minority for disputed comparisons).
Keep report counts/exclusions/observed date bounds; empty results must be explained
rather than silently altering thresholds. The raw full-vote graph stays intact.

New load batches and deletions invalidate all managed derived edges in the same
transaction and advance DemoGraphState revision. Publication checks the revision
atomically and aborts if input changed. Do not add an execution worker/advisory lock.
Keep revision nodes out of the business schema and preserve revision across deletion.
Rerun is manual. The HTTP 202 administrative endpoint and PT/EN form use normal
cancel/retry commands. Run reports describe historical executions, not guaranteed
current graph results. Tests must verify the original query, PoC criteria, atomic
replacement/cancellation, revision conflicts and deletion on disposable databases.
