import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.modules.diarization.infrastructure.repositories.diarization_repository import (
    DiarizationRepository,
)
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)


class DiarizationOrderTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        DiarizationModel.__table__.create(self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                DiarizationModel.__table__.insert(),
                [
                    {
                        "id": "old-request-new-result",
                        "file_path": "old.mp4",
                        "step": "COMPLETED",
                        "created_at": datetime(2026, 9, 1),
                        "updated_at": datetime(2026, 9, 29),
                    },
                    {
                        "id": "new-request-old-result",
                        "file_path": "new.mp4",
                        "step": "COMPLETED",
                        "created_at": datetime(2026, 9, 20),
                        "updated_at": datetime(2026, 9, 21),
                    },
                    {
                        "id": "legacy-result",
                        "file_path": "legacy.mp4",
                        "step": "COMPLETED",
                        "created_at": datetime(2026, 9, 15),
                        "updated_at": None,
                    },
                    {
                        "id": "pending",
                        "file_path": "pending.mp4",
                        "step": "PENDING",
                        "created_at": datetime(2026, 9, 25),
                        "updated_at": datetime(2026, 9, 30),
                    },
                ],
            )
        self.session = Session(self.engine)
        self.repository = DiarizationRepository(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_completed_results_use_processing_recency_across_pages(self):
        first, total = self.repository.get_paginated(page=1, limit=2, step="COMPLETED")
        second, _ = self.repository.get_paginated(page=2, limit=2, step="COMPLETED")
        self.assertEqual(total, 3)
        self.assertEqual(
            [item.id for item in first + second],
            ["old-request-new-result", "new-request-old-result", "legacy-result"],
        )

    def test_all_tasks_keep_request_order(self):
        items, total = self.repository.get_paginated(page=1, limit=20, step="ALL")
        self.assertEqual(total, 4)
        self.assertEqual(items[0].id, "pending")
        self.assertEqual(items[-1].id, "old-request-new-result")

    def test_equal_processing_dates_have_stable_page_boundaries(self):
        self.session.execute(
            DiarizationModel.__table__.insert(),
            [
                {
                    "id": identifier,
                    "file_path": "same-date.mp4",
                    "step": "COMPLETED",
                    "created_at": datetime(2026, 9, 1),
                    "updated_at": datetime(2026, 10, 1),
                }
                for identifier in ["same-a", "same-z"]
            ],
        )
        first, _ = self.repository.get_paginated(page=1, limit=1, step="completed")
        second, _ = self.repository.get_paginated(page=2, limit=1, step="completed")
        self.assertEqual(first[0].id, "same-z")
        self.assertEqual(second[0].id, "same-a")


if __name__ == "__main__":
    unittest.main()
