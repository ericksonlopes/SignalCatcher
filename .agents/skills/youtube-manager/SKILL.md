---
name: youtube-manager
description: >-
  Agente especializado em gerenciar e manipular tudo relacionado ao YouTube no SignalCatcher.
  Use esta skill quando o usuário pedir para modificar, debugar, criar ou gerenciar qualquer
  funcionalidade YouTube — incluindo models, endpoints, pipeline de ingestão, jobs agendados,
  scraping com yt-dlp, componentes React do frontend, ou integração full-stack.
  Exemplos: adicionar campos em vídeos, criar novos endpoints, modificar o pipeline de download,
  ajustar jobs do APScheduler, alterar componentes do frontend YouTube, debugar erros de ingestão.
---

# 🎬 YouTube Manager — Skill de Gerenciamento YouTube

Esta skill fornece conhecimento especializado para manipular toda a infraestrutura YouTube
do projeto SignalCatcher (backend FastAPI + frontend React/Vite).

---

## Arquitetura Backend (FastAPI + Clean Architecture)

**Projeto**: `c:\Users\ofcer\PycharmProjects\SignalCatcher`

### Camadas e Arquivos-Chave

```
src/modules/youtube/
├── domain/                         # Camada de domínio (sem dependências externas)
│   ├── entities/                   # YoutubeContentEntity, ChannelEntity, YouTubeVideoDTO
│   ├── enums/                      # ContentStep (máquina de estados do pipeline)
│   ├── interfaces/                 # Contratos: repos, services, notifications
│   └── error_classifier.py         # Classificação de erros YouTube e detecção de bot
│
├── application/                    # Camada de aplicação
│   ├── dtos/                       # Request/Response DTOs
│   ├── mappers/                    # Conversores entity ↔ DTO
│   └── use_cases/
│       ├── channels/               # ChannelCommands, ChannelQueries
│       ├── content/                # AddContentFromLink, AddContentFromPlaylist
│       └── jobs/                   # DownloadVideo, ExtractMetadata, ProcessErrors, ReprocessVideo
│
├── infrastructure/                 # Implementações concretas
│   ├── notifications/              # VoiceMonkeyNotification (Alexa)
│   ├── repositories/
│   │   └── models/                 # YoutubeContentModel, YouTubeChannelModel,
│   │                               # YouTubeMonitoredChannelModel, StepTrackingModel
│   └── services/                   # ScraperService (yt-dlp/oEmbed), MonitorTaskService,
│                                   # ContentService
│
└── presentation/
    ├── api/routes/                  # video_route.py, channel_route.py, playlist_route.py
    └── schedules/jobs/              # youtube_monitor_channels_job, youtube_extract_metadata_job
```

### Pipeline de Processamento (ContentStep)

O pipeline de vídeos segue esta máquina de estados:

```
STARTED → PENDING_METADATA_EXTRACTION → EXTRACTING_METADATA → METADATA_EXTRACTED
→ PENDING_DOWNLOAD → DOWNLOADING → DOWNLOADED → COMPLETED
```

**Estados de erro**: `MEMBERS_ONLY`, `AGE_RESTRICTED`, `PRIVATE_VIDEO`, `COPYRIGHT_REMOVED`,
`ACCOUNT_TERMINATED`, `VIDEO_REMOVED`, `DELETED`, `ERROR`, `REPROCESSING`

### Endpoints API

| Método | Rota | Ação |
|--------|------|------|
| POST | /api/youtube/monitored_channels | Registrar canal |
| GET | /api/youtube/monitored_channels | Listar canais monitorados |
| GET | /api/youtube/channels | Listar canais salvos |
| PATCH | /api/youtube/monitored_channels/{id}/status | Toggle monitoramento |
| POST | /api/youtube/content | Ingerir vídeo por link |
| POST | /api/youtube/playlist | Ingerir playlist |
| GET | /api/youtube/content | Listar vídeos (paginado) |
| GET | /api/youtube/content/status-count | Contagem por status |
| GET | /api/youtube/content/{id}/tracking | Histórico pipeline |
| POST | /api/youtube/content/{id}/retry | Retry específico |
| POST | /api/youtube/content/retry-errors | Retry global |
| DELETE | /api/youtube/content/{id} | Deletar vídeo + arquivo |
| POST | /api/youtube/jobs/{job_id}/run | Executar job manual |

