from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as SqlSession
from sqlalchemy.orm import sessionmaker

from src.core.database.connector import Session
from src.modules.demograph.domain.contracts import DATASETS, TERMINAL, Run, resolve_datasets
from src.modules.demograph.infrastructure.catalog.serialization import model_dict, now
from src.modules.demograph.infrastructure.models import (
    ArtifactModel,
    DatasetModel,
    IssueModel,
    RunModel,
    SchemaModel,
)


class SqlCatalog:
    def __init__(self, sessions: sessionmaker[SqlSession] = Session) -> None:
        self.sessions = sessions

    @contextmanager
    def graph_mutation(self) -> Iterator[SqlSession]:
        # Serializable admission prevents write skew between starting a graph run
        # and deleting an extraction. No advisory lock or execution worker is used.
        with self.sessions.begin() as session:
            session.connection(execution_options={"isolation_level": "SERIALIZABLE"})
            yield session

    def create(
        self,
        operation: str,
        parameters: dict[str, Any],
        extraction_id: str | None = None,
        *,
        status: str = "queued",
    ) -> str:
        run_id = str(uuid4())
        with self.graph_mutation() as session:
            if operation in {"load", "pipeline", "schema", "analysis"} and session.scalar(
                select(RunModel.id).where(RunModel.status == "deleting").limit(1)
            ):
                raise ValueError("Wait for the extraction deletion to finish.")
            if operation == "load":
                original = session.get(RunModel, extraction_id)
                if original is None or original.operation not in {"extract", "pipeline"}:
                    raise LookupError("Extraction not found.")
                if not original.progress.get("extraction_complete") or original.status in {
                    "queued",
                    "running",
                    "deleting",
                    "delete_failed",
                }:
                    raise ValueError("Only a finished extraction can be loaded separately.")
                parameters = dict(original.parameters)
            elif operation not in {"schema", "analysis"}:
                parameters = {**parameters, "datasets": resolve_datasets(parameters["datasets"])}
                parameters["snapshot_at"] = now().isoformat()
            for dataset in DATASETS:
                if session.get(DatasetModel, dataset) is None:
                    session.add(DatasetModel(id=dataset, source="CAMARA_DOS_DEPUTADOS"))
            session.add(
                RunModel(
                    id=run_id,
                    extraction_id=extraction_id or run_id,
                    operation=operation,
                    parameters=parameters,
                    status=status,
                    stage="starting" if status == "running" else "queued",
                    progress={},
                    completed_stages=[],
                    cancel_requested=False,
                    schema_stale=False,
                    created_at=now(),
                    started_at=now() if status == "running" else None,
                )
            )
        return run_id

    def run(self, run_id: str) -> Run:
        with self.sessions() as session:
            row = session.get(RunModel, run_id)
            if row is None:
                raise LookupError("Run not found.")
            return Run(
                row.id,
                row.operation,
                row.extraction_id,
                dict(row.parameters),
                row.status,
                row.stage,
                dict(row.progress),
                list(row.completed_stages),
                row.cancel_requested,
            )

    def update(self, run_id: str, **values: Any) -> None:
        with self.sessions.begin() as session:
            row = session.get(RunModel, run_id, with_for_update=True)
            if row is None:
                raise LookupError("Run not found.")
            if values.pop("finished", False):
                row.finished_at = now()
            if values.get("status") == "running" and row.started_at is None:
                row.started_at = now()
            for key, value in values.items():
                setattr(row, key, value)

    def progress(self, run_id: str, **values: Any) -> None:
        with self.sessions.begin() as session:
            row = session.get(RunModel, run_id, with_for_update=True)
            if row is None:
                raise LookupError("Run not found.")
            row.progress = {**row.progress, **values}

    def issue(self, run_id: str, message: str, context: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            session.add(
                IssueModel(
                    id=str(uuid4()),
                    run_id=run_id,
                    message=message,
                    context=context,
                    created_at=now(),
                )
            )
            row = session.get(RunModel, run_id, with_for_update=True)
            if row is not None:
                row.progress = {**row.progress, "issues": row.progress.get("issues", 0) + 1}

    def artifacts(self, extraction_id: str, dataset: str | None = None) -> list[dict[str, Any]]:
        with self.sessions() as session:
            columns = [
                column for column in ArtifactModel.__table__.columns if column.name != "file_schema"
            ]
            query = select(*columns).where(ArtifactModel.extraction_id == extraction_id)
            if dataset:
                query = query.where(ArtifactModel.dataset_id == dataset)
            return [
                dict(item)
                for item in session.execute(query.order_by(ArtifactModel.path)).mappings()
            ]

    def artifact_at(self, extraction_id: str, path: str) -> dict[str, Any] | None:
        with self.sessions() as session:
            item = session.scalar(
                select(ArtifactModel).where(
                    ArtifactModel.extraction_id == extraction_id, ArtifactModel.path == path
                )
            )
            return model_dict(item) if item else None

    def artifact_count(self, extraction_id: str) -> int:
        with self.sessions() as session:
            return (
                session.scalar(
                    select(func.count())
                    .select_from(ArtifactModel)
                    .where(ArtifactModel.extraction_id == extraction_id)
                )
                or 0
            )

    def add_artifact(self, values: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            exists = session.scalar(
                select(ArtifactModel.id).where(
                    ArtifactModel.extraction_id == values["extraction_id"],
                    ArtifactModel.path == values["path"],
                )
            )
            if not exists:
                session.add(ArtifactModel(id=str(uuid4()), **values))

    def artifact(self, artifact_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(ArtifactModel, artifact_id)
            if row is None:
                raise LookupError("Artifact not found.")
            return model_dict(row)

    def detail(self, run_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.get(RunModel, run_id)
            if row is None:
                raise LookupError("Run not found.")
            result = model_dict(row)
            result["issues"] = [
                model_dict(item)
                for item in session.scalars(
                    select(IssueModel)
                    .where(IssueModel.run_id == run_id)
                    .order_by(IssueModel.created_at.desc())
                    .limit(100)
                )
            ]
            result["artifacts"] = self.artifacts(row.extraction_id)
            return result

    def list_runs(self, page: int, page_size: int, status: str | None = None) -> dict[str, Any]:
        with self.sessions() as session:
            query = select(RunModel)
            if status:
                query = query.where(RunModel.status == status)
            total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = session.scalars(
                query.order_by(RunModel.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return {
                "items": [model_dict(row) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def datasets(self, version_page: int = 1, version_page_size: int = 20) -> list[dict[str, Any]]:
        with self.sessions() as session:
            extractions = list(
                session.scalars(
                    select(RunModel)
                    .where(RunModel.operation.in_(["extract", "pipeline"]))
                    .order_by(RunModel.created_at.desc())
                )
            )
            loads = list(
                session.scalars(
                    select(RunModel)
                    .where(
                        RunModel.operation.in_(["pipeline", "load"]),
                        RunModel.status.in_(["completed", "completed_with_errors"]),
                    )
                    .order_by(RunModel.finished_at.desc())
                )
            )
            aggregate = {
                (row.extraction_id, row.dataset_id): row
                for row in session.execute(
                    select(
                        ArtifactModel.extraction_id,
                        ArtifactModel.dataset_id,
                        func.count().label("files"),
                        func.sum(ArtifactModel.records).label("records"),
                        func.sum(ArtifactModel.bytes).label("bytes"),
                    ).group_by(ArtifactModel.extraction_id, ArtifactModel.dataset_id)
                )
            }
            latest_loads: dict[str, RunModel] = {}
            for load_run in loads:
                latest_loads.setdefault(load_run.extraction_id, load_run)
            items = []
            for dataset in DATASETS:
                versions = []
                matching = [item for item in extractions if dataset in item.parameters["datasets"]]
                offset = (version_page - 1) * version_page_size
                for extraction in matching[offset : offset + version_page_size]:
                    stats = aggregate.get((extraction.id, dataset))
                    load = latest_loads.get(extraction.id)
                    versions.append(
                        {
                            "extraction_id": extraction.id,
                            "created_at": extraction.created_at,
                            "parameters": extraction.parameters,
                            "status": extraction.status,
                            "extraction_complete": f"extract:{dataset}"
                            in extraction.completed_stages,
                            "files": stats.files if stats else 0,
                            "records": stats.records if stats else 0,
                            "bytes": stats.bytes if stats else 0,
                            "last_load": model_dict(load) if load else None,
                        }
                    )
                items.append(
                    {
                        "id": dataset,
                        "source": "CAMARA_DOS_DEPUTADOS",
                        "versions": versions,
                        "total_versions": len(matching),
                        "version_page": version_page,
                        "last_ingestion": next(
                            (
                                model_dict(load)
                                for load in loads
                                if dataset in load.parameters["datasets"]
                            ),
                            None,
                        ),
                    }
                )
            return items

    def retry(self, run_id: str, *, status: str = "queued") -> None:
        with self.graph_mutation() as session:
            row = session.get(RunModel, run_id, with_for_update=True)
            if row is None:
                raise LookupError("Run not found.")
            if row.status not in {"failed", "cancelled", "queued"}:
                raise ValueError("Only pending, failed or cancelled runs can be resumed.")
            original = session.get(RunModel, row.extraction_id)
            if original and original.status in {"deleting", "delete_failed"}:
                raise ValueError("The extraction is being deleted. Retry its deletion.")
            if row.operation in {"pipeline", "load", "schema", "analysis"} and session.scalar(
                select(RunModel.id).where(RunModel.status == "deleting").limit(1)
            ):
                raise ValueError("Wait for the extraction deletion to finish.")
            row.status, row.cancel_requested, row.error = status, False, None
            row.stage = "starting" if status == "running" else "queued"
            row.finished_at = None

    def cancel(self, run_id: str) -> None:
        with self.sessions.begin() as session:
            row = session.get(RunModel, run_id, with_for_update=True)
            if row is None:
                raise LookupError("Run not found.")
            if row.status in TERMINAL:
                raise ValueError("Run has already finished.")
            row.cancel_requested = True
            if row.status == "queued":
                row.status, row.finished_at = "cancelled", now()

    def save_schema(self, run_id: str | None, schema: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            session.add(
                SchemaModel(id=str(uuid4()), run_id=run_id, observed_at=now(), schema_json=schema)
            )
            # A successful observation supersedes all previous stale observations.
            for row in session.scalars(select(RunModel).where(RunModel.schema_stale.is_(True))):
                row.schema_stale = False

    def schema(self) -> dict[str, Any]:
        with self.sessions() as session:
            row = session.scalar(
                select(SchemaModel).order_by(SchemaModel.observed_at.desc()).limit(1)
            )
            stale = bool(
                session.scalar(select(RunModel.id).where(RunModel.schema_stale.is_(True)).limit(1))
            )
            return {
                "observed_at": row.observed_at if row else None,
                "stale": stale,
                "nodes": row.schema_json["nodes"] if row else [],
                "relationships": row.schema_json["relationships"] if row else [],
                "constraints": row.schema_json.get("constraints", []) if row else [],
            }

    def begin_delete(self, extraction_id: str) -> dict[str, Any]:
        with self.graph_mutation() as session:
            original = session.get(RunModel, extraction_id, with_for_update=True)
            if original is None or original.operation not in {"extract", "pipeline"}:
                raise LookupError("Extraction not found.")
            associated = list(
                session.scalars(select(RunModel).where(RunModel.extraction_id == extraction_id))
            )
            if any(row.status == "running" for row in associated):
                raise ValueError("Wait for execution or cancellation to finish before deleting.")
            if session.scalar(
                select(RunModel.id)
                .where(
                    RunModel.status.in_(["running", "deleting"]),
                    RunModel.operation.in_(["pipeline", "load", "schema", "analysis"]),
                    RunModel.id != extraction_id,
                )
                .limit(1)
            ):
                raise ValueError("Wait for the current graph operation to finish before deleting.")
            original.status, original.stage, original.schema_stale = "deleting", "delete", True
            return {
                "run_ids": [row.id for row in associated],
                "artifacts": self.artifacts(extraction_id),
                "graph_deleted": original.progress.get("graph_deleted", False),
                "may_have_graph": any(row.operation in {"pipeline", "load"} for row in associated),
            }

    def finish_delete(self, extraction_id: str) -> None:
        with self.sessions.begin() as session:
            graph_changed = bool(
                session.scalar(
                    select(RunModel.id)
                    .where(
                        RunModel.extraction_id == extraction_id,
                        RunModel.operation.in_(["pipeline", "load"]),
                    )
                    .limit(1)
                )
            )
            ids = select(RunModel.id).where(RunModel.extraction_id == extraction_id)
            session.execute(delete(IssueModel).where(IssueModel.run_id.in_(ids)))
            # Observations describe the whole graph and become invalid after deletion.
            if graph_changed:
                session.execute(delete(SchemaModel))
            else:
                session.execute(delete(SchemaModel).where(SchemaModel.run_id.in_(ids)))
            session.execute(
                delete(ArtifactModel).where(ArtifactModel.extraction_id == extraction_id)
            )
            session.execute(delete(RunModel).where(RunModel.extraction_id == extraction_id))
            if graph_changed:
                for row in session.scalars(select(RunModel)):
                    row.schema_stale = True
