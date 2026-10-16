import unittest
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database.connector import Base
from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
)
from src.modules.voice_recognition.application.dtos.identify_speakers_dto import (
    AssignSpeakerLabelDTO,
    IdentifyDiarizationSpeakersRequestDTO,
)
from src.modules.voice_recognition.application.dtos.speaker_profile_dto import (
    CreateSpeakerProfileDTO,
    UpdateSpeakerProfileDTO,
)
from src.modules.voice_recognition.application.use_cases import (
    EnrollSpeakerUseCase,
    IdentifyDiarizationSpeakersUseCase,
    ManageSpeakerProfilesUseCase,
)
from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.infrastructure.repositories.models import (
    SpeakerProfileModel,
    VoiceSampleModel,
)
from src.modules.voice_recognition.infrastructure.repositories.speaker_repository import (
    SpeakerRepository,
)


class VoiceRecognitionUseCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.speaker_repo = MagicMock()
        self.embedding_service = MagicMock()
        self.diarization_repo = MagicMock()

        self.manage_use_case = ManageSpeakerProfilesUseCase(
            speaker_repository=self.speaker_repo,
            voice_embedding_service=self.embedding_service,
        )
        self.enroll_use_case = EnrollSpeakerUseCase(
            speaker_repository=self.speaker_repo,
            voice_embedding_service=self.embedding_service,
            diarization_repository=self.diarization_repo,
        )
        self.identify_use_case = IdentifyDiarizationSpeakersUseCase(
            speaker_repository=self.speaker_repo,
            voice_embedding_service=self.embedding_service,
            diarization_repository=self.diarization_repo,
            enroll_use_case=self.enroll_use_case,
        )

    def test_create_and_list_speaker_profiles(self) -> None:
        self.speaker_repo.create_profile.return_value = SpeakerProfileEntity(
            id="spk-1",
            name="Alice Martins",
            description="Host",
            samples_count=0,
        )
        self.speaker_repo.list_samples.return_value = []

        res = self.manage_use_case.create_profile(
            CreateSpeakerProfileDTO(name="Alice Martins", description="Host")
        )
        self.assertEqual(res.id, "spk-1")
        self.assertEqual(res.name, "Alice Martins")
        self.assertEqual(res.samples_count, 0)

        self.speaker_repo.list_profiles.return_value = [
            SpeakerProfileEntity(id="spk-1", name="Alice Martins", samples_count=2)
        ]
        profiles = self.manage_use_case.list_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].samples_count, 2)

    def test_update_and_delete_speaker_profile(self) -> None:
        self.speaker_repo.update_profile.return_value = SpeakerProfileEntity(
            id="spk-1",
            name="Alice M.",
            description="Updated",
            samples_count=1,
        )
        self.speaker_repo.list_samples.return_value = []
        updated = self.manage_use_case.update_profile(
            "spk-1", UpdateSpeakerProfileDTO(name="Alice M.", description="Updated")
        )
        self.assertEqual(updated.name, "Alice M.")

        self.speaker_repo.delete_profile.return_value = True
        self.assertTrue(self.manage_use_case.delete_profile("spk-1"))

    def test_enroll_from_diarization_updates_result_json(self) -> None:
        self.diarization_repo.get_task.return_value = DiarizationEntity(
            id="diar-100",
            entity_id="yt-100",
            entity_type="YOUTUBE",
            file_path="video.mp4",
            result_json={
                "speakers": ["SPEAKER_00", "SPEAKER_01"],
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start": 0.0,
                        "end": 4.5,
                        "text": "Olá pessoal",
                    },
                    {
                        "speaker": "SPEAKER_01",
                        "start": 4.5,
                        "end": 8.0,
                        "text": "Tudo bem",
                    },
                ],
            },
        )
        self.speaker_repo.get_profile_by_name.return_value = None
        self.speaker_repo.create_profile.return_value = SpeakerProfileEntity(
            id="spk-alice",
            name="Alice",
            samples_count=0,
        )
        self.embedding_service.extract_embedding_from_segments.return_value = [0.25] * 256
        self.speaker_repo.add_sample.return_value = VoiceSampleEntity(
            id="smp-1",
            speaker_id="spk-alice",
        )
        self.speaker_repo.get_profile.return_value = SpeakerProfileEntity(
            id="spk-alice",
            name="Alice",
            samples_count=1,
        )

        response = self.enroll_use_case.enroll_from_diarization(
            EnrollFromDiarizationDTO(
                diarization_id="diar-100",
                speaker_label="SPEAKER_00",
                speaker_name="Alice",
                apply_to_diarization=True,
            )
        )

        self.assertEqual(response.speaker_id, "spk-alice")
        self.assertEqual(response.speaker_name, "Alice")
        self.assertEqual(response.segments_used, 1)
        self.assertEqual(response.speech_duration_seconds, 4.5)
        self.assertTrue(response.applied_to_diarization)

        self.diarization_repo.update_result_json.assert_called_once()
        updated_arg = self.diarization_repo.update_result_json.call_args[0][1]
        self.assertEqual(updated_arg["segments"][0]["speaker"], "Alice")
        self.assertEqual(updated_arg["segments"][0]["original_speaker"], "SPEAKER_00")
        self.assertEqual(updated_arg["speakers"], ["Alice", "SPEAKER_01"])
        self.assertIn("SPEAKER_00", updated_arg["speaker_mappings"])

    def test_identify_diarization_speakers_matches_and_applies(self) -> None:
        self.diarization_repo.get_task.return_value = DiarizationEntity(
            id="diar-200",
            entity_id="yt-200",
            file_path="podcast.mp4",
            result_json={
                "speakers": ["SPEAKER_00", "SPEAKER_01"],
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start": 0.0,
                        "end": 10.0,
                        "text": "Bom dia",
                    },
                    {
                        "speaker": "SPEAKER_01",
                        "start": 10.0,
                        "end": 18.0,
                        "text": "Obrigado",
                    },
                ],
            },
        )
        self.embedding_service.extract_speakers_embeddings.return_value = {
            "SPEAKER_00": [1.0] + [0.0] * 255,
            "SPEAKER_01": [0.0, 1.0] + [0.0] * 254,
        }

        sample_alice = VoiceSampleEntity(id="smp-a", speaker_id="spk-alice")
        profile_alice = SpeakerProfileEntity(id="spk-alice", name="Alice", samples_count=2)

        def fake_nearest(query_vector, top_k=1, min_similarity=0.65):
            if query_vector[0] == 1.0 and min_similarity <= 0.92:
                return [(sample_alice, profile_alice, 0.92)]
            return []

        self.speaker_repo.find_nearest_speaker.side_effect = fake_nearest

        result = self.identify_use_case.identify_diarization(
            "diar-200",
            IdentifyDiarizationSpeakersRequestDTO(similarity_threshold=0.70, auto_apply=True),
        )

        self.assertEqual(result.total_speakers, 2)
        self.assertEqual(result.identified_count, 1)
        self.assertTrue(result.auto_applied)
        self.assertEqual(result.matches[0].matched_speaker_name, "Alice")
        self.assertFalse(result.matches[1].identified)
        self.diarization_repo.update_result_json.assert_called_once()

    def test_assign_speaker_without_enrollment(self) -> None:
        self.diarization_repo.get_task.return_value = DiarizationEntity(
            id="diar-300",
            file_path="clip.mp4",
            result_json={
                "speakers": ["SPEAKER_00"],
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "start": 1.0,
                        "end": 5.0,
                        "text": "Teste",
                    },
                ],
            },
        )
        res = self.identify_use_case.assign_speaker_in_diarization(
            "diar-300",
            AssignSpeakerLabelDTO(
                speaker_label="SPEAKER_00",
                speaker_name="Carlos",
                enroll_voice=False,
            ),
        )
        self.assertEqual(res["speaker_name"], "Carlos")
        self.assertFalse(res["enrolled"])
        self.diarization_repo.update_result_json.assert_called_once()


class SpeakerRepositorySqliteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[SpeakerProfileModel.__table__, VoiceSampleModel.__table__],
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.session = self.SessionLocal()
        self.repo = SpeakerRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_sqlite_crud_and_cosine_similarity_search(self) -> None:
        profile = self.repo.create_profile(
            SpeakerProfileEntity(name="Dr. Roberto", description="Keynote Speaker")
        )
        self.assertIsNotNone(profile.id)

        vec_roberto = [1.0, 0.0, 0.0] + [0.0] * 253
        sample = self.repo.add_sample(
            VoiceSampleEntity(
                speaker_id=profile.id or "",
                source_id="diar-1",
                speaker_label="SPEAKER_00",
                embedding=vec_roberto,
            )
        )
        self.assertIsNotNone(sample.id)

        updated_profile = self.repo.get_profile(profile.id or "")
        self.assertIsNotNone(updated_profile)
        self.assertEqual(updated_profile.samples_count, 1)  # type: ignore[union-attr]

        matches = self.repo.find_nearest_speaker(
            query_vector=[0.95, 0.05, 0.0] + [0.0] * 253,
            top_k=1,
            min_similarity=0.80,
        )
        self.assertEqual(len(matches), 1)
        matched_sample, matched_profile, sim = matches[0]
        self.assertEqual(matched_profile.name, "Dr. Roberto")
        self.assertGreater(sim, 0.95)


if __name__ == "__main__":
    unittest.main()
