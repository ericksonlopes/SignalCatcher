from datetime import datetime, timezone

from sqlalchemy import case, func, or_, text
from sqlalchemy.orm import Session

from src.modules.diarization.domain.entities.diarization_entity import DiarizationEntity
from src.modules.diarization.domain.enums.diarization_step import DiarizationStep
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.diarization.infrastructure.repositories.mappers.diarization_mapper import (
    DiarizationMapper,
)
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)


class DiarizationRepository(IDiarizationRepository):
    """Persistence for diarization tasks.

    Takes part in the caller's transaction: writes flush but never commit, so the unit
    of work decides when the operation is complete.

    Returns domain entities. It used to hand out SQLAlchemy models and even
    presentation-ready dicts, and it reached into the youtube_contents table directly to
    build them; composing the two modules is the application layer's job now.
    """

    def __init__(self, session: Session):
        self.session = session

    def create_task(self, task: DiarizationEntity) -> DiarizationEntity:
        if task.entity_id:
            # Serialize concurrent requests for a linked video across API replicas.
            if self.session.get_bind().dialect.name == "postgresql":
                self.session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": f"diarization:{task.entity_type}:{task.entity_id}"},
                )
            active = (
                self.session.query(DiarizationModel)
                .filter(
                    DiarizationModel.entity_id == task.entity_id,
                    DiarizationModel.entity_type == task.entity_type,
                    DiarizationModel.step.in_(
                        ["PENDING", *[s.value for s in DiarizationStep.in_progress()]]
                    ),
                )
                .order_by(DiarizationModel.created_at.desc(), DiarizationModel.id.desc())
                .first()
            )
            if active:
                return DiarizationMapper.to_domain(active)
        model = DiarizationMapper.to_model(task)
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def get_task(self, task_id: str) -> DiarizationEntity | None:
        model = self.session.query(DiarizationModel).filter(DiarizationModel.id == task_id).first()
        return DiarizationMapper.to_domain(model) if model else None

    @staticmethod
    def _apply_step_filter(query, step: str | None):
        if not step or step.upper() == "ALL":
            return query
        step_upper = step.upper()
        if step_upper == DiarizationStep.PROCESSING.value:
            # "PROCESSING" is a UI bucket covering every in-flight step.
            return query.filter(
                DiarizationModel.step.in_([s.value for s in DiarizationStep.in_progress()])
            )
        return query.filter(DiarizationModel.step == step_upper)

    @staticmethod
    def _build_entity_conditions(
        entity_ids: list[str] | None,
        entity_id_search: str | None,
    ) -> list | None:
        if entity_ids is None and entity_id_search is None:
            return None
        conditions = []
        if entity_ids:
            conditions.append(DiarizationModel.entity_id.in_(entity_ids))
        if entity_id_search:
            conditions.append(DiarizationModel.entity_id.ilike(f"%{entity_id_search}%"))
        return conditions

    def get_paginated(
        self,
        page: int,
        limit: int,
        step: str | None = None,
        entity_ids: list[str] | None = None,
        entity_id_search: str | None = None,
    ) -> tuple[list[DiarizationEntity], int]:
        # Completed tasks are ordered by their last processing update, so a task
        # requested earlier but finished now appears among the latest results.
        is_completed = bool(step and step.upper() == DiarizationStep.COMPLETED.value)
        latest = (
            func.coalesce(DiarizationModel.updated_at, DiarizationModel.created_at)
            if is_completed
            else DiarizationModel.created_at
        )
        query = self._current_tasks()
        if not step or step.upper() == "ALL":
            # Rank active work before pagination so it is visible on the first page.
            query = query.order_by(
                case(
                    (
                        DiarizationModel.step.in_([s.value for s in DiarizationStep.in_progress()]),
                        0,
                    ),
                    else_=1,
                )
            )
        query = query.order_by(latest.desc(), DiarizationModel.id.desc())
        query = self._apply_step_filter(query, step)

        conditions = self._build_entity_conditions(entity_ids, entity_id_search)
        if conditions is not None:
            if not conditions:
                # A search was requested and nothing could possibly match.
                return [], 0
            query = query.filter(or_(*conditions))

        total = query.count()
        offset = (page - 1) * limit
        models = query.offset(offset).limit(limit).all()
        return [DiarizationMapper.to_domain(m) for m in models], total

    def _current_tasks(self):
        # Choose the latest request before applying status/search filters. Historical
        # attempts remain stored, but never create duplicate video rows in the library.
        ranked = self.session.query(
            DiarizationModel.id.label("id"),
            func.row_number()
            .over(
                partition_by=(
                    DiarizationModel.entity_id.is_(None),
                    func.coalesce(DiarizationModel.entity_type, ""),
                    func.coalesce(DiarizationModel.entity_id, DiarizationModel.id),
                ),
                order_by=(DiarizationModel.created_at.desc(), DiarizationModel.id.desc()),
            )
            .label("position"),
        ).subquery()
        return (
            self.session.query(DiarizationModel)
            .join(ranked, ranked.c.id == DiarizationModel.id)
            .filter(ranked.c.position == 1)
        )

    def count_by_step(self) -> dict[str, int]:
        counts = (
            self._current_tasks()
            .with_entities(DiarizationModel.step, func.count(DiarizationModel.id))
            .group_by(DiarizationModel.step)
            .all()
        )
        return {step: count for step, count in counts if step}

    def get_steps_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        info = self.get_info_by_entity_ids(entity_ids)
        return {eid: data["step"] for eid, data in info.items() if data.get("step")}

    def get_info_by_entity_ids(self, entity_ids: list[str]) -> dict[str, dict]:
        if not entity_ids:
            return {}
        records = (
            self.session.query(
                DiarizationModel.entity_id,
                DiarizationModel.step,
                DiarizationModel.progress_percent,
            )
            .filter(DiarizationModel.entity_id.in_(entity_ids))
            .order_by(DiarizationModel.created_at.desc())
            .all()
        )
        result: dict[str, dict] = {}
        for entity_id, step, progress in records:
            if entity_id and entity_id not in result:
                result[entity_id] = {"step": step, "progress_percent": progress}
        return result

    def _find_model(self, task_id: str) -> DiarizationModel | None:
        """Looks a task up by its own id, falling back to the latest task of an entity."""
        model = self.session.query(DiarizationModel).filter(DiarizationModel.id == task_id).first()
        if model:
            return model
        return (
            self.session.query(DiarizationModel)
            .filter(DiarizationModel.entity_id == task_id)
            .order_by(DiarizationModel.created_at.desc())
            .first()
        )

    def reprocess_task(self, task_id: str) -> DiarizationEntity | None:
        model = self._find_model(task_id)
        if not model:
            return None

        if model.entity_id:
            if self.session.get_bind().dialect.name == "postgresql":
                self.session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                    {"key": f"diarization:{model.entity_type}:{model.entity_id}"},
                )
            active = (
                self.session.query(DiarizationModel)
                .filter(
                    DiarizationModel.entity_id == model.entity_id,
                    DiarizationModel.entity_type == model.entity_type,
                    DiarizationModel.step.in_(
                        ["PENDING", *[s.value for s in DiarizationStep.in_progress()]]
                    ),
                )
                .order_by(DiarizationModel.created_at.desc(), DiarizationModel.id.desc())
                .first()
            )
            if active:
                return DiarizationMapper.to_domain(active)
        model.step = DiarizationStep.PENDING.value
        model.progress_percent = None
        model.worker_token = None
        model.lease_expires_at = None
        model.error_message = None
        model.result_json = None
        model.queue_priority = 0
        model.queued_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def cancel_task(self, task_id: str) -> DiarizationEntity | None:
        model = self._find_model(task_id)
        if not model:
            return None

        cancellable = {s.value for s in DiarizationStep.cancellable()}
        if model.step not in cancellable:
            # Returned unchanged so the caller can tell "not found" from "not cancellable".
            return DiarizationMapper.to_domain(model)

        model.step = DiarizationStep.CANCELLED.value
        model.progress_percent = None
        model.worker_token = None
        model.lease_expires_at = None
        model.queue_priority = 0
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def prioritize_task(self, task_id: str) -> DiarizationEntity | None:
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('diarization:queue'))")
            )
        model = self._find_model(task_id)
        if model is None:
            return None
        if model.step == DiarizationStep.COMPLETED.value:
            raise ValueError("Request a new diarization before prioritizing a completed result.")
        if model.step in {step.value for step in DiarizationStep.in_progress()}:
            return DiarizationMapper.to_domain(model)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active = (
            self.session.query(DiarizationModel)
            .filter(
                DiarizationModel.step.in_([step.value for step in DiarizationStep.in_progress()])
            )
            .order_by(DiarizationModel.id)
            .with_for_update()
            .all()
        )
        for current in active:
            # Revoke ownership before requeuing. Late progress/results from the old
            # subprocess cannot overwrite the next attempt, even for the same task.
            current.step = DiarizationStep.PENDING.value
            current.worker_token = None
            current.lease_expires_at = None
            current.progress_percent = None
            current.result_json = None
            current.error_message = None
            current.queue_priority = 0
            current.queued_at = now

        self.session.query(DiarizationModel).filter(
            DiarizationModel.step == DiarizationStep.PENDING.value,
            DiarizationModel.queue_priority != 0,
        ).update({DiarizationModel.queue_priority: 0}, synchronize_session="fetch")
        model.step = DiarizationStep.PENDING.value
        model.worker_token = None
        model.lease_expires_at = None
        model.progress_percent = None
        model.result_json = None
        model.error_message = None
        model.queue_priority = 1
        model.queued_at = now
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def update_result_json(self, task_id: str, result_json: dict) -> DiarizationEntity | None:
        model = self._find_model(task_id)
        if model is None:
            return None
        model.result_json = result_json
        model.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)
