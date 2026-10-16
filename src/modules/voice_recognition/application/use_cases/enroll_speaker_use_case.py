import copy
import logging
import os
import re
import subprocess
import time
from typing import Any

from src.core.config.settings import settings
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
    EnrollFromVideoClipDTO,
    EnrollResponseDTO,
)
from src.modules.voice_recognition.domain.entities.speaker_profile_entity import (
    SpeakerProfileEntity,
)
from src.modules.voice_recognition.domain.entities.voice_sample_entity import (
    VoiceSampleEntity,
)
from src.modules.voice_recognition.domain.enums.voice_source_type import VoiceSourceType
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)
from src.modules.youtube.domain.interfaces.repositories.youtube_content_repository import (
    IYoutubeContentRepository,
)

logger = logging.getLogger(__name__)


def apply_speaker_mapping_to_result_json(
    result_json: dict[str, Any],
    target_label: str,
    speaker_name: str,
    speaker_id: str | None = None,
    similarity_score: float = 1.0,
) -> dict[str, Any]:
    """Replaces `target_label` with `speaker_name` in a diarization `result_json`,
    preserving `original_speaker` and recording `speaker_mappings`."""
    updated = copy.deepcopy(result_json)
    segments = updated.get("segments", [])
    original_key = target_label

    for seg in segments:
        curr_spk = seg.get("speaker", "UNKNOWN")
        orig_spk = seg.get("original_speaker", curr_spk)
        if curr_spk == target_label or orig_spk == target_label:
            seg["original_speaker"] = orig_spk
            seg["speaker"] = speaker_name
            if speaker_id:
                seg["speaker_id"] = speaker_id
            original_key = orig_spk

    # Rebuild speakers list in order of appearance
    seen_speakers: list[str] = []
    for seg in segments:
        spk = seg.get("speaker")
        if spk and spk not in seen_speakers:
            seen_speakers.append(spk)
    updated["speakers"] = seen_speakers

    mappings = dict(updated.get("speaker_mappings") or {})
    mappings[original_key] = {
        "original_speaker": original_key,
        "speaker_id": speaker_id,
        "speaker_name": speaker_name,
        "similarity_score": round(float(similarity_score), 4),
    }
    updated["speaker_mappings"] = mappings
    return updated


def save_clip_to_voice_training(
    file_path: str,
    speaker_name: str,
    start_time: float,
    end_time: float,
    label: str | None = None,
) -> str | None:
    """Exports a clipped .wav audio file to the configured voice training directory."""
    try:
        base_dir = settings.VOICE_TRAINING_PATH
        if not base_dir or not os.path.exists(file_path):
            return None
        safe_name = re.sub(r'[\\/*?:"<>| ]+', "_", speaker_name.strip())
        target_dir = os.path.join(base_dir, safe_name)
        os.makedirs(target_dir, exist_ok=True)
        clip_tag = label or f"clip_{int(start_time)}s_{int(end_time)}s"
        safe_tag = re.sub(r'[\\/*?:"<>| ]+', "_", clip_tag)
        filename = f"{safe_tag}_{int(time.time())}.wav"
        output_file = os.path.join(target_dir, filename)

        ffmpeg_bin = "ffmpeg"
        if settings.FFMPEG_LOCATION:
            candidate = os.path.join(settings.FFMPEG_LOCATION, "ffmpeg")
            if os.path.exists(candidate) or os.path.exists(candidate + ".exe"):
                ffmpeg_bin = candidate

        duration = max(0.1, end_time - start_time)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-nostdin",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            file_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            output_file,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
        if proc.returncode == 0 and os.path.exists(output_file):
            logger.info("Saved voice training clip to %s", output_file)
            return output_file
    except Exception as exc:
        logger.warning(
            "Could not export voice training clip to %s: %s",
            settings.VOICE_TRAINING_PATH,
            exc,
        )
    return None


