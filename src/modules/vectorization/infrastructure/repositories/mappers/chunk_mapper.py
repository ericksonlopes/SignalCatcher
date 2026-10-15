from src.modules.vectorization.domain.entities.vector_chunk_entity import (
    VectorChunkEntity,
)
from src.modules.vectorization.domain.enums.source_type import SourceType
from src.modules.vectorization.infrastructure.repositories.models.vector_chunk_model import (
    VectorChunkModel,
)


class ChunkMapper:
    @staticmethod
    def to_entity(model: VectorChunkModel) -> VectorChunkEntity:
        source_type = SourceType.CUSTOM
        try:
            source_type = SourceType(model.source_type)
        except ValueError:
            source_type = SourceType.CUSTOM

        return VectorChunkEntity(
            id=model.id,
            source_type=source_type,
            source_id=model.source_id,
            parent_id=model.parent_id,
            chunk_index=model.chunk_index,
            text=model.text,
            metadata=model.metadata_ if isinstance(model.metadata_, dict) else {},
            embedding=list(model.embedding) if model.embedding is not None else None,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(entity: VectorChunkEntity) -> VectorChunkModel:
        return VectorChunkModel(
            id=entity.id,
            source_type=entity.source_type.value,
            source_id=entity.source_id,
            parent_id=entity.parent_id,
            chunk_index=entity.chunk_index,
            text=entity.text,
            metadata_=entity.metadata,
            embedding=entity.embedding,
            created_at=entity.created_at,
        )
