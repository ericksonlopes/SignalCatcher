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
    - `samples_count` (`INTEGER`, Default `0`): Quantidade de amostras de voz cadastradas.
    - `created_at` / `updated_at` (`TIMESTAMP`).

2. **`voice_samples`**:
    - `id` (`VARCHAR`, PK): UUID da amostra.
    - `speaker_id` (`VARCHAR`, FK -> `speaker_profiles.id ON DELETE CASCADE`).
    - `source_type` (`VARCHAR(50)`): `DIARIZATION_SEGMENT`, `AUDIO_UPLOAD` ou `YOUTUBE_CLIP`.
    - `source_id` (`VARCHAR(255)`): ID da tarefa de diarização ou nome do arquivo.
    - `speaker_label` (`VARCHAR(100)`): Rótulo original (ex: `SPEAKER_00`).
    - `start_time`, `end_time`, `duration_seconds` (`FLOAT`).
    - `metadata` (`JSON`): Metadados extras (`entity_id`, `segments_count`, `sample_text`).
    - `embedding` (`vector(256)`): Vetor L2-normalizado de 256 dimensões.
    - Índice HNSW: `ix_voice_samples_embedding_hnsw` com `vector_cosine_ops`.

### Migration Alembic

- Revisão: `d4f8a1e2b3c9_add_voice_recognition_tables.py` (sucede `c7c9ce3f01a1`).

---

## 3. Extração de Embeddings no Worker (`SignalCatcherDiarization`)

- **Serviço**: `src/modules/diarization/infrastructure/services/voice_embedder.py` (`VoiceEmbedder`)
- **Modelo Principal**: `pyannote/wespeaker-voxceleb-resnet34-LM` (256 dimensões, carregado sob demanda via
  `model_loader.get_voice_embedding_inference` e descarregado após uso com `unload_voice_embedding()`).
- **Fallback Acústico**: Caso o modelo Pyannote não esteja disponível no ambiente, utiliza extração espectral
  STFT/log-magnitude normalizada em 256 dimensões.
- **Rotas do Worker** (`/api/voice-recognition`):
    - `POST /api/voice-recognition/extract-segments`: extrai embedding de uma lista de segmentos `[start, end]`.
    - `POST /api/voice-recognition/extract-batch`: extrai embeddings de múltiplos locutores carregando o áudio apenas
      uma vez.
    - `POST /api/voice-recognition/extract-file`: extrai embedding de um arquivo enviado via upload.

---

## 4. Contrato de Atualização de `result_json` na Diarização

Quando um locutor é cadastrado (`enroll_from_diarization`), identificado automaticamente (`identify_diarization`) ou
renomeado (`assign_speaker_in_diarization`):

- A função `apply_speaker_mapping_to_result_json` preserva o rótulo original de clusterização em
  `segment["original_speaker"]` (ex: `"SPEAKER_00"`) antes de substituir `segment["speaker"]` pelo nome real.
- Assim, re-identificações futuras ou novos cadastros continuam funcionando mesmo depois que `SPEAKER_00` já foi
  substituído pelo nome da pessoa.
- O mapa consolidado é gravado em `result_json["speaker_mappings"]`.

---

## 5. Endpoints REST da API Principal (`/api/voice-recognition`)

| Método e Rota                                           | Descrição                                                                                     |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `GET /api/voice-recognition/stats`                      | Estatísticas de perfis, amostras, dimensão (`256`) e saúde do worker                          |
| `GET /api/voice-recognition/profiles`                   | Lista perfis de voz (suporta `?search=` e `?include_samples=true`)                            |
| `POST /api/voice-recognition/profiles`                  | Cria um novo perfil de voz                                                                    |
| `GET /api/voice-recognition/profiles/{speaker_id}`      | Detalhes de um perfil com suas amostras                                                       |
| `PATCH /api/voice-recognition/profiles/{speaker_id}`    | Atualiza nome/descrição de um perfil                                                          |
| `DELETE /api/voice-recognition/profiles/{speaker_id}`   | Remove perfil e suas amostras em cascata                                                      |
| `DELETE /api/voice-recognition/samples/{sample_id}`     | Remove uma amostra de voz específica                                                          |
| `POST /api/voice-recognition/enroll/from-diarization`   | Extrai voz de um `SPEAKER_XX`, falas selecionadas ou recorte de tempo customizado (`start_time`/`end_time`), salva no `pgvector` e na pasta de cortes |
| `POST /api/voice-recognition/enroll/video-clip`          | Treina a voz a partir de um trecho de vídeo (`start_time` / `end_time`), salva em `D:/voice_training` |
| `POST /api/voice-recognition/enroll/audio`              | Cadastra amostra de voz via áudio em Base64                                                   |
| `POST /api/voice-recognition/diarization/{id}/identify` | Compara todos os locutores da diarização no `pgvector` e aplica os nomes identificados        |
| `POST /api/voice-recognition/diarization/{id}/assign`   | Renomeia um locutor na diarização e opcionalmente cadastra sua voz no `pgvector`              |

---

## 6. Integração Frontend (`SignalCatcherFrontend`)

1. **`src/components/apps/VoiceRecognitionApp.tsx`**:
    - Acessível pela barra lateral (`Fingerprint`) e pelo Command Palette (`Ctrl+K` -> "Reconhecimento de Voz").
    - Permite gerenciar perfis de voz, cadastrar amostras a partir de qualquer diarização concluída ou upload de áudio,
      e executar identificação automática com ajuste de limiar de similaridade (`similarity_threshold`).
2. **`src/components/apps/diarization/DiarizationViewer.tsx`**:
    - Botão **"Identificar Locutores"** no cabeçalho da transcrição para reconhecer automaticamente os falantes do vídeo
      aberto.
    - Ao renomear qualquer locutor na barra lateral, persiste o nome no backend e permite cadastrar automaticamente a
      amostra de voz no `pgvector`.
3. **Mocks (`server.ts`)**:
    - Todos os endpoints `/api/voice-recognition/*` possuem implementação mockada em memória no `server.ts`.

---

## 7. Testes e Verificação

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
uv run ruff check src/modules/voice_recognition/ tests/test_voice_recognition_use_cases.py
uv run mypy src/modules/voice_recognition/ main.py
```

### Política de Documentação Viva

Sempre que novos endpoints, dimensões de embedding ou contratos de `result_json` forem alterados no módulo
`voice_recognition`, atualize imediatamente este arquivo `SKILL.md`.
