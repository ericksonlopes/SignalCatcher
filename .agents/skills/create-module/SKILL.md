---
name: create-module
description: >-
  Specialist in creating, scaffolding, maintaining, and refactoring business modules within
  `src/modules/<module_name>/` in the api-cosmos project, strictly following the Vertical
  Clean / Hexagonal Architecture established by the pilot CSAT module.
---

# Skill: Business Module Creation & Scaffolding (`src/modules`)

This skill guides the creation, restructuring, and maintenance of modular business features within `src/modules/<module_name>/` in the **api-cosmos** project, strictly adhering to **Vertical Clean / Hexagonal Architecture**.

---

## 1. Modular Directory Layout (The Blueprint)

Every new module must strictly follow this exact 4-layer structure with granular file separation and clean facade exports:

```
src/modules/<module_name>/
├── presentation/
│   └── rest/
│       └── v1/
│           ├── routes/
│           │   └── <module_name>_route.py        # FastAPI endpoints & dependency injection
│           └── dtos/                             
│               ├── requests/                     
│               │   ├── <name>_request.py         # Each input DTO isolated in its own file
│               │   └── __init__.py
│               ├── response/                     
│               │   ├── <name>_response.py        # Each output DTO isolated in its own file
│               │   └── __init__.py
│               └── __init__.py                   # Unified export of all request and response DTOs
│
├── application/
│   └── use_cases/
│       └── <module_name>_use_case.py             # Business use case orchestration
│
├── domain/
│   ├── entities/                                 
│   │   ├── enums/                                # Domain enums segregated into individual files
│   │   │   ├── <enum_name>.py
│   │   │   └── ...
│   │   ├── <entity_name>.py                      # Pure business entities (Pydantic / pure Python)
│   │   └── __init__.py                           # Re-exports entities and enums
│   ├── interfaces/                               
│   │   ├── repositories/
│   │   │   └── <module_name>_repository.py       # I<Module>Repository (Port / ABC)
│   │   ├── services/
│   │   │   └── <module_name>_service.py          # I<Module>Service (Port / ABC)
│   │   └── __init__.py                           # Re-exports all domain interfaces
│   └── rules/                                    
│       ├── <rule_type>_rules.py                  # Pure business rules / trigger calculation functions
│       └── __init__.py                           # Re-exports rule functions
│
└── infrastructure/
    ├── repositories/
    │   ├── models/                               
    │   │   ├── <model_name>.py                   # SQLAlchemy ORM models isolated per table
    │   │   └── __init__.py                       # Re-exports all ORM models
    │   └── <module_name>_repository.py           # Concrete implementation of I<Module>Repository
    └── services/
        └── <module_name>_service.py              # Concrete implementation of I<Module>Service
```

---

## 2. Golden Rules for `__init__.py` (Boilerplate Prevention)

To keep the codebase lean, prevent circular imports, and eliminate unnecessary intermediate cascades:

### ✅ The ONLY 5 Permitted `__init__.py` Files in the Module:
These 5 files are the only permitted facade `__init__.py` files. **IMPORTANT: You MUST ONLY create these files (and their parent directories) if there is actual content/files to be placed inside them.** If a module does not have enums or rules, do NOT create the empty directories or empty `__init__.py` files.
1. `domain/entities/__init__.py` — Groups and re-exports entities and enums.
2. `domain/interfaces/__init__.py` — Groups and re-exports repository and service contracts.
3. `domain/rules/__init__.py` — Groups and re-exports pure business rule functions.
4. `infrastructure/repositories/models/__init__.py` — Groups and re-exports SQLAlchemy ORM models (critical for Alembic auto-discovery).
5. `presentation/rest/v1/dtos/__init__.py` — Groups and re-exports all request and response schemas.

---

## 3. Import and Dependency Guidelines

1. **Mandatory `src.` Absolute Import Prefix:**
   - Every internal import MUST use the absolute project path starting with `src.`, for example:
     ```python
     from src.modules.<module_name>.domain.entities import <Entity>
     from src.modules.<module_name>.infrastructure.repositories.<module_name>_repository import <Repo>
     ```
   - ⚠️ Never omit `src.` (e.g. `from modules.<module_name> ...` will raise `ModuleNotFoundError: No module named 'modules'`).

2. **Unified SQLAlchemy `Base`:**
   - All ORM models in `infrastructure/repositories/models/` must inherit from the shared `Base`:
     ```python
     from src.shared.adapters.postgres.connector import Base
     ```
   - Always define `__table_args__ = {'extend_existing': True}` on declarative models to prevent metadata collisions during test runs.

