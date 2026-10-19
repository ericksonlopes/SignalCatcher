---
name: voice_recognition-manager
description: >-
  Agente especializado em gerenciar, debugar, manter e evoluir o módulo de Reconhecimento
  de Voz e Identificação Biométrica de Locutores (Speaker Identification) no SignalCatcher.
  Use esta skill para trabalhar com perfis de locutores (speaker_profiles), amostras de voz
  com pgvector (voice_samples), extração de embeddings de voz via Pyannote/WeSpeaker no worker
  SignalCatcherDiarization, mapeamento automático de SPEAKER_XX em transcrições diarizadas
  e interface React no SignalCatcherFrontend.
---

# 🎙️ Voice Recognition & Speaker Identification Manager

Esta skill fornece conhecimento especializado para manter e evoluir o módulo de **Reconhecimento de Voz e Identificação
de Locutores** (`voice_recognition`) em todo o ecossistema SignalCatcher (`SignalCatcher` API +
`SignalCatcherDiarization` Worker + `SignalCatcherFrontend`).

---

## 1. Visão Geral e Arquitetura

O módulo `voice_recognition` permite cadastrar perfis de pessoas conhecidas (**Voice Enrollment**) a partir de trechos
de diarizações já concluídas ou amostras de áudio avulsas, armazenando seus vetores biométricos de voz (**voiceprints**)
no PostgreSQL via `pgvector`, e identificar automaticamente quem é cada `SPEAKER_00`, `SPEAKER_01`, etc. em vídeos,
áudios ou conteúdos do YouTube.

### Árvore do Módulo (`src/modules/voice_recognition/`)

```
src/modules/voice_recognition/
├── domain/                                           # Domínio puro (sem dependências externas)
│   ├── entities/
│   │   ├── speaker_profile_entity.py                 # SpeakerProfileEntity (perfil de pessoa)
│   │   ├── voice_sample_entity.py                    # VoiceSampleEntity (amostra + embedding 256d)
│   │   ├── speaker_identification_result_entity.py   # SpeakerIdentificationMatchEntity
│   │   └── __init__.py
│   ├── enums/
│   │   ├── voice_source_type.py                      # VoiceSourceType (DIARIZATION_SEGMENT, AUDIO_UPLOAD, YOUTUBE_CLIP)
│   │   └── __init__.py
│   ├── interfaces/
│   │   ├── repositories/
│   │   │   └── speaker_repository_interface.py       # ISpeakerRepository (CRUD, find_nearest_speaker)
│   │   ├── services/
│   │   │   └── voice_embedding_service_interface.py  # IVoiceEmbeddingService (extração de embeddings)
│   │   └── __init__.py
│   └── __init__.py
│
├── application/                                      # Casos de uso e DTOs
│   ├── dtos/
│   │   ├── speaker_profile_dto.py                    # Create/Update/Response DTOs e Stats
│   │   ├── enroll_speaker_dto.py                     # EnrollFromDiarizationDTO, EnrollResponseDTO
│   │   ├── identify_speakers_dto.py                  # IdentifyDiarizationSpeakersRequestDTO, AssignSpeakerLabelDTO
│   │   └── __init__.py
│   └── use_cases/
│       ├── manage_speaker_profiles_use_case.py       # CRUD de perfis, amostras e estatísticas
│       ├── enroll_speaker_use_case.py                # Cadastro de voz a partir de diarização ou upload
│       ├── identify_diarization_speakers_use_case.py # Matching via cosseno no pgvector e substituição no result_json
│       └── __init__.py
│
├── infrastructure/                                   # Implementações concretas
│   ├── repositories/
│   │   ├── models/
│   │   │   ├── speaker_profile_model.py              # SpeakerProfileModel & VoiceSampleModel (Vector 256)
│   │   │   └── __init__.py
│   │   ├── mappers/
│   │   │   └── speaker_mapper.py                     # Conversão Model ↔ Entity
│   │   └── speaker_repository.py                     # Queries SQLAlchemy + pgvector cosine_distance (e fallback SQLite)
│   ├── services/
│   │   └── worker_voice_embedding_service.py         # Cliente HTTP para o worker + fallback acústico/espectral local
│   └── unit_of_work.py                               # Transação compartilhada entre speakers e diarizations
│
└── presentation/                                     # Camada HTTP FastAPI
    └── api/
        ├── dependencies.py                           # Providers de DI
        └── routes/
            ├── voice_recognition_route.py            # Rotas sob /api/voice-recognition
            └── __init__.py
```

---

## 2. Banco de Dados e Modelagem (`pgvector`)

### Tabelas

