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
worker behavior, deployment or tests. Check actual source before relying on this map.

## Preserve architecture

- Keep domain entities, interfaces, dataset rules and mapping free of infrastructure
  dependencies. Application use cases orchestrate domain contracts; infrastructure
  implements them; presentation validates requests and wires dependencies.
- Preserve the granular folders. Each ORM table has its own file under
  `infrastructure/models/`. Each dataset has an extractor, mapper and graph query
  in the appropriate package. Shared transport, storage and schema observation stay
  reusable. HTTP routes, DTOs, dependency injection and workers stay separate.
- Export ORM models through `infrastructure/models/__init__.py` for Alembic discovery.
  Keep the shared `src.core.database.connector.Base`; add migrations when database
  structure changes. Use absolute `src.` imports, and update runtime module commands
  when moving worker entrypoints.

## Pipeline invariants

- `votes` and `topics` require `votings`. Histories without votes include current
  deputies. Preserve dependency ordering from `domain/rules/datasets.py`.
- Annual CSVs retain full source coverage. The inclusive date interval filters graph
  loads by voting dates, not saved CSV contents. Deputies represent the current
  snapshot; histories retain the official historical records.
- Preserve all official vote choices, including abstention and obstruction. Do not
  reintroduce similarity calculations or PoC filters without a user request.
- Default artifact storage is a sibling of `DOWNLOAD_YOUTUBE_PATH` named `demograph`.
  Create missing directories automatically. Registered paths stay within this root.
  Keep `.gitignore` storage rules anchored at the repository root so they cannot
  hide `src/modules/demograph/`.
- Publish files atomically, then register checksum, origin, time, encoding, counts
  and observed fields. Verify registered checksums on resume and before loading.
  Preserve complete JSON envelopes, pagination-loop detection, bounded transient
  retries and cooperative cancellation during streaming and batches.
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
availability/checksum, worker heartbeat and Neo4j health before choosing a retry.
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
