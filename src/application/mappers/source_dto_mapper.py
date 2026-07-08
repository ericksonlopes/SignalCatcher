from src.application.dtos.source_create_dto import SourceCreateDTO
from src.application.dtos.source_response_dto import SourceResponseDTO
from src.domain.models.source_entity import SourceEntity


class SourceDtoMapper:
    @staticmethod
    def to_entity(dto: SourceCreateDTO) -> SourceEntity:
        return SourceEntity(
            name=dto.name,
            url=dto.url,
            source_platform=dto.source_platform
        )

    @staticmethod
    def to_response_dto(entity: SourceEntity) -> SourceResponseDTO:
        return SourceResponseDTO.model_validate(entity)
