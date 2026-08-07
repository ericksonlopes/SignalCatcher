import logging
import os
import re
import sys

import yt_dlp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.domain.models.enums.content_step import ContentStep
from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel


def download_video(url: str, content_id: str, origin: str, output_path: str):
    parts = [re.sub(r'[\\*?:"<>|]', "_", p) for p in origin.split('/')]
    final_output_path = os.path.join(output_path, *parts)
    os.makedirs(final_output_path, exist_ok=True)
    ydl_opts = {
        'outtmpl': f'{final_output_path}/{content_id}_%(title)s.%(ext)s',
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[ext=mp4]/best',
        'ffmpeg_location': r'C:\Users\ofcer\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin',
        'quiet': False,
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github']
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main():
    logging.info("Starting video download process...")
    output_path = r"D:\Youtube"
    while True:
        with ConnectorPostgres() as session:
            # Find one pending download
            content = session.query(YoutubeContentModel).filter(
                YoutubeContentModel.step == ContentStep.PENDING_DOWNLOAD
            ).first()

            if not content:
                logging.info("No more videos pending download. Finishing.")
                break

            logging.info(f"Processing content: {content.title} ({content.url})")

            # Update step to DOWNLOADING
            content.step = ContentStep.DOWNLOADING
            session.commit()

            try:
                download_video(url=content.url, content_id=content.external_id, origin=content.origin,
                               output_path=output_path)

                # Update step to PENDING_METADATA_EXTRACTION
                content.step = ContentStep.PENDING_METADATA_EXTRACTION
                session.commit()
                logging.info(f"Successfully downloaded: {content.title}")
            except Exception as e:
                error_msg = str(e).lower()
                logging.error(f"Error downloading {content.title}: {e}")
                # Save error info
                content.error_info = str(e)
                # Check if it's a members-only error
                if "members-only content like this video" in error_msg or "members on level" in error_msg:
                    content.step = ContentStep.MEMBERS_ONLY
                elif "sign in to confirm your age" in error_msg:
                    content.step = ContentStep.AGE_RESTRICTED
                elif "private video" in error_msg and "sign in if you've been granted access" in error_msg:
                    content.step = ContentStep.PRIVATE_VIDEO
                elif "removed following a copyright" in error_msg:
                    content.step = ContentStep.COPYRIGHT_REMOVED
                elif "account associated with this video has been terminated" in error_msg:
                    content.step = ContentStep.ACCOUNT_TERMINATED
                else:
                    content.step = ContentStep.ERROR
                session.commit()

                # Check for YouTube bot detection
                if "sign in to confirm you’re not a bot" in error_msg or "sign in to confirm you're not a bot" in error_msg:
                    logging.critical("YouTube bot detection triggered! Stopping the system to prevent IP ban.")
                    sys.exit(1)


if __name__ == "__main__":
    main()
