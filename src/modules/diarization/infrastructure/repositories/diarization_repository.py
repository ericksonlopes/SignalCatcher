import logging
from typing import Optional
from src.modules.diarization.infrastructure.repositories.models.diarization_model import DiarizationModel
from src.core.database.connector import ConnectorPostgres

logger = logging.getLogger(__name__)


class DiarizationRepository:
    def create_task(
        self,
        file_path: str,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        language: Optional[str] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        model_size: str = "large-v2"
    ) -> DiarizationModel:
        with ConnectorPostgres() as db:
            new_task = DiarizationModel(
                file_path=file_path,
                entity_id=entity_id,
                entity_type=entity_type,
                step="PENDING",
                language=language,
                num_speakers=num_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                model_size=model_size
            )
            db.add(new_task)
            db.commit()
            db.refresh(new_task)
            db.expunge(new_task)
            return new_task

    def get_task(self, task_id: str) -> Optional[DiarizationModel]:
        with ConnectorPostgres() as db:
            task = db.query(DiarizationModel).filter(DiarizationModel.id == task_id).first()
            if task:
                db.expunge(task)
            return task

    def get_all_diarizations(self) -> list[DiarizationModel]:
        with ConnectorPostgres() as db:
            diarizations = db.query(DiarizationModel).order_by(DiarizationModel.created_at.desc()).all()
            for d in diarizations:
                db.expunge(d)
            return diarizations

    def get_diarizations_with_details(
        self,
        page: int = 1,
        limit: int = 20,
        step: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        from src.modules.youtube.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
        from sqlalchemy import or_

        with ConnectorPostgres() as db:
            query = (
                db.query(DiarizationModel, YoutubeContentModel)
                .outerjoin(YoutubeContentModel, DiarizationModel.entity_id == YoutubeContentModel.external_id)
                .order_by(DiarizationModel.created_at.desc())
            )

            if step and step.upper() != "ALL":
                step_upper = step.upper()
                if step_upper == "PENDING":
                    query = query.filter(DiarizationModel.step == "PENDING")
                elif step_upper == "PROCESSING":
                    query = query.filter(
                        DiarizationModel.step.in_(
                            ["STARTED", "TRANSCRIPTION", "ALIGNMENT", "DIARIZATION", "PROCESSING"]
                        )
                    )
                elif step_upper == "ERROR":
                    query = query.filter(DiarizationModel.step == "ERROR")
                elif step_upper == "COMPLETED":
                    query = query.filter(DiarizationModel.step == "COMPLETED")
                else:
                    query = query.filter(DiarizationModel.step == step)

            if search:
                search_filter = f"%{search}%"
                query = query.filter(
                    or_(
                        YoutubeContentModel.title.ilike(search_filter),
                        YoutubeContentModel.origin.ilike(search_filter),
                        DiarizationModel.entity_id.ilike(search_filter),
                    )
                )

            total = query.count()
            offset = (page - 1) * limit
            results = query.offset(offset).limit(limit).all()

            diarizations = []
            for d_model, y_model in results:
                diarizations.append({
                    "id": d_model.id,
                    "step": d_model.step,
                    "created_at": d_model.created_at.isoformat() if d_model.created_at else None,
                    "entity_id": d_model.entity_id,
                    "entity_type": d_model.entity_type,
                    "title": y_model.title if y_model else "Desconhecido",
                    "channelName": y_model.origin if y_model else "Desconhecido",
                    "thumbnail": y_model.thumbnail if y_model else "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=300&auto=format&fit=crop&q=80",
                    "duration": str(y_model.duration) if y_model else "00:00:00",
                    "result_json": d_model.result_json
                })
            return diarizations, total

    def count_by_step(self) -> dict[str, int]:
        from sqlalchemy import func

        with ConnectorPostgres() as db:
            counts = (
                db.query(DiarizationModel.step, func.count(DiarizationModel.id))
                .group_by(DiarizationModel.step)
                .all()
            )
            return {step: count for step, count in counts if step}

    def get_diarization_statuses_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        if not entity_ids:
            return {}
        with ConnectorPostgres() as db:
            records = (
                db.query(DiarizationModel.entity_id, DiarizationModel.step)
                .filter(DiarizationModel.entity_id.in_(entity_ids))
                .order_by(DiarizationModel.created_at.desc())
                .all()
            )
            result = {}
            for entity_id, step in records:
                if entity_id and entity_id not in result:
                    result[entity_id] = step
            return result

    def reprocess_task(self, task_id: str) -> Optional[DiarizationModel]:
        with ConnectorPostgres() as db:
            task = db.query(DiarizationModel).filter(DiarizationModel.id == task_id).first()
            if not task:
                task = (
                    db.query(DiarizationModel)
                    .filter(DiarizationModel.entity_id == task_id)
                    .order_by(DiarizationModel.created_at.desc())
                    .first()
                )
            if not task:
                return None

            task.step = "PENDING"
            task.error_message = None
            task.result_json = None
            db.commit()
            db.refresh(task)
            db.expunge(task)
            return task

    def cancel_task(self, task_id: str) -> Optional[DiarizationModel]:
        """
        Cancels a diarization task that is currently in progress.
        Only cancellable if step is in: PENDING, STARTED, TRANSCRIPTION, ALIGNMENT, DIARIZATION.
        Returns None if task not found; returns the task with step='CANCELLED' otherwise.
        Returns the task unchanged if it is already in a terminal state (COMPLETED, CANCELLED, ERROR).
        """
        cancellable_steps = {"PENDING", "STARTED", "TRANSCRIPTION", "ALIGNMENT", "DIARIZATION"}
        with ConnectorPostgres() as db:
            task = db.query(DiarizationModel).filter(DiarizationModel.id == task_id).first()
            if not task:
                task = (
                    db.query(DiarizationModel)
                    .filter(DiarizationModel.entity_id == task_id)
                    .order_by(DiarizationModel.created_at.desc())
                    .first()
                )
            if not task:
                return None

            if task.step not in cancellable_steps:
                # Return the task as-is so the caller can detect it's not cancellable
                db.expunge(task)
                return task

            task.step = "CANCELLED"
            db.commit()
            db.refresh(task)
            db.expunge(task)
            return task
