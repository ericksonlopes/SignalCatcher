# 📡 SignalCatcher

**SignalCatcher** is a backend application for automated monitoring of content sources (such as YouTube channels). It performs daily captures of newly published videos, records metadata in a PostgreSQL database, and exposes a REST API for managing sources and scheduled jobs.

---

## ✨ Features

- 🔎 **YouTube Channel Monitoring** — Extracts video metadata via `yt-dlp`
- ⏰ **Scheduled Daily Capture** — Automated job runs at 03:00 UTC (with immediate execution on startup)
- 🗄️ **PostgreSQL Persistence** — Storage of captured sources and content
- 🌐 **REST API (FastAPI)** — Endpoints to register sources and manually trigger jobs
- 🐳 **Docker** — Simplified deployment with `docker-compose`
- 🔄 **Alembic Migrations** — Automatic database schema versioning

---

## 🏗️ Architecture

The project follows a **Clean Architecture** organized in layers:

```
src/
├── config/              # Configuration (environment variables via Pydantic Settings)
├── domain/              # Entities, enums, and interfaces (contracts)
│   ├── models/          # SourceEntity, ContentEntity, DTOs
│   ├── interfaces/      # Repository and service interfaces
│   └── models/enums/    # SourcePlatform, ContentStatus
├── application/         # Use cases and input/output DTOs
│   ├── use_cases/       # CreateSourceUseCase, RunDailyCaptureUseCase
│   ├── dtos/            # SourceCreateDTO, SourceResponseDTO
│   ├── interfaces/      # ILogger and other application interfaces
│   └── mappers/         # Mappers between layers
├── infrastructure/      # Concrete implementations
│   ├── repositories/    # SQLAlchemy repositories + database connector
│   ├── services/        # YouTubeScraperService, MonitorTaskService
│   └── loggers/         # Custom logger
└── presentation/        # Entry layer (API and scheduler)
    ├── api/             # FastAPI routes + dependency injection
    │   └── routes/      # source_routes, scheduler_routes
    └── schedules/       # APScheduler (jobs and manager)
        └── jobs/        # Scheduled jobs (daily_youtube_capture_job)
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+
- **PostgreSQL** running and accessible
- **uv** (Python package manager) — [Installation](https://docs.astral.sh/uv/)
- **Docker** and **Docker Compose** (optional, for containerized deployment)

### Local Installation

1. **Clone the repository:**

```bash
git clone https://github.com/ericksonlopes/SignalCatcher.git
cd SignalCatcher
```

2. **Configure environment variables:**

Create a `.env` file in the project root:

```env
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_DATABASE=signalcatcher
LIST_LOG_LEVELS=ERROR,WARNING,INFO
```

3. **Install dependencies:**

```bash
uv sync
```

4. **Run database migrations:**

```bash
uv run alembic upgrade head
```

5. **Start the application:**

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

The API will be available at: **http://127.0.0.1:8000**

---

### Using Docker

```bash
docker-compose up --build -d
```

> The container automatically runs migrations (`alembic upgrade head`) before starting the server.

---

## 📚 API Endpoints

Interactive documentation (Swagger UI) is available at: **http://localhost:8000/docs**

### Health Check

| Method | Route     | Description               |
|--------|-----------|---------------------------|
| `GET`  | `/status` | Returns the API status    |

### Sources

| Method | Route           | Description                                       |
|--------|-----------------|---------------------------------------------------|
| `POST` | `/api/sources/` | Registers a new content source for monitoring     |

**Body example (POST):**

```json
{
  "name": "Channel Name",
  "url": "https://www.youtube.com/@channel",
  "source_platform": "youtube"
}
```

### Scheduler

| Method | Route                              | Description                            |
|--------|------------------------------------|----------------------------------------|
| `POST` | `/api/scheduler/jobs/{job_id}/run` | Manually triggers a job by its ID      |

**Example:**

```bash
curl -X POST http://localhost:8000/api/scheduler/jobs/daily_youtube_capture_job/run
```

---

## ⚙️ Environment Variables

| Variable             | Description                                       | Example              |
|----------------------|---------------------------------------------------|----------------------|
| `POSTGRES_USER`      | PostgreSQL user                                   | `postgres`           |
| `POSTGRES_PASSWORD`  | PostgreSQL password                               | `secure_password`    |
| `POSTGRES_HOST`      | PostgreSQL host                                   | `localhost`          |
| `POSTGRES_DATABASE`  | Database name                                     | `signalcatcher`      |
| `LIST_LOG_LEVELS`    | Log levels (comma-separated)                      | `ERROR,WARNING,INFO` |

---

## 🛠️ Technology Stack

| Technology        | Purpose                            |
|-------------------|------------------------------------|
| **FastAPI**       | Web framework / REST API           |
| **Uvicorn**       | ASGI server                        |
| **SQLAlchemy**    | ORM / database access              |
| **Alembic**       | Database migrations                |
| **Pydantic**      | Data validation and serialization  |
| **APScheduler**   | Background task scheduling         |
| **yt-dlp**        | YouTube metadata extraction        |
| **PostgreSQL**    | Relational database                |
| **Docker**        | Application containerization       |

---

## 📂 Content Pipeline

Captured content goes through the following statuses:

```
PENDING_DOWNLOAD → DOWNLOADING → DOWNLOADED
                                       ↘ ERROR
```

| Status              | Description                              |
|---------------------|------------------------------------------|
| `PENDING_DOWNLOAD`  | Detected, awaiting processing            |
| `DOWNLOADING`       | In the process of downloading            |
| `DOWNLOADED`        | Download completed successfully          |
| `ERROR`             | Failed during the process                |

---

## 📄 License

This project is for personal use. Consult the author for licensing information.

---

<p align="center">
  Developed with ❤️ by <a href="https://github.com/ericksonlopes">Erickson Lopes</a>
</p>
