from enum import Enum


class SampleReviewStatus(str, Enum):
    """Review and curation status of an enrolled voice sample."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