### Jobs APScheduler

- `youtube_monitor_channels_job` — a cada 30 min, escaneia canais ativos, notifica via Alexa
- `youtube_extract_metadata_job` — extrai metadados pendentes
- Jobs de download — baixa vídeos em 1080p MP4

### Integração yt-dlp

- **Não usa YouTube Data API v3** para vídeos (usa yt-dlp)
- Headers customizados (User-Agent spoofing Chrome)
- Player clients: `mediaconnect`, `android`, `web`, `mweb`
- Suporte a `cookies.txt` para bypass de bot
- YouTube oEmbed para metadados básicos sem trigger de bot
- Error classifier com detecção de bot block (pausa scheduler)
- Downloads organizados: `<DOWNLOAD_YOUTUBE_PATH>/<ChannelName>/<ContentID>_<Title>.<ext>`

### Configuração (.env)

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DATABASE`
- `DOWNLOAD_YOUTUBE_PATH` (ex: `D:/Youtube`)
- `VOICE_MONKEY_API_TOKEN`, `VOICE_MONKEY_NEW_VIDEO_FOR_DOWNLOAD_MONKEY_ID`

---

## Arquitetura Frontend (React + Vite + Express)

**Projeto**: `c:\Users\ofcer\PycharmProjects\SignalCatcherFrontend`

### Arquivos-Chave YouTube

| Arquivo | Função |
|---------|--------|
| `src/components/apps/SignalCatcherApp.tsx` | Módulo principal YouTube (UI completa) |
| `src/App.tsx` | Shell: polling 5s, busca debounced, filtros, paginação |
| `server.ts` | API Express local (rotas mock `/api/youtube/*`) |
| `src/types.ts` | Interfaces TypeScript (CapturedVideo, ContentSource, etc.) |
| `src/components/apps/CreatorDashboardsApp.tsx` | Dashboard de métricas de criadores |
| `src/components/apps/FollowerAnalyticsApp.tsx` | Analytics multi-plataforma |

### SignalCatcherApp.tsx — Sub-módulos

- **Captures**: Grid de vídeos + modal de detalhes + VideoTrackingViewer
- **Saved Channels**: Canais salvos com metadados
- **Monitored Sources**: Canais em monitoramento ativo
- **Background Jobs**: Status dos jobs agendados

---

## Procedimento para Modificações

### Adicionar novo campo em vídeos (exemplo end-to-end)

1. **Domain**: Adicionar campo na entity (`domain/entities/`)
2. **Infrastructure**: Adicionar coluna no model SQLAlchemy (`infrastructure/repositories/models/`)
3. **Migration**: Criar migration Alembic (`alembic revision --autogenerate -m "add field"`)
4. **Application**: Atualizar DTOs e mappers (`application/dtos/`, `application/mappers/`)
5. **Presentation**: Atualizar rota se necessário (`presentation/api/routes/`)
6. **Frontend Types**: Atualizar interface em `src/types.ts`
7. **Frontend UI**: Atualizar componente em `src/components/apps/SignalCatcherApp.tsx`
8. **Frontend Mock**: Atualizar `server.ts` se necessário

### Criar novo endpoint

1. Criar use case em `application/use_cases/`
2. Adicionar rota em `presentation/api/routes/`
3. Registrar rota no `main.py` se for novo router
4. Adicionar mock no `server.ts` do frontend
5. Consumir no componente React

### Modificar job agendado

1. Localizar job em `presentation/schedules/jobs/`
2. Modificar lógica do job
3. Ajustar frequência no scheduler setup se necessário

### Debugar erros de ingestão

1. Verificar `error_classifier.py` para entender classificação
2. Checar logs do scraper service
3. Verificar se é bot block (checar `is_bot_block`)
4. Verificar cookies.txt se necessário
5. Testar com yt-dlp diretamente no terminal

---

## Regras

1. **SEMPRE leia os arquivos antes de modificar**
2. **Respeite Clean Architecture**: Domain → Application → Infrastructure → Presentation
3. **Mantenha consistência**: siga patterns existentes no código
4. **Migrations**: sempre crie ao alterar models
5. **Full-stack**: ao alterar backend, atualize frontend correspondente
6. **i18n**: textos visíveis em `src/locales/` (en, pt)
7. **Responda em português brasileiro**