class EnrollSpeakerUseCase:
    """Enrolls a speaker voiceprint from a completed diarization, a video clip,
    or from an uploaded audio file."""

    def __init__(
        self,
        speaker_repository: ISpeakerRepository,
        voice_embedding_service: IVoiceEmbeddingService,
        diarization_repository: IDiarizationRepository,
        youtube_content_repository: IYoutubeContentRepository | None = None,
    ) -> None:
        self.speaker_repository = speaker_repository
        self.voice_embedding_service = voice_embedding_service
        self.diarization_repository = diarization_repository
        self.youtube_content_repository = youtube_content_repository

    def _resolve_or_create_profile(
        self,
        speaker_id: str | None,
        speaker_name: str | None,
        description: str | None = None,
    ) -> SpeakerProfileEntity:
        if speaker_id:
            profile = self.speaker_repository.get_profile(speaker_id)
            if not profile:
                raise ValueError(f"Speaker profile '{speaker_id}' not found.")
            return profile

        if not speaker_name or not speaker_name.strip():
            raise ValueError("Either speaker_id or speaker_name must be provided.")

        cleaned_name = speaker_name.strip()
        existing = self.speaker_repository.get_profile_by_name(cleaned_name)
        if existing:
            return existing

        return self.speaker_repository.create_profile(
            SpeakerProfileEntity(name=cleaned_name, description=description)
        )

    def _resolve_media_file_path(self, video_id: str) -> tuple[str, str | None]:
        # 1. Check if video_id is a Diarization task ID
        task = self.diarization_repository.get_task(video_id)
        if task and task.file_path:
            return task.file_path, task.entity_id or task.id

        # 2. Check if video_id is a YouTube external ID in content repository
        if self.youtube_content_repository:
            content = self.youtube_content_repository.get_by_external_id(video_id)
            if content and content.file_path:
                return content.file_path, content.external_id

        # 3. Check direct path on disk
        if os.path.exists(video_id):
            return video_id, None

        # 4. Check settings.DOWNLOAD_YOUTUBE_PATH
        if settings.DOWNLOAD_YOUTUBE_PATH:
            candidate = os.path.join(settings.DOWNLOAD_YOUTUBE_PATH, video_id)
            if os.path.exists(candidate):
                return candidate, None

        raise ValueError(f"Media file for video '{video_id}' could not be located on the server.")

    def enroll_from_video_clip(self, request: EnrollFromVideoClipDTO) -> EnrollResponseDTO:
        if request.end_time <= request.start_time:
            raise ValueError("The end time must be greater than the start time.")

        clip_duration = request.end_time - request.start_time
        if clip_duration < 1.0:
            raise ValueError("The speech clip must be at least 1 second long.")

        file_path, entity_id = self._resolve_media_file_path(request.video_id)

        segments = [{"start": request.start_time, "end": request.end_time}]
        embedding = self.voice_embedding_service.extract_embedding_from_segments(
            file_path=file_path,
            segments=segments,
        )

        profile = self._resolve_or_create_profile(
            speaker_id=request.speaker_id,
            speaker_name=request.speaker_name,
            description=request.description,
        )

        label = request.label or f"CLIP_{int(request.start_time)}s_{int(request.end_time)}s"
        saved_clip_path = save_clip_to_voice_training(
            file_path=file_path,
            speaker_name=profile.name,
            start_time=request.start_time,
            end_time=request.end_time,
            label=label,
        )

        sample = VoiceSampleEntity(
            speaker_id=profile.id or "",
            source_type=VoiceSourceType.YOUTUBE_CLIP,
            source_id=entity_id or request.video_id,
            speaker_label=label,
            start_time=round(request.start_time, 2),
            end_time=round(request.end_time, 2),
            duration_seconds=round(clip_duration, 2),
            metadata={
                "clip": True,
                "video_id": request.video_id,
                "entity_id": entity_id,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "training_clip_path": saved_clip_path,
            },
            embedding=embedding,
        )
        saved_sample = self.speaker_repository.add_sample(sample)
        updated_profile = self.speaker_repository.get_profile(profile.id or "") or profile

        logger.info(
            "Enrolled speaker '%s' (id=%s) from video clip %s [%.1fs - %.1fs] (%.1fs)",
            profile.name,
            profile.id,
            request.video_id,
            request.start_time,
            request.end_time,
            clip_duration,
        )

        return EnrollResponseDTO(
            speaker_id=profile.id or "",
            speaker_name=profile.name,
            sample_id=saved_sample.id or "",
            source_type=VoiceSourceType.YOUTUBE_CLIP.value,
            source_id=entity_id or request.video_id,
            speaker_label=label,
            segments_used=1,
            speech_duration_seconds=round(clip_duration, 2),
            applied_to_diarization=False,
            samples_count=updated_profile.samples_count,
        )

    def enroll_from_diarization(self, request: EnrollFromDiarizationDTO) -> EnrollResponseDTO:
        task = self.diarization_repository.get_task(request.diarization_id)
        if not task:
            raise ValueError(f"Diarization task '{request.diarization_id}' not found.")

        if not task.result_json or not isinstance(task.result_json, dict):
            raise ValueError(
                f"Diarization '{request.diarization_id}' has no completed transcript result_json."
            )

        raw_segments = task.result_json.get("segments", [])
        matching_segments = [
            seg
            for seg in raw_segments
            if seg.get("speaker") == request.speaker_label
            or seg.get("original_speaker") == request.speaker_label
        ]

        if not matching_segments:
            raise ValueError(
                f"No segments found for speaker '{request.speaker_label}' "
                f"in diarization '{request.diarization_id}'."
            )

        # Apply specific speech segment selection if requested
        if request.selected_segment_indices is not None and request.selected_segment_indices:
            selected = [
                matching_segments[i]
                for i in request.selected_segment_indices
                if 0 <= i < len(matching_segments)
            ]
            if not selected:
                raise ValueError("None of the selected segment indices were valid.")
            matching_segments = selected

        profile = self._resolve_or_create_profile(
            speaker_id=request.speaker_id,
            speaker_name=request.speaker_name,
            description=request.description,
        )

        if request.start_time is not None and request.end_time is not None:
            if request.end_time <= request.start_time:
                raise ValueError("The end time must be greater than the start time.")
            clip_dur = request.end_time - request.start_time
            if clip_dur < 1.0:
                raise ValueError("The speech clip must be at least 1 second long.")
            matching_segments = [{"start": request.start_time, "end": request.end_time}]
            start_time = request.start_time
            end_time = request.end_time
            speech_duration = clip_dur
        else:
            start_time = min(float(s.get("start", 0.0)) for s in matching_segments)
            end_time = max(float(s.get("end", 0.0)) for s in matching_segments)
            speech_duration = sum(
                max(0.0, float(s.get("end", 0.0)) - float(s.get("start", 0.0)))
                for s in matching_segments
            )

        embedding = self.voice_embedding_service.extract_embedding_from_segments(
            file_path=task.file_path,
            segments=matching_segments,
        )

        saved_clip_path = save_clip_to_voice_training(
            file_path=task.file_path,
            speaker_name=profile.name,
            start_time=start_time,
            end_time=end_time,
            label=request.speaker_label,
        )

        sample = VoiceSampleEntity(
            speaker_id=profile.id or "",
            source_type=VoiceSourceType.DIARIZATION_SEGMENT,
            source_id=task.id,
            speaker_label=request.speaker_label,
            start_time=round(start_time, 3),
            end_time=round(end_time, 3),
            duration_seconds=round(speech_duration, 3),
            metadata={
                "entity_id": task.entity_id,
                "entity_type": task.entity_type,
                "segments_count": len(matching_segments),
                "selected_indices": request.selected_segment_indices,
                "sample_text": " ".join(
                    str(s.get("text", "")).strip() for s in matching_segments[:3]
                )[:240],
                "training_clip_path": saved_clip_path,
                "custom_time_range": request.start_time is not None,
            },
            embedding=embedding,
        )
        saved_sample = self.speaker_repository.add_sample(sample)

        applied = False
        if request.apply_to_diarization and task.id:
            updated_json = apply_speaker_mapping_to_result_json(
                result_json=task.result_json,
                target_label=request.speaker_label,
                speaker_name=profile.name,
                speaker_id=profile.id,
                similarity_score=1.0,
            )
            self.diarization_repository.update_result_json(task.id, updated_json)
            applied = True

        updated_profile = self.speaker_repository.get_profile(profile.id or "") or profile

        logger.info(
            "Enrolled speaker '%s' (id=%s) from diarization %s speaker %s (%d segments, %.1fs)",
            profile.name,
            profile.id,
            task.id,
            request.speaker_label,
            len(matching_segments),
            speech_duration,
        )

        return EnrollResponseDTO(
            speaker_id=profile.id or "",
            speaker_name=profile.name,
            sample_id=saved_sample.id or "",
            source_type=VoiceSourceType.DIARIZATION_SEGMENT.value,
            source_id=task.id,
            speaker_label=request.speaker_label,
            segments_used=len(matching_segments),
            speech_duration_seconds=round(speech_duration, 2),
            applied_to_diarization=applied,
            samples_count=updated_profile.samples_count,
        )

    def enroll_from_upload(
        self,
        audio_bytes: bytes,
        filename: str,
        speaker_id: str | None = None,
        speaker_name: str | None = None,
        description: str | None = None,
    ) -> EnrollResponseDTO:
        profile = self._resolve_or_create_profile(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            description=description,
        )

        embedding = self.voice_embedding_service.extract_embedding_from_bytes(
            audio_bytes=audio_bytes,
            filename=filename,
        )

        sample = VoiceSampleEntity(
            speaker_id=profile.id or "",
            source_type=VoiceSourceType.AUDIO_UPLOAD,
            source_id=filename,
            speaker_label="UPLOAD",
            metadata={"filename": filename, "size_bytes": len(audio_bytes)},
            embedding=embedding,
        )
        saved_sample = self.speaker_repository.add_sample(sample)
        updated_profile = self.speaker_repository.get_profile(profile.id or "") or profile

        return EnrollResponseDTO(
            speaker_id=profile.id or "",
            speaker_name=profile.name,
            sample_id=saved_sample.id or "",
            source_type=VoiceSourceType.AUDIO_UPLOAD.value,
            source_id=filename,
            speaker_label="UPLOAD",
            segments_used=1,
            speech_duration_seconds=0.0,
            applied_to_diarization=False,
            samples_count=updated_profile.samples_count,
        )
