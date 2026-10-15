from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.interfaces.repositories.chunk_repository_interface import (
    IChunkRepository,
)
from src.modules.vectorization.infrastructure.repositories.mappers.chunk_mapper import (
    ChunkMapper,
)
from src.modules.vectorization.infrastructure.repositories.models.vector_chunk_model import (
    VectorChunkModel,
)


class ChunkRepository(IChunkRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_chunks(self, chunks: list[VectorChunkEntity]) -> None:
        if not chunks:
            return
        models = [ChunkMapper.to_model(chunk) for chunk in chunks]
        self.session.add_all(models)
        self.session.flush()

    def delete_by_source(self, source_type: str, source_id: str) -> int:
        deleted = (
            self.session.query(VectorChunkModel)
            .filter(
                VectorChunkModel.source_type == source_type,
                VectorChunkModel.source_id == source_id,
            )
            .delete(synchronize_session=False)
        )
        self.session.flush()
        return deleted

    def get_chunks_by_source(
        self, source_type: str, source_id: str
    ) -> list[VectorChunkEntity]:
        models = (
            self.session.query(VectorChunkModel)
            .filter(
                VectorChunkModel.source_type == source_type,
                VectorChunkModel.source_id == source_id,
            )
            .order_by(VectorChunkModel.chunk_index.asc())
            .all()
        )
        return [ChunkMapper.to_entity(m) for m in models]

    def count_indexed_sources(self, source_type: str | None = None) -> int:
        query = self.session.query(func.count(distinct(VectorChunkModel.source_id)))
        if source_type:
            query = query.filter(VectorChunkModel.source_type == source_type)
        count = query.scalar() or 0
        return int(count)

    def count_total_chunks(self, source_type: str | None = None) -> int:
        query = self.session.query(func.count(VectorChunkModel.id))
        if source_type:
            query = query.filter(VectorChunkModel.source_type == source_type)
        count = query.scalar() or 0
        return int(count)

    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        source_type: str | None = None,
        parent_id: str | None = None,
        min_similarity: float = 0.3,
    ) -> list[tuple[VectorChunkEntity, float]]:
        # Cosine distance in pgvector: 0 is identical, 2 is opposite.
        # Cosine similarity = 1 - cosine_distance.
        distance_expr = VectorChunkModel.embedding.cosine_distance(query_vector)
        similarity_expr = 1.0 - distance_expr

        query = self.session.query(VectorChunkModel, similarity_expr)

        if source_type:
            query = query.filter(VectorChunkModel.source_type == source_type)

        if parent_id:
            query = query.filter(VectorChunkModel.parent_id == parent_id)

        if min_similarity > 0.0:
            max_distance = 1.0 - min_similarity
            query = query.filter(distance_expr <= max_distance)

        results = query.order_by(distance_expr.asc()).limit(top_k).all()

        return [
            (ChunkMapper.to_entity(model), float(similarity))
            for model, similarity in results
        ]
