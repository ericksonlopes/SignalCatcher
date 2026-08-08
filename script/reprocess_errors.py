import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add the root directory of the project to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.repositories.connector import ConnectorPostgres
from src.infrastructure.repositories.models.youtube_content_model import YoutubeContentModel
from src.infrastructure.repositories.models.step_tracking_model import StepTrackingModel
from src.domain.models.enums.content_step import ContentStep
from sqlalchemy import desc

def map_to_pending_step(step: ContentStep) -> ContentStep:
    """Mapeia um step em processamento de volta para seu estado pendente."""
    if step == ContentStep.EXTRACTING_METADATA:
        return ContentStep.PENDING_METADATA_EXTRACTION
    if step == ContentStep.DOWNLOADING:
        return ContentStep.PENDING_DOWNLOAD
    return step

def main():
    logging.info("Analyzing items in ERROR state to revert to their previous steps...")

    with ConnectorPostgres() as session:
        errored_items = session.query(YoutubeContentModel).filter(
            YoutubeContentModel.step == ContentStep.ERROR
        ).all()

        if not errored_items:
            logging.info("No items in ERROR state found. Nothing to do.")
            return

        logging.info(f"Found {len(errored_items)} items in ERROR state. Analyzing tracking history...")

        for item in errored_items:
            # Pega o último registro de tracking onde ele entrou em ERROR
            last_error_track = session.query(StepTrackingModel).filter(
                StepTrackingModel.entity_id == item.id,
                StepTrackingModel.entity_type == "youtube_contents",
                StepTrackingModel.new_step == ContentStep.ERROR
            ).order_by(desc(StepTrackingModel.changed_at)).first()

            if last_error_track and last_error_track.previous_step:
                # Volta para o step anterior (ou para a fila de pendentes se estava no meio de um processamento)
                step_to_revert = map_to_pending_step(last_error_track.previous_step)
                item.step = step_to_revert
                logging.info(f"Item {item.id} reverted to {step_to_revert.name} (from {last_error_track.previous_step.name})")
            else:
                # Se por acaso não tiver histórico, podemos assumir um fallback ou pular
                logging.warning(f"Item {item.id} tem step ERROR mas não possui histórico de entrada em erro. Mantendo em ERROR.")

        session.commit()
        logging.info("Successfully processed errored items!")

if __name__ == "__main__":
    main()
