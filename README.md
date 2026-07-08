# 📡 SignalCatcher

**SignalCatcher** é uma aplicação backend para monitoramento automatizado de fontes de conteúdo (como canais do YouTube). Ela realiza capturas diárias de novos vídeos publicados, registra os metadados em um banco de dados PostgreSQL e expõe uma API REST para gerenciamento das fontes e dos jobs agendados.

---

## ✨ Funcionalidades

- 🔎 **Monitoramento de canais do YouTube** — Extrai metadados de vídeos via `yt-dlp`
- ⏰ **Captura diária agendada** — Job automático executado às 03:00 UTC (com execução imediata ao iniciar)
- 🗄️ **Persistência em PostgreSQL** — Armazenamento de fontes e conteúdos capturados
- 🌐 **API REST (FastAPI)** — Endpoints para cadastrar fontes e disparar jobs manualmente
- 🐳 **Docker** — Deploy simplificado com `docker-compose`
- 🔄 **Migrações com Alembic** — Versionamento automático do schema do banco

---

## 🏗️ Arquitetura

O projeto segue uma **Arquitetura Limpa (Clean Architecture)** organizada em camadas:

```
src/
├── config/              # Configurações (variáveis de ambiente via Pydantic Settings)
├── domain/              # Entidades, enums e interfaces (contratos)
│   ├── models/          # SourceEntity, ContentEntity, DTOs
│   ├── interfaces/      # Interfaces de repositórios e serviços
│   └── models/enums/    # SourcePlatform, ContentStatus
├── application/         # Casos de uso e DTOs de entrada/saída
│   ├── use_cases/       # CreateSourceUseCase, RunDailyCaptureUseCase
│   ├── dtos/            # SourceCreateDTO, SourceResponseDTO
│   ├── interfaces/      # ILogger e outras interfaces da aplicação
│   └── mappers/         # Mapeadores entre camadas
├── infrastructure/      # Implementações concretas
│   ├── repositories/    # Repositórios SQLAlchemy + conector do banco
│   ├── services/        # YouTubeScraperService, MonitorTaskService
│   └── loggers/         # Logger customizado
└── presentation/        # Camada de entrada (API e scheduler)
    ├── api/             # Rotas FastAPI + injeção de dependências
    │   └── routes/      # source_routes, scheduler_routes
    └── schedules/       # APScheduler (jobs e gerenciador)
        └── jobs/        # Jobs agendados (daily_youtube_capture_job)
```

---

## 🚀 Começando

### Pré-requisitos

- **Python** 3.10+
- **PostgreSQL** em execução e acessível
- **uv** (gerenciador de pacotes Python) — [Instalação](https://docs.astral.sh/uv/)
- **Docker** e **Docker Compose** (opcional, para deploy containerizado)

### Instalação Local

1. **Clone o repositório:**

```bash
git clone https://github.com/ericksonlopes/SignalCatcher.git
cd SignalCatcher
```

2. **Configure as variáveis de ambiente:**

Crie um arquivo `.env` na raiz do projeto:

```env
POSTGRES_USER=seu_usuario
POSTGRES_PASSWORD=sua_senha
POSTGRES_HOST=localhost
POSTGRES_DATABASE=signalcatcher
LIST_LOG_LEVELS=ERROR,WARNING,INFO
```

3. **Instale as dependências:**

```bash
uv sync
```

4. **Execute as migrações do banco:**

```bash
uv run alembic upgrade head
```

5. **Inicie a aplicação:**

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

A API estará disponível em: **http://127.0.0.1:8000**

---

### Usando Docker

```bash
docker-compose up --build -d
```

> O container executa automaticamente as migrações (`alembic upgrade head`) antes de iniciar o servidor.

---

## 📚 Endpoints da API

A documentação interativa (Swagger UI) está disponível em: **http://localhost:8000/docs**

### Health Check

| Método | Rota      | Descrição                 |
|--------|-----------|---------------------------|
| `GET`  | `/status` | Retorna o status da API   |

### Sources (Fontes)

| Método | Rota            | Descrição                                             |
|--------|-----------------|-------------------------------------------------------|
| `POST` | `/api/sources/` | Cadastra uma nova fonte de conteúdo para monitoramento |

**Exemplo de body (POST):**

```json
{
  "name": "Nome do Canal",
  "url": "https://www.youtube.com/@canal",
  "source_platform": "youtube"
}
```

### Scheduler (Agendador)

| Método | Rota                              | Descrição                                |
|--------|-----------------------------------|------------------------------------------|
| `POST` | `/api/scheduler/jobs/{job_id}/run` | Dispara manualmente um job pelo seu ID   |

**Exemplo:**

```bash
curl -X POST http://localhost:8000/api/scheduler/jobs/daily_youtube_capture_job/run
```

---

## ⚙️ Variáveis de Ambiente

| Variável             | Descrição                                         | Exemplo              |
|----------------------|---------------------------------------------------|----------------------|
| `POSTGRES_USER`      | Usuário do PostgreSQL                             | `postgres`           |
| `POSTGRES_PASSWORD`  | Senha do PostgreSQL                               | `senha_segura`       |
| `POSTGRES_HOST`      | Host do PostgreSQL                                | `localhost`           |
| `POSTGRES_DATABASE`  | Nome do banco de dados                            | `signalcatcher`      |
| `LIST_LOG_LEVELS`    | Níveis de log (separados por vírgula)             | `ERROR,WARNING,INFO` |

---

## 🛠️ Stack Tecnológica

| Tecnologia        | Finalidade                         |
|-------------------|------------------------------------|
| **FastAPI**       | Framework web / API REST           |
| **Uvicorn**       | Servidor ASGI                      |
| **SQLAlchemy**    | ORM / acesso ao banco de dados     |
| **Alembic**       | Migrações do banco de dados        |
| **Pydantic**      | Validação e serialização de dados  |
| **APScheduler**   | Agendamento de tarefas em background |
| **yt-dlp**        | Extração de metadados do YouTube   |
| **PostgreSQL**    | Banco de dados relacional          |
| **Docker**        | Containerização da aplicação       |

---

## 📂 Pipeline de Conteúdo

O conteúdo capturado passa pelos seguintes status:

```
PENDING_DOWNLOAD → DOWNLOADING → DOWNLOADED
                                       ↘ ERROR
```

| Status              | Descrição                                |
|---------------------|------------------------------------------|
| `PENDING_DOWNLOAD`  | Detectado, aguardando processamento      |
| `DOWNLOADING`       | Em processo de download                  |
| `DOWNLOADED`        | Download concluído com sucesso           |
| `ERROR`             | Falha durante o processo                 |

---

## 📄 Licença

Este projeto é de uso pessoal. Consulte o autor para informações sobre licenciamento.

---

<p align="center">
  Desenvolvido com ❤️ por <a href="https://github.com/ericksonlopes">Erickson Lopes</a>
</p>
