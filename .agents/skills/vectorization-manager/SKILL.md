---
name: vectorization-manager
description: >-
  Agente especializado em gerenciar, debugar, manter e evoluir o módulo de Vetorização e Busca
  Semântica Polimórfica no SignalCatcher. Use esta skill para trabalhar com pgvector, embeddings
  via Text Embeddings Inference (TEI), estratégias de chunking (áudio/diarização e documentos),
  repositórios, use cases, endpoints REST no backend FastAPI e interface React no SignalCatcherFrontend.
---

# 🧠 Vectorization & Semantic Search Manager

Esta skill fornece conhecimento especializado para manipular toda a infraestrutura de **Vetorização Polimórfica** e **Busca Semântica** do ecossistema SignalCatcher (backend FastAPI + banco PostgreSQL com extensão `pgvector` + serviço Text Embeddings Inference (TEI) + frontend React/Vite).

---

## 1. Visão Geral e Arquitetura

O módulo `vectorization` é projetado de forma **polimórfica**, permitindo armazenar e indexar vetores gerados a partir de diferentes fontes de conteúdo:
- `AUDIO_TRANSCRIPT`: transcrições diarizadas pelo WhisperX (com timestamps `start_time`, `end_time` e `speaker`).
- `DOCUMENT`: documentos e PDFs processados.
- `NOTE`: anotações de texto livre.
- `ARTICLE`: artigos e conteúdos web extraídos.

### Árvore do Módulo (`src/modules/vectorization/`)

```
src/modules/vectorization/
├── domain/                                    # Domínio puro (sem deps de infra/framework)
│   ├── entities/
│   │   ├── vector_chunk_entity.py             # VectorChunkEntity (chunk polimórfico)
│   │   ├── semantic_search_result_entity.py   # SemanticSearchResultEntity (score de similaridade)
│   │   └── __init__.py
│   ├── enums/
│   │   ├── source_type.py                     # SourceType (AUDIO_TRANSCRIPT, DOCUMENT, etc.)
│   │   └── __init__.py
│   ├── interfaces/
│   │   ├── repositories/
│   │   │   └── chunk_repository_interface.py  # IChunkRepository (CRUD, search_similar, stats)
│   │   ├── services/
│   │   │   ├── embedding_service_interface.py # IEmbeddingService (geração de vetores)
│   │   │   └── chunking_strategy_interface.py # IChunkingStrategy (estratégias de particionamento)
│   │   └── __init__.py
│   └── __init__.py
│
├── application/                               # Casos de uso e DTOs de orquestração
│   ├── dtos/
│   │   ├── search_query_dto.py                # SearchQueryDTO (query, top_k, threshold, filters)
│   │   ├── search_result_dto.py               # SearchResultDTO, ChunkMetadataDTO
│   │   ├── vectorization_status_dto.py        # VectorizationStatsDTO
│   │   └── __init__.py
│   └── use_cases/
│       ├── semantic_search_use_case.py        # Orquestra embed da query + busca por similaridade
│       ├── vectorize_diarization_use_case.py  # Extrai segmentos, particiona, gera embeds e persiste
│       └── __init__.py
│
├── infrastructure/                            # Implementações concretas
│   ├── repositories/
│   │   ├── models/
│   │   │   ├── vector_chunk_model.py          # SQLAlchemy ORM model com Vector(768) + JSONB
│   │   │   └── __init__.py
│   │   ├── mappers/
│   │   │   └── chunk_mapper.py                # Conversão Model ↔ Entity
│   │   └── chunk_repository.py                # Implementação concreta com SQLAlchemy + pgvector
│   ├── services/
│   │   ├── tei_embedding_service.py           # Cliente HTTP TEI com pooling httpx e prefixos e5
│   │   ├── audio_transcript_chunking_strategy.py # Janela de tempo/falantes com overlap
│   │   └── document_text_chunking_strategy.py    # Sliding window com overlap de tokens/palavras
│   └── unit_of_work.py                        # Context manager transacional
│
└── presentation/                              # Camada HTTP e injeção de dependência
    └── api/
        ├── dependencies.py                    # Factories de serviços, repos e use cases
        └── routes/
            ├── search_route.py                # POST /api/search/semantic
            ├── vectorization_route.py         # POST /api/vectorization/*, GET /stats, DELETE
            └── __init__.py
```

