from collections.abc import Callable

from src.core.logger.interfaces import ILogger
from src.modules.youtube.application.use_cases.jobs.content_lease import ContentLease
from src.modules.youtube.domain.enums.content_step import ContentStep
from src.modules.youtube.domain.interfaces.services.content_storage import IContentStorage
from src.modules.youtube.domain.interfaces.unit_of_work import IYoutubeUnitOfWork
from src.modules.youtube.domain.processing import LeaseLostError


class DeleteContentUseCase:
    def __init__(
        self,
        uow_factory: Callable[[], IYoutubeUnitOfWork],
        storage: IContentStorage,
        logger: ILogger,
    ):
        self.uow_factory = uow_factory
        self.storage = storage
        self.logger = logger

    def execute(self) -> bool:
        with self.uow_factory() as uow:
            content = uow.contents.claim_next([], None, deletion=True)
            uow.commit()
        if content is None:
            return False
        with ContentLease(self.uow_factory, content, self.logger) as lease:
            try:
                lease.ensure_owned()
                self.storage.delete_files(content)
                lease.ensure_owned()
                content.step = ContentStep.DELETED
                content.file_path = None
                content.error_info = None
                with self.uow_factory() as uow:
                    uow.contents.update_content(content)
                    uow.commit()
            except LeaseLostError:
                raise
            except Exception as exc:
                lease.ensure_owned()
                content.error_info = f"File deletion failed: {exc}"
                with self.uow_factory() as uow:
                    uow.contents.update_content(content)
                    uow.commit()
                self.logger.error(f"File deletion failed for {content.external_id}: {exc}")
        return True
