import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.modules.diarization.application.mappers.diarization_card_mapper import (
    DiarizationCardMapper,
)
from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.diarization.infrastructure.repositories.diarization_repository import (
    DiarizationRepository,
)
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)
from src.modules.youtube.infrastructure.repositories.models.step_tracking_model import (
    StepTrackingModel,
)


class DiarizationTrackingTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        DiarizationModel.__table__.create(self.engine)
        StepTrackingModel.__table__.create(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_library_uses_latest_attempt_before_status_filtering(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.add_all(
            [
                DiarizationModel(
                    file_path="old.wav",
                    entity_id="video",
                    entity_type="YOUTUBE",
                    step="COMPLETED",
                    created_at=now - timedelta(days=1),
                ),
                DiarizationModel(
                    file_path="new.wav",
                    entity_id="video",
                    entity_type="YOUTUBE",
                    step="PENDING",
                    created_at=now,
                ),
                DiarizationModel(file_path="upload-one.wav", step="PENDING"),
                DiarizationModel(file_path="upload-two.wav", step="PENDING"),
            ]
        )
        self.session.flush()
        repository = DiarizationRepository(self.session)
        items, total = repository.get_paginated(1, 20)
        self.assertEqual(total, 3)
        self.assertEqual(len(items), 3)
        self.assertEqual(repository.get_paginated(1, 20, step="COMPLETED")[1], 0)
        self.assertEqual(repository.count_by_step(), {"PENDING": 3})

    def test_repeated_requests_reuse_active_task(self):
        repository = DiarizationRepository(self.session)
        request = DiarizationEntity(file_path="audio.wav", entity_id="video", entity_type="YOUTUBE")
        first = repository.create_task(request)
        second = repository.create_task(request)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.session.query(DiarizationModel).count(), 1)

    def test_start_now_requeues_current_and_prioritizes_selected_video(self):
        current = DiarizationModel(
            file_path="current.wav",
            step="TRANSCRIPTION",
            worker_token="old-worker",
            progress_percent=65,
        )
        selected = DiarizationModel(file_path="selected.wav", step="PENDING")
        self.session.add_all([current, selected])
        self.session.flush()
        repository = DiarizationRepository(self.session)
        result = repository.prioritize_task(selected.id)
        self.assertEqual(result.queue_priority, 1)
        self.assertEqual(current.step, "PENDING")
        self.assertIsNone(current.worker_token)
        self.assertIsNone(current.progress_percent)
        self.assertEqual(current.queue_priority, 0)
        rows = self.session.scalars(
            select(StepTrackingModel)
            .where(StepTrackingModel.entity_id == current.id)
            .order_by(StepTrackingModel.id)
        ).all()
        self.assertEqual(rows[-1].new_step, "PENDING")
        self.assertEqual(rows[-1].previous_step, "TRANSCRIPTION")

    def test_request_reprocess_cancel_keep_task_identity_and_utc(self):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        task = DiarizationModel(
            file_path="audio.wav", entity_id="video", entity_type="YOUTUBE", step="PENDING"
        )
        self.session.add(task)
        self.session.flush()
        repository = DiarizationRepository(self.session)
        task.step = "DIARIZED"
        self.session.flush()
        self.assertEqual(repository.get_task(task.id).step, DiarizationStep.DIARIZED)
        self.assertIn(DiarizationStep.DIARIZED, DiarizationStep.in_progress())
        task.step = "COMPLETED"
        self.session.flush()
        repository.reprocess_task(task.id)
        repository.cancel_task(task.id)
        self.session.commit()
        rows = self.session.scalars(select(StepTrackingModel).order_by(StepTrackingModel.id)).all()
        self.assertEqual(
            [row.new_step for row in rows],
            ["PENDING", "DIARIZED", "COMPLETED", "PENDING", "CANCELLED"],
        )
        self.assertTrue(all(row.entity_type == "diarization" for row in rows))
        self.assertTrue(all(row.entity_id == task.id for row in rows))
        self.assertGreaterEqual(rows[0].changed_at, before)
        self.assertLessEqual(rows[-1].changed_at, datetime.now(timezone.utc).replace(tzinfo=None))
        self.assertEqual((task.entity_id, task.entity_type), ("video", "YOUTUBE"))

    def test_rolled_back_request_does_not_leave_history(self):
        self.session.add(DiarizationModel(file_path="upload.wav", step="PENDING"))
        self.session.flush()
        self.session.rollback()
        self.assertEqual(self.session.scalars(select(StepTrackingModel)).all(), [])

    def test_progress_is_exposed_on_cards_and_cleared_on_reprocess_and_cancel(self):
        task = DiarizationModel(file_path="audio.wav", step="ALIGNMENT", progress_percent=65)
        self.session.add(task)
        self.session.flush()
        repository = DiarizationRepository(self.session)
        entity = repository.get_task(task.id)
        self.assertEqual(DiarizationCardMapper.to_card(entity, None).progress_percent, 65)
        self.assertIsNone(repository.reprocess_task(task.id).progress_percent)
        task.step, task.progress_percent = "DIARIZATION", 42
        self.session.flush()
        self.assertIsNone(repository.cancel_task(task.id).progress_percent)


if __name__ == "__main__":
    unittest.main()
