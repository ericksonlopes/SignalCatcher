import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.sample_review_status import (
    SampleReviewStatus,
)
from src.modules.voice_recognition.domain.interfaces import ISpeakerRepository
from src.modules.voice_recognition.infrastructure.repositories.mappers.speaker_mapper import (
    SpeakerMapper,
)
from src.modules.voice_recognition.infrastructure.repositories.models.speaker_profile_model import (
    SpeakerProfileModel,
    VoiceSampleModel,
)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if math.isclose(norm_a, 0.0, abs_tol=1e-9) or math.isclose(norm_b, 0.0, abs_tol=1e-9):
        return 0.0
    return dot / (norm_a * norm_b)


def _compute_centroid(embeddings: list[list[float]]) -> list[float] | None:
    valid_vecs = [v for v in embeddings if v]
    if not valid_vecs:
        return None
    dim = len(valid_vecs[0])
    acc = [0.0] * dim
    for vec in valid_vecs:
        for i in range(min(dim, len(vec))):
            acc[i] += vec[i]
    norm = math.sqrt(sum(x * x for x in acc))
    if norm <= 1e-12:
        return None
    return [round(x / norm, 6) for x in acc]


class SpeakerRepository(ISpeakerRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_profile(self, profile: SpeakerProfileEntity) -> SpeakerProfileEntity:
        existing = self.get_profile_by_name(profile.name)
        if existing:
            return existing
        model = SpeakerMapper.profile_to_model(profile)
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return SpeakerMapper.profile_to_entity(model)

    def get_profile(self, speaker_id: str) -> SpeakerProfileEntity | None:
        model = (
            self.session.query(SpeakerProfileModel)
            .filter(SpeakerProfileModel.id == speaker_id)
            .first()
        )
        return SpeakerMapper.profile_to_entity(model) if model else None

    def get_profile_by_name(self, name: str) -> SpeakerProfileEntity | None:
        cleaned = name.strip()
        if not cleaned:
            return None
        model = (
            self.session.query(SpeakerProfileModel)
            .filter(func.lower(SpeakerProfileModel.name) == cleaned.lower())
            .first()
        )
        return SpeakerMapper.profile_to_entity(model) if model else None

    def list_profiles(self, search: str | None = None) -> list[SpeakerProfileEntity]:
        query = self.session.query(SpeakerProfileModel)
        if search and search.strip():
            query = query.filter(SpeakerProfileModel.name.ilike(f"%{search.strip()}%"))
        models = query.order_by(SpeakerProfileModel.name.asc()).all()
        return [SpeakerMapper.profile_to_entity(m) for m in models]

    def update_profile(
        self,
        speaker_id: str,
        name: str | None = None,
        description: str | None = None,
        avatar_url: str | None = None,
    ) -> SpeakerProfileEntity | None:
        model = (
            self.session.query(SpeakerProfileModel)
            .filter(SpeakerProfileModel.id == speaker_id)
            .first()
        )
        if not model:
            return None

        if name is not None and name.strip():
            model.name = name.strip()
        if description is not None:
            model.description = description
        if avatar_url is not None:
            model.avatar_url = avatar_url
        model.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        self.session.flush()
        self.session.refresh(model)
        return SpeakerMapper.profile_to_entity(model)

    def delete_profile(self, speaker_id: str) -> bool:
        model = (
            self.session.query(SpeakerProfileModel)
            .filter(SpeakerProfileModel.id == speaker_id)
            .first()
        )
        if not model:
            return False
        self.session.delete(model)
        self.session.flush()
        return True

    def _update_profile_aggregates(self, speaker_id: str) -> None:
        profile_model = (
            self.session.query(SpeakerProfileModel)
            .filter(SpeakerProfileModel.id == speaker_id)
            .first()
        )
        if not profile_model:
            return

        approved_count = (
            self.session.query(func.count(VoiceSampleModel.id))
            .filter(
                VoiceSampleModel.speaker_id == speaker_id,
                VoiceSampleModel.status == SampleReviewStatus.APPROVED.value,
            )
            .scalar()
            or 0
        )
        pending_count = (
            self.session.query(func.count(VoiceSampleModel.id))
            .filter(
                VoiceSampleModel.speaker_id == speaker_id,
                VoiceSampleModel.status == SampleReviewStatus.PENDING_REVIEW.value,
            )
            .scalar()
            or 0
        )

        profile_model.samples_count = int(approved_count)
        profile_model.pending_count = int(pending_count)

        # Compute centroid of approved samples
        approved_samples = (
            self.session.query(VoiceSampleModel)
            .filter(
                VoiceSampleModel.speaker_id == speaker_id,
                VoiceSampleModel.status == SampleReviewStatus.APPROVED.value,
            )
            .all()
        )
        embeddings = [list(s.embedding) for s in approved_samples if s.embedding is not None]
        profile_model.centroid = _compute_centroid(embeddings)
        profile_model.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def add_sample(self, sample: VoiceSampleEntity) -> VoiceSampleEntity:
        model = SpeakerMapper.sample_to_model(sample)
        self.session.add(model)
        self.session.flush()
        self._update_profile_aggregates(sample.speaker_id)
        self.session.flush()
        self.session.refresh(model)
        return SpeakerMapper.sample_to_entity(model)

    def get_sample(self, sample_id: str) -> VoiceSampleEntity | None:
        model = (
            self.session.query(VoiceSampleModel).filter(VoiceSampleModel.id == sample_id).first()
        )
        return SpeakerMapper.sample_to_entity(model) if model else None

    def list_samples(
        self,
        speaker_id: str | None = None,
        status: SampleReviewStatus | None = None,
    ) -> list[VoiceSampleEntity]:
        query = self.session.query(VoiceSampleModel)
        if speaker_id:
            query = query.filter(VoiceSampleModel.speaker_id == speaker_id)
        if status:
            query = query.filter(VoiceSampleModel.status == status.value)
        models = query.order_by(VoiceSampleModel.created_at.desc()).all()
        return [SpeakerMapper.sample_to_entity(m) for m in models]

    def update_sample(
        self,
        sample: VoiceSampleEntity,
    ) -> VoiceSampleEntity:
        model = (
            self.session.query(VoiceSampleModel).filter(VoiceSampleModel.id == sample.id).first()
        )
        if not model:
            raise ValueError(f"Voice sample '{sample.id}' not found.")

        model.status = sample.status.value
        model.clip_path = sample.clip_path
        model.quality = sample.quality or {}
        model.reviewed_at = sample.reviewed_at
        model.embedding_model = sample.embedding_model
        if sample.start_time is not None:
            model.start_time = sample.start_time
        if sample.end_time is not None:
            model.end_time = sample.end_time
        if sample.duration_seconds is not None:
            model.duration_seconds = sample.duration_seconds
        if sample.metadata:
            model.metadata_ = sample.metadata
        if sample.embedding is not None:
            model.embedding = sample.embedding

        self.session.flush()
        self._update_profile_aggregates(str(model.speaker_id))
        self.session.flush()
        self.session.refresh(model)
        return SpeakerMapper.sample_to_entity(model)

    def delete_sample(self, sample_id: str) -> bool:
        model = (
            self.session.query(VoiceSampleModel).filter(VoiceSampleModel.id == sample_id).first()
        )
        if not model:
            return False
        speaker_id = str(model.speaker_id)
        self.session.delete(model)
        self.session.flush()
        self._update_profile_aggregates(speaker_id)
        self.session.flush()
        return True

    def count_profiles(self) -> int:
        count = self.session.query(func.count(SpeakerProfileModel.id)).scalar() or 0
        return int(count)

    def count_samples(self, status: SampleReviewStatus | None = None) -> int:
        query = self.session.query(func.count(VoiceSampleModel.id))
        if status:
            query = query.filter(VoiceSampleModel.status == status.value)
        count = query.scalar() or 0
        return int(count)

    def recompute_profile_centroid(self, speaker_id: str) -> list[float] | None:
        self._update_profile_aggregates(speaker_id)
        profile = self.get_profile(speaker_id)
        return profile.centroid if profile else None

    def find_nearest_speaker(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_similarity: float = 0.65,
        only_approved: bool = True,
    ) -> list[tuple[VoiceSampleEntity, SpeakerProfileEntity, float]]:
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            distance_expr = VoiceSampleModel.embedding.cosine_distance(query_vector)
            similarity_expr = 1.0 - distance_expr

            query = self.session.query(VoiceSampleModel, SpeakerProfileModel, similarity_expr).join(
                SpeakerProfileModel,
                SpeakerProfileModel.id == VoiceSampleModel.speaker_id,
            )

            if only_approved:
                query = query.filter(VoiceSampleModel.status == SampleReviewStatus.APPROVED.value)

            if min_similarity > 0.0:
                max_distance = 1.0 - min_similarity
                query = query.filter(distance_expr <= max_distance)

            rows = query.order_by(distance_expr.asc()).limit(top_k).all()
            return [
                (
                    SpeakerMapper.sample_to_entity(sample_m),
                    SpeakerMapper.profile_to_entity(profile_m),
                    float(sim),
                )
                for sample_m, profile_m, sim in rows
            ]

        # Fallback for SQLite in unit/integration tests
        query_sqlite = self.session.query(VoiceSampleModel, SpeakerProfileModel).join(
            SpeakerProfileModel,
            SpeakerProfileModel.id == VoiceSampleModel.speaker_id,
        )
        if only_approved:
            query_sqlite = query_sqlite.filter(
                VoiceSampleModel.status == SampleReviewStatus.APPROVED.value
            )

        rows_all = query_sqlite.all()
        scored: list[tuple[VoiceSampleEntity, SpeakerProfileEntity, float]] = []
        for sample_m, profile_m in rows_all:
            sample_entity = SpeakerMapper.sample_to_entity(sample_m)
            if not sample_entity.embedding:
                continue
            sim = _cosine_similarity(query_vector, sample_entity.embedding)
            if sim >= min_similarity:
                scored.append(
                    (
                        sample_entity,
                        SpeakerMapper.profile_to_entity(profile_m),
                        float(sim),
                    )
                )
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:top_k]
