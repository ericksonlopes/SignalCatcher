import base64
import os
import subprocess
import tempfile
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.core.config.settings import settings
from src.core.logger.logger import logger
from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
    EnrollFromVideoClipDTO,
    EnrollResponseDTO,
)
from src.modules.voice_recognition.application.dtos.identify_speakers_dto import (
    AssignSpeakerLabelDTO,
    IdentifyDiarizationResponseDTO,
    IdentifyDiarizationSpeakersRequestDTO,
)
from src.modules.voice_recognition.application.dtos.speaker_profile_dto import (
    BulkReviewSamplesRequestDTO,
    CreateSpeakerProfileDTO,
    ReviewSampleRequestDTO,
    SpeakerProfileResponseDTO,
    SuggestedClipDTO,
    UpdateSpeakerProfileDTO,
    VoiceRecognitionStatsDTO,
    VoiceSampleResponseDTO,
)
from src.modules.voice_recognition.application.use_cases import (
    EnrollSpeakerUseCase,
    IdentifyDiarizationSpeakersUseCase,
    ManageSpeakerProfilesUseCase,
)
from src.modules.voice_recognition.presentation.api.dependencies import (
    get_enroll_speaker_use_case,
    get_identify_speakers_use_case,
    get_manage_speaker_profiles_use_case,
    get_shared_diarization_repository,
)

router = APIRouter(tags=["Voice Recognition"])


class EnrollAudioBase64RequestDTO(BaseModel):
    audio_base64: str = Field(..., min_length=4, description="Base64-encoded audio file content")
    filename: str = Field(default="sample.wav")
    speaker_id: str | None = None
    speaker_name: str | None = None
    description: str | None = None


