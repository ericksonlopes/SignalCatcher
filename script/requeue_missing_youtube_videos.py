"""Return missing COMPLETED videos from an audit CSV to the download queue."""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script.find_missing_youtube_videos import has_video, index_videos
from src.modules.youtube.domain.enums.content_step import ContentStep


def requeue_missing_videos(report: Path, root: Path) -> list[str]:
    from sqlalchemy import select

    from src.core.logger.logger import logger
    from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
        YoutubeContentModel,
    )
    from src.modules.youtube.infrastructure.unit_of_work import YoutubeUnitOfWork

    with report.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"external_id", "step"}.issubset(reader.fieldnames or []):
            raise ValueError("O CSV precisa das colunas external_id e step.")
        external_ids = sorted(
            {
                row["external_id"]
                for row in reader
                if row["step"] == ContentStep.COMPLETED.value and row["external_id"]
            }
        )

    if not external_ids:
        return []

    root = root.expanduser().resolve()
    print(f"Conferindo {len(external_ids)} registros do relatório em: {root}")
    paths, video_ids = index_videos(root)
    if not paths:
        raise ValueError("Nenhum vídeo visível no SSD. Confira a montagem antes de alterar a fila.")

    queued: list[str] = []
    with YoutubeUnitOfWork(logger=logger) as uow:
        for external_id in external_ids:
            model = uow.session.scalars(
                select(YoutubeContentModel)
                .where(YoutubeContentModel.external_id == external_id)
                .with_for_update()
            ).first()
            if model is None or model.step != ContentStep.COMPLETED:
                print(f"[IGNORADO] {external_id}: registro ausente ou não está mais COMPLETED.")
                continue
            if model.lease_token or model.deletion_requested:
                print(f"[IGNORADO] {external_id}: reservado ou aguardando exclusão.")
                continue
            if model.drive_file_id and model.storage_location in {"DRIVE", "BOTH"}:
                print(f"[IGNORADO] {external_id}: possui cópia no Drive; use Restaurar no SSD.")
                continue
            content = uow.contents.get_by_external_id(external_id)
            if content is None:
                continue
            if has_video(content.model_dump(), root, paths, video_ids):
                print(f"[IGNORADO] {external_id}: arquivo encontrado no SSD.")
                continue

            content.step = ContentStep.PENDING_DOWNLOAD
            content.file_path = None
            content.error_info = None
            content.next_retry_at = None
            uow.contents.update_content(content)
            model.attempt_count = 0
            model.lease_expires_at = None
            queued.append(external_id)

        uow.commit()

    for external_id in queued:
        print(f"[NA FILA] {external_id} | COMPLETED -> PENDING_DOWNLOAD")
    print(f"Vídeos devolvidos à fila de download: {len(queued)}")
    return queued


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recoloca na fila os vídeos COMPLETED do CSV que continuam sem arquivo."
    )
    parser.add_argument("report", type=Path, help="CSV gerado pela auditoria de vídeos ausentes.")
    parser.add_argument("--path", type=Path, required=True, help="Pasta de vídeos do SSD.")
    args = parser.parse_args()
    requeue_missing_videos(args.report, args.path)


if __name__ == "__main__":
    main()
