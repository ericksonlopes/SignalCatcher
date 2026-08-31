from typing import Optional

from sqlalchemy import func, or_
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
        model = DiarizationMapper.to_model(task)
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def get_task(self, task_id: str) -> Optional[DiarizationEntity]:
        model = (
            self.session.query(DiarizationModel)
            .filter(DiarizationModel.id == task_id)
            .first()
        )
        return DiarizationMapper.to_domain(model) if model else None

    def get_paginated(
        self,
        page: int,
        limit: int,
        step: Optional[str] = None,
        entity_ids: Optional[list[str]] = None,
        entity_id_search: Optional[str] = None,
    ) -> tuple[list[DiarizationEntity], int]:
        query = self.session.query(DiarizationModel).order_by(
            DiarizationModel.created_at.desc()
        )

        if step and step.upper() != "ALL":
            step_upper = step.upper()
            if step_upper == DiarizationStep.PROCESSING.value:
                # "PROCESSING" is a UI bucket covering every in-flight step.
                query = query.filter(
                    DiarizationModel.step.in_(
                        [s.value for s in DiarizationStep.in_progress()]
                    )
                )
            else:
                query = query.filter(DiarizationModel.step == step_upper)

        if entity_ids is not None or entity_id_search is not None:
            # A search term can match either the linked entity (resolved by the caller,
            # which is the only side that can look at video titles) or the raw id.
            conditions = []
            if entity_ids:
                conditions.append(DiarizationModel.entity_id.in_(entity_ids))
            if entity_id_search:
                conditions.append(
                    DiarizationModel.entity_id.ilike(f"%{entity_id_search}%")
                )
            if conditions:
                query = query.filter(or_(*conditions))
            else:
                # A search was requested and nothing could possibly match.
                return [], 0

        total = query.count()
        offset = (page - 1) * limit
        models = query.offset(offset).limit(limit).all()
        return [DiarizationMapper.to_domain(m) for m in models], total

    def count_by_step(self) -> dict[str, int]:
        counts = (
            self.session.query(DiarizationModel.step, func.count(DiarizationModel.id))
            .group_by(DiarizationModel.step)
            .all()
        )
        return {step: count for step, count in counts if step}

    def get_steps_by_entity_ids(self, entity_ids: list[str]) -> dict[str, str]:
        if not entity_ids:
            return {}
        records = (
            self.session.query(DiarizationModel.entity_id, DiarizationModel.step)
            .filter(DiarizationModel.entity_id.in_(entity_ids))
            .order_by(DiarizationModel.created_at.desc())
            .all()
        )
        result: dict[str, str] = {}
        for entity_id, step in records:
            if entity_id and entity_id not in result:
                result[entity_id] = step
        return result

    def _find_model(self, task_id: str) -> Optional[DiarizationModel]:
        """Looks a task up by its own id, falling back to the latest task of an entity."""
        model = (
            self.session.query(DiarizationModel)
            .filter(DiarizationModel.id == task_id)
            .first()
        )
        if model:
            return model
        return (
            self.session.query(DiarizationModel)
            .filter(DiarizationModel.entity_id == task_id)
            .order_by(DiarizationModel.created_at.desc())
            .first()
        )

    def reprocess_task(self, task_id: str) -> Optional[DiarizationEntity]:
        model = self._find_model(task_id)
        if not model:
            return None

        model.step = DiarizationStep.PENDING.value
        model.error_message = None
        model.result_json = None
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)

    def cancel_task(self, task_id: str) -> Optional[DiarizationEntity]:
        model = self._find_model(task_id)
        if not model:
            return None

        cancellable = {s.value for s in DiarizationStep.cancellable()}
        if model.step not in cancellable:
            # Returned unchanged so the caller can tell "not found" from "not cancellable".
            return DiarizationMapper.to_domain(model)

        model.step = DiarizationStep.CANCELLED.value
        self.session.flush()
        self.session.refresh(model)
        return DiarizationMapper.to_domain(model)
