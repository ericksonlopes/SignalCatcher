"""Isolated persistence and media-selection regression tests."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.core.database.connector import Base
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)
from src.modules.voice_identity.infrastructure.repositories.models.voice_job_model import VoiceJob
from src.modules.voice_identity.presentation import routes


class VoiceApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "original.mp4").write_bytes(b"original media")
        self.setting = patch.object(routes.settings, "DOWNLOAD_YOUTUBE_PATH", str(self.root))
        self.setting.start()
        self.source = DiarizationModel(
            id="video",
            file_path="original.mp4",
            step="COMPLETED",
            result_json={"duration": 100, "segments": [], "speakers": ["SPEAKER_00"]},
        )
        self.db.add(self.source)
        self.db.flush()
        self.person = routes.create_person(routes.PersonRequest(name="Alice"), self.db)

    def tearDown(self):
        self.setting.stop()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def test_preview_only_returns_original_without_processing(self):
        with patch.object(routes.subprocess, "run") as run:
            response = routes.original_media("video", self.db)
        self.assertEqual(Path(response.path), self.root / "original.mp4")
        run.assert_not_called()
        self.assertEqual(list(self.db.scalars(select(VoiceJob))), [])

    def test_explicit_request_is_deduplicated_and_keeps_selection_snapshot(self):
        request = routes.TrainingRequest(
            person_id=self.person["id"], task_id="video", start=1, end=60
        )
        with patch.object(
            routes.subprocess,
            "run",
            return_value=SimpleNamespace(stdout='{ "format": { "duration": "100" } }'),
        ):
            first = routes.train(request, self.db)
            second = routes.train(request, self.db)
        self.assertEqual(first["id"], second["id"])
        request.end = 90
        self.assertEqual(first["payload"]["end"], 60)
        self.assertEqual(len(list(self.db.scalars(select(VoiceJob)))), 1)

    def test_selection_is_checked_against_real_media_duration(self):
        request = routes.TrainingRequest(
            person_id=self.person["id"], task_id="video", start=1, end=101
        )
        with patch.object(
            routes.subprocess,
            "run",
            return_value=SimpleNamespace(stdout='{ "format": { "duration": "100" } }'),
        ):
            with self.assertRaises(HTTPException) as error:
                routes.train(request, self.db)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(list(self.db.scalars(select(VoiceJob))), [])

    def test_media_path_cannot_escape_root(self):
        with self.assertRaises(HTTPException):
            routes.media_path("../outside", self.root)

    def test_assignment_is_persistent_and_versioned(self):
        routes.assign(
            "video", "SPEAKER_00", routes.AssignmentRequest(person_id=self.person["id"]), self.db
        )
        self.db.flush()
        self.assertEqual(
            routes.identities("video", self.db)["assignments"]["SPEAKER_00"]["name"], "Alice"
        )
        self.source.result_json = {"segments": [], "speakers": ["SPEAKER_00"], "duration": 99}
        self.db.flush()
        self.assertEqual(routes.identities("video", self.db)["assignments"], {})

    def test_homonyms_are_distinct(self):
        other = routes.create_person(routes.PersonRequest(name="Alice"), self.db)
        self.assertNotEqual(other["id"], self.person["id"])


class VoiceHttpContractTests(unittest.TestCase):
    def test_error_responses_are_exposed_in_openapi(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(routes.router)
        paths = app.openapi()["paths"]
        expected = {
            ("/voices/training", "post"): {"404", "409", "422"},
            ("/voices/jobs/{job_id}/retry", "post"): {"404", "409"},
            ("/diarization/{task_id}/identities/{speaker}", "put"): {"404", "409", "422"},
            ("/voices/people/{person_id}", "patch"): {"404", "422"},
        }
        for (path, method), codes in expected.items():
            with self.subTest(path=path):
                self.assertTrue(codes.issubset(paths[path][method]["responses"]))

    def test_captions_are_clipped_and_shifted_without_media_processing(self):
        transcript = {
            "segments": [
                {"start": 1, "end": 4, "text": "First"},
                {"start": 5, "end": 8, "text": "Second"},
                {"start": 10, "end": 12, "text": "Outside"},
            ]
        }
        with patch.object(routes.subprocess, "run") as run:
            captions = routes.sample_captions(transcript, 2, 7)
        self.assertIn("00:00:00.000 --> 00:00:02.000", captions)
        self.assertIn("00:00:03.000 --> 00:00:05.000", captions)
        self.assertNotIn("Outside", captions)
        run.assert_not_called()
