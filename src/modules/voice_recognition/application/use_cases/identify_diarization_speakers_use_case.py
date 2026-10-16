import logging
from collections import defaultdict
from typing import Any

from src.modules.diarization.domain.interfaces.repositories.diarization_repository import (
    IDiarizationRepository,
)
from src.modules.voice_recognition.application.dtos.enroll_speaker_dto import (
    EnrollFromDiarizationDTO,
)
from src.modules.voice_recognition.application.dtos.identify_speakers_dto import (
    AssignSpeakerLabelDTO,
    IdentifyDiarizationResponseDTO,
    IdentifyDiarizationSpeakersRequestDTO,
    SpeakerMatchDTO,
)
from src.modules.voice_recognition.application.use_cases.enroll_speaker_use_case import (
    EnrollSpeakerUseCase,
    apply_speaker_mapping_to_result_json,
)
from src.modules.voice_recognition.domain.interfaces import (
    ISpeakerRepository,
    IVoiceEmbeddingService,
)

logger = logging.getLogger(__name__)


def _calculate_speech_duration(segments: list[dict[str, Any]]) -> float:
    return sum(max(0.0, float(s.get("end", 0.0)) - float(s.get("start", 0.0))) for s in segments)


def _group_segments_by_speaker(
    raw_segments: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    segments_by_original: dict[str, list[dict[str, Any]]] = defaultdict(list)
    current_label_by_original: dict[str, str] = {}
    for seg in raw_segments:
        curr_label = str(seg.get("speaker") or "UNKNOWN")
        orig_label = str(seg.get("original_speaker") or curr_label)
        if orig_label == "UNKNOWN":
            continue
        segments_by_original[orig_label].append(seg)
        current_label_by_original[orig_label] = curr_label
    return dict(segments_by_original), current_label_by_original


class IdentifyDiarizationSpeakersUseCase:
    """Identifies anonymous speakers in a completed diarization task by comparing their
    voice embeddings against enrolled voice samples in pgvector."""

    def __init__(
        self,
        speaker_repository: ISpeakerRepository,
        voice_embedding_service: IVoiceEmbeddingService,
        diarization_repository: IDiarizationRepository,
        enroll_use_case: EnrollSpeakerUseCase,
    ) -> None:
        self.speaker_repository = speaker_repository
        self.voice_embedding_service = voice_embedding_service
        self.diarization_repository = diarization_repository
        self.enroll_use_case = enroll_use_case

    def _get_validated_task(self, diarization_id: str):
        task = self.diarization_repository.get_task(diarization_id)
        if not task:
            raise ValueError(f"Diarization task '{diarization_id}' not found.")

        if not task.result_json or not isinstance(task.result_json, dict):
            raise ValueError(f"Diarization task '{diarization_id}' does not have result_json yet.")
        return task

    def _match_single_speaker(
        self,
        orig_label: str,
        curr_label: str,
        segs: list[dict[str, Any]],
        duration: float,
        vec: list[float] | None,
        similarity_threshold: float,
    ) -> tuple[SpeakerMatchDTO, Any | None, float]:
        if not vec:
            dto = SpeakerMatchDTO(
                original_speaker_label=orig_label,
                current_speaker_label=curr_label,
                segments_count=len(segs),
                speech_duration_seconds=round(duration, 2),
                identified=False,
                applied=False,
            )
            return dto, None, 0.0

        candidates = self.speaker_repository.find_nearest_speaker(
            query_vector=vec,
            top_k=1,
            min_similarity=similarity_threshold,
        )
        if candidates:
            best_sample, best_profile, sim_score = candidates[0]
            dto = SpeakerMatchDTO(
                original_speaker_label=orig_label,
                current_speaker_label=curr_label,
                matched_speaker_id=best_profile.id,
                matched_speaker_name=best_profile.name,
                matched_sample_id=best_sample.id,
                similarity_score=round(sim_score, 4),
                segments_count=len(segs),
                speech_duration_seconds=round(duration, 2),
                identified=True,
                applied=False,
            )
            return dto, best_profile, sim_score

        top_any = self.speaker_repository.find_nearest_speaker(
            query_vector=vec,
            top_k=1,
            min_similarity=0.0,
        )
        best_score = round(top_any[0][2], 4) if top_any else 0.0
        dto = SpeakerMatchDTO(
            original_speaker_label=orig_label,
            current_speaker_label=curr_label,
            similarity_score=best_score,
            segments_count=len(segs),
            speech_duration_seconds=round(duration, 2),
            identified=False,
            applied=False,
        )
        return dto, None, 0.0

    def identify_diarization(
        self,
        diarization_id: str,
        request: IdentifyDiarizationSpeakersRequestDTO,
    ) -> IdentifyDiarizationResponseDTO:
        task = self._get_validated_task(diarization_id)

        raw_segments: list[dict[str, Any]] = task.result_json.get("segments", [])
        if not raw_segments:
            return IdentifyDiarizationResponseDTO(
                diarization_id=task.id or diarization_id,
                entity_id=task.entity_id,
                total_speakers=0,
                identified_count=0,
                auto_applied=False,
                matches=[],
            )

        segments_by_original, current_label_by_original = _group_segments_by_speaker(raw_segments)

        embeddings_by_speaker = self.voice_embedding_service.extract_speakers_embeddings(
            file_path=task.file_path,
            segments_by_speaker=segments_by_original,
        )

        matches: list[SpeakerMatchDTO] = []
        updated_json = dict(task.result_json)
        any_applied = False
        identified_count = 0

        for orig_label, segs in segments_by_original.items():
            curr_label = current_label_by_original.get(orig_label, orig_label)
            duration = _calculate_speech_duration(segs)
            vec = embeddings_by_speaker.get(orig_label)

            match_dto, best_profile, sim_score = self._match_single_speaker(
                orig_label=orig_label,
                curr_label=curr_label,
                segs=segs,
                duration=duration,
                vec=vec,
                similarity_threshold=request.similarity_threshold,
            )

            if match_dto.identified and best_profile:
                identified_count += 1
                if request.auto_apply:
                    updated_json = apply_speaker_mapping_to_result_json(
                        result_json=updated_json,
                        target_label=orig_label,
                        speaker_name=best_profile.name,
                        speaker_id=best_profile.id,
                        similarity_score=sim_score,
                    )
                    match_dto.applied = True
                    match_dto.current_speaker_label = best_profile.name
                    any_applied = True

            matches.append(match_dto)

        if any_applied and task.id:
            self.diarization_repository.update_result_json(task.id, updated_json)

        logger.info(
            "Voice recognition on diarization %s: %d/%d speakers identified (threshold=%.2f)",
            task.id or diarization_id,
            identified_count,
            len(segments_by_original),
            request.similarity_threshold,
        )

        return IdentifyDiarizationResponseDTO(
            diarization_id=task.id or diarization_id,
            entity_id=task.entity_id,
            total_speakers=len(segments_by_original),
            identified_count=identified_count,
            auto_applied=any_applied,
            matches=matches,
        )

    def assign_speaker_in_diarization(
        self,
        diarization_id: str,
        request: AssignSpeakerLabelDTO,
    ) -> dict[str, Any]:
        """Assigns a real speaker name to a speaker cluster in a diarization task,
        and optionally enrolls the speaker's voiceprint into pgvector."""
        if request.enroll_voice:
            enroll_res = self.enroll_use_case.enroll_from_diarization(
                EnrollFromDiarizationDTO(
                    diarization_id=diarization_id,
                    speaker_label=request.speaker_label,
                    speaker_id=request.speaker_id,
                    speaker_name=request.speaker_name,
                    apply_to_diarization=True,
                )
            )
            task = self.diarization_repository.get_task(diarization_id)
            return {
                "diarization_id": diarization_id,
                "speaker_label": request.speaker_label,
                "speaker_id": enroll_res.speaker_id,
                "speaker_name": enroll_res.speaker_name,
                "enrolled": True,
                "sample_id": enroll_res.sample_id,
                "result_json": task.result_json if task else None,
            }

        task = self.diarization_repository.get_task(diarization_id)
        if not task or not task.result_json:
            raise ValueError(f"Diarization task '{diarization_id}' not found or has no transcript.")

        updated_json = apply_speaker_mapping_to_result_json(
            result_json=task.result_json,
            target_label=request.speaker_label,
            speaker_name=request.speaker_name.strip(),
            speaker_id=request.speaker_id,
            similarity_score=1.0,
        )
        updated_task = self.diarization_repository.update_result_json(
            task.id or diarization_id, updated_json
        )
        return {
            "diarization_id": diarization_id,
            "speaker_label": request.speaker_label,
            "speaker_id": request.speaker_id,
            "speaker_name": request.speaker_name.strip(),
            "enrolled": False,
            "sample_id": None,
            "result_json": updated_task.result_json if updated_task else updated_json,
        }
