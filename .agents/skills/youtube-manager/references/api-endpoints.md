# Endpoints API YouTube — Referência Detalhada

## Canais Monitorados

### POST /api/youtube/monitored_channels
Registra um novo canal para monitoramento automático.

**Request Body:**
```json
{
  "channel_url": "https://www.youtube.com/@ChannelName"
}
```

**Response:** Canal registrado com ID e metadados extraídos.

---

### GET /api/youtube/monitored_channels
Lista todos os canais registrados para monitoramento.

**Response:** Array de canais com status (active/paused/error), URL, nome, avatar, contagem de inscritos.

---

### PATCH /api/youtube/monitored_channels/{id}/status
Ativa ou desativa o monitoramento de um canal específico.

**Request Body:**
```json
{
  "is_active": true
}
```

---

## Canais Salvos

### GET /api/youtube/channels
Lista todos os canais que já tiveram vídeos capturados (mesmo sem monitoramento ativo).

---

## Conteúdo (Vídeos)

### POST /api/youtube/content
Ingere um vídeo único a partir de um link YouTube.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

---

### POST /api/youtube/playlist
Ingere todos os vídeos de uma playlist YouTube.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
  "save_in_playlist_folder": true
}
```

---

### GET /api/youtube/content
Lista vídeos capturados com paginação, busca e filtro por step.

**Query Params:**
- `page` (int) — Número da página
- `size` (int) — Itens por página
- `search` (string) — Busca por título
- `step` (string) — Filtro por ContentStep

---

### GET /api/youtube/content/status-count
Retorna contagem de vídeos agrupados por step/status.

**Response:**
```json
{
  "COMPLETED": 150,
  "DOWNLOADING": 3,
  "ERROR": 5,
  "PENDING_DOWNLOAD": 10
}
```

---

### GET /api/youtube/content/{id}/tracking
Retorna o log completo de transições de step para um vídeo.

**Response:** Array ordenado por timestamp com step anterior, step novo e detalhes.

---

### POST /api/youtube/content/{id}/retry
Coloca um vídeo específico na fila de retry (muda step para REPROCESSING).

---

### POST /api/youtube/content/retry-errors
Faz retry de todos os vídeos com step ERROR.

---

### DELETE /api/youtube/content/{id}
Deleta um vídeo do banco e remove o arquivo físico do disco.

---

## Jobs

### POST /api/youtube/jobs/{job_id}/run
Executa manualmente um job agendado do APScheduler.

**Path Params:**
- `job_id` — ID do job (ex: `youtube_monitor_channels_job`)
