from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends

from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.voice_recognition.application.use_cases import (
    EnrollSpeakerUseCase,
    IdentifyDiarizationSpeakersUseCase,
    ManageSpeakerProfilesUseCase,
)
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)
from src.modules.voice_recognition.infrastructure.services.worker_voice_embedding_service import (
    WorkerVoiceEmbeddingService,
)
from src.modules.voice_recognition.infrastructure.unit_of_work import (
    VoiceRecognitionUnitOfWork,
)


def get_voice_recognition_unit_of_work() -> Iterator[VoiceRecognitionUnitOfWork]:
    """Provides one database transaction per voice recognition request."""
    with VoiceRecognitionUnitOfWork() as uow:
        yield uow
        uow.commit()


def get_speaker_repository(
    uow: VoiceRecognitionUnitOfWork = Depends(get_voice_recognition_unit_of_work),
) -> ISpeakerRepository:
    return uow.speakers


def get_shared_diarization_repository(
    uow: VoiceRecognitionUnitOfWork = Depends(get_voice_recognition_unit_of_work),
) -> IDiarizationRepository:
    return uow.diarizations


@lru_cache(maxsize=1)
def get_voice_embedding_service() -> IVoiceEmbeddingService:
    return WorkerVoiceEmbeddingService()


def get_manage_speaker_profiles_use_case(
    speaker_repository: ISpeakerRepository = Depends(get_speaker_repository),
    voice_embedding_service: IVoiceEmbeddingService = Depends(get_voice_embedding_service),
) -> ManageSpeakerProfilesUseCase:
    return ManageSpeakerProfilesUseCase(
        speaker_repository=speaker_repository,
        voice_embedding_service=voice_embedding_service,
    )


def get_enroll_speaker_use_case(
    speaker_repository: ISpeakerRepository = Depends(get_speaker_repository),
    voice_embedding_service: IVoiceEmbeddingService = Depends(get_voice_embedding_service),
    diarization_repository: IDiarizationRepository = Depends(get_shared_diarization_repository),
) -> EnrollSpeakerUseCase:
    return EnrollSpeakerUseCase(
        speaker_repository=speaker_repository,
        voice_embedding_service=voice_embedding_service,
        diarization_repository=diarization_repository,
    )


def get_identify_speakers_use_case(
    speaker_repository: ISpeakerRepository = Depends(get_speaker_repository),
    voice_embedding_service: IVoiceEmbeddingService = Depends(get_voice_embedding_service),
    diarization_repository: IDiarizationRepository = Depends(get_shared_diarization_repository),
    enroll_use_case: EnrollSpeakerUseCase = Depends(get_enroll_speaker_use_case),
) -> IdentifyDiarizationSpeakersUseCase:
    return IdentifyDiarizationSpeakersUseCase(
        speaker_repository=speaker_repository,
        voice_embedding_service=voice_embedding_service,
        diarization_repository=diarization_repository,
        enroll_use_case=enroll_use_case,
    )