1. **`speaker_profiles`**:
    - `id` (`VARCHAR`, PK): UUID do perfil.
    - `name` (`VARCHAR(255)`, Unique, Indexed): Nome real da pessoa (ex: `"João Silva"`).
    - `description` (`TEXT`, Nullable): Cargo, canal ou observações.
    - `avatar_url` (`VARCHAR(512)`, Nullable): URL opcional de avatar.
    - `samples_count` (`INTEGER`, Default `0`): Quantidade de amostras **aprovadas** cadastradas.
    - `pending_count` (`INTEGER`, Default `0`): Quantidade de amostras aguardando curadoria (`PENDING_REVIEW`).
    - `profile_strength` (`VARCHAR(20)`, Default `'weak'`): Força do perfil (`weak`, `moderate`, `strong`).
    - `centroid` (`vector(256)`, Nullable): Centróide L2-normalizado dos embeddings das amostras aprovadas.
    - `created_at` / `updated_at` (`TIMESTAMP`).

2. **`voice_samples`**:
    - `id` (`VARCHAR`, PK): UUID da amostra.
    - `speaker_id` (`VARCHAR`, FK -> `speaker_profiles.id ON DELETE CASCADE`).
    - `source_type` (`VARCHAR(50)`): `DIARIZATION_SEGMENT`, `AUDIO_UPLOAD` ou `YOUTUBE_CLIP`.
    - `source_id` (`VARCHAR(255)`): ID da tarefa de diarização ou nome do arquivo.
    - `speaker_label` (`VARCHAR(100)`): Rótulo original (ex: `SPEAKER_00`).
    - `start_time`, `end_time`, `duration_seconds` (`FLOAT`).
    - `status` (`VARCHAR(30)`, Default `'PENDING_REVIEW'`): `PENDING_REVIEW`, `APPROVED`, `REJECTED`.
    - `clip_path` (`VARCHAR(1024)`, Nullable): Caminho absoluto do arquivo WAV mono 16kHz em disco.
    - `quality` (`JSON`): Métricas de VAD (`speech_ratio`, `speech_seconds`, `sample_rate`, etc.).
    - `reviewed_at` (`TIMESTAMP`, Nullable): Data/hora em que a amostra foi aprovada ou rejeitada.
    - `embedding_model` (`VARCHAR(100)`): Modelo neural utilizado (`pyannote/wespeaker-voxceleb-resnet34-LM`).
    - `metadata` (`JSON`): Metadados extras (`entity_id`, `segments_count`, `text`).
    - `embedding` (`vector(256)`): Vetor L2-normalizado de 256 dimensões.
    - Índices: HNSW `ix_voice_samples_embedding_hnsw` (`vector_cosine_ops`), `ix_voice_samples_status`, `ix_voice_samples_speaker_status`.

### Migrations Alembic

- `d4f8a1e2b3c9_add_voice_recognition_tables.py`: Criação das tabelas iniciais com pgvector.
- `e1a2b3c4d5e6_add_voice_sample_curation_fields.py`: Adiciona colunas de curadoria, campos de status e migra registros legados para `PENDING_REVIEW` com `samples_count = 0` ("revisar do zero").

---

## 3. Extração de Embeddings & Qualidade no Worker (`SignalCatcherDiarization`)

- **Serviço**: `src/modules/diarization/infrastructure/services/voice_embedder.py` (`VoiceEmbedder`)
- **Modelo Principal**: `pyannote/wespeaker-voxceleb-resnet34-LM` (256 dimensões, normalizado L2).
- **VAD & Filtragem**:
    - Janelamento deslizante de 3.0s com hop de 1.5s sobre os turnos de fala.
    - Filtro de VAD por RMS e speech ratio.
    - Rejeição de outliers por similaridade de cosseno intra-janelas.
- **Fallback Acústico**: Caso o modelo Pyannote não esteja disponível no ambiente, utiliza extração espectral STFT/log-magnitude normalizada em 256 dimensões (`spectral-v1`).
- **Rotas do Worker** (`/api/voice-recognition`):
    - `POST /api/voice-recognition/extract-segments`: extrai embedding de uma lista de segmentos `[start, end]`, retornando `embedding`, `quality` e `embedding_model`.
    - `POST /api/voice-recognition/extract-batch`: extrai embeddings de múltiplos locutores carregando o áudio apenas uma vez.
    - `POST /api/voice-recognition/extract-file`: extrai embedding de um arquivo enviado via upload.

---

## 4. Curadoria de Voz (Human-in-the-Loop) & Força do Perfil

- **Fluxo do Treinamento**:
    1. Novos recortes criados a partir de vídeos ou diarizações são salvos como WAV mono 16kHz em disco e entram inicialmente com status `PENDING_REVIEW`.
    2. O usuário escuta a amostra pelo player de áudio embutido (`VoiceClipPlayer`), confere o texto e as métricas de qualidade (VAD, fala útil, SNR).
    3. O usuário pode ajustar o início/fim com botões de passo e ouvir uma prévia em tempo real (`/api/voice-recognition/preview`).
    4. Ao aprovar, a amostra passa para `APPROVED`, é incorporada ao `centroid` do perfil e incrementa o `samples_count`.
    5. Apenas amostras **aprovadas** com modelo neural verificado participam da identificação automática de locutores por cosseno.
