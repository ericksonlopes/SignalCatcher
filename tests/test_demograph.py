import csv
import importlib.util
import io
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.api.security import require_admin
from src.core.config.settings import settings
from src.modules.demograph.application.use_cases.delete_extraction import DeleteExtraction
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
)
from src.modules.demograph.infrastructure.storage.deletion import ExtractionFiles
from src.modules.demograph.infrastructure.storage.files import rows, safe_path
from src.modules.demograph.infrastructure.storage.schema import SchemaObserver
from src.modules.demograph.presentation.dependencies.providers import (
    get_catalog,
    get_deletion,
    get_pipeline,
)
from src.modules.demograph.presentation.routes import router

TABLES = [
    model.__table__ for model in (DatasetModel, RunModel, ArtifactModel, IssueModel, SchemaModel)
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
        if path.endswith(("/historico", "/temas")) and parse_qs(urlparse(url).query):
            response.status_code = 400
            response._content = json.dumps(
                {"status": 400, "detail": "Invalid parameters.", "instance": "pagina, itens"}
            ).encode()
            response._content_consumed = True
            return response
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

    def test_delete_files_catalog_and_http_authorization(self) -> None:
        first, other = self.extract(["deputies"]), self.extract(["deputies"])
        self.catalog.save_schema(
            None, {"nodes": [{"label": "Person", "count": 1}], "relationships": []}
        )
        graph = Mock()
        app = self.direct_api()
        app.dependency_overrides[get_deletion] = lambda: DeleteExtraction(
            self.catalog, graph, ExtractionFiles(self.root)
        )
        file_id = self.catalog.artifacts(first)[0]["id"]
        with (
            patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
            TestClient(app) as client,
        ):
            path = f"/api/demograph/extractions/{first}"
            self.assertEqual(client.delete(path).status_code, 401)
            result = client.delete(path, headers={"X-API-Key": "test-only"})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["status"], "deleted")
            self.assertEqual(
                client.get(f"/api/demograph/artifacts/{file_id}/preview").status_code, 404
            )
            self.assertEqual(
                client.delete(path, headers={"X-API-Key": "test-only"}).status_code, 404
            )
        self.assertFalse((self.root / first).exists())
        self.assertTrue((self.root / other).exists())
        self.assertEqual(self.catalog.datasets()[0]["total_versions"], 1)
        self.assertEqual(self.catalog.schema()["nodes"][0]["label"], "Person")
        graph.delete_extraction.assert_not_called()

    def test_delete_failures_resume_after_graph_commit_and_protect_paths(self) -> None:
        extraction = self.extract(["deputies"])
        load_id = self.catalog.create("load", {}, extraction)
        self.catalog.update(load_id, status="completed", finished=True)
        graph = Mock()
        graph.schema.return_value = {"nodes": [], "relationships": [], "constraints": []}
        storage = ExtractionFiles(self.root)
        deletion = DeleteExtraction(self.catalog, graph, storage)
        with patch.object(storage, "delete_extraction", side_effect=PermissionError("test")):
            with self.assertRaises(PermissionError):
                deletion.execute(extraction)
        self.assertEqual(self.catalog.run(extraction).status, "delete_failed")
        self.assertTrue(self.catalog.run(extraction).progress["graph_deleted"])
        with self.assertRaises(ValueError):
            self.catalog.create("load", {}, extraction)
        deletion.execute(extraction)
        graph.delete_extraction.assert_called_once()
        with self.assertRaises(LookupError):
            self.catalog.run(load_id)
        with self.assertRaises(ValueError):
            storage.validate_deletion("..", [])
        with self.assertRaises(ValueError):
            storage.validate_deletion(extraction, [{"path": "../youtube/video.mp4"}])
        with self.assertRaises(ValueError):
            storage.validate_deletion(extraction, [{"path": "another-extraction/file.json"}])

    def test_delete_refuses_active_runs_and_retains_files_on_graph_failure(self) -> None:
        extraction = self.extract(["deputies"])
        load_id = self.catalog.create("load", {}, extraction, status="running")
        graph = Mock()
        deletion = DeleteExtraction(self.catalog, graph, ExtractionFiles(self.root))
        with self.assertRaises(ValueError):
            deletion.execute(extraction)
        graph.delete_extraction.assert_not_called()
        self.catalog.update(load_id, status="failed")
        graph.delete_extraction.side_effect = RuntimeError("Neo4j unavailable")
        with self.assertRaises(RuntimeError):
            deletion.execute(extraction)
        self.assertTrue((self.root / extraction).exists())
        self.assertEqual(self.catalog.run(extraction).status, "delete_failed")
        self.assertFalse(self.catalog.run(extraction).progress.get("graph_deleted", False))
        # An API restart can leave this stage; explicit deletion may resume it.
        self.catalog.update(extraction, status="deleting")
        graph.delete_extraction.side_effect = None
        graph.schema.return_value = {"nodes": [], "relationships": [], "constraints": []}
        deletion.execute(extraction)
        self.assertFalse((self.root / extraction).exists())

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
        api_spec = importlib.util.spec_from_file_location(
            "demograph_api_migration",
            migration_path.with_name("da2026100202_demograph_api_execution.py"),
        )
        assert api_spec is not None and api_spec.loader is not None
        api_migration = importlib.util.module_from_spec(api_spec)
        api_spec.loader.exec_module(api_migration)
        for table in reversed(TABLES):
            table.drop(self.engine)
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                api_migration.upgrade()
            inspector = inspect(connection)
            self.assertNotIn("demograph_worker", inspector.get_table_names())
            for table in TABLES:
                self.assertEqual(
                    {column.name for column in table.columns},
                    {column["name"] for column in inspector.get_columns(table.name)},
                )
            with Operations.context(MigrationContext.configure(connection)):
                api_migration.downgrade()
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

    def test_histories_and_topics_use_unpaginated_source_contracts(self) -> None:
        run_id = self.extract(["histories", "topics"])
        urls = [urlparse(url) for url in self.source.calls]
        histories = [url for url in urls if url.path.endswith("/historico")]
        topics = [url for url in urls if url.path.endswith("/temas")]
        self.assertTrue(histories)
        self.assertTrue(topics)
        self.assertTrue(all(not url.query for url in [*histories, *topics]))
        deputies = next(url for url in urls if url.path.endswith("/deputados"))
        self.assertEqual(parse_qs(deputies.query), {"pagina": ["1"], "itens": ["100"]})
        self.assertEqual(len(self.catalog.artifacts(run_id, "histories")), 1)
        self.assertEqual(len(self.catalog.artifacts(run_id, "topics")), 3)

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

    def direct_api(self) -> FastAPI:
        catalog = self.catalog

        class FixtureLoader:
            def load(self, run) -> None:
                catalog.progress(run.id, load_complete=True)

            def schema(self, run_id=None) -> dict:
                return {"nodes": [], "relationships": [], "constraints": []}

        app = FastAPI()
        app.include_router(router, prefix="/api/demograph", dependencies=[Depends(require_admin)])
        pipeline = Pipeline(self.catalog, self.extractor, FixtureLoader())
        app.dependency_overrides[get_catalog] = lambda: self.catalog
        app.dependency_overrides[get_pipeline] = lambda: pipeline
        return app

    def test_click_starts_and_completes_extraction_without_worker(self) -> None:
        with (
            patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
            TestClient(self.direct_api()) as client,
        ):
            response = client.post(
                "/api/demograph/runs",
                headers={"X-API-Key": "test-only"},
                json={
                    "operation": "extract",
                    "datasets": ["deputies"],
                    "start": "2023-02-01",
                    "end": "2023-02-28",
                },
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["status"], "running")
            run_id = response.json()["id"]
            self.assertEqual(self.catalog.run(run_id).status, "completed")
            self.assertEqual(len(self.catalog.artifacts(run_id)), 1)
            health = client.get("/api/demograph/health").json()
            self.assertEqual(health["execution"], "api")
            self.assertNotIn("worker", health)

    def test_pipeline_load_and_schema_refresh_execute_from_click(self) -> None:
        with (
            patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
            TestClient(self.direct_api()) as client,
        ):
            headers = {"X-API-Key": "test-only"}
            response = client.post(
                "/api/demograph/runs",
                headers=headers,
                json={"datasets": ["deputies"], "start": "2023-02-01", "end": "2023-02-28"},
            )
            run_id = response.json()["id"]
            self.assertEqual(self.catalog.run(run_id).status, "completed")
            self.assertTrue(self.catalog.run(run_id).progress["load_complete"])
            for path in (f"/extractions/{run_id}/load", "/schema/refresh"):
                response = client.post(f"/api/demograph{path}", headers=headers)
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.json()["status"], "running")
                self.assertEqual(self.catalog.run(response.json()["id"]).status, "completed")
            self.assertIsNotNone(self.catalog.schema()["observed_at"])

    def test_legacy_pending_run_can_be_started_and_active_run_cannot_be_restarted(self) -> None:
        run_id = self.create(["deputies"])
        with (
            patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
            TestClient(self.direct_api()) as client,
        ):
            headers = {"X-API-Key": "test-only"}
            response = client.post(f"/api/demograph/runs/{run_id}/retry", headers=headers)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["status"], "running")
            self.assertEqual(self.catalog.run(run_id).status, "completed")
            self.catalog.update(run_id, status="running")
            self.assertEqual(
                client.post(f"/api/demograph/runs/{run_id}/retry", headers=headers).status_code, 409
            )

    @unittest.skipUnless(os.environ.get("DEMOGRAPH_TEST_SQL_URL"), "Dedicated PostgreSQL required")
    def test_click_executes_while_diarization_holds_its_lock(self) -> None:
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as owner:
            owner.execute(text("SELECT pg_advisory_lock(:key)"), {"key": 73401953})
            try:
                self.test_click_starts_and_completes_extraction_without_worker()
            finally:
                owner.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 73401953})

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
    def test_real_graph_delete_restores_shared_legacy_version_and_protects_foreign_edges(
        self,
    ) -> None:
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
            old = self.extract()
            old_load = self.catalog.create("load", {}, old)
            pipeline = Pipeline(self.catalog, self.extractor, graph)
            pipeline.execute(old_load)
            with patch(f"{__name__}.deputy", return_value=deputy(name="New version", party_id=20)):
                newer = self.extract(["deputies"])
            newer_load = self.catalog.create("load", {}, newer)
            pipeline.execute(newer_load)
            self.assertEqual(self.catalog.run(newer_load).status, "completed")
            with graph.driver() as driver, driver.session() as session:
                session.run(
                    "MATCH (b:DemoGraphBatch {run_id: $id}) REMOVE b.payload_json, b.extraction_id",
                    id=old_load,
                ).consume()
                session.run(
                    "MATCH (p:Person {camara_id: 1}) MERGE (x:External {key: 'keep'}) "
                    "MERGE (x)-[:KEEP]->(p)"
                ).consume()
                before = session.run("MATCH (b:DemoGraphBatch) RETURN count(b) AS n").single()["n"]
            old_file = safe_path(self.root, self.catalog.artifacts(old)[0]["path"])
            original_bytes = old_file.read_bytes()
            old_file.write_bytes(b"tampered")
            deletion = DeleteExtraction(self.catalog, graph, ExtractionFiles(self.root))
            with self.assertRaises(ValueError):
                deletion.execute(newer)
            self.assertTrue((self.root / newer).exists())
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(
                    session.run("MATCH (b:DemoGraphBatch) RETURN count(b) AS n").single()["n"],
                    before,
                )
                self.assertEqual(
                    session.run("MATCH (p:Person {camara_id: 1}) RETURN p.name AS name").single()[
                        "name"
                    ],
                    "New version",
                )
            old_file.write_bytes(original_bytes)
            deletion.execute(newer)
            self.assertTrue((self.root / old).exists())
            self.assertFalse((self.root / newer).exists())
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(
                    session.run("MATCH (p:Person {camara_id: 1}) RETURN p.name AS name").single()[
                        "name"
                    ],
                    "Deputado",
                )
                self.assertEqual(
                    session.run(
                        "MATCH (p:Person)-[:AFFILIATED_WITH]->(party) RETURN party.camara_id AS id"
                    ).single()["id"],
                    10,
                )
                self.assertEqual(
                    session.run("MATCH ()-[r:VOTED_IN]->() RETURN count(r) AS n").single()["n"], 3
                )
                self.assertEqual(
                    session.run(
                        "MATCH (b:DemoGraphBatch) WHERE b.payload_json IS NULL RETURN count(b) AS n"
                    ).single()["n"],
                    0,
                )
            self.assertFalse(self.catalog.schema()["stale"])
            deletion.execute(old)
            self.assertEqual(self.catalog.schema()["nodes"], [])
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(
                    session.run("MATCH (b:DemoGraphBatch) RETURN count(b) AS n").single()["n"], 0
                )
                self.assertEqual(
                    session.run("MATCH ()-[r:VOTED_IN]->() RETURN count(r) AS n").single()["n"], 0
                )
                self.assertEqual(
                    session.run(
                        "MATCH (:External)-[r:KEEP]->(:Person) RETURN count(r) AS n"
                    ).single()["n"],
                    1,
                )
                self.assertEqual(
                    session.run("MATCH (p:Party) RETURN count(p) AS n").single()["n"], 0
                )
        finally:
            with graph.driver() as driver, driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n").consume()

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

    @unittest.skipUnless(os.environ.get("DEMOGRAPH_TEST_SQL_URL"), "Dedicated PostgreSQL required")
    def test_graph_admission_rejects_concurrent_start_and_delete(self) -> None:
        extraction = self.extract(["deputies"])
        artifacts = self.catalog.artifacts

        def overlapping_start(extraction_id):
            # A second connection starts after deletion read active runs but
            # before its status change commits: serializable isolation aborts it.
            self.catalog.create(
                "pipeline",
                {"datasets": ["deputies"], "start": "2023-02-01", "end": "2023-02-28"},
                status="running",
            )
            return artifacts(extraction_id)

        with patch.object(self.catalog, "artifacts", side_effect=overlapping_start):
            with self.assertRaises(OperationalError) as caught:
                self.catalog.begin_delete(extraction)
        self.assertEqual(getattr(caught.exception.orig, "pgcode", None), "40001")
        self.assertEqual(self.catalog.run(extraction).status, "completed")
        self.assertTrue((self.root / extraction).exists())

    @unittest.skipUnless(os.environ.get("DEMOGRAPH_TEST_NEO4J_URI"), "Dedicated Neo4j required")
    def test_real_graph_click_pipeline_and_delete_from_http(self) -> None:
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
        app = self.direct_api()
        app.dependency_overrides[get_pipeline] = lambda: Pipeline(
            self.catalog, self.extractor, graph
        )
        app.dependency_overrides[get_deletion] = lambda: DeleteExtraction(
            self.catalog, graph, ExtractionFiles(self.root)
        )
        try:
            with (
                patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
                TestClient(app) as client,
            ):
                headers = {"X-API-Key": "test-only"}
                result = client.post(
                    "/api/demograph/runs",
                    headers=headers,
                    json={
                        "operation": "pipeline",
                        "datasets": ["deputies"],
                        "start": "2023-02-01",
                        "end": "2023-02-28",
                    },
                )
                self.assertEqual(result.status_code, 202, result.text)
                run_id = result.json()["id"]
                self.assertEqual(self.catalog.run(run_id).status, "completed")
                with graph.driver() as driver, driver.session() as session:
                    self.assertGreater(
                        session.run("MATCH (n) RETURN count(n) AS n").single()["n"], 0
                    )
                result = client.delete(f"/api/demograph/extractions/{run_id}", headers=headers)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertFalse((self.root / run_id).exists())
                self.assertEqual(client.get("/api/demograph/runs").json()["total"], 0)
                with graph.driver() as driver, driver.session() as session:
                    self.assertEqual(session.run("MATCH (n) RETURN count(n) AS n").single()["n"], 0)
        finally:
            with graph.driver() as driver, driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n").consume()


if __name__ == "__main__":
    unittest.main()
