"""Read-only audit of youtube_contents against the mounted downloads directory."""

import argparse
import csv
import os
import re
import stat
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.utils.file_utils import sanitize_path_parts
from src.modules.youtube.domain.enums.content_step import ContentStep

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".m4v", ".ts", ".3gp"}
VIDEO_ID = re.compile(r"^([A-Za-z0-9_-]{11})(?:_|\.)")
FRAGMENT = re.compile(r"\.(?:f\d+|part\d*|temp)(?:\.|$)", re.IGNORECASE)
CSV_FIELDS = ["id", "external_id", "title", "origin", "step", "url", "file_path"]


def index_videos(root: Path) -> tuple[set[Path], set[str]]:
    """Scan once; reject unreadable trees instead of reporting false missing files."""
    if not root.is_dir():
        raise ValueError(f"Pasta de vídeos indisponível: {root}. Confira a montagem do SSD.")

    paths: set[Path] = set()
    external_ids: set[str] = set()

    directories = [root]
    while directories:
        # DirEntry caches file metadata on Windows, avoiding repeated SMB requests.
        with os.scandir(directories.pop()) as entries:
            for entry in entries:
                metadata = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or (
                    getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    continue
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    directories.append(path)
                    continue
                if path.suffix.lower() not in VIDEO_EXTENSIONS or FRAGMENT.search(entry.name):
                    continue
                if not entry.is_file(follow_symlinks=False) or metadata.st_size == 0:
                    continue
                paths.add(path)
                match = VIDEO_ID.match(entry.name)
                if match:
                    external_ids.add(match.group(1))
    return paths, external_ids


def stored_video_path(content: Mapping[str, Any], root: Path) -> Path | None:
    """Map the stored public path to the local downloads directory."""
    stored = content["file_path"]
    if not stored:
        return None
    stored = str(stored).replace("\\", "/")
    if stored.startswith("/youtube/"):
        candidate = root / stored.removeprefix("/youtube/")
    else:
        candidate = Path(stored)
        if not candidate.is_absolute():
            candidate = root / candidate
    return candidate


def has_video(
    content: Mapping[str, Any], root: Path, paths: set[Path], external_ids: set[str]
) -> bool:
    """Accept a stored path or an ID match anywhere within the downloads root."""
    if content["external_id"] in external_ids:
        return True
    candidate = stored_video_path(content, root)
    return candidate is not None and candidate.resolve() in paths


def expected_video_path(content: Mapping[str, Any], root: Path) -> Path:
    """Use the stored filename, or an ID pattern when no filename is recorded."""
    stored = stored_video_path(content, root)
    if stored is not None:
        return stored
    directory = root.joinpath(*sanitize_path_parts(content["origin"] or ""))
    return directory / f"{content['external_id']}_*"


def write_report(
    contents: Iterable[Mapping[str, Any]],
    root: Path,
    output: Path,
    paths: set[Path],
    external_ids: set[str],
    expected_root: Path | None = None,
) -> tuple[int, int]:
    checked = missing = 0
    with output.open("w", encoding="utf-8-sig", newline="") as report:
        writer = csv.DictWriter(report, fieldnames=[*CSV_FIELDS, "expected_path"])
        writer.writeheader()
        for content in contents:
            if content["step"] != ContentStep.COMPLETED:
                continue
            checked += 1
            if has_video(content, root, paths, external_ids):
                continue
            row = {field: content[field] for field in CSV_FIELDS}
            step = row["step"]
            row["step"] = step.value if isinstance(step, ContentStep) else step
            row["expected_path"] = str(expected_video_path(content, expected_root or root))
            writer.writerow(row)
            missing += 1
            print(
                f"[SEM VÍDEO] {row['external_id']} | {row['step']} | {row['title']} "
                f"| Caminho esperado: {row['expected_path']}"
            )
    return checked, missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lista registros COMPLETED de youtube_contents sem vídeo no SSD. "
        "Não altera o banco nem os vídeos. A verificação é de presença, não de integridade.",
    )
    parser.add_argument("--path", type=Path, help="Pasta do SSD (padrão: DOWNLOAD_YOUTUBE_PATH).")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("missing_youtube_videos.csv"),
        help="CSV de saída (padrão: missing_youtube_videos.csv; substitui se existir).",
    )
    parser.add_argument(
        "--step",
        choices=[ContentStep.COMPLETED.value],
        default=ContentStep.COMPLETED.value,
        help="Status verificado: somente COMPLETED (padrão).",
    )
    args = parser.parse_args()

    # Delay configuration/database imports so --help works without an .env file.
    from sqlalchemy import or_, select

    from src.core.config.settings import settings
    from src.core.database.connector import ConnectorPostgres
    from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
        YoutubeContentModel,
    )

    configured_path = str(args.path) if args.path is not None else settings.DOWNLOAD_YOUTUBE_PATH
    if not configured_path.strip():
        parser.error("Configure DOWNLOAD_YOUTUBE_PATH ou informe --path.")
    root = Path(configured_path).expanduser().resolve()
    print(f"Verificando arquivos em: {root}")
    try:
        paths, external_ids = index_videos(root)
        print(f"Arquivos de vídeo não vazios encontrados: {len(paths)}")
        statement = (
            select(*(getattr(YoutubeContentModel, field) for field in CSV_FIELDS))
            .where(
                YoutubeContentModel.step == ContentStep.COMPLETED,
                or_(
                    YoutubeContentModel.storage_location.is_(None),
                    YoutubeContentModel.storage_location != "DRIVE",
                ),
            )
            .order_by(YoutubeContentModel.id)
        )
        with ConnectorPostgres() as db:
            contents = db.execute(statement.execution_options(yield_per=500)).mappings()
            checked, missing = write_report(
                contents,
                root,
                args.output,
                paths,
                external_ids,
                expected_root=Path(configured_path).expanduser().absolute(),
            )
    except (OSError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(
        f"\nRegistros verificados: {checked} | Com vídeo: {checked - missing} "
        f"| Sem vídeo: {missing}"
    )
    print(f"Relatório: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
