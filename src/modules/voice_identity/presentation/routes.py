"""Media reads are side-effect free; only explicit POST requests enqueue work."""

import json
import subprocess
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DatabaseSession

from src.core.config.settings import settings
from src.core.database.connector import Session
from src.modules.diarization.infrastructure.repositories.models.diarization_model import (
    DiarizationModel,
)
from src.modules.voice_identity.domain.selection import (
    selection_key,
    transcript_version,
    validate_selection,
)
from src.modules.voice_identity.infrastructure.repositories.models.voice_assignment_model import (
    VoiceAssignment,
)
from src.modules.voice_identity.infrastructure.repositories.models.voice_job_model import VoiceJob
from src.modules.voice_identity.infrastructure.repositories.models.voice_person_model import (
    VoicePerson,
)
from src.modules.voice_identity.infrastructure.repositories.models.voice_sample_model import (
    VoiceSample,
)

router = APIRouter()
PERSON_NOT_FOUND = "Person not found"
DIARIZATION_NOT_COMPLETED = "Diarization must be completed"


def database():
    with Session() as session, session.begin():
        yield session


DB = Annotated[DatabaseSession, Depends(database)]


def task(session, task_id):
    value = session.get(DiarizationModel, task_id)
    if value is None:
        raise HTTPException(404, "Diarization not found")
    return value


def media_path(relative, root):
    base = Path(root).resolve()
    path = (base / str(relative).lstrip("/\\")).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404, "Media unavailable")
    return path


def job_data(job):
    return {
        key: getattr(job, key)
        for key in ("id", "kind", "task_id", "state", "payload", "result", "error")
    }


class PersonRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TrainingRequest(BaseModel):
    person_id: str
    task_id: str
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    speaker: str | None = None


class AssignmentRequest(BaseModel):
    person_id: str | None = None


@router.get("/voices/people")
def people(db: DB):
    return [
        {"id": p.id, "name": p.name}
        for p in db.scalars(select(VoicePerson).order_by(VoicePerson.name))
    ]


@router.post(
    "/voices/people", status_code=201, responses={422: {"description": "Request validation failed"}}
)
def create_person(body: PersonRequest, db: DB):
    if not body.name.strip():
        raise HTTPException(422, "Name cannot be blank")
    person = VoicePerson(name=body.name.strip())
    db.add(person)
    db.flush()
    return commit_result(db, {"id": person.id, "name": person.name})


@router.patch(
    "/voices/people/{person_id}",
    responses={
        404: {"description": "Requested resource or media was not found"},
        422: {"description": "Request validation failed"},
    },
)
def rename_person(person_id: str, body: PersonRequest, db: DB):
    person = db.get(VoicePerson, person_id)
    if person is None:
        raise HTTPException(404, PERSON_NOT_FOUND)
    if not body.name.strip():
        raise HTTPException(422, "Name cannot be blank")
    person.name = body.name.strip()
    return commit_result(db, {"id": person.id, "name": person.name})


@router.get(
    "/diarization/{task_id}/media",
    responses={404: {"description": "Requested resource or media was not found"}},
)
def original_media(task_id: str, db: DB):
    return FileResponse(media_path(task(db, task_id).file_path, settings.DOWNLOAD_YOUTUBE_PATH))


