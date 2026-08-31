from collections.abc import Iterator

from fastapi import Depends

from src.modules.diarization.application.use_cases.diarization_commands import (
    DiarizationCommands,
)
from src.modules.diarization.application.use_cases.diarization_queries import (
    DiarizationQueries,
)
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.diarization.infrastructure.unit_of_work import DiarizationUnitOfWork
from src.modules.youtube.domain.interfaces.services.youtube_content_service import (
    IYoutubeContentService,
)
from src.modules.youtube.presentation.api.dependencies import (
    get_youtube_content_service,
)


def get_diarization_unit_of_work() -> Iterator[DiarizationUnitOfWork]:
    """Provides one transaction per request.

    The commit sits after the yield, which is only reached when the endpoint returned
    without raising: a failed request leaves the block through `__exit__`, which rolls
    back.
    """
    with DiarizationUnitOfWork() as uow:
        yield uow
        uow.commit()


def get_diarization_repository(
    uow: DiarizationUnitOfWork = Depends(get_diarization_unit_of_work),
) -> IDiarizationRepository:
    return uow.diarizations


def get_diarization_commands(
    repository: IDiarizationRepository = Depends(get_diarization_repository),
) -> DiarizationCommands:
    return DiarizationCommands(repository=repository)


def get_diarization_queries(
    repository: IDiarizationRepository = Depends(get_diarization_repository),
    youtube_contents: IYoutubeContentService = Depends(get_youtube_content_service),
) -> DiarizationQueries:
    # Two units of work take part here, one per module. Both sides of this query are
    # read-only, so they do not need to share a transaction.
    return DiarizationQueries(
        repository=repository, youtube_contents=youtube_contents
    )