---

## 2. Banco de Dados e Modelagem (`pgvector`)

### Tabela `vector_chunks`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | `UUID` (PK) | Identificador único do chunk |
| `source_type` | `VARCHAR(50)` | Tipo da fonte (`AUDIO_TRANSCRIPT`, `DOCUMENT`, etc.) |
| `source_id` | `VARCHAR(255)` | ID da entidade original (ex: UUID da tarefa de diarização) |
| `chunk_index` | `INTEGER` | Posição sequencial do chunk no documento original |
| `content` | `TEXT` | Texto bruto do fragmento |
| `embedding` | `vector(768)` | Vetor gerado pelo modelo de embeddings |
| `metadata_` | `JSONB` | Metadados arbitrários (`start_time`, `end_time`, `speaker`, etc.) |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | Data/hora de inserção |

### Índices Criados

1. **HNSW Cosine Similarity Index**:
   ```sql
   CREATE INDEX ix_vector_chunks_embedding_hnsw 
   ON vector_chunks USING hnsw (embedding vector_cosine_ops)
   WITH (m = 16, ef_construction = 64);
   ```
2. **Índice Composto de Busca**:
   ```sql
   CREATE INDEX ix_vector_chunks_source_type_id 
   ON vector_chunks (source_type, source_id);
   ```

### Migration Alembic
- Revisão: `c7c9ce3f01a1_add_pgvector_and_transcript_chunks.py`
- Executa `CREATE EXTENSION IF NOT EXISTS vector;` antes de criar as tabelas.

---

## 3. Integração com Text Embeddings Inference (TEI)

### Modelo Padrão
- **Modelo**: `intfloat/multilingual-e5-base`
- **Dimensão**: `768` floats
- **Comportamento de Prefixo (Regra E5)**:
  - Textos a serem indexados (passagens/chunks) **devem** ser prefixados com: `passage: `
  - Queries de busca semântica **devem** ser prefixadas com: `query: `
  - A classe `TeiEmbeddingService` aplica automaticamente esses prefixos baseado no parâmetro booleano `is_query`.

### Configuração de Ambiente (`.env`)

```ini
# Vectorization & Embeddings (TEI)
EMBEDDING_API_URL=http://localhost:8080
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-base
EMBEDDING_DIMENSION=768
EMBEDDING_BATCH_SIZE=32
EMBEDDING_TIMEOUT_SECONDS=60.0
```

### Docker Compose / Portainer no Raspberry Pi 5 (ARM64)

```yaml
services:
  tei-embeddings:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-latest
    container_name: tei-embeddings
    restart: unless-stopped
    ports:
      - "8080:80"
    environment:
      - MODEL_ID=intfloat/multilingual-e5-base
      - REVISION=main
      - MAX_BATCH_SIZE=16
      - MAX_CONCURRENT_REQUESTS=32
    volumes:
      - tei_cache:/data

volumes:
  tei_cache:
```

---

## 4. Estratégias de Chunking (Strategy Pattern)

As estratégias implementam a interface `IChunkingStrategy`:

1. **`AudioTranscriptChunkingStrategy`** (`src/modules/vectorization/infrastructure/services/audio_transcript_chunking_strategy.py`):
   - Agrupa segmentos consecutivos de áudio respeitando uma janela temporal configurável (default `window_seconds=30.0`) e overlap (`overlap_seconds=5.0`).
   - Identifica falantes no texto (`[SPEAKER_00]: Olá...`) para contextualizar as buscas.
   - Extrai metadados precisos: `start_time`, `end_time`, `speakers`, `words_count`.

