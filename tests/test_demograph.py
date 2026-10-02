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
from src.modules.demograph.infrastructure.extraction.parallel import resources
from src.modules.demograph.infrastructure.graph import GraphLoader
from src.modules.demograph.infrastructure.graph.party_similarity import PartySimilarity
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

        def session_factory() -> requests.Session:
            session = requests.Session()
            session.get = self.source.get
            return session

        self.extractor = ChamberExtractor(self.catalog, self.root, session_factory=session_factory)
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

    def test_topics_parallel_sessions_progress_and_deduplication(self) -> None:
        self.source.votings = [
            {"id": f"100-{index}", "data": "2023-02-03", "descricao": "Voting"}
            for index in range(8)
        ]
        voting_barrier = threading.Barrier(4)
        topic_barrier = threading.Barrier(2)
        sessions = []
        active = 0
        peak = 0
        mutex = threading.Lock()

        def factory():
            session = requests.Session()
            owner = None

            def get(url, **kwargs):
                nonlocal owner, active, peak
                ident = threading.get_ident()
                if owner is None:
                    owner = ident
                self.assertEqual(owner, ident)
                with mutex:
                    active += 1
                    peak = max(peak, active)
                try:
                    (topic_barrier if url.endswith("/temas") else voting_barrier).wait(5)
                    response = self.source.get(url, **kwargs)
                    if "/votacoes/" in url:
                        data = json.loads(response.content)
                        data["dados"]["id"] = url.rsplit("/", 1)[1]
                        response._content = json.dumps(data).encode()
                    return response
                finally:
                    with mutex:
                        active -= 1

            session.get = get
            session.close = Mock(wraps=session.close)
            sessions.append(session)
            return session

        self.extractor.session_factory = factory
        run_id = self.extract(["topics"])
        self.assertEqual(peak, 4)
        self.assertTrue(all(session.close.call_count == 1 for session in sessions))
        self.assertEqual(sum(url.endswith("/temas") for url in self.source.calls), 2)
        progress = self.catalog.run(run_id).progress
        self.assertEqual(progress["resources_phase"], "proposition_topics")
        self.assertEqual(progress["resources_done"], 2)
        self.assertEqual(progress["resources_total"], 2)
        self.assertEqual(progress["files_saved"], 11)

    def test_parallel_failure_joins_requests_and_resume_reuses_files(self) -> None:
        run_id = self.create(["topics"])
        run = self.catalog.run(run_id)
        published = threading.Event()
        finished = threading.Event()

        def operation(transport, item):
            if item == 1:
                self.assertTrue(published.wait(5))
                raise ValueError("test failure")
            try:
                transport.fetch(run, "topics", "kept.json", f"{API}votacoes/100-1", {})
                published.set()
                self.assertTrue(transport.aborted.wait(5))
                transport.guard(run_id)
            finally:
                finished.set()

        with self.assertRaisesRegex(ValueError, "test failure"):
            list(resources(self.extractor, run_id, [0, 1], operation))
        self.assertTrue(finished.is_set())
        calls = len(self.source.calls)
        self.extractor.fetch(run, "topics", "kept.json", f"{API}votacoes/100-1", {})
        self.assertEqual(len(self.source.calls), calls)
        self.assertEqual(self.catalog.artifact_count(run.extraction_id), 1)

    def test_parallel_cancellation_stops_admission_and_joins(self) -> None:
        from src.modules.demograph.application.use_cases.pipeline import Cancelled

        run_id = self.create(["topics"])
        barrier = threading.Barrier(4)
        started = []
        finished = []

        def operation(transport, item):
            started.append(item)
            try:
                barrier.wait(5)
                if item == 0:
                    with transport.catalog_mutex:
                        self.catalog.cancel(run_id)
                barrier.wait(5)
                transport.guard(run_id)
            finally:
                finished.append(item)

        with self.assertRaises(Cancelled):
            list(resources(self.extractor, run_id, range(100), operation))
        self.assertEqual(len(started), 4)
        self.assertEqual(sorted(started), sorted(finished))

    def test_rate_limit_retry_after_and_cancellable_backoff(self) -> None:
        run_id = self.create(["deputies"])
        run = self.catalog.run(run_id)
        response = self.source.get(f"{API}deputados")
        response.status_code = 429
        response.headers["Retry-After"] = "3"
        get = Mock(side_effect=[response, self.source.get(f"{API}deputados")])
        self.extractor.http.get = get
        with patch("src.modules.demograph.infrastructure.extraction.transport.time.sleep") as sleep:
            self.extractor.fetch(run, "deputies", "test.json", f"{API}deputados", {})
        self.assertEqual(get.call_count, 2)
        self.assertGreaterEqual(sum(call.args[0] for call in sleep.call_args_list), 3)
        self.extractor.http.get = Mock(return_value=response)
        with patch(
            "src.modules.demograph.infrastructure.extraction.transport.time.sleep",
            side_effect=lambda _: self.catalog.cancel(run_id),
        ):
            from src.modules.demograph.application.use_cases.pipeline import Cancelled

            with self.assertRaises(Cancelled):
                self.extractor.fetch(run, "deputies", "cancel.json", f"{API}deputados", {})
        self.assertEqual(self.extractor.http.get.call_count, 1)

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

    def test_analysis_http_dispatch_auth_and_validation(self) -> None:
        analyzer = Mock()
        graph = Mock()
        graph.schema.return_value = {"nodes": [], "relationships": [], "constraints": []}
        app = self.direct_api()
        app.dependency_overrides[get_pipeline] = lambda: Pipeline(
            self.catalog, self.extractor, graph, analyzer
        )
        with (
            patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
            TestClient(app) as client,
        ):
            body = {"start": "2023-02-01", "end": "2026-09-30"}
            path = "/api/demograph/analyses/party-similarity"
            self.assertEqual(client.post(path, json=body).status_code, 401)
            headers = {"X-API-Key": "test-only"}
            self.assertEqual(
                client.post(path, json={**body, "min_common": 0}, headers=headers).status_code, 422
            )
            self.assertEqual(
                client.post(
                    path, json={**body, "start": "2026-10-01"}, headers=headers
                ).status_code,
                422,
            )
            result = client.post(path, json=body, headers=headers)
            self.assertEqual(result.status_code, 202, result.text)
            run = self.catalog.run(result.json()["id"])
            self.assertEqual(run.operation, "analysis")
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.parameters["min_common"], 30)
            self.assertEqual(run.parameters["datasets"], [])
            analyzer.analyze.assert_called_once()
            self.assertEqual(self.source.calls, [])

    @unittest.skipUnless(os.environ.get("DEMOGRAPH_TEST_NEO4J_URI"), "Dedicated Neo4j required")
    def test_real_graph_party_analysis_query_replay_invalidation_and_delete(self) -> None:
        from test_demograph_analysis import fixture

        from src.modules.demograph.application.use_cases.pipeline import Cancelled

        votings, votes, histories = fixture()
        self.source.votings = [
            {**votings[index % 3], "id": f"100-{index + 1}"} for index in range(45)
        ]
        self.source.votes = [
            {
                "idVotacao": f"100-{index + 1}",
                "deputado_id": str(vote["person_id"]),
                "deputado_uri": f"{API}deputados/{vote['person_id']}",
                "deputado_nome": "Deputado",
                "dataHoraVoto": vote["at"],
                "voto": vote["choice"],
                "deputado_idLegislatura": vote["deputado_idLegislatura"],
                "deputado_uriPartido": vote["deputado_uriPartido"],
            }
            for index in range(45)
            for vote in votes[index % 3 * 100 : (index % 3 + 1) * 100]
        ]
        original_get = self.source.get

        def get(url, **kwargs):
            response = original_get(url, **kwargs)
            if url.endswith("/historico"):
                person = int(url.split("/")[-2])
                response._content = json.dumps(
                    {"dados": [histories[person - 1]], "links": []}
                ).encode()
            return response

        self.source.get = get
        self.extractor.http.get = get
        graph = GraphLoader(
            self.catalog,
            self.root,
            os.environ["DEMOGRAPH_TEST_NEO4J_URI"],
            "neo4j",
            os.environ["DEMOGRAPH_TEST_NEO4J_PASSWORD"],
            "neo4j",
        )
        analyzer = PartySimilarity(graph)
        with graph.driver() as driver, driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
        try:
            extraction = self.extract(["votes", "histories"])
            load = self.catalog.create("load", {}, extraction)
            Pipeline(self.catalog, self.extractor, graph).execute(load)
            self.assertEqual(self.catalog.run(load).status, "completed")
            app = self.direct_api()
            app.dependency_overrides[get_pipeline] = lambda: Pipeline(
                self.catalog, self.extractor, graph, analyzer
            )
            body = {"start": "2023-02-01", "end": "2026-09-30"}
            with (
                patch.object(settings, "ADMIN_API_KEY", SecretStr("test-only")),
                TestClient(app) as client,
            ):
                response = client.post(
                    "/api/demograph/analyses/party-similarity",
                    json=body,
                    headers={"X-API-Key": "test-only"},
                )
            self.assertEqual(response.status_code, 202, response.text)
            analysis_id = response.json()["id"]
            run = self.catalog.run(analysis_id)
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.progress["analysis"]["included_votes"], 4500)
            key = "majority_sim_nao_v1:2023-02-01:2026-09-30:1:30"
            with graph.driver() as driver, driver.session() as session:
                result = session.run(
                    "MATCH (:Party {acronym:'PT'})-[r:VOTING_SIMILARITY]-(party:Party) "
                    "WHERE r.analysis_key = $key AND r.disputed_common_votes >= 30 "
                    "RETURN party.acronym AS party, "
                    "round(r.disputed_agreement * 100, 2) AS agreement, "
                    "r.disputed_common_votes AS votes ORDER BY agreement DESC",
                    key=key,
                ).data()
                self.assertIn({"party": "PSB", "agreement": 50.0, "votes": 30}, result)
                # Recalculation replaces the same key without duplicate derived edges.
                analyzer.analyze(run)
                self.assertEqual(
                    session.run("MATCH ()-[r:VOTING_SIMILARITY]->() RETURN count(r) AS n").single()[
                        "n"
                    ],
                    3,
                )
                # Cancellation while replacing results rolls back the whole publication.
                data, revision = session.execute_read(analyzer.read, run)
                checks = 0

                def cancel_during_publish(_):
                    nonlocal checks
                    checks += 1
                    if checks == 3:
                        raise Cancelled()

                with patch.object(graph.guard_adapter, "guard", side_effect=cancel_during_publish):
                    with self.assertRaises(Cancelled):
                        session.execute_write(analyzer.publish, run, data, revision)
                self.assertEqual(
                    session.run("MATCH ()-[r:VOTING_SIMILARITY]->() RETURN count(r) AS n").single()[
                        "n"
                    ],
                    3,
                )
                # A new committed load invalidates all derived edges and stale publication.
                new_load = self.catalog.create("load", {}, extraction)
                Pipeline(self.catalog, self.extractor, graph).execute(new_load)
                self.assertEqual(self.catalog.run(new_load).status, "completed")
                self.assertEqual(
                    session.run("MATCH ()-[r:VOTING_SIMILARITY]->() RETURN count(r) AS n").single()[
                        "n"
                    ],
                    0,
                )
                self.assertEqual(
                    session.run(
                        "MATCH (a:SimilarityAnalysis {key:$key}) RETURN a.status AS status", key=key
                    ).single()["status"],
                    "stale",
                )
                with self.assertRaisesRegex(ValueError, "Graph changed"):
                    session.execute_write(analyzer.publish, run, data, revision)
                analyzer.analyze(run)
            DeleteExtraction(self.catalog, graph, ExtractionFiles(self.root)).execute(extraction)
            with graph.driver() as driver, driver.session() as session:
                self.assertEqual(
                    session.run(
                        "MATCH ()-[r:VOTING_SIMILARITY|VOTING_POSITION|VOTED_IN]->() "
                        "RETURN count(r) AS n"
                    ).single()["n"],
                    0,
                )
                self.assertEqual(
                    session.run(
                        "MATCH (n) WHERE NOT n:DemoGraphState RETURN count(n) AS n"
                    ).single()["n"],
                    0,
                )
        finally:
            with graph.driver() as driver, driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n").consume()

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
                    self.assertEqual(
                        session.run(
                            "MATCH (n) WHERE NOT n:DemoGraphState RETURN count(n) AS n"
                        ).single()["n"],
                        0,
                    )
        finally:
            with graph.driver() as driver, driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n").consume()


if __name__ == "__main__":
    unittest.main()
