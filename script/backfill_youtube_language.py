import sys
import os

# Ensure the root project directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from src.core.database.connector import ConnectorPostgres
from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
from src.modules.youtube.domain.enums.content_step import ContentStep

def backfill_language():
    with ConnectorPostgres() as db:
        updated_count = 0
        offset = 0
        
        print("Starting backfill one by one (using offset/limit)...")
        
        while True:
            try:
                # Fetch exactly one record at a time without .all()
                content = (
                    db.query(YoutubeContentModel)
                    .filter(YoutubeContentModel.step == ContentStep.COMPLETED)
                    .order_by(YoutubeContentModel.id)
                    .offset(offset)
                    .limit(1)
                    .first()
                )
                
                if not content:
                    break  # No more records found
                
                if content.raw_metadata and isinstance(content.raw_metadata, dict):
                    language = content.raw_metadata.get("language")
                    if language:
                        content.language = language
                        db.commit()
                        updated_count += 1
                        print(f"[Offset: {offset}] Updated '{content.external_id}' with language: {language}")
                    else:
                        print(f"[Offset: {offset}] Skipped '{content.external_id}' (no language in metadata)")
                else:
                    print(f"[Offset: {offset}] Skipped '{content.external_id}' (no valid metadata)")

                offset += 1

            except Exception as e:
                db.rollback()
                print(f"[Offset: {offset}] Error: {e}")
                offset += 1  # Still increment offset to not get stuck in infinite loop
        
        print(f"Backfill complete! Updated {updated_count} records.")

if __name__ == "__main__":
    backfill_language()
