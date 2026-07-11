import sys
import os

# Add the root directory of the project to PYTHONPATH so that we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add the script directory to PYTHONPATH to import download_video
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.content_model import ContentModel
from src.domain.models.enums.content_status import ContentStatus
from download_videos import download_video

def main():
    print("Starting error retry process...")
    output_path = r"D:\Youtube"
    
    with ConnectorPostgres() as session:
        # Find all videos that failed previously
        error_contents = session.query(ContentModel).filter(
            ContentModel.status == ContentStatus.ERROR
        ).all()
        
        if not error_contents:
            print("No videos with ERROR status found.")
            return

        print(f"Found {len(error_contents)} videos to retry.\n")

        for content in error_contents:
            print(f"\nRetrying content: {content.title} ({content.url})")
            print(f"Previous Error: {content.error_info}")
            
            # Update status to DOWNLOADING
            content.status = ContentStatus.DOWNLOADING
            session.commit()
            
            try:
                download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                               output_path=output_path)
                
                # Update status to DOWNLOADED and clear error info
                content.status = ContentStatus.DOWNLOADED
                content.error_info = None
                session.commit()
                print(f"Successfully downloaded on retry: {content.title}")
            except Exception as e:
                error_msg = str(e).lower()
                print(f"Error downloading again {content.title}: {e}")
                # Save error info
                content.error_info = str(e)
                # Check if it's a members-only error
                if "members-only content like this video" in error_msg or "members on level" in error_msg:
                    content.status = ContentStatus.MEMBERS_ONLY
                else:
                    content.status = ContentStatus.ERROR
                session.commit()

if __name__ == "__main__":
    main()
