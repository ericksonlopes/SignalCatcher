from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.dtos.channel_create_dto import ChannelCreateDTO
from src.modules.youtube.application.dtos.youtube_channel_response_dto import (
    YouTubeChannelResponseDTO,
)
from src.modules.youtube.application.mappers.channel_dto_mapper import ChannelDtoMapper
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import (
    IYouTubeChannelRepository,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import (
    IYouTubeMonitoredChannelRepository,
)
from src.modules.youtube.domain.interfaces.services.channel_service import (
    IChannelService,
)
from src.modules.youtube.domain.interfaces.services.scraper import IYouTubeScraper


class ChannelCommands:
    def __init__(
        self,
        channel_service: IChannelService,
        repository: IYouTubeMonitoredChannelRepository,
        logger: ILogger,
        scraper: IYouTubeScraper | None = None,
        yt_channel_repo: IYouTubeChannelRepository | None = None,
    ):
        self.channel_service = channel_service
        self.repository = repository
        self.logger = logger
        self.scraper = scraper
        self.yt_channel_repo = yt_channel_repo

    def create_channel(self, data: ChannelCreateDTO) -> YouTubeChannelResponseDTO:
        self.logger.debug(
            "Iniciando a criação de um novo canal.", context={"channel_url": data.url}
        )

        # Verify and extract channel info
        if self.scraper and self.yt_channel_repo:
            try:
                channel_info = self.scraper.extract_channel_info(data.url)
                self.yt_channel_repo.upsert_channel(channel_info)

                data.external_id = channel_info.get("id")

                # Auto-fill name if not provided
                if not data.name and channel_info.get("title"):
                    data.name = channel_info.get("title")
            except Exception as e:
                self.logger.error(
                    f"Falha ao extrair informações do canal {data.url}",
                    context={"error": str(e)},
                )
                raise ValueError(f"Não foi possível validar o canal: {str(e)}")

        # Maps DTO to Entity
        channel_entity = ChannelDtoMapper.to_entity(data)

        # Calls the infrastructure to persist
        try:
            created_channel = self.channel_service.create_channel(channel_entity)
            self.logger.debug(
                "Canal criado com sucesso.", context={"channel_id": created_channel.id}
            )
        except Exception as e:
            self.logger.error("Erro ao criar canal.", context={"error": str(e)})
            raise

        # Maps the Entity to the response DTO
        return ChannelDtoMapper.to_youtube_response_dto(created_channel)

    def toggle_channel_status(self, channel_id: int) -> YouTubeChannelResponseDTO:
        self.logger.debug(f"Alternando status do canal {channel_id}.")
        channel_entity = self.repository.get_by_id(channel_id)
        if not channel_entity:
            raise ValueError(f"Canal com ID {channel_id} não encontrado.")

        channel_entity.active = not channel_entity.active
        updated_entity = self.repository.update(channel_entity)
        return ChannelDtoMapper.to_youtube_response_dto(updated_entity)
