import os
import sys

from src.core.config.settings import settings
from src.core.database.connector import ConnectorPostgres
from src.core.utils.file_utils import format_storage_path
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import (
    YoutubeContentModel,
)


def _external_id_from_filename(file: str) -> str | None:
    """Extracts the 11-char YouTube id from a "ID_Title.ext" filename.

    Returns None when the name does not carry an id at all.
    """
    # A YouTube id is exactly 11 chars; the canonical format is ID_Title.ext.
    if len(file) > 12 and file[11] == "_":
        return file[:11]
    if "_" not in file:
        return None
    return file.split("_", 1)[0]


def _link_file_to_content(db, content, file: str) -> str:
    """Points a content row at the file found on disk and marks it COMPLETED."""
    storage_path = format_storage_path(content.origin or "", file)
    content.file_path = storage_path
    content.step = ContentStep.COMPLETED
    db.commit()
    return storage_path


def run_backfill():
    sys.stdout.reconfigure(encoding="utf-8")

    if not settings.DOWNLOAD_YOUTUBE_PATH:
        print("Erro: DOWNLOAD_YOUTUBE_PATH não configurado nas variáveis de ambiente.")
        return

    print(f"Iniciando busca reversa (Arquivos -> Banco) em: {settings.DOWNLOAD_YOUTUBE_PATH}")

    updated_count = 0
    not_found_in_db_count = 0

    with ConnectorPostgres() as db:
        for _root, _dirs, files in os.walk(settings.DOWNLOAD_YOUTUBE_PATH):
            for file in files:
                external_id = _external_id_from_filename(file)
                if external_id is None:
                    continue

                content = db.query(YoutubeContentModel).filter(
                    YoutubeContentModel.external_id == external_id
                ).first()

                if content:
                    storage_path = _link_file_to_content(db, content, file)
                    updated_count += 1
                    print(f"[SUCCESS] Arquivo vinculado e step COMPLETED: {content.title} -> {storage_path}")
                else:
                    not_found_in_db_count += 1
                    print(f"[MISSING IN DB] Arquivo no disco sem registro no banco: {file}")

        print("\nResumo da migração:")
        print(f"- Vídeos atualizados: {updated_count}")
        print(f"- Arquivos no disco não encontrados no banco: {not_found_in_db_count}")


if __name__ == "__main__":
    run_backfill()
