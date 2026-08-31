import enum


class DiarizationStep(str, enum.Enum):
    """Step of a diarization task.

    A separate lifecycle from `ContentStep`: these values used to live inside the
    YouTube enum, which mixed two unrelated state machines and left `CANCELLED` out
    entirely, since no YouTube content is ever cancelled.
    """

    PENDING = "PENDING"
    STARTED = "STARTED"
    TRANSCRIPTION = "TRANSCRIPTION"
    ALIGNMENT = "ALIGNMENT"
    DIARIZATION = "DIARIZATION"
    # Kept because rows written by earlier versions may still carry it, and the list
    # endpoint filters on it.
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"

    @classmethod
    def in_progress(cls) -> tuple["DiarizationStep", ...]:
        """Steps that mean the task is currently being worked on."""
        return (
            cls.STARTED,
            cls.TRANSCRIPTION,
            cls.ALIGNMENT,
            cls.DIARIZATION,
            cls.PROCESSING,
        )

    @classmethod
    def cancellable(cls) -> tuple["DiarizationStep", ...]:
        """Steps from which a task can still be cancelled."""
        return (
            cls.PENDING,
            cls.STARTED,
            cls.TRANSCRIPTION,
            cls.ALIGNMENT,
            cls.DIARIZATION,
        )