@router.get(
    "/stats",
    summary="Get voice recognition and pgvector speaker stats",
)
def get_voice_recognition_stats(
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> VoiceRecognitionStatsDTO:
    return use_case.get_stats()


@router.get(
    "/profiles",
    summary="List enrolled speaker profiles",
)
def list_speaker_profiles(
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
    search: Annotated[str | None, Query(description="Filter by speaker name")] = None,
    include_samples: Annotated[bool, Query(description="Include enrolled voice samples")] = False,
) -> list[SpeakerProfileResponseDTO]:
    return use_case.list_profiles(search=search, include_samples=include_samples)


@router.post(
    "/profiles",
    summary="Create a new speaker profile",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid profile name or data"},
    },
)
def create_speaker_profile(
    request: CreateSpeakerProfileDTO,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> SpeakerProfileResponseDTO:
    try:
        return use_case.create_profile(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/profiles/{speaker_id}",
    summary="Get speaker profile details by ID",
    responses={
        404: {"description": "Speaker profile not found"},
    },
)
def get_speaker_profile(
    speaker_id: str,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> SpeakerProfileResponseDTO:
    try:
        return use_case.get_profile(speaker_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/profiles/{speaker_id}",
    summary="Update speaker profile metadata",
    responses={
        404: {"description": "Speaker profile not found"},
    },
)
def update_speaker_profile(
    speaker_id: str,
    request: UpdateSpeakerProfileDTO,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> SpeakerProfileResponseDTO:
    try:
        return use_case.update_profile(speaker_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/profiles/{speaker_id}",
    summary="Delete a speaker profile and cascade delete its samples",
    responses={
        404: {"description": "Speaker profile not found"},
    },
)
def delete_speaker_profile(
    speaker_id: str,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> dict[str, Any]:
    try:
        use_case.delete_profile(speaker_id)
        return {"deleted": True, "speaker_id": speaker_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# =========================================================================
# SAMPLE REVIEW & AUDIO CURATION ENDPOINTS
# =========================================================================


@router.get(
    "/samples/review-queue",
    summary="List sample candidates for curation and review",
)
def list_review_queue(
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
    speaker_id: Annotated[str | None, Query(description="Filter by speaker profile ID")] = None,
    status: Annotated[
        str, Query(description="Status filter: PENDING_REVIEW, APPROVED, REJECTED")
    ] = "PENDING_REVIEW",
) -> list[VoiceSampleResponseDTO]:
    return use_case.list_review_queue(speaker_id=speaker_id, status_filter=status)


@router.patch(
    "/samples/{sample_id}/review",
    summary="Approve, reject, or adjust crop for a voice sample candidate",
)
def review_sample(
    sample_id: str,
    request: ReviewSampleRequestDTO,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> VoiceSampleResponseDTO:
    try:
        return use_case.review_sample(sample_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/samples/review/bulk",
    summary="Bulk approve or reject voice sample candidates",
)
def bulk_review_samples(
    request: BulkReviewSamplesRequestDTO,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> dict[str, Any]:
    return use_case.bulk_review_samples(request)


@router.get(
    "/samples/{sample_id}/audio",
    summary="Stream or download the WAV audio clip of an enrolled voice sample",
)
def get_sample_audio(
    sample_id: str,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
):
    try:
        file_path = use_case.get_sample_audio_file(sample_id)
        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename=os.path.basename(file_path),
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/preview",
    summary="Listen to an on-demand audio preview clip before enrolling",
)
def preview_audio_clip(
    diarization_id: Annotated[str, Query(description="Diarization task ID")],
    start: Annotated[float, Query(ge=0.0, description="Start time in seconds")],
    end: Annotated[float, Query(gt=0.0, description="End time in seconds")],
    diarization_repo: Annotated[IDiarizationRepository, Depends(get_shared_diarization_repository)],
):
    if end <= start:
        raise HTTPException(status_code=400, detail="End time must be greater than start time.")
    duration = min(end - start, 60.0)  # capped at 60s

    task = diarization_repo.get_task(diarization_id)
    if not task or not task.file_path or not os.path.exists(task.file_path):
        raise HTTPException(status_code=404, detail="Diarization media file not found.")

    ffmpeg_bin = "ffmpeg"
    if settings.FFMPEG_LOCATION:
        candidate = os.path.join(settings.FFMPEG_LOCATION, "ffmpeg")
        if os.path.exists(candidate) or os.path.exists(candidate + ".exe"):
            ffmpeg_bin = candidate

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-nostdin",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        task.file_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        tmp_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=20, check=False)
    if proc.returncode != 0 or not os.path.exists(tmp_path):
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail="Failed to generate audio preview.")

    return FileResponse(
        path=tmp_path,
        media_type="audio/wav",
        filename=f"preview_{int(start)}s_{int(end)}s.wav",
        background=None,
    )


@router.get(
    "/diarization/{diarization_id}/speakers/{speaker_label}/suggested-clips",
    summary="Rank and return best speech turns of a speaker in a diarization for voice training",
)
def get_suggested_speaker_clips(
    diarization_id: str,
    speaker_label: str,
    diarization_repo: Annotated[IDiarizationRepository, Depends(get_shared_diarization_repository)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[SuggestedClipDTO]:
    task = diarization_repo.get_task(diarization_id)
    if not task or not task.result_json:
        raise HTTPException(status_code=404, detail="Diarization transcript not found.")

    raw_segments: list[dict[str, Any]] = task.result_json.get("segments", [])
    if not raw_segments:
        return []

    # Filter speaker turns
    speaker_segs = [
        s
        for s in raw_segments
        if s.get("speaker") == speaker_label or s.get("original_speaker") == speaker_label
    ]

    # Rank segments: prefer 5s-25s duration, clean text length
    candidates: list[SuggestedClipDTO] = []
    for s in speaker_segs:
        st = float(s.get("start", 0.0))
        en = float(s.get("end", 0.0))
        dur = en - st
        if dur < 1.0:
            continue
        text = str(s.get("text", "")).strip()

        # Check overlap with adjacent segments from other speakers
        has_overlap = False
        for other in raw_segments:
            other_spk = other.get("speaker") or other.get("original_speaker")
            if other_spk == speaker_label:
                continue
            o_st = float(other.get("start", 0.0))
            o_en = float(other.get("end", 0.0))
            if max(st, o_st) < min(en, o_en) - 0.15:
                has_overlap = True
                break

        # Quality scoring heuristic
        score = 1.0
        quality_hint = "good"
        if 8.0 <= dur <= 30.0:
            score += 2.0
        elif 4.0 <= dur < 8.0:
            score += 1.0
        else:
            quality_hint = "short"

        if has_overlap:
            score -= 1.5
            quality_hint = "overlap"

        candidates.append(
            SuggestedClipDTO(
                start=round(st, 3),
                end=round(en, 3),
                duration=round(dur, 2),
                text=text,
                energy_score=round(max(score, 0.1), 2),
                has_overlap=has_overlap,
                quality_hint=quality_hint,
            )
        )

    candidates.sort(key=lambda c: (not c.has_overlap, c.energy_score, c.duration), reverse=True)
    return candidates[:limit]


@router.delete(
    "/samples/{sample_id}",
    summary="Delete a single enrolled voice sample",
    responses={
        404: {"description": "Voice sample not found"},
    },
)
def delete_voice_sample(
    sample_id: str,
    use_case: Annotated[
        ManageSpeakerProfilesUseCase, Depends(get_manage_speaker_profiles_use_case)
    ],
) -> dict[str, Any]:
    try:
        use_case.delete_sample(sample_id)
        return {"deleted": True, "sample_id": sample_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/enroll/from-diarization",
    summary="Enroll a speaker voiceprint from a completed diarization's speaker turns",
    responses={
        400: {"description": "Invalid enrollment request"},
        500: {"description": "Internal server error"},
    },
)
def enroll_from_diarization(
    request: EnrollFromDiarizationDTO,
    use_case: Annotated[EnrollSpeakerUseCase, Depends(get_enroll_speaker_use_case)],
) -> EnrollResponseDTO:
    try:
        return use_case.enroll_from_diarization(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to enroll speaker from diarization: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/enroll/video-clip",
    summary="Enroll a speaker voiceprint from a specific video time range (start/end clip)",
    responses={
        400: {"description": "Invalid clip range or missing video media"},
        500: {"description": "Internal server error"},
    },
)
def enroll_from_video_clip(
    request: EnrollFromVideoClipDTO,
    use_case: Annotated[EnrollSpeakerUseCase, Depends(get_enroll_speaker_use_case)],
) -> EnrollResponseDTO:
    try:
        return use_case.enroll_from_video_clip(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to enroll speaker from video clip: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/enroll/audio",
    summary="Enroll a speaker voiceprint from base64-encoded audio sample",
    responses={
        400: {"description": "Invalid audio data or enrollment request"},
        500: {"description": "Internal server error"},
    },
)
def enroll_from_audio_base64(
    request: EnrollAudioBase64RequestDTO,
    use_case: Annotated[EnrollSpeakerUseCase, Depends(get_enroll_speaker_use_case)],
) -> EnrollResponseDTO:
    try:
        raw_b64 = request.audio_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        audio_bytes = base64.b64decode(raw_b64)
        return use_case.enroll_from_upload(
            audio_bytes=audio_bytes,
            filename=request.filename,
            speaker_id=request.speaker_id,
            speaker_name=request.speaker_name,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to enroll speaker from audio: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/diarization/{diarization_id}/identify",
    summary="Identify speakers in a completed diarization using pgvector voice similarity",
    responses={
        404: {"description": "Diarization task not found or has no transcript"},
        500: {"description": "Internal server error"},
    },
)
def identify_diarization_speakers(
    diarization_id: str,
    use_case: Annotated[
        IdentifyDiarizationSpeakersUseCase, Depends(get_identify_speakers_use_case)
    ],
    request: Annotated[IdentifyDiarizationSpeakersRequestDTO | None, Body()] = None,
) -> IdentifyDiarizationResponseDTO:
    req = request or IdentifyDiarizationSpeakersRequestDTO()
    try:
        return use_case.identify_diarization(diarization_id, req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to identify speakers in diarization {diarization_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/diarization/{diarization_id}/assign",
    summary="Assign a real speaker name to a speaker cluster in a diarization",
    responses={
        400: {"description": "Invalid speaker assignment or diarization not found"},
        500: {"description": "Internal server error"},
    },
)
def assign_speaker_in_diarization(
    diarization_id: str,
    request: AssignSpeakerLabelDTO,
    use_case: Annotated[
        IdentifyDiarizationSpeakersUseCase, Depends(get_identify_speakers_use_case)
    ],
) -> dict[str, Any]:
    try:
        return use_case.assign_speaker_in_diarization(diarization_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to assign speaker in diarization {diarization_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/diarization/{diarization_id}/reset",
    summary="Reset and restore original anonymous speakers in a diarization",
    responses={
        400: {"description": "Diarization task not found"},
        500: {"description": "Internal server error"},
    },
)
def reset_diarization_speakers(
    diarization_id: str,
    use_case: Annotated[
        IdentifyDiarizationSpeakersUseCase, Depends(get_identify_speakers_use_case)
    ],
) -> dict[str, Any]:
    try:
        return use_case.reset_diarization_speakers(diarization_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to reset speakers in diarization {diarization_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
