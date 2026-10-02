import json
import logging
import time
from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import urlparse

import requests

from src.modules.demograph.application.use_cases.pipeline import Cancelled
from src.modules.demograph.domain.contracts import Run
from src.modules.demograph.infrastructure.catalog import SqlCatalog, now
from src.modules.demograph.infrastructure.storage.files import (
    checksum,
    safe_path,
)
from src.modules.demograph.infrastructure.storage.schema import SchemaObserver

logger = logging.getLogger(__name__)

API = "https://dadosabertos.camara.leg.br/api/v2/"
FILES = "https://dadosabertos.camara.leg.br/arquivos/"


class ChamberTransport:
    def __init__(self, catalog: SqlCatalog, root: Path, stopped: Event | None = None) -> None:
        self.catalog = catalog
        self.root = root
        self.stopped = stopped or Event()
        self.http = requests.Session()
        self.http.headers["Accept"] = "application/json"

    def guard(self, run_id: str) -> None:
        if self.stopped.is_set():
            raise RuntimeError("Worker stopped or lost its lock.")
        if self.catalog.run(run_id).cancel_requested:
            raise Cancelled()

    def paged(
        self,
        run: Run,
        dataset: str,
        endpoint: str,
        name: str,
        metadata: dict[str, Any],
        allow_missing: bool = False,
    ) -> None:
        url = f"{API}{endpoint}?pagina=1&itens=100"
        seen: set[str] = set()
        fingerprints: set[str] = set()
        page = 1
        logger.info(f"Starting pagination for dataset {dataset} at endpoint {endpoint}")
        while url:
            self.guard(run.id)
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "dadosabertos.camara.leg.br"
                or not parsed.path.startswith("/api/v2/")
            ):
                logger.error(f"Unsafe pagination URL detected: {url}")
                raise ValueError("Unsafe pagination URL.")
            if url in seen:
                logger.error(f"Pagination loop detected: {url}")
                raise ValueError("Pagination loop detected.")
            seen.add(url)
            logger.debug(f"Fetching page {page} for dataset {dataset}")
            artifact = self.fetch(
                run,
                dataset,
                f"{name}-{page:06}.json",
                url,
                {**metadata, "page": page},
                allow_missing,
            )
            envelope = json.loads(
                safe_path(self.root, artifact["path"]).read_text(encoding="utf-8")
            )
            data = envelope.get("dados")
            if not isinstance(data, list):
                logger.error(f"Expected paginated array, got {type(data)} at {url}")
                raise ValueError("Expected a paginated array.")
            fingerprint = json.dumps(data, sort_keys=True, ensure_ascii=False)
            if data and fingerprint in fingerprints:
                logger.error(f"Source repeated a page at {url}")
                raise ValueError("Source repeated a page.")
            fingerprints.add(fingerprint)
            if not data:
                logger.info(f"Pagination finished for dataset {dataset} at page {page} (no data)")
                return
            url = next(
                (link["href"] for link in envelope.get("links", []) if link.get("rel") == "next"),
                "",
            )
            if url:
                logger.debug(f"Next page URL: {url}")
            page += 1

    def fetch(
        self,
        run: Run,
        dataset: str,
        name: str,
        url: str,
        metadata: dict[str, Any],
        allow_missing: bool = False,
    ) -> dict[str, Any]:
        logger.debug(f"Fetching artifact {name} for dataset {dataset}")
        relative = f"{run.extraction_id}/{dataset}/{name}"
        existing = self.catalog.artifact_at(run.extraction_id, relative)
        target = safe_path(self.root, relative)
        if existing:
            if not target.is_file() or checksum(target) != existing["checksum"]:
                logger.error(f"Artifact missing or corrupted: {relative}")
                raise ValueError("A registered artifact is missing or has changed.")
            logger.debug(f"Returning existing artifact: {relative}")
            return existing
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        collected = now()
        for attempt in range(4):
            self.guard(run.id)
            try:
                logger.info(f"Downloading {url} (attempt {attempt + 1})")
                with self.http.get(
                    url, timeout=(10, 120), stream=True, allow_redirects=False
                ) as response:
                    if response.status_code == 404 and allow_missing:
                        logger.warning(f"Resource unavailable (404) for {url}, but allowed.")
                        temporary.write_text(
                            json.dumps({"dados": [], "unavailable": True}), encoding="utf-8"
                        )
                        metadata = {**metadata, "unavailable": True}
                        self.catalog.issue(
                            run.id, "Source resource unavailable (404).", {"url": url}
                        )
                        break
                    response.raise_for_status()
                    if 300 <= response.status_code < 400:
                        logger.error(f"Unexpected redirect for {url}: {response.status_code}")
                        raise ValueError("Unexpected redirect from official source.")
                    received = 0
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_content(1024 * 1024):
                            self.guard(run.id)
                            handle.write(chunk)
                            received += len(chunk)
                            self.catalog.progress(
                                run.id,
                                current_file=name,
                                bytes_received=received,
                                bytes_total=response.headers.get("Content-Length"),
                            )
                    logger.info(f"Download complete: {name} ({received} bytes)")
                    break
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                logger.warning(f"Request failed: {exc} (Status: {status})")
                if attempt == 3 or (status is not None and status not in {429, 500, 502, 503, 504}):
                    logger.error(f"Max retries reached or non-retryable status for {url}")
                    raise
                logger.info(f"Waiting before retry for {url}")
                for _ in range(2**attempt * 5):
                    self.guard(run.id)
                    time.sleep(0.2)
        # Schema and record counts are derived from the complete file before publication.
        observer = SchemaObserver(csv_mode=target.suffix == ".csv")
        if target.suffix == ".csv":
            metadata = {**metadata, "encoding": "utf-8-sig"}
            # rows() dispatches by extension; the temporary CSV has a .part suffix.
            try:
                self.scan_csv(temporary, observer, metadata["encoding"], run.id)
            except UnicodeDecodeError:
                observer = SchemaObserver(csv_mode=True)
                metadata["encoding"] = "cp1252"
                self.scan_csv(temporary, observer, metadata["encoding"], run.id)
        else:
            envelope = json.loads(temporary.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict) or "dados" not in envelope:
                raise ValueError("Invalid Câmara envelope.")
            data = envelope["dados"]
            records = data if isinstance(data, list) else [data]
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("Invalid source record.")
                observer.observe(record)
        self.guard(run.id)
        temporary.replace(target)
        values = {
            "extraction_id": run.extraction_id,
            "dataset_id": dataset,
            "path": relative,
            "format": target.suffix[1:],
            "checksum": checksum(target),
            "bytes": target.stat().st_size,
            "records": observer.count,
            "source_url": url,
            "collected_at": collected,
            "file_schema": observer.result(),
            "metadata_json": {**metadata, "extractor_version": "1"},
        }
        self.catalog.add_artifact(values)
        self.catalog.progress(run.id, files_saved=self.catalog.artifact_count(run.extraction_id))
        return values

    def scan_csv(self, path: Path, observer: SchemaObserver, encoding: str, run_id: str) -> None:
        import csv

        with path.open(encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            if not reader.fieldnames:
                raise ValueError("CSV has no header.")
            required = (
                {"idVotacao", "deputado_id", "voto", "dataHoraVoto"}
                if "votacoesVotos" in path.name
                else {"id", "data"}
            )
            if not required.issubset(reader.fieldnames):
                raise ValueError("CSV does not match the official dataset contract.")
            for index, record in enumerate(reader):
                if None in record:
                    raise ValueError("CSV row has unexpected columns.")
                observer.observe(record)
                if index % 1000 == 0:
                    self.guard(run_id)
