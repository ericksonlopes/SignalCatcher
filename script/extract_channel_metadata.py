import argparse
import json
import sys
import os

# Adiciona a raiz do projeto ao sys.path para permitir importações de 'src'
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.infrastructure.services.youtube_scraper import YouTubeScraperService
from src.infrastructure.loggers.logger import logger

def main():

    channel_url = "https://www.youtube.com/@IShowSpeed"

    print(f"Extracting metadata for channel: {channel_url}")
    
    # Instantiate the scraper with the project's logger
    scraper = YouTubeScraperService(logger=logger)

    try:
        metadata = scraper.extract_channel_info(channel_url)
        print("\n=== Channel Metadata ===")
        print(json.dumps(metadata, indent=4, ensure_ascii=False))
        print("========================")
    except Exception as e:
        print(f"\n[ERROR] Failed to extract channel metadata: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
