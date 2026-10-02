# Module map

Paths below are relative to the backend root unless prefixed with `frontend:`.

## Backend responsibilities

| Path | Responsibility |
| --- | --- |
| `src/modules/demograph/domain/entities/run.py` | Pure run entity |
| `domain/interfaces/{catalog,extractor,loader}.py` | Pipeline ports; paths under the module |
| `domain/contracts.py` | Public domain facade |
| `domain/rules/datasets.py` | Dataset ordering, dependency resolver, terminal statuses |
| `domain/mapping/` | Dispatcher, shared identities and one mapper per dataset |
| `application/use_cases/pipeline.py` | Extract/load/schema orchestration and terminal outcomes |
| `infrastructure/models/` | One SQLAlchemy model per table and discovery exports |
| `infrastructure/catalog/repository.py` | SQL catalog, runs, artifacts, issues, cached schema |
| `infrastructure/catalog/serialization.py` | Timestamp and ORM serialization helpers |
| `infrastructure/extraction/transport.py` | HTTP, retries, pagination, publication and cancellation |
| `infrastructure/extraction/extractor.py` | Dataset dispatch and extraction checkpoints |
| `infrastructure/extraction/annual.py` | Shared annual CSV extraction |
| `infrastructure/extraction/selection.py` | Voting/deputy identities selected from artifacts |
| `infrastructure/extraction/{deputies,votings,votes,histories,topics}.py` | Dataset-specific extraction |
| `infrastructure/storage/files.py` | Safe paths, streaming SHA-256, CSV/JSON decoding |
| `infrastructure/storage/schema.py` | Complete-file field observation and CSV type inference |
| `infrastructure/graph/loader.py` | Neo4j constraints, transactions, batch receipts, observed schema |
| `infrastructure/graph/queries/` | Cypher per dataset, voting details and proposition topics |
| `presentation/routes/` | Catalog, runs, artifacts, schema and health routers |
| `presentation/dtos/run_request.py` | Run selection/date validation |
| `presentation/dependencies/` | SQL catalog and graph dependency factories |
| `presentation/workers/prepare_storage.py` | Missing directory creation and mount ownership preparation |

`main.py` registers the router at `/api/demograph` with the existing administrative
security dependency. `alembic/env.py` imports the ORM facade. The initial migration
is `alembic/versions/da2026100201_demograph_catalog.py`; the follow-up `da2026100202_demograph_api_execution.py` removes the obsolete
worker heartbeat table. Add later migrations rather
than rewriting a migration that has already been applied.

## PostgreSQL catalog

| Table / model | Purpose |
| --- | --- |
| `demograph_datasets` / `DatasetModel` | Supported source datasets |
| `demograph_runs` / `RunModel` | Operation, selection, period, source snapshot, lifecycle, progress, cancellation and stale schema |
| `demograph_artifacts` / `ArtifactModel` | Version/dataset, registered path, format, checksum, size/count, origin, timestamp, observed fields and metadata |
| `demograph_issues` / `IssueModel` | Sanitized run issues and context |
| `demograph_schemas` / `SchemaModel` | Timestamped observed graph schema linked to a run |

Graph concepts include Person, Party, Voting, Legislature, State, PublicOffice,
DeputyHistory, Proposition and Topic. `DemoGraphBatch` is an internal transaction
receipt. Check current `KEYS` and dataset Cypher for identity/relationship behavior.

## HTTP contracts

All paths use `/api/demograph`:

- `GET /datasets`, `GET /datasets/{dataset_id}`: catalog and paginated versions.
- `GET /runs`, `POST /runs`, `GET /runs/{run_id}`: immediate background dispatch and run details.
- `POST /runs/{run_id}/retry`, `POST /runs/{run_id}/cancel`: lifecycle commands.
- `POST /extractions/{extraction_id}/load`: load retained source files separately.
- `GET /artifacts/{artifact_id}/schema`, `/preview`, `/download`: registered files.
- `GET /schema`, `POST /schema/refresh`: cached observation and immediate background refresh.
- `GET /health`: API execution mode, storage availability and Neo4j connectivity.

Operations are `extract`, `pipeline`, `load` and `schema`; the public run request
accepts `extract` or `pipeline`. Outcomes include `completed_with_errors`, not only
completed/failed. Check routes and repository validation before changing retry rules.

## Frontend

Resolve the sibling `SignalCatcherFrontend` root. Important files:

- `src/components/apps/DemoGraphApp.tsx`: catalog, run creation/detail and schema.
- `src/components/apps/demograph/SchemaDiagram.tsx`: interactive type diagram.
- `src/demographTypes.ts`, `src/types.ts`: typed HTTP contracts and exports.
- `src/locales/demograph.ts`, `src/locales/pt.ts`, `src/locales/en.ts`: translations.
- `src/App.tsx`, `src/navigationStorage.ts`, `src/components/CommandPalette.tsx`:
  module navigation and shortcuts; verify the current component path when editing.
- `src/api.ts`: shared HTTP/auth behavior.
- `server/demographMock.ts`, `server.ts`: development routes and deterministic fixtures.

The catalog is the default DemoGraph screen. Run polling occurs while visible;
health polling has its own interval. Preserve bounded file lists and version/run
pagination when extending the UI.
