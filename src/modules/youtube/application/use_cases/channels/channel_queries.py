from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.dtos.saved_youtube_channel_response_dto import SavedYouTubeChannelResponseDTO
from src.modules.youtube.application.dtos.youtube_channel_response_dto import YouTubeChannelResponseDTO
from src.modules.youtube.application.mappers.channel_dto_mapper import ChannelDtoMapper
from src.modules.youtube.domain.interfaces.repositories.youtube_channel_repository import IYouTubeChannelRepository
from src.modules.youtube.domain.interfaces.repositories.youtube_monitored_channel_repository import IYouTubeMonitoredChannelRepository

class ChannelQueries:
    def __init__(
        self,
        repository: IYouTubeMonitoredChannelRepository,
        logger: ILogger,
        yt_channel_repo: IYouTubeChannelRepository | None = None,
    ):
        self.repository = repository
        self.logger = logger
        self.yt_channel_repo = yt_channel_repo

    def get_all_channels(self) -> list[YouTubeChannelResponseDTO]:
        self.logger.debug("Iniciando a busca de todos os canais.")
        try:
            channels = self.repository.get_all()
            return [ChannelDtoMapper.to_youtube_response_dto(s) for s in channels]
        except Exception as e:
            self.logger.error("Erro ao buscar canais.", context={"error": str(e)})
            raise

    def get_saved_channels(self) -> list[SavedYouTubeChannelResponseDTO]:
        self.logger.debug("Iniciando a busca de todos os canais salvos (youtube_channels).")
        try:
            if not self.yt_channel_repo:
                raise ValueError("YouTube Channel Repository não configurado.")
            saved_channels = self.yt_channel_repo.get_all()
            return [ChannelDtoMapper.to_saved_youtube_channel_response_dto(s) for s in saved_channels]
        except Exception as e:
            self.logger.error("Erro ao buscar canais salvos.", context={"error": str(e)})
            raise
