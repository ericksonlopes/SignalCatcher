# SignalCatcher Agent Rules

## Projeto

Este é o **SignalCatcher** — um sistema de captura automatizada de vídeos do YouTube, construído com:

- **FastAPI** + **Uvicorn** (ASGI server)
- **SQLAlchemy 2.0** + **Alembic** (ORM + migrations)
- **APScheduler** (jobs agendados)
- **yt-dlp** + **FFmpeg** (download de vídeos)
- **Pydantic v2** (validação e settings)
- **PostgreSQL** (banco de dados)
- **Docker** + **Docker Compose** (containerização)

## Arquitetura

O projeto segue **Clean Architecture / DDD** com camadas bem definidas:

```
src/modules/youtube/
├── domain/          → Entidades, enums, interfaces (sem dependências externas)
├── application/     → DTOs, mappers, use cases (orquestração)
├── infrastructure/  → Implementações concretas (repos, services, notificações)
└── presentation/    → Rotas FastAPI, jobs APScheduler
```

## Regras de Desenvolvimento

1. **Respeite as camadas**: Domain não depende de nada externo. Application depende só de Domain. Infrastructure implementa interfaces de Domain. Presentation consome Application.
2. **Migrations Alembic**: Sempre crie migrations ao alterar models SQLAlchemy.
3. **DTOs e Mappers**: Use DTOs para comunicação entre camadas. Use mappers para converter entre entities e DTOs.
4. **Dependency Injection**: Siga o padrão de DI existente nas rotas FastAPI.
5. **Pydantic Settings**: Configurações vêm do `.env` via `src/core/config/settings.py`.
6. **Testes**: Mantenha testes para use cases e services.
7. **Linguagem**: Responda em português brasileiro. Código e comentários técnicos em inglês.
