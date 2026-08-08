from src.application.dtos.channel_create_dto import ChannelCreateDTO
from src.application.dtos.youtube_channel_response_dto import YouTubeChannelResponseDTO
from src.application.mappers.channel_dto_mapper import ChannelDtoMapper
from src.domain.interfaces.logger import ILogger
from src.domain.interfaces.channel_service import IChannelService
from src.domain.interfaces.youtube_monitored_channel_repository import IYouTubeMonitoredChannelRepository


class ChannelsUseCase:
    def __init__(self, channel_service: IChannelService, repository: IYouTubeMonitoredChannelRepository, logger: ILogger):
        self.channel_service = channel_service
        self.repository = repository
        self.logger = logger

    def create_channel(self, data: ChannelCreateDTO) -> YouTubeChannelResponseDTO:
        self.logger.debug("Iniciando a criação de um novo canal.", context={"channel_url": data.url})
        
        # Maps DTO to Entity
        channel_entity = ChannelDtoMapper.to_entity(data)
        
        # Calls the infrastructure to persist
        try:
            created_channel = self.channel_service.create_channel(channel_entity)
            self.logger.debug("Canal criado com sucesso.", context={"channel_id": created_channel.id})
        except Exception as e:
            self.logger.error("Erro ao criar canal.", context={"error": str(e)})
            raise
            
        # Maps the Entity to the response DTO
        return ChannelDtoMapper.to_youtube_response_dto(created_channel)

    def get_all_channels(self) -> list[YouTubeChannelResponseDTO]:
        self.logger.debug("Iniciando a busca de todos os canais.")
        try:
            channels = self.repository.get_all()
            return [ChannelDtoMapper.to_youtube_response_dto(s) for s in channels]
        except Exception as e:
            self.logger.error("Erro ao buscar canais.", context={"error": str(e)})
            raise

    def toggle_channel_status(self, channel_id: int) -> YouTubeChannelResponseDTO:
        self.logger.debug(f"Alternando status do canal {channel_id}.")
        channel_entity = self.repository.get_by_id(channel_id)
        if not channel_entity:
            raise ValueError(f"Canal com ID {channel_id} não encontrado.")
        
        channel_entity.active = not channel_entity.active
        updated_entity = self.repository.update(channel_entity)
        return ChannelDtoMapper.to_youtube_response_dto(updated_entity)
