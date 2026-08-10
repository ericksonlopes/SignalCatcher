# Pipeline de Processamento YouTube — Referência Detalhada

## Máquina de Estados (ContentStep)

```
STARTED
  ↓
PENDING_METADATA_EXTRACTION
  ↓
EXTRACTING_METADATA
  ↓
METADATA_EXTRACTED
  ↓
PENDING_DOWNLOAD
  ↓
DOWNLOADING
  ↓
DOWNLOADED
  ↓
COMPLETED
```

## Transições de Erro

Qualquer estado pode transicionar para os seguintes estados de erro:

| Estado de Erro | Causa | Recuperável |
|----------------|-------|-------------|
| `MEMBERS_ONLY` | Vídeo restrito a membros do canal | Não |
| `AGE_RESTRICTED` | Requer confirmação de idade (sign-in) | Sim (com cookies) |
| `PRIVATE_VIDEO` | Vídeo marcado como privado | Não |
| `COPYRIGHT_REMOVED` | Removido por reclamação de copyright | Não |
| `ACCOUNT_TERMINATED` | Conta do canal encerrada pelo YouTube | Não |
| `VIDEO_REMOVED` | Removido pelo uploader | Não |
| `DELETED` | Deletado manualmente pelo usuário | N/A |
| `ERROR` | Erro genérico de execução | Sim |
| `REPROCESSING` | Vídeo em fila de retry manual | Sim |

## Retry de Erros

### Global
- Endpoint: `POST /api/youtube/content/retry-errors`
- Comportamento: Busca todos os vídeos com step `ERROR` e muda para `REPROCESSING`
- Use case: `ProcessErrors` em `application/use_cases/jobs/`

### Individual
- Endpoint: `POST /api/youtube/content/{id}/retry`
- Comportamento: Muda o step do vídeo para `REPROCESSING`
- Use case: `ReprocessVideo` em `application/use_cases/jobs/`

## Step Tracking

- Tabela: `step_tracking`
- Gatilho: SQLAlchemy event listeners (`after_insert`, `after_update`)
- Registra: step anterior → step novo, timestamp, detalhes
- Consulta: `GET /api/youtube/content/{id}/tracking`

## Error Classifier

O `error_classifier.py` analisa mensagens de erro do yt-dlp e classifica em estados específicos:

- Detecta se é bot block (`is_bot_block`) → pausa o scheduler
- Classifica erros de acesso (membros, idade, privado)
- Classifica erros de disponibilidade (removido, copyright, conta encerrada)

## Download de Vídeos

- Formato: `bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]`
- Ferramenta: yt-dlp + FFmpeg
- Organização: `<DOWNLOAD_YOUTUBE_PATH>/<ChannelName>/<ContentID>_<Title>.<ext>`
- Contramedidas anti-bot:
  - User-Agent: Chrome 123
  - Referer: Google
  - Player clients: mediaconnect, android, web, mweb
  - Suporte a cookies.txt na raiz do projeto

## Monitoramento de Canais

- Job: `youtube_monitor_channels_job`
- Frequência: A cada 30 minutos
- Processo:
  1. Lista canais ativos no banco
  2. Para cada canal, usa yt-dlp com `extract_flat="in_playlist"` para listar vídeos
  3. Compara com vídeos já registrados
  4. Registra novos vídeos no banco (step STARTED)
  5. Envia notificação via Alexa (VoiceMonkey) se novos vídeos encontrados
  6. Se detecta bot block, pausa o scheduler

## Extração de Metadados

- Job: `youtube_extract_metadata_job`
- Processo:
  1. Busca vídeos com step `PENDING_METADATA_EXTRACTION`
  2. Usa YouTube oEmbed (`https://www.youtube.com/oembed`) para título e canal
  3. Usa yt-dlp para metadados completos (thumbnail, tags, duração, data)
  4. Salva metadados no banco
  5. Muda step para `METADATA_EXTRACTED` → `PENDING_DOWNLOAD`
