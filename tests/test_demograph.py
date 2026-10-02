import csv
import importlib.util
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import requests
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.api.security import require_admin
from src.core.config.settings import settings
from src.modules.demograph.application.use_cases.pipeline import Pipeline
from src.modules.demograph.domain.contracts import DATASETS, resolve_datasets
from src.modules.demograph.domain.mapping import map_record
from src.modules.demograph.infrastructure.catalog import SqlCatalog, now
from src.modules.demograph.infrastructure.extraction import API, ChamberExtractor
from src.modules.demograph.infrastructure.graph import GraphLoader
from src.modules.demograph.infrastructure.models import (
    ArtifactModel,
    DatasetModel,
    IssueModel,
    RunModel,
    SchemaModel,
    WorkerModel,
)
from src.modules.demograph.infrastructure.storage.files import rows, safe_path
from src.modules.demograph.infrastructure.storage.schema import SchemaObserver
from src.modules.demograph.presentation.dependencies.providers import get_catalog
from src.modules.demograph.presentation.routes import router

TABLES = [
    model.__table__
    for model in (DatasetModel, RunModel, ArtifactModel, IssueModel, SchemaModel, WorkerModel)
]


def deputy(person_id: int = 1, name: str = "Deputado", party_id: int = 10) -> dict:
    return {
        "id": person_id,
        "uri": f"{API}deputados/{person_id}",
        "nome": name,
        "siglaUf": "SP",
        "idLegislatura": 57,
        "siglaPartido": "PARTIDO",
        "uriPartido": f"{API}partidos/{party_id}",
        "email": None,
    }


def csv_bytes(records: list[dict]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=list(records[0]), delimiter=";")
    writer.writeheader()
    writer.writerows(records)
    return handle.getvalue().encode("cp1252")


class FakeSource:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.missing_topics = False
        self.votings = [
            {"id": "100-1", "data": "2023-02-03", "descricao": "Votação nominal"},
            {"id": "100-2", "data": "2023-01-01", "descricao": "Fora do período"},
        ]
        self.votes = [
            {
                "idVotacao": "100-1",
                "deputado_id": str(person_id),
                "deputado_uri": f"{API}deputados/{person_id}",
                "deputado_nome": f"Pessoa {person_id}",
                "dataHoraVoto": "2023-02-03T12:00:00",
                "voto": choice,
                "deputado_uriPartido": f"{API}partidos/10",
            }
            for person_id, choice in enumerate(("Sim", "Abstenção", "Obstrução"), 1)
        ]
        self.votes.append({**self.votes[0], "idVotacao": "100-2"})

    def get(self, url: str, **_kwargs: object) -> requests.Response:
        self.calls.append(url)
        response = requests.Response()
        response.url, response.status_code = url, 200
        path = urlparse(url).path
        if "votacoesVotos" in path:
            content = csv_bytes(self.votes)
        elif path.endswith(".csv"):
            content = csv_bytes(self.votings)
        else:
            if path.endswith("/deputados"):
                data = [deputy()]
            elif path.endswith("/historico"):
                data = [
                    {
                        "dataHora": "2023-02-01T00:00:00",
                        "idLegislatura": 57,
                        "siglaPartido": "PARTIDO",
                        "uriPartido": f"{API}partidos/10",
                    }
                ]
            elif path.endswith("/temas"):
                if self.missing_topics:
                    response.status_code = 404
                data = [{"codTema": 40, "tema": "Educação"}]
            else:
                data = {
                    "id": "100-1",
                    "objetosPossiveis": [{"id": 100, "ementa": "Proposta"}],
                    "proposicoesAfetadas": [{"id": 101, "ementa": "Outra proposta"}],
                }
            content = json.dumps({"dados": data, "links": []}, ensure_ascii=False).encode()
        response._content = content
        response._content_consumed = True
        response.headers["Content-Length"] = str(len(content))
        return response


class DemoGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        temp_root = Path(__file__).resolve().parents[1] / ".cache" / "demograph-tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.root = Path(self.temp.name)
        sql_url = os.environ.get("DEMOGRAPH_TEST_SQL_URL")
        if sql_url:
            self.engine = create_engine(sql_url)
        else:
            self.engine = create_engine(
                "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        for table in TABLES:
            table.create(self.engine, checkfirst=True)
        self.catalog = SqlCatalog(sessionmaker(self.engine))
        self.source = FakeSource()
        self.extractor = ChamberExtractor(self.catalog, self.root)
        self.extractor.http.get = self.source.get

    def tearDown(self) -> None:
        for table in reversed(TABLES):
            table.drop(self.engine)
        self.engine.dispose()
        self.temp.cleanup()

    def create(self, datasets: list[str] | None = None, operation: str = "extract") -> str:
        return self.catalog.create(
            operation,
            {"datasets": datasets or list(DATASETS), "start": "2023-02-01", "end": "2023-02-28"},
        )

    def extract(self, datasets: list[str] | None = None) -> str:
        run_id = self.create(datasets)
        graph = GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j")
        Pipeline(self.catalog, self.extractor, graph).execute(run_id)
        self.assertEqual(self.catalog.run(run_id).status, "completed")
        return run_id

    def test_dependency_resolution_and_all_vote_choices(self) -> None:
        self.assertEqual(
            resolve_datasets(["votes", "histories"]), ["votings", "votes", "histories"]
        )
        with self.assertRaises(ValueError):
            resolve_datasets(["unknown"])
        for raw in self.source.votes[:3]:
            self.assertEqual(map_record("votes", raw, {})["choice"], raw["voto"])

    def test_storage_is_sibling_of_youtube(self) -> None:
        with (
            patch.object(settings, "DOWNLOAD_YOUTUBE_PATH", "/media/disk/youtube"),
            patch.object(settings, "DEMOGRAPH_STORAGE_PATH", None),
        ):
            self.assertEqual(Path(settings.demograph_storage_path), Path("/media/disk/demograph"))

    def test_storage_is_created_automatically_and_preserves_existing_files(self) -> None:
        from src.modules.demograph.presentation.workers.prepare_storage import prepare_storage

        directory = self.root / "new-parent" / "demograph"
        with patch.object(settings, "DEMOGRAPH_STORAGE_PATH", str(directory)):
            self.assertEqual(prepare_storage(), directory)
            self.assertTrue(directory.is_dir())
            existing = directory / "existing.json"
            existing.write_text("{}", encoding="utf-8")
            prepare_storage()
            self.assertEqual(existing.read_text(encoding="utf-8"), "{}")

    def test_migration_matches_models_and_can_be_reversed(self) -> None:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "da2026100201_demograph_catalog.py"
        )
        spec = importlib.util.spec_from_file_location("demograph_migration", migration_path)
        assert spec is not None and spec.loader is not None
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        for table in reversed(TABLES):
            table.drop(self.engine)
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            inspector = inspect(connection)
            for table in TABLES:
                self.assertEqual(
                    {column.name for column in table.columns},
                    {column["name"] for column in inspector.get_columns(table.name)},
                )
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
        for table in TABLES:
            table.create(self.engine)

    def test_repeated_pagination_and_mid_download_cancellation(self) -> None:
        run_id = self.create(["deputies"])
        original = self.source.get

        def repeated(url: str, **kwargs: object) -> requests.Response:
            response = original(url, **kwargs)
            response._content = json.dumps(
                {
                    "dados": [deputy()],
                    "links": [{"rel": "next", "href": f"{API}deputados?pagina=2"}],
                }
            ).encode()
            return response

        self.extractor.http.get = repeated
        with self.assertRaises(ValueError):
            self.extractor.extract(self.catalog.run(run_id))
        self.assertLessEqual(len(self.source.calls), 2)
        another = self.create(["deputies"])

        def cancelled(url: str, **kwargs: object) -> requests.Response:
            self.catalog.update(another, cancel_requested=True)
            return original(url, **kwargs)

        self.extractor.http.get = cancelled
        Pipeline(
            self.catalog,
            self.extractor,
            GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j"),
        ).execute(another)
        self.assertEqual(self.catalog.run(another).status, "cancelled")
        self.assertEqual(self.catalog.artifacts(another), [])

    @unittest.skipUnless(os.environ.get("DEMOGRAPH_TEST_SQL_URL"), "Dedicated PostgreSQL required")
    def test_worker_runs_queue_and_releases_singleton_lock(self) -> None:
        from src.modules.demograph.presentation.workers import pipeline as worker

        run_id = self.create(["deputies"])
        stopped = threading.Event()
        graph = GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j", stopped)
        self.extractor.stopped = stopped

        def monitor() -> None:
            for _ in range(100):
                if self.catalog.run(run_id).status in {"completed", "failed"}:
                    stopped.set()
                    return
                if stopped.wait(0.1):
                    return
            stopped.set()

        observer = threading.Thread(target=monitor)
        with (
            patch.object(worker, "engine", self.engine),
            patch.object(worker, "Session", self.catalog.sessions),
            patch.object(worker, "SqlCatalog", return_value=self.catalog),
            patch.object(worker, "get_graph", return_value=graph),
            patch.object(worker, "ChamberExtractor", return_value=self.extractor),
            patch.object(worker, "Event", return_value=stopped),
            patch.object(worker.signal, "signal"),
            patch.object(settings, "DEMOGRAPH_STORAGE_PATH", str(self.root)),
        ):
            observer.start()
            worker.main()
            observer.join()
        self.assertEqual(self.catalog.run(run_id).status, "completed")
        with self.engine.connect() as connection:
            self.assertTrue(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": worker.LOCK_ID}
                ).scalar()
            )
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": worker.LOCK_ID})

    def test_extraction_publishes_full_files_schema_and_does_not_require_neo4j(self) -> None:
        run_id = self.extract()
        artifacts = self.catalog.artifacts(run_id)
        self.assertEqual(len(artifacts), 9)
        votes = next(item for item in artifacts if item["dataset_id"] == "votes")
        self.assertEqual(votes["records"], 4)
        self.assertEqual(votes["metadata_json"]["encoding"], "cp1252")
        self.assertIn(
            "Obstrução",
            [row["voto"] for row in rows(self.root / votes["path"], votes["metadata_json"])],
        )
        schema = self.catalog.artifact(votes["id"])["file_schema"]
        self.assertEqual(schema["records"], 4)
        self.assertFalse(any(self.root.rglob("*.part")))
        self.assertFalse(self.catalog.datasets()[0]["versions"][0]["last_load"])

    def test_resume_reuses_registered_artifacts_and_detects_tampering(self) -> None:
        run_id = self.extract(["deputies"])
        before = len(self.source.calls)
        self.catalog.update(run_id, status="failed", completed_stages=[])
        self.catalog.retry(run_id)
        self.extractor.extract(self.catalog.run(run_id))
        self.assertEqual(len(self.source.calls), before)
        artifact = self.catalog.artifacts(run_id)[0]
        (self.root / artifact["path"]).write_text("tampered", encoding="utf-8")
        self.catalog.update(run_id, completed_stages=[])
        with self.assertRaises(ValueError):
            self.extractor.extract(self.catalog.run(run_id))

    def test_missing_topics_are_explicit_not_silently_empty(self) -> None:
        self.source.missing_topics = True
        run_id = self.create(["topics"])
        graph = GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j")
        Pipeline(self.catalog, self.extractor, graph).execute(run_id)
        detail = self.catalog.detail(run_id)
        self.assertEqual(detail["status"], "completed_with_errors")
        self.assertEqual(len(detail["issues"]), 2)
        self.assertTrue(any(a["metadata_json"].get("unavailable") for a in detail["artifacts"]))

    def test_network_failure_leaves_no_published_artifact(self) -> None:
        run_id = self.create(["deputies"])

        def failure(*_args: object, **_kwargs: object) -> requests.Response:
            raise requests.ConnectionError("private connection details")

        self.extractor.http.get = failure
        with patch("src.modules.demograph.infrastructure.extraction.transport.time.sleep"):
            Pipeline(
                self.catalog,
                self.extractor,
                GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j"),
            ).execute(run_id)
        self.assertEqual(self.catalog.run(run_id).status, "failed")
        self.assertEqual(self.catalog.artifacts(run_id), [])
        self.assertNotIn("private", json.dumps(self.catalog.detail(run_id), default=str))

    def test_cancel_and_paths_and_nested_schema(self) -> None:
        run_id = self.create(["deputies"])
        self.catalog.cancel(run_id)
        self.assertEqual(self.catalog.run(run_id).status, "cancelled")
        self.catalog.retry(run_id)
        self.assertEqual(self.catalog.run(run_id).status, "queued")
        with self.assertRaises(ValueError):
            safe_path(self.root, "../outside")
        observer = SchemaObserver()
        observer.observe({"value": None, "nested": {"x": 1}, "list": [{"v": "a"}, {"v": "b"}]})
        observer.observe({"value": "present"})
        fields = {field["path"]: field for field in observer.result()["fields"]}
        self.assertEqual(fields["value"]["types"], ["null", "string"])
        self.assertEqual(fields["nested.x"]["present"], 1)
        self.assertEqual(fields["list[].v"]["present"], 2)

    def test_load_failure_retains_extraction_and_allows_separate_load(self) -> None:
        run_id = self.create(["deputies"], "pipeline")
        Pipeline(
            self.catalog,
            self.extractor,
            GraphLoader(self.catalog, self.root, None, "neo4j", None, "neo4j"),
        ).execute(run_id)
        self.assertEqual(self.catalog.run(run_id).status, "failed")
        self.assertTrue(self.catalog.run(run_id).progress["extraction_complete"])
        self.assertTrue(self.catalog.artifacts(run_id))
        load_id = self.catalog.create("load", {}, run_id)
        self.assertEqual(self.catalog.run(load_id).extraction_id, run_id)

    def test_http_contracts_auth_catalog_download_and_unknown_ids(self) -> None:
        app = FastAPI()
        app.include_router(router, prefix="/api/demograph", dependencies=[Depends(require_admin)])
        app.dependency_overrides[get_catalog] = lambda: self.catalog
        with (
            patch.object(settings, "DEMOGRAPH_STORAGE_PATH", str(self.root)),
            TestClient(app) as client,
        ):
            self.assertEqual(client.get("/api/demograph/datasets").status_code, 200)
            self.assertIn(
                client.post(
                    "/api/demograph/runs",
                    json={"datasets": ["deputies"], "start": "2023-02-01", "end": "2023-02-28"},
                ).status_code,
                (401, 503),
            )
            self.assertEqual(client.get("/api/demograph/runs/missing").status_code, 404)
            run_id = self.extract(["deputies"])
            artifact = self.catalog.artifacts(run_id)[0]
            self.assertEqual(
                client.get(f"/api/demograph/artifacts/{artifact['id']}/download").status_code, 200
            )
            self.assertEqual(
                len(
                    client.get(f"/api/demograph/artifacts/{artifact['id']}/preview").json()["items"]
                ),
                1,
            )
            self.assertEqual(
                client.get("/api/demograph/datasets/deputies").json()["total_versions"], 1
            )

    @unittest.skipUnless(
        os.environ.get("DEMOGRAPH_TEST_NEO4J_URI"), "Dedicated Neo4j test database required"
    )
    def test_real_graph_replays_receipts_preserves_newer_data_and_observes_schema(self) -> None:
        graph = GraphLoader(
            self.catalog,
            self.root,
            os.environ["DEMOGRAPH_TEST_NEO4J_URI"],
            "neo4j",
            os.environ["DEMOGRAPH_TEST_NEO4J_PASSWORD"],
            "neo4j",
        )
        with graph.driver() as driver, driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
        try:
            extraction_id = self.extract()
            load_id = self.catalog.create("load", {}, extraction_id)
            pipeline = Pipeline(self.catalog, self.extractor, graph)
            pipeline.execute(load_id)
            self.assertEqual(self.catalog.run(load_id).status, "completed")
            with graph.driver() as driver, driver.session() as session:
                count = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
                choices = {
                    row["choice"]
                    for row in session.run("MATCH ()-[r:VOTED_IN]->() RETURN r.choice AS choice")
                }
                self.assertEqual(choices, {"Sim", "Abstenção", "Obstrução"})
                self.assertEqual(
                    session.run("MATCH (v:Voting) RETURN count(v) AS n").single()["n"], 1
                )
            # Reconcile the same run after a PostgreSQL checkpoint was lost.
            self.catalog.update(load_id, status="failed", progress={})
            self.catalog.retry(load_id)
            pipeline.execute(load_id)
            self.assertEqual(self.catalog.run(load_id).status, "completed")
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(session.run("MATCH (n) RETURN count(n) AS n").single()["n"], count)
            with graph.driver() as driver, driver.session() as session:
                newer = (now() + timedelta(days=1)).isoformat()
                session.run(
                    "MATCH (p:Person {camara_id: 1}) "
                    "SET p.name = 'New name', p.observed_at = $newer",
                    newer=newer,
                ).consume()
            another = self.catalog.create("load", {}, extraction_id)
            pipeline.execute(another)
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(
                    session.run("MATCH (p:Person {camara_id: 1}) RETURN p.name AS name").single()[
                        "name"
                    ],
                    "New name",
                )
            schema = self.catalog.schema()
            self.assertIn("Person", [node["label"] for node in schema["nodes"]])
            self.assertIn("VOTED_IN", [relation["type"] for relation in schema["relationships"]])
            self.assertFalse(schema["stale"])
        finally:
            with graph.driver() as driver, driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n").consume()


if __name__ == "__main__":
    unittest.main()
