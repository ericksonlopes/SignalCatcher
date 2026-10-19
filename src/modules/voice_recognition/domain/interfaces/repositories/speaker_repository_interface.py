from abc import ABC, abstractmethod

from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.sample_review_status import (
    SampleReviewStatus,
)


class ISpeakerRepository(ABC):
    @abstractmethod
    def create_profile(self, profile: SpeakerProfileEntity) -> SpeakerProfileEntity:
        """Persists a new speaker profile."""
        pass

    @abstractmethod
    def get_profile(self, speaker_id: str) -> SpeakerProfileEntity | None:
        """Returns a speaker profile by its ID."""
        pass

    @abstractmethod
    def get_profile_by_name(self, name: str) -> SpeakerProfileEntity | None:
        """Returns a speaker profile by its case-insensitive name."""
        pass

    @abstractmethod
    def list_profiles(self, search: str | None = None) -> list[SpeakerProfileEntity]:
        """Lists all speaker profiles, optionally filtered by name."""
        pass

    @abstractmethod
    def update_profile(
        self,
        speaker_id: str,
        name: str | None = None,
        description: str | None = None,
        avatar_url: str | None = None,
    ) -> SpeakerProfileEntity | None:
        """Updates a speaker profile's metadata."""
        pass

    @abstractmethod
    def delete_profile(self, speaker_id: str) -> bool:
        """Deletes a speaker profile and all of its associated voice samples."""
        pass

    @abstractmethod
    def add_sample(self, sample: VoiceSampleEntity) -> VoiceSampleEntity:
        """Persists a voiceprint sample and updates profile sample counters and centroid."""
        pass

    @abstractmethod
    def get_sample(self, sample_id: str) -> VoiceSampleEntity | None:
        """Returns a specific voice sample by its ID."""
        pass

    @abstractmethod
    def list_samples(
        self,
        speaker_id: str | None = None,
        status: SampleReviewStatus | None = None,
    ) -> list[VoiceSampleEntity]:
        """Lists voiceprint samples, optionally filtered by speaker_id and/or status."""
        pass

    @abstractmethod
    def update_sample(
        self,
        sample: VoiceSampleEntity,
    ) -> VoiceSampleEntity:
        """Updates sample fields (e.g. status, quality, clip_path, embedding)."""
        pass

    @abstractmethod
    def delete_sample(self, sample_id: str) -> bool:
        """Deletes a specific voice sample and updates profile counters and centroid."""
        pass

    @abstractmethod
    def count_profiles(self) -> int:
        """Counts total registered speaker profiles."""
        pass

    @abstractmethod
    def count_samples(self, status: SampleReviewStatus | None = None) -> int:
        """Counts registered voice samples, optionally filtered by status."""
        pass

    @abstractmethod
    def recompute_profile_centroid(self, speaker_id: str) -> list[float] | None:
        """Recomputes and saves the L2-normalized centroid of all APPROVED samples of a profile."""
        pass

    @abstractmethod
    def find_nearest_speaker(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_similarity: float = 0.65,
        only_approved: bool = True,
    ) -> list[tuple[VoiceSampleEntity, SpeakerProfileEntity, float]]:
        """Searches voice samples nearest to query_vector using cosine similarity."""
        pass
