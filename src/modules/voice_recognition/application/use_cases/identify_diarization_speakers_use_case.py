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

    def _collect_candidate_pairs(
        self,
        embeddings_by_speaker: dict[str, list[float]],
        similarity_threshold: float,
    ) -> tuple[dict[str, list[tuple[Any, Any, float]]], list[tuple[float, str, Any, Any]]]:
        candidates_by_speaker: dict[str, list[tuple[Any, Any, float]]] = {}
        candidate_pairs: list[tuple[float, str, Any, Any]] = []

        for orig_label, vec in embeddings_by_speaker.items():
            if not vec:
                candidates_by_speaker[orig_label] = []
                continue

            candidates = self.speaker_repository.find_nearest_speaker(
                query_vector=vec,
                top_k=5,
                min_similarity=0.0,
            )
            candidates_by_speaker[orig_label] = candidates
            for sample_m, profile_m, score in candidates:
                if score >= similarity_threshold:
                    candidate_pairs.append((float(score), orig_label, profile_m, sample_m))

        return candidates_by_speaker, candidate_pairs

    @staticmethod
    def _resolve_exclusive_assignments(
        candidate_pairs: list[tuple[float, str, Any, Any]],
    ) -> dict[str, tuple[Any, Any, float]]:
        candidate_pairs.sort(key=lambda item: item[0], reverse=True)
        assigned_speakers: dict[str, tuple[Any, Any, float]] = {}
        used_profile_ids: set[str] = set()

        for score, orig_label, profile_m, sample_m in candidate_pairs:
            if orig_label in assigned_speakers or profile_m.id in used_profile_ids:
                continue
            assigned_speakers[orig_label] = (profile_m, sample_m, score)
            used_profile_ids.add(profile_m.id)

        return assigned_speakers

    @staticmethod
    def _create_identified_match(
        orig_label: str,
        curr_label: str,
        segs: list[dict[str, Any]],
        assigned_info: tuple[Any, Any, float],
        auto_apply: bool,
        current_json: dict[str, Any],
    ) -> tuple[SpeakerMatchDTO, dict[str, Any]]:
        best_profile, best_sample, sim_score = assigned_info
        duration = _calculate_speech_duration(segs)

        match_dto = SpeakerMatchDTO(
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

        updated_json = current_json
        if auto_apply:
            updated_json = apply_speaker_mapping_to_result_json(
                result_json=current_json,
                target_label=orig_label,
                speaker_name=best_profile.name,
                speaker_id=best_profile.id,
                similarity_score=sim_score,
            )
            match_dto.applied = True
            match_dto.current_speaker_label = best_profile.name

        return match_dto, updated_json

    @staticmethod
    def _create_unidentified_match(
        orig_label: str,
        curr_label: str,
        segs: list[dict[str, Any]],
        candidates: list[tuple[Any, Any, float]] | None,
    ) -> SpeakerMatchDTO:
        duration = _calculate_speech_duration(segs)
        nearest_sample = candidates[0][0] if candidates else None
        nearest_profile = candidates[0][1] if candidates else None
        best_score = round(candidates[0][2], 4) if candidates else 0.0

        return SpeakerMatchDTO(
            original_speaker_label=orig_label,
            current_speaker_label=curr_label,
            matched_speaker_id=nearest_profile.id if nearest_profile else None,
            matched_speaker_name=nearest_profile.name if nearest_profile else None,
            matched_sample_id=nearest_sample.id if nearest_sample else None,
            similarity_score=best_score,
            segments_count=len(segs),
            speech_duration_seconds=round(duration, 2),
            identified=False,
            applied=False,
        )

    def _process_speaker_matches(
        self,
        segments_by_original: dict[str, list[dict[str, Any]]],
        current_label_by_original: dict[str, str],
        assigned_speakers: dict[str, tuple[Any, Any, float]],
        candidates_by_speaker: dict[str, list[tuple[Any, Any, float]]],
        auto_apply: bool,
        initial_json: dict[str, Any],
    ) -> tuple[list[SpeakerMatchDTO], dict[str, Any], int]:
        matches: list[SpeakerMatchDTO] = []
        updated_json = dict(initial_json)
        identified_count = 0

        for orig_label, segs in segments_by_original.items():
            curr_label = current_label_by_original.get(orig_label, orig_label)
            if orig_label in assigned_speakers:
                match_dto, updated_json = self._create_identified_match(
                    orig_label=orig_label,
                    curr_label=curr_label,
                    segs=segs,
                    assigned_info=assigned_speakers[orig_label],
                    auto_apply=auto_apply,
                    current_json=updated_json,
                )
                identified_count += 1
            else:
                match_dto = self._create_unidentified_match(
                    orig_label=orig_label,
                    curr_label=curr_label,
                    segs=segs,
                    candidates=candidates_by_speaker.get(orig_label),
                )
            matches.append(match_dto)

        return matches, updated_json, identified_count

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

        segments_by_orig, current_labels = _group_segments_by_speaker(raw_segments)
        embeddings = self.voice_embedding_service.extract_speakers_embeddings(
            file_path=task.file_path,
            segments_by_speaker=segments_by_orig,
        )

        candidates_map, pairs = self._collect_candidate_pairs(
            embeddings, request.similarity_threshold
        )
        assigned_speakers = self._resolve_exclusive_assignments(pairs)

        matches, updated_json, identified_count = self._process_speaker_matches(
            segments_by_original=segments_by_orig,
            current_label_by_original=current_labels,
            assigned_speakers=assigned_speakers,
            candidates_by_speaker=candidates_map,
            auto_apply=request.auto_apply,
            initial_json=task.result_json,
        )

        any_applied = request.auto_apply and identified_count > 0
        if any_applied and task.id:
            self.diarization_repository.update_result_json(task.id, updated_json)

        logger.info(
            "Voice recognition on diarization %s: %d/%d identified (threshold=%.2f, 1-to-1)",
            task.id or diarization_id,
            identified_count,
            len(segments_by_orig),
            request.similarity_threshold,
        )

        return IdentifyDiarizationResponseDTO(
            diarization_id=task.id or diarization_id,
            entity_id=task.entity_id,
            total_speakers=len(segments_by_orig),
            identified_count=identified_count,
            auto_applied=any_applied,
            matches=matches,
        )

    def reset_diarization_speakers(self, diarization_id: str) -> dict[str, Any]:
        """Restores original anonymous speaker labels (SPEAKER_00, SPEAKER_01...) in result_json,
        clearing collapsed mappings and unifications."""
        task = self._get_validated_task(diarization_id)
        raw_segments: list[dict[str, Any]] = task.result_json.get("segments", [])
        if not raw_segments:
            return {"restored": False, "diarization_id": diarization_id}

        import copy

        updated = copy.deepcopy(task.result_json)
        segments = updated.get("segments", [])
        seen_speakers: list[str] = []
        for seg in segments:
            orig = seg.get("original_speaker")
            if orig:
                seg["speaker"] = orig
                seg.pop("speaker_id", None)
            curr = seg.get("speaker")
            if curr and curr not in seen_speakers:
                seen_speakers.append(curr)

        updated["speakers"] = seen_speakers
        updated["speaker_mappings"] = {}
        if task.id:
            self.diarization_repository.update_result_json(task.id, updated)
        return {
            "restored": True,
            "diarization_id": diarization_id,
            "speakers": seen_speakers,
            "total_segments": len(segments),
            "result_json": updated,
        }

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
