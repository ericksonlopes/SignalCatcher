import csv
import tempfile
import unittest
from pathlib import Path

from script.find_missing_youtube_videos import has_video, index_videos, write_report
from src.modules.youtube.domain.enums.content_step import ContentStep


class MissingYoutubeVideosTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def create_file(self, name, data=b"video"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_finds_id_with_underscores_when_path_is_absent_or_stale(self):
        self.create_file("new-channel/ab_cd-ef_12_New title.MP4")
        paths, ids = index_videos(self.root)
        for stored in (None, "/youtube/old-channel/old-title.mp4"):
            self.assertTrue(
                has_video(
                    {"external_id": "ab_cd-ef_12", "file_path": stored}, self.root, paths, ids
                )
            )
        self.assertFalse(
            has_video({"external_id": "ab_cd-ef_13", "file_path": None}, self.root, paths, ids)
        )

    def test_resolves_public_relative_and_absolute_paths(self):
        path = self.create_file("channel/custom-name.webm")
        paths, ids = index_videos(self.root)
        for stored in ("/youtube/channel/custom-name.webm", "channel/custom-name.webm", str(path)):
            self.assertTrue(
                has_video(
                    {"external_id": "12345678901", "file_path": stored}, self.root, paths, ids
                )
            )

    def test_ignores_sidecars_empty_files_and_download_fragments(self):
        for filename in (
            "12345678901_title.mp4.part",
            "12345678901_title.f137.mp4",
            "12345678901_title.temp.mp4",
            "12345678901_title.info.json",
            "12345678901_title.m4a",
            "12345678901_title.jpg",
        ):
            self.create_file(filename)
        self.create_file("12345678901_title.mp4", data=b"")
        self.assertEqual(index_videos(self.root), (set(), set()))

    def test_unavailable_root_aborts_scan(self):
        with self.assertRaisesRegex(ValueError, "indisponível"):
            index_videos(self.root / "unmounted-ssd")

    def test_report_only_contains_missing_records(self):
        self.create_file("12345678901_title.mp4")
        paths, ids = index_videos(self.root)
        records = [
            dict(
                id=index,
                external_id=external_id,
                title="Vídeo, título",
                origin="Canal",
                step=ContentStep.COMPLETED,
                url="https://youtube.com/watch?v=" + external_id,
                file_path=None,
            )
            for index, external_id in enumerate(("12345678901", "98765432109"), start=1)
        ]
        output = self.root / "missing.csv"
        self.assertEqual(write_report(records, self.root, output, paths, ids), (2, 1))
        with output.open(encoding="utf-8-sig", newline="") as report:
            rows = list(csv.DictReader(report))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["external_id"], "98765432109")
        self.assertEqual(rows[0]["step"], "COMPLETED")
        self.assertEqual(rows[0]["title"], "Vídeo, título")


if __name__ == "__main__":
    unittest.main()