3. **Automatic Alembic Discovery:**
   - `alembic/env.py` dynamically scans `src.modules.<module_name>.infrastructure.repositories.models`.
   - By placing models strictly in this folder and exporting them in `models/__init__.py`, Alembic automatically detects them for autogenerated migrations with zero manual configuration changes.

4. **Strict Layer Direction (Clean Architecture):**
   - `domain`: Zero dependencies on infrastructure, database, FastAPI, or external libraries. Uses only Python standard library and Pydantic.
   - `application`: Orchestrates use case flows, depending solely on abstractions from `domain.interfaces`.
   - `infrastructure`: Implements domain interfaces, accessing PostgreSQL (`ConnectorPostgres`), external APIs, or messaging from `src.shared.*`.
   - `presentation`: HTTP layer (FastAPI), validates input/output via DTOs, and injects `UseCase`, `Service`, and `Repository`.

---

## 4. Step-by-Step Module Scaffolding Procedure

### Step 1: Domain (`domain/`)
1. Create domain enums in `domain/entities/enums/<enum_name>.py`.
2. Create business entities in `domain/entities/<entity_name>.py`.
3. Create `domain/entities/__init__.py` re-exporting entities and enums.
4. Define abstract interfaces (ports):
   - `domain/interfaces/repositories/<module_name>_repository.py` (`I<Module>Repository`)
   - `domain/interfaces/services/<module_name>_service.py` (`I<Module>Service`)
5. Create `domain/interfaces/__init__.py` re-exporting these contracts.
6. Define pure business rules in `domain/rules/<rule_type>_rules.py` and re-export in `domain/rules/__init__.py`.

### Step 2: Infrastructure (`infrastructure/`)
1. Create SQLAlchemy ORM models in `infrastructure/repositories/models/<model_name>.py` inheriting from `src.shared.adapters.postgres.connector.Base`.
2. Create `infrastructure/repositories/models/__init__.py` re-exporting all models.
3. Implement the concrete repository in `infrastructure/repositories/<module_name>_repository.py` using `ConnectorPostgres`.
4. Implement concrete services in `infrastructure/services/<module_name>_service.py`.

### Step 3: Application (`application/`)
1. Implement use cases in `application/use_cases/<module_name>_use_case.py`.
2. Inject service and repository interfaces via constructor (`__init__`).

### Step 4: Presentation (`presentation/`)
1. Create input DTOs in `presentation/rest/v1/dtos/requests/<name>_request.py`.
2. Create output DTOs in `presentation/rest/v1/dtos/response/<name>_response.py`.
3. Create `presentation/rest/v1/dtos/__init__.py` re-exporting directly from request and response files.
4. Implement the FastAPI router in `presentation/rest/v1/routes/<module_name>_route.py` exposing `<module_name>_router`.
5. Register the router in `src/entrypoints/api/routes.py`:
   ```python
   from src.modules.<module_name>.presentation.rest.v1.routes.<module_name>_route import <module_name>_router
   api_router.include_router(<module_name>_router, prefix=f"/{version}")
   ```

### Step 5: Unit Tests (`tests/modules/<module_name>/`)
Rigorously mirror the module structure:
```
tests/modules/<module_name>/
├── presentation/
│   └── rest/
│       └── v1/
│           └── routes/
│               └── test_<module_name>_route.py
├── application/
│   └── test_<module_name>_use_case.py
├── domain/
│   └── rules/
│       └── test_<rule_type>_rules.py
└── infrastructure/
    ├── repositories/
    │   └── test_<module_name>_repository.py
    └── services/
        └── test_<module_name>_service.py
```

### Step 6: Quality & Verification Checks
Run the module unit test suite and the global test suite to ensure 100% pass rate and coverage requirements:
```powershell
.venv\Scripts\pytest tests/modules/<module_name> -v
.venv\Scripts\pytest -q
```

### Step 7: Create Module Skill (MANDATORY)
Every new module MUST have a specialized skill created for it in the `.agents/skills/` directory.
1. Create a new directory: `.agents/skills/<module_name>/`
2. Create the file `.agents/skills/<module_name>/SKILL.md` written in English.
3. The skill must document the module's architecture, core business logic, database schema, and API endpoints, following the exact structure seen in other skills (e.g., `csat` or `feature-highlights`).
4. Include a "Mandatory Living Documentation Policy" section to ensure the skill is updated alongside the code.
