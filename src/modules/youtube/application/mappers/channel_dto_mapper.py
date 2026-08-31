from src.modules.youtube.application.dtos.channel_create_dto import ChannelCreateDTO
from src.modules.youtube.application.dtos.saved_youtube_channel_response_dto import (
    SavedYouTubeChannelResponseDTO,
)
from src.modules.youtube.application.dtos.youtube_channel_response_dto import (
    YouTubeChannelResponseDTO,
)
from src.modules.youtube.domain.entities.channel_entity import ChannelEntity


class ChannelDtoMapper:
    @staticmethod
    def to_entity(dto: ChannelCreateDTO) -> ChannelEntity:
        return ChannelEntity(external_id=dto.external_id, name=dto.name, url=dto.url)

    @staticmethod
    def to_youtube_response_dto(entity: ChannelEntity) -> YouTubeChannelResponseDTO:
        return YouTubeChannelResponseDTO.model_validate(entity)

    @staticmethod
    def to_saved_youtube_channel_response_dto(model) -> SavedYouTubeChannelResponseDTO:
        return SavedYouTubeChannelResponseDTO.model_validate(model)
