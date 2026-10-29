---
name: voice-identity-manager
description: Maintain explicit voice enrollment, samples, and human-confirmed speaker identification.
---

# Voice identity

The API owns migrations and exposes `/api/voices` plus diarization media and identity operations.
The worker owns extraction and inference. The frontend embeds voice controls in the transcript viewer.

## Critical behavior

- Selection and preview only read original media with HTTP Range. Never extract, transcode, or enqueue from a GET or selection event.
- Only POST `/api/voices/training` authorizes clipping. Validate finite bounds against actual media duration via ffprobe.
- Preserve original speaker labels and transcript text. Assignments are separate, versioned records.
- Training requests are deduplicated by person, task, transcript version and interval using an advisory transaction lock.
- Explicit training creates MP4 and mono 16 kHz WAV files. Profiles use valid sample embeddings only. Compatibility is based on actual embedding-weight fingerprints and installed library versions.
- Voice jobs use subprocesses, execution exclusion, attempt tokens and leases. Publication checks the transcript version.
- Samples survive source-video deletion. Both containers require the same `signalcatcher_voice_samples` volume.
- Apply migration `a10428voice01` in the API repository before enabling the worker. Do not create a worker migration chain.
- Ranking returns at most three cosine similarities, never confidence percentages or automatic name assignments.

## Routes

People: GET/POST `/api/voices/people`, PATCH `/api/voices/people/{id}`.
Training: POST `/api/voices/training` with person_id, task_id, start, end and optional speaker.
Jobs: GET `/api/voices/jobs`, POST `/api/voices/jobs/{id}/retry`.
Samples: GET `/api/voices/samples`, GET `/api/voices/samples/{id}/{video|audio}`, DELETE `/api/voices/samples/{id}`.
Video: GET `/api/diarization/{id}/media`; identify: POST `/api/diarization/{id}/identify`;
identities: GET `/api/diarization/{id}/identities`, PUT `/api/diarization/{id}/identities/{speaker}`.

## Validation

Run API Ruff, mypy and unittest; worker isolated inference/scheduler tests; frontend TypeScript, build and tests.
Use held-out videos for actual recognition evaluation. Mock and SQLite success does not establish PostgreSQL lock behavior or recognition accuracy.

## Deployment and validation limits

The Docker volume is named `signalcatcher_voice_samples`; start the API Compose project before the worker so this volume exists.
The migration is additive and has a single head; apply it before starting the voice-aware scheduler.
No shared database migration or service restart is performed by the implementation task.
Synthetic FFmpeg validation exercises a 2.5-second excerpt and mono 16 kHz audio.
PostgreSQL integration and held-out real-video recognition still require an available isolated database and reference media.

## ORM model organization

Keep one SQLAlchemy model per file under `infrastructure/repositories/models/`:
- `voice_person_model.py`: `VoicePerson` / `voice_people`.
- `voice_job_model.py`: `VoiceJob` / `voice_jobs`.
- `voice_sample_model.py`: `VoiceSample` / `voice_samples`.
- `voice_assignment_model.py`: `VoiceAssignment` / `voice_assignments`.

Import models directly from their individual modules. Keep the API and worker mappings synchronized.
This organization does not change table names, columns, constraints, defaults, or migration history.

## Accessible media and HTTP contracts

The voice-training UI uses named action handlers to keep function nesting at five levels or fewer.
Unavailable-preview announcements use native `output`. Video and audio elements include caption tracks.
Original-video captions come from existing transcript segments; sample captions use the saved training transcript snapshot,
clipped and shifted to sample-relative timestamps. Legacy jobs fall back only to an unchanged source transcript.
GET `/api/voices/samples/{id}/captions` returns WebVTT without extracting or creating any media.
Document explicit 404, 409 and 422 errors on each applicable FastAPI route using `responses`.
Mutations commit before returning their result, including sample deletion before background file cleanup;
this does not depend on the FastAPI dependency `scope` keyword.