2. **`DocumentTextChunkingStrategy`** (`src/modules/vectorization/infrastructure/services/document_text_chunking_strategy.py`):
   - Particiona textos gerais por contagem de palavras/tokens (default `chunk_size_words=200`, `overlap_words=40`).
   - Mantém preservação de pontuação e estrutura de parágrafos.

---

## 5. Endpoints REST da API

### 1. Busca Semântica
- **Rota**: `POST /api/search/semantic`
- **Payload**:
  ```json
  {
    "query": "qual foi o resultado financeiro?",
    "source_types": ["AUDIO_TRANSCRIPT"],
    "top_k": 10,
    "similarity_threshold": 0.5
  }
  ```
- **Resposta**: Lista de `SearchResultDTO` contendo `chunk_id`, `source_type`, `source_id`, `content`, `similarity_score`, `chunk_index` e `metadata` (`start_time`, `speaker`, etc.).

### 2. Vetorizar Tarefa de Diarização Individual
- **Rota**: `POST /api/vectorization/diarization/{diarization_id}`
- **Parâmetros**: `overwrite: bool = True` (se True, limpa vetores anteriores antes de gerar novamente).

### 3. Vetorizar Tarefas de Diarização em Lote
- **Rota**: `POST /api/vectorization/diarization/batch`
- **Payload (opcional)**: `{"max_items": 10, "overwrite": false}`
- **Ação**: Encontra diarizações concluídas que ainda não foram vetorizadas e processa sequencialmente.

### 4. Estatísticas de Vetorização
- **Rota**: `GET /api/vectorization/stats`
- **Resposta**:
  ```json
  {
    "total_chunks": 1420,
    "chunks_by_source": {
      "AUDIO_TRANSCRIPT": 1420
    },
    "pending_diarizations": 3
  }
  ```

### 5. Deletar Vetores de uma Fonte
- **Rota**: `DELETE /api/vectorization/{source_type}/{source_id}`
- **Ação**: Remove todos os chunks associados a uma entidade.

---

## 6. Integração Frontend (`SignalCatcherFrontend`)

- **Componente**: `src/components/apps/SemanticSearchApp.tsx`
- **Funcionalidades**:
  - Busca semântica em tempo real com barra de query e tags de filtro (`AUDIO_TRANSCRIPT`, `DOCUMENT`).
  - Slider interativo para ajustar `similarity_threshold` (ex: 0.0 a 1.0) e `top_k`.
  - Badges de score de similaridade (verde > 80%, âmbar > 60%, cinza < 60%).
  - Suporte a reprodução/salto para o timestamp exato (`start_time`) em transcrições de áudio.
  - Acesso via **Command Palette** (`Ctrl+K` -> "Busca Semântica").
- **Mocks no Dev Server**: `server.ts` possui implementações completas dos endpoints para rodar desconectado do backend.

---

## 7. Diretrizes de Testes e Manutenção

1. **Testes Unitários**:
   - `tests/modules/vectorization/domain/`: teste de validação de entidades e enums.
   - `tests/modules/vectorization/infrastructure/`: teste de chunking strategies com dados simulados e teste do client TEI com `respx` / mocks de HTTP.
   - `tests/modules/vectorization/application/`: teste dos use cases (`VectorizeDiarizationUseCase`, `SemanticSearchUseCase`).
   - `tests/modules/vectorization/presentation/`: teste das rotas FastAPI usando `TestClient`.

2. **Execução da Suíte de Testes**:
   ```powershell
   uv run pytest tests/modules/vectorization/ -v
   ```

3. **Verificação de Tipagem e Linter**:
   ```powershell
   uv run ruff check src/modules/vectorization/
   uv run mypy src/modules/vectorization/
   ```

4. **Regra de Ouro da Documentação Viva**:
   Ao alterar dimensões de modelos, adicionar novos tipos de `SourceType` ou novas estratégias de chunking, **atualize este arquivo de skill** imediatamente.
