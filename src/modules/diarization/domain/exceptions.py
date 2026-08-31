class DiarizationError(Exception):
    """Base class for errors raised by the diarization module."""


class DiarizationApiError(DiarizationError):
    """Raised when communication with the external diarization API fails."""