- **Força do Perfil (`profile_strength`)**:
    - `weak`: < 3 amostras aprovadas ou < 30s úteis de fala.
    - `moderate`: ≥ 3 amostras aprovadas e ≥ 15s de voz.
    - `strong`: ≥ 5 amostras aprovadas, ≥ 60s de voz e ≥ 2 fontes distintas de vídeo.

---

## 5. Endpoints REST da API Principal (`/api/voice-recognition`)

| Método e Rota                                           | Descrição                                                                                     |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `GET /api/voice-recognition/stats`                      | Estatísticas de perfis, amostras aprovadas/pendentes, dimensão (`256`) e worker               |
| `GET /api/voice-recognition/profiles`                   | Lista perfis de voz (suporta `?search=` e `?include_samples=true`)                            |
| `POST /api/voice-recognition/profiles`                  | Cria um novo perfil de voz                                                                    |
| `GET /api/voice-recognition/profiles/{speaker_id}`      | Detalhes de um perfil com suas amostras e força                                               |
| `PATCH /api/voice-recognition/profiles/{speaker_id}`    | Atualiza nome/descrição de um perfil                                                          |
| `DELETE /api/voice-recognition/profiles/{speaker_id}`   | Remove perfil e suas amostras em cascata                                                      |
| `DELETE /api/voice-recognition/samples/{sample_id}`     | Remove uma amostra de voz específica                                                          |
| `GET /api/voice-recognition/samples/review-queue`       | Fila de curadoria filtrável por `?status=PENDING_REVIEW|APPROVED|REJECTED` e `?speaker_id=`    |
| `PATCH /api/voice-recognition/samples/{id}/review`      | Aprova/rejeita amostra, suporta corte retificado (`start_time`/`end_time`) e re-extração       |
| `POST /api/voice-recognition/samples/review/bulk`       | Aprovação ou rejeição em lote de múltiplas amostras                                           |
| `GET /api/voice-recognition/samples/{id}/audio`         | Stream/download direto do arquivo WAV da amostra                                              |
| `GET /api/voice-recognition/preview`                    | Prévia on-demand de áudio de qualquer vídeo (`?video_id=&start_time=&end_time=`) via ffmpeg    |
| `GET /api/voice-recognition/diarization/{id}/speakers/{label}/suggested-clips` | Retorna as top falas mais limpas do locutor para treinamento    |
| `POST /api/voice-recognition/enroll/from-diarization`   | Extrai voz de um `SPEAKER_XX`, cria amostra como `PENDING_REVIEW` com WAV salvo em disco       |
| `POST /api/voice-recognition/enroll/video-clip`          | Treina a voz a partir de um trecho de vídeo (`start_time` / `end_time`), salva WAV em disco    |
| `POST /api/voice-recognition/enroll/audio`              | Cadastra amostra de voz via áudio em Base64                                                   |
| `POST /api/voice-recognition/diarization/{id}/identify` | Compara locutores da diarização contra amostras aprovadas no `pgvector` e aplica os nomes     |
| `POST /api/voice-recognition/diarization/{id}/assign`   | Renomeia um locutor na diarização e opcionalmente cadastra sua voz no `pgvector`              |

---

## 6. Integração Frontend (`SignalCatcherFrontend`)

1. **`src/components/apps/VoiceRecognitionApp.tsx`**:
    - Abas dedicadas:
        - **Curadoria de Voz** (`VoiceCurationQueue`): fila de aprovação com player de áudio integrado, badges de VAD/SNR, atalhos de teclado (`A` para aprovar, `R` para rejeitar, `Espaço` para play/pause), botões de ajuste de corte com prévia e aprovação em massa.
        - **Treinamento & Recortes**: formulários para recortar vídeos ou selecionar turnos contíguos de fala, enriquecido com **Trechos Sugeridos** (`VoiceSuggestedClips`) para escutar e treinar as melhores falas com 1 clique.
        - **Perfis de Locutores & Identificação**: diretório com badge de força do perfil (`Fraco`, `Médio`, `Forte`), contadores de pendências e amostras com mini players de áudio, além do painel de identificação por cosseno pgvector.
2. **`src/components/apps/voice/VoiceClipPlayer.tsx`**:
    - Player de áudio com scrubbing de barra de progresso, velocidade ajustável (1x, 1.25x, 1.5x), mute e modo compacto/completo.
3. **`src/components/apps/diarization/DiarizationViewer.tsx`**:
    - Botão **"Trechos Sugeridos para Treino"** no card de cada locutor, permitindo escutar os melhores turnos e cadastrá-los na fila de curadoria diretamente da transcrição.
4. **Mocks (`server.ts`)**:
    - Endpoints de fila de curadoria, aprovação, rejeição, bulk, streaming de áudio e suggested clips implementados.

---

## 7. Testes e Verificação

```powershell
# Backend
uv run python -m unittest discover -s tests -p "test_*.py" -v
uv run ruff check src/modules/voice_recognition/

# Frontend
npx tsc --noEmit
npm run lint
npm run build
```
