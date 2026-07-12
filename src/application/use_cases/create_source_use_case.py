from src.application.dtos.source_create_dto import SourceCreateDTO
from src.application.dtos.source_response_dto import SourceResponseDTO
from src.domain.interfaces.logger import ILogger
from src.application.mappers.source_dto_mapper import SourceDtoMapper
from src.domain.interfaces.source_service import ISourceService


class CreateSourceUseCase:
    def __init__(self, source_service: ISourceService, logger: ILogger):
        self.source_service = source_service
        self.logger = logger

    def execute(self, data: SourceCreateDTO) -> SourceResponseDTO:
        self.logger.debug("Iniciando a criação de uma nova fonte de conteúdo.", context={"source_platform": data.source_platform, "source_url": data.url})
        
        # Maps DTO to Entity
        source_entity = SourceDtoMapper.to_entity(data)
        
        # Calls the infrastructure to persist
        try:
            created_source = self.source_service.create_source(source_entity)
            self.logger.debug("Fonte criada com sucesso.", context={"source_id": created_source.id})
        except Exception as e:
            self.logger.error("Erro ao criar fonte.", context={"error": str(e)})
            raise
            
        # Maps the Entity to the response DTO
        return SourceDtoMapper.to_response_dto(created_source)
