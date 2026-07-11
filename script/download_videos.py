import os
import re

import yt_dlp

from src.domain.models.enums.content_status import ContentStatus
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.content_model import ContentModel


def download_video(url: str, content_id: str, origin: str, output_path: str):
    safe_origin = re.sub(r'[\\/*?:"<>|]', "_", origin)
    final_output_path = os.path.join(output_path, safe_origin)
    os.makedirs(final_output_path, exist_ok=True)
    ydl_opts = {
        'outtmpl': f'{final_output_path}/{content_id}_%(title)s.%(ext)s',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'ffmpeg_location': r'C:\Users\ofcer\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin',
        'quiet': False
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main():
    print("Starting video download process...")
    output_path = r"D:\Youtube"
    while True:
        with ConnectorPostgres() as session:
            # Find one pending download
            content = session.query(ContentModel).filter(
                ContentModel.status == ContentStatus.PENDING_DOWNLOAD
            ).first()

            if not content:
                print("No more videos pending download. Finishing.")
                break

            print(f"\nProcessing content: {content.title} ({content.url})")

            # Update status to DOWNLOADING
            content.status = ContentStatus.DOWNLOADING
            session.commit()

            try:
                download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                               output_path=output_path)

                # Update status to DOWNLOADED
                content.status = ContentStatus.DOWNLOADED
                session.commit()
                print(f"Successfully downloaded: {content.title}")
            except Exception as e:
                print(f"Error downloading {content.title}: {e}")
                # Update status to ERROR and save error info
                content.status = ContentStatus.ERROR
                content.error_info = str(e)
                session.commit()


if __name__ == "__main__":
    main()
