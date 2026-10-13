"""Model and table migration tracker for Alembic.

Tracks table creation attempts during Alembic migrations, verifies existence
of models and tables against the database before and after migrations,
and logs per-table status via standard Alembic logging.
"""

import logging
from contextlib import contextmanager
from typing import Any

from alembic.operations import Operations
from sqlalchemy import MetaData, inspect
from sqlalchemy.engine import Connection

from src.core.database.connector import Base

logger = logging.getLogger("alembic.runtime.migration")

__all__ = ["MigrationModelTracker", "ModelStatus"]


class ModelStatus:
    CREATED = "[CREATED]"
    ALREADY_EXISTS = "[ALREADY_EXISTS]"
    EXISTS = "[EXISTS]"
    MISSING = "[MISSING]"
    REGISTERED = "[REGISTERED]"


class MigrationModelTracker:
    """Tracks and logs model table status during Alembic upgrade/migration runs."""

    def __init__(
        self,
        target_metadata: MetaData,
        connection: Connection | None = None,
        database_url: str | None = None,
    ) -> None:
        self.target_metadata = target_metadata
        self.connection = connection
        self.database_url = database_url
        self.tables_before: set[str] = set()
        self.tables_after: set[str] = set()
        self.attempted_creates: set[str] = set()
        self.attempted_drops: set[str] = set()
        self.applied_revisions: list[str] = []

        if self.connection is not None:
            self._capture_tables_before()

    def _capture_tables_before(self) -> None:
        """Capture database table names prior to running migrations."""
        try:
            inspector = inspect(self.connection)
            self.tables_before = set(inspector.get_table_names())
        except Exception as exc:
            logger.warning(f"Could not inspect tables before migration: {exc}")
            self.tables_before = set()

    def _capture_tables_after(self) -> None:
        """Capture database table names after running migrations."""
        if self.connection is None:
            return
        try:
            inspector = inspect(self.connection)
            self.tables_after = set(inspector.get_table_names())
        except Exception as exc:
            logger.warning(f"Could not inspect tables after migration: {exc}")
            self.tables_after = set()

    def on_version_apply(self, *args: Any, **kwargs: Any) -> None:
        """Alembic callback invoked after each migration step is applied."""
        step = kwargs.get("step")
        if step is None and len(args) > 1:
            step = args[1]
        elif step is None and args:
            step = args[0]

        up_rev = getattr(step, "up_revision_id", None)
        if up_rev:
            self.applied_revisions.append(str(up_rev))
        else:
            down_revs = getattr(step, "down_revision_ids", None)
            if down_revs:
                self.applied_revisions.extend([str(r) for r in down_revs])

    @contextmanager
    def track_operations(self):
        """Intercept Alembic create/drop table calls to record and log attempts."""
        orig_create_table = Operations.create_table
        orig_drop_table = Operations.drop_table

        tracker_self = self

        def wrapped_create_table(op_self, *args, **kwargs):
            table_name = args[0] if args else kwargs.get("name")
            if table_name:
                tracker_self.attempted_creates.add(str(table_name))
                if_not_exists = kwargs.get("if_not_exists", False)
                clause = " (if_not_exists=True)" if if_not_exists else ""
                logger.info(f"Creating table '{table_name}'{clause}")
            return orig_create_table(op_self, *args, **kwargs)

        def wrapped_drop_table(op_self, *args, **kwargs):
            table_name = args[0] if args else kwargs.get("table_name")
            if table_name:
                tracker_self.attempted_drops.add(str(table_name))
                if_exists = kwargs.get("if_exists", False)
                clause = " (if_exists=True)" if if_exists else ""
                logger.info(f"Dropping table '{table_name}'{clause}")
            return orig_drop_table(op_self, *args, **kwargs)

        Operations.create_table = wrapped_create_table
        Operations.drop_table = wrapped_drop_table
        try:
            yield
        finally:
            Operations.create_table = orig_create_table
            Operations.drop_table = orig_drop_table

    def _extract_module_origin(self, model_cls: type) -> str:
        """Extract a readable origin/module name from the model class module path."""
        module_path = getattr(model_cls, "__module__", "")
        if "src.modules." in module_path:
            parts = module_path.split("src.modules.")[1].split(".")
            return parts[0]
        elif "src.core." in module_path:
            return "core"
        elif "src.infrastructure." in module_path:
            return "legacy"
        elif module_path:
            return module_path.split(".")[-1]
        return "unknown"

    def get_registered_models(self) -> list[dict[str, Any]]:
        """Collect and map all registered models from Base metadata and mappers."""
        table_to_classes: dict[str, list[type]] = {}
        for mapper in Base.registry.mappers:
            target_tbl = getattr(mapper.local_table, "name", None)
            if target_tbl:
                table_to_classes.setdefault(target_tbl, []).append(mapper.class_)

        models_info = []
        for table_name, table in sorted(self.target_metadata.tables.items()):
            classes = table_to_classes.get(table_name, [])
            if classes:
                class_names = ", ".join(cls.__name__ for cls in classes)
                origin = self._extract_module_origin(classes[0])
            else:
                class_names = "(no ORM class)"
                origin = "schema"

            col_count = len(table.columns)

            models_info.append(
                {
                    "table_name": table_name,
                    "model_name": class_names,
                    "module": origin,
                    "columns": col_count,
                }
            )
        return models_info

    def determine_model_status(self, table_name: str) -> str:
        """Determine a table status from before/after DB state and attempted actions."""
        exists_after = table_name in self.tables_after
        existed_before = table_name in self.tables_before
        attempted_create = table_name in self.attempted_creates

        if not exists_after:
            return ModelStatus.MISSING
        if attempted_create and not existed_before:
            # A real CREATE TABLE was issued and the table is new
            return ModelStatus.CREATED
        if attempted_create and existed_before:
            # A CREATE TABLE IF NOT EXISTS was issued but the table already existed
            return ModelStatus.ALREADY_EXISTS
        # Table exists and no CREATE was attempted: it was already there
        return ModelStatus.EXISTS

    def log_report(self) -> list[str]:
        """Log per-table status entries and a summary line using Alembic logger."""
        self._capture_tables_after()
        models = self.get_registered_models()

        counts = {
            ModelStatus.CREATED: 0,
            ModelStatus.ALREADY_EXISTS: 0,
            ModelStatus.EXISTS: 0,
            ModelStatus.MISSING: 0,
        }

        logged_messages: list[str] = []

        for item in models:
            t_name = item["table_name"]
            m_name = item["model_name"]
            mod = item["module"]
            cols = item["columns"]

            prefix = f"Table '{t_name}' (model: {m_name}, module: {mod})"
            status = self.determine_model_status(t_name)
            counts[status] = counts.get(status, 0) + 1

            if status == ModelStatus.CREATED:
                msg = f"{prefix}: [CREATED] table created successfully ({cols} columns)"
                logger.info(msg)
            elif status == ModelStatus.ALREADY_EXISTS:
                msg = (
                    f"{prefix}: [ALREADY_EXISTS] already exists "
                    f"(verified with IF NOT EXISTS, {cols} columns)"
                )
                logger.info(msg)
            elif status == ModelStatus.EXISTS:
                msg = f"{prefix}: [EXISTS] verified in database ({cols} columns)"
                logger.info(msg)
            else:  # MISSING
                msg = f"{prefix}: [MISSING] table not found in database!"
                logger.warning(msg)

            logged_messages.append(msg)

        created_count = counts[ModelStatus.CREATED]
        already_count = counts[ModelStatus.ALREADY_EXISTS]
        exists_count = counts[ModelStatus.EXISTS]
        missing_count = counts[ModelStatus.MISSING]
        total_models = len(models)

        summary_msg = (
            f"Model verification: {total_models} models verified ("
            f"{created_count} created, {already_count} already existed, "
            f"{exists_count} existing, {missing_count} missing)."
        )
        if missing_count > 0:
            logger.warning(summary_msg)
        else:
            logger.info(summary_msg)

        logged_messages.append(summary_msg)
        return logged_messages

    def print_report(self) -> None:
        """Alias to log_report for compatibility."""
        self.log_report()

    def log_offline_report(self) -> list[str]:
        """Log registered models in offline mode."""
        models = self.get_registered_models()
        logged: list[str] = []
        for item in models:
            msg = (
                f"Registered model: table '{item['table_name']}' "
                f"(model: {item['model_name']}, module: {item['module']}, "
                f"{item['columns']} columns)"
            )
            logger.info(msg)
            logged.append(msg)

        summary_msg = f"Offline registry: {len(models)} models registered in metadata."
        logger.info(summary_msg)
        logged.append(summary_msg)
        return logged

    def print_offline_report(self) -> None:
        """Alias to log_offline_report for compatibility."""
        self.log_offline_report()
