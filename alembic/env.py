import importlib
import pkgutil
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic.autogenerate import rewriter
from alembic.operations import ops
from sqlalchemy import engine_from_config, pool, text

from alembic import context
from src.core.config.settings import settings
from src.core.database.connector import Base
from src.core.database.job_control import JobControlModel  # noqa: F401
from src.core.database.model_tracker import MigrationModelTracker

# env.py lives in <project_root>/alembic/env.py, so project root is two levels up
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    importlib.invalidate_caches()


def _import_models_from_package(package_name: str) -> None:
    """Import all model modules exclusively from a repositories models package."""
    try:
        pkg = importlib.import_module(package_name)
    except ModuleNotFoundError:
        return
    except Exception as exc:
        raise RuntimeError(f"The package could not be imported {package_name}. Error: {exc}")

    if hasattr(pkg, "__path__"):
        for _finder, _name, _ispkg in pkgutil.iter_modules(pkg.__path__):
            if _name.startswith("_"):
                continue
            importlib.import_module(f"{package_name}.{_name}")


# 1. Models from core/shared repositories
_import_models_from_package("src.core.database")

# 2. Modular models: src.modules.<module>.infrastructure.repositories.models
modules_dir = project_root / "src" / "modules"
if modules_dir.exists():
    for module_path in modules_dir.iterdir():
        if not module_path.is_dir() or module_path.name.startswith(("_", ".")):
            continue
        for repo_models_pkg in [
            f"src.modules.{module_path.name}.infrastructure.repositories.models",
            f"src.modules.{module_path.name}.infrastructure.repositories.postgres.models",
        ]:
            _import_models_from_package(repo_models_pkg)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Skip tables that exist only in the database (prevents autogenerate drop_table)
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


writer = rewriter.Rewriter()


@writer.rewrites(ops.CreateTableOp)
@writer.rewrites(ops.CreateIndexOp)
def add_if_not_exists(context, revision, op):
    op.if_not_exists = True
    return op


@writer.rewrites(ops.DropTableOp)
@writer.rewrites(ops.DropIndexOp)
def add_if_exists(context, revision, op):
    op.if_exists = True
    return op


def _heal_orphaned_revisions(connection) -> None:
    """If the database alembic_version points to a removed revision (e.g. removed module),
    reset it to the current available head to avoid 'Can't locate revision' errors."""
    try:
        result = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar()
        if not result:
            return

        script = context.script
        try:
            script.get_revision(result)
        except Exception:
            heads = script.get_heads()
            target_head = heads[0] if heads else None
            if target_head:
                connection.execute(
                    text("UPDATE alembic_version SET version_num = :head"),
                    {"head": target_head},
                )
                for table in (
                    "demograph_worker",
                    "demograph_schemas",
                    "demograph_issues",
                    "demograph_artifacts",
                    "demograph_runs",
                    "demograph_datasets",
                ):
                    connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                connection.commit()
    except Exception:
        pass


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    tracker = MigrationModelTracker(
        target_metadata=target_metadata, database_url=settings.database_url
    )
    tracker.print_offline_report()

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=writer,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=settings.database_url,
    )

    with connectable.connect() as connection:
        _heal_orphaned_revisions(connection)

        tracker = MigrationModelTracker(
            target_metadata=target_metadata,
            connection=connection,
            database_url=settings.database_url,
        )

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            process_revision_directives=writer,
            on_version_apply=tracker.on_version_apply,
        )

        with tracker.track_operations():
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()

        tracker.print_report()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
