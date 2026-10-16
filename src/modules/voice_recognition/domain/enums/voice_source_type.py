from enum import Enum


class VoiceSourceType(str, Enum):
    """Types of audio sources used to enroll a speaker's voiceprint."""

    DIARIZATION_SEGMENT = "DIARIZATION_SEGMENT"
    AUDIO_UPLOAD = "AUDIO_UPLOAD"
    YOUTUBE_CLIP = "YOUTUBE_CLIP"