@router.post(
    "/voices/training",
    status_code=202,
    responses={
        404: {"description": "Requested resource or media was not found"},
        409: {"description": "Operation conflicts with the current processing state"},
        422: {"description": "Request validation failed"},
    },
)
def train(body: TrainingRequest, db: DB):
    source = task(db, body.task_id)
    if source.step != "COMPLETED":
        raise HTTPException(409, DIARIZATION_NOT_COMPLETED)
    if db.get(VoicePerson, body.person_id) is None:
        raise HTTPException(404, PERSON_NOT_FOUND)
    path = media_path(source.file_path, settings.DOWNLOAD_YOUTUBE_PATH)
    probe = subprocess.run(
        [
            settings.FFMPEG_PROBE,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    try:
        validate_selection(body.start, body.end, duration)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    version = transcript_version(source.result_json, str(source.updated_at))
    key = selection_key(body.person_id, body.task_id, version, body.start, body.end)
    return enqueue(
        db, "TRAIN", source, version, key, {**body.model_dump(), "transcript": source.result_json}
    )


def enqueue(db, kind, source, version, key, payload):
    # Serialize duplicate clicks across API processes, not only in the browser.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
    existing = db.scalar(select(VoiceJob).where(VoiceJob.request_key == key))
    if existing is not None:
        return job_data(existing)
    job = VoiceJob(
        kind=kind,
        task_id=source.id,
        version=version,
        request_key=key,
        payload={**payload, "file_path": source.file_path},
        result={},
    )
    db.add(job)
    db.flush()
    return commit_result(db, job_data(job))


@router.get("/voices/jobs")
def jobs(db: DB):
    return [
        job_data(j)
        for j in db.scalars(select(VoiceJob).order_by(VoiceJob.created_at.desc()).limit(100))
    ]


@router.post(
    "/voices/jobs/{job_id}/retry",
    status_code=202,
    responses={
        404: {"description": "Requested resource or media was not found"},
        409: {"description": "Operation conflicts with the current processing state"},
    },
)
def retry(job_id: str, db: DB):
    job = db.get(VoiceJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.state != "ERROR":
        raise HTTPException(409, "Only failed jobs may be retried")
    if (
        transcript_version(task(db, job.task_id).result_json, str(task(db, job.task_id).updated_at))
        != job.version
    ):
        raise HTTPException(409, "Transcript changed; submit a new request")
    job.state, job.error, job.token, job.lease = "PENDING", None, None, None
    return commit_result(db, job_data(job))


@router.get("/voices/samples")
def samples(db: DB):
    return [
        {"id": s.id, "person_id": s.person_id, "start": s.start, "end": s.end}
        for s in db.scalars(select(VoiceSample))
    ]


@router.get(
    "/voices/samples/{sample_id}/{media_kind}",
    responses={404: {"description": "Requested resource or media was not found"}},
)
def sample_media(sample_id: str, media_kind: str, db: DB):
    sample = db.get(VoiceSample, sample_id)
    if sample is None or media_kind not in ("video", "audio", "captions"):
        raise HTTPException(404, "Sample not found")
    if media_kind == "captions":
        job = db.get(VoiceJob, sample_id)
        transcript = (job.payload.get("transcript") or {}) if job else {}
        if not transcript and job:
            source = db.get(DiarizationModel, sample.task_id)
            if (
                source
                and transcript_version(cast(dict, source.result_json), str(source.updated_at))
                == job.version
            ):
                transcript = source.result_json or {}
        return Response(
            sample_captions(transcript, sample.start, sample.end), media_type="text/vtt"
        )
    relative = sample.video_path if media_kind == "video" else sample.audio_path
    return FileResponse(media_path(relative, settings.VOICE_SAMPLES_PATH))


@router.delete(
    "/voices/samples/{sample_id}",
    status_code=204,
    responses={404: {"description": "Requested resource or media was not found"}},
)
def delete_sample(sample_id: str, background: BackgroundTasks, db: DB):
    sample = db.get(VoiceSample, sample_id)
    if sample is None:
        raise HTTPException(404, "Sample not found")
    paths = (sample.video_path, sample.audio_path)
    previous_job = db.get(VoiceJob, sample_id)
    if previous_job is not None:
        previous_job.request_key = "deleted:" + str(uuid4())
    db.delete(sample)
    db.commit()
    background.add_task(clean_sample_files, sample_id, paths)


@router.post(
    "/diarization/{task_id}/identify",
    status_code=202,
    responses={
        404: {"description": "Requested resource or media was not found"},
        409: {"description": "Operation conflicts with the current processing state"},
    },
)
def identify(task_id: str, db: DB):
    source = task(db, task_id)
    if source.step != "COMPLETED":
        raise HTTPException(409, DIARIZATION_NOT_COMPLETED)
    media_path(source.file_path, settings.DOWNLOAD_YOUTUBE_PATH)
    version = transcript_version(source.result_json, str(source.updated_at))
    return enqueue(
        db, "IDENTIFY", source, version, str(uuid4()), {"transcript": source.result_json}
    )


@router.get(
    "/diarization/{task_id}/identities",
    responses={404: {"description": "Requested resource or media was not found"}},
)
def identities(task_id: str, db: DB):
    version = transcript_version(task(db, task_id).result_json, str(task(db, task_id).updated_at))
    assignments = db.scalars(
        select(VoiceAssignment).where(
            VoiceAssignment.task_id == task_id, VoiceAssignment.version == version
        )
    )
    names = {p.id: p.name for p in db.scalars(select(VoicePerson))}
    latest = db.scalar(
        select(VoiceJob)
        .where(
            VoiceJob.task_id == task_id, VoiceJob.version == version, VoiceJob.kind == "IDENTIFY"
        )
        .order_by(VoiceJob.created_at.desc())
    )
    return {
        "assignments": {
            a.speaker: {
                "person_id": a.person_id,
                "name": names.get(a.person_id) if a.person_id else None,
            }
            for a in assignments
        },
        "job": job_data(latest) if latest else None,
    }


@router.put(
    "/diarization/{task_id}/identities/{speaker}",
    responses={
        404: {"description": "Requested resource or media was not found"},
        409: {"description": "Operation conflicts with the current processing state"},
        422: {"description": "Request validation failed"},
    },
)
def assign(task_id: str, speaker: str, body: AssignmentRequest, db: DB):
    source = task(db, task_id)
    if source.step != "COMPLETED":
        raise HTTPException(409, DIARIZATION_NOT_COMPLETED)
    if speaker not in (source.result_json or {}).get("speakers", []):
        raise HTTPException(422, "Unknown speaker")
    if body.person_id and db.get(VoicePerson, body.person_id) is None:
        raise HTTPException(404, PERSON_NOT_FOUND)
    version = transcript_version(source.result_json, str(source.updated_at))
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"{task_id}:{speaker}"}
        )
    value = db.scalar(
        select(VoiceAssignment).where(
            VoiceAssignment.task_id == task_id,
            VoiceAssignment.version == version,
            VoiceAssignment.speaker == speaker,
        )
    )
    if value is None:
        value = VoiceAssignment(task_id=task_id, version=version, speaker=speaker)
        db.add(value)
    value.person_id = body.person_id
    return commit_result(db, {"speaker": speaker, "person_id": body.person_id})


def clean_sample_files(sample_id: str, paths: tuple[str, str]):
    with Session() as session:
        if session.get(VoiceSample, sample_id) is not None:
            return
    for relative in paths:
        try:
            media_path(relative, settings.VOICE_SAMPLES_PATH).unlink(missing_ok=True)
        except HTTPException:
            pass


def commit_result(db, result):
    """Commit before the HTTP response and before background file cleanup."""
    db.commit()
    return result


def caption_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, fraction = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{fraction:03}"


def sample_captions(transcript: dict, start: float, end: float) -> str:
    cues = ["WEBVTT", ""]
    for segment in transcript.get("segments", []):
        cue_start = max(start, segment["start"])
        cue_end = min(end, segment["end"])
        if cue_start >= cue_end:
            continue
        text = str(segment.get("text", "")).replace("-->", "→").strip()
        if text:
            cues.extend(
                [
                    f"{caption_timestamp(cue_start - start)} --> "
                    f"{caption_timestamp(cue_end - start)}",
                    text,
                    "",
                ]
            )
    return "\n".join(cues) + "\n"
