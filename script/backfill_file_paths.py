import os
from sqlalchemy.orm import Session
from src.core.database.connector import ConnectorPostgres
from src.core.config.settings import settings
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel

def run_backfill():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    if not settings.DOWNLOAD_YOUTUBE_PATH:
        print("Erro: DOWNLOAD_YOUTUBE_PATH não configurado nas variáveis de ambiente.")
        return

    print(f"Iniciando busca reversa (Arquivos -> Banco) em: {settings.DOWNLOAD_YOUTUBE_PATH}")
    
    updated_count = 0
    not_found_in_db_count = 0
    
    from src.modules.youtube.domain.enums.content_step import ContentStep
    
    with ConnectorPostgres() as db:
        # Percorre todos os arquivos dentro do diretório raiz
        for root, dirs, files in os.walk(settings.DOWNLOAD_YOUTUBE_PATH):
            for file in files:
                # O ID do YouTube tem exatamente 11 caracteres. O formato é ID_Titulo.ext
                if len(file) > 12 and file[11] == '_':
                    external_id = file[:11]
                else:
                    # Fallback para nomes que talvez não sigam a regra estrita
                    if '_' not in file:
                        continue
                    external_id = file.split('_', 1)[0]
                
                # Busca no banco se existe algum conteúdo com esse ID
                content = db.query(YoutubeContentModel).filter(
                    YoutubeContentModel.external_id == external_id
                ).first()
                
                if content:
                    from src.core.utils.file_utils import format_storage_path
                    storage_path = format_storage_path(content.origin or "", file)
                        
                    content.file_path = storage_path
                    content.step = ContentStep.COMPLETED
                    db.commit()
                    updated_count += 1
                    print(f"[SUCCESS] Arquivo vinculado e step COMPLETED: {content.title} -> {storage_path}")
                else:
                    # Verifica se já foi atualizado ou se não existe no banco
                    exists = db.query(YoutubeContentModel).filter(YoutubeContentModel.external_id == external_id).first()
                    if not exists:
                        not_found_in_db_count += 1
                        print(f"[MISSING IN DB] Arquivo no disco sem registro no banco: {file}")
                        
        print(f"\nResumo da migração:")
        print(f"- Vídeos atualizados: {updated_count}")
        print(f"- Arquivos no disco não encontrados no banco: {not_found_in_db_count}")

if __name__ == "__main__":
    run_backfill()
