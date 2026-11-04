import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.modules.youtube.infrastructure.services import youtube_scraper


class YoutubeScraperOptionsTest(unittest.TestCase):
    def test_project_root_cookies_are_loaded_independently_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cookies = root / "cookies.txt"
            cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            scraper = root / "src/modules/youtube/infrastructure/services/youtube_scraper.py"
            with patch.object(youtube_scraper, "__file__", str(scraper)):
                options = youtube_scraper.YouTubeScraperService._get_common_ydl_opts()
            self.assertEqual(options["cookiefile"], str(cookies))
            cookies.unlink()
            with patch.object(youtube_scraper, "__file__", str(scraper)):
                options = youtube_scraper.YouTubeScraperService._get_common_ydl_opts()
            self.assertNotIn("cookiefile", options)

    def test_https_certificates_are_verified(self):
        options = youtube_scraper.YouTubeScraperService._get_common_ydl_opts()
        self.assertFalse(options.get("nocheckcertificate", False))
