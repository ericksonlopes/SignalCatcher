import base64
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.core.logger.logger import logger
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
    EnrollResponseDTO,
)
from src.modules.voice_recognition.application.dtos.identify_speakers_dto import (
    AssignSpeakerLabelDTO,
    IdentifyDiarizationResponseDTO,
    IdentifyDiarizationSpeakersRequestDTO,
)
from src.modules.voice_recognition.application.dtos.speaker_profile_dto import (
    CreateSpeakerProfileDTO,
    SpeakerProfileResponseDTO,
    UpdateSpeakerProfileDTO,
    VoiceRecognitionStatsDTO,
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
)

router = APIRouter(tags=["Voice Recognition"])


class EnrollAudioBase64RequestDTO(BaseModel):
    audio_base64: str = Field(
        ..., min_length=4, description="Base64-encoded audio file content"
    )
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
    include_samples: Annotated[
        bool, Query(description="Include enrolled voice samples")
    ] = False,
) -> list[SpeakerProfileResponseDTO]:
    return use_case.list_profiles(search=search, include_samples=include_samples)


@router.post(
    "/profiles",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new speaker profile",
    responses={
        400: {"description": "Invalid speaker profile data"},
        500: {"description": "Internal server error"},
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
    except Exception as exc:
        logger.error(f"Failed to create speaker profile: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/profiles/{speaker_id}",
    summary="Get speaker profile details and voice samples",
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
    summary="Update a speaker profile",
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
    summary="Delete a speaker profile and all of its voice samples",
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
        logger.error(
            f"Failed to identify speakers in diarization {diarization_id}: {exc}"
        )
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
