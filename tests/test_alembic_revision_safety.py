import unittest
from pathlib import Path
from unittest.mock import patch

from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect, text

from alembic import command


class AlembicRevisionSafetyTest(unittest.TestCase):
    def test_unknown_revision_stops_upgrade_without_changing_version_or_schema(self):
        engine = create_engine("sqlite:///:memory:")
        self.addCleanup(engine.dispose)
        with engine.begin() as db:
            db.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
            db.exec_driver_sql("INSERT INTO alembic_version VALUES ('removed-revision')")
            db.exec_driver_sql("CREATE TABLE youtube_contents (id INTEGER PRIMARY KEY)")
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        # Keep this migration test isolated from credentials and the configured PostgreSQL.
        with patch("sqlalchemy.engine_from_config", return_value=engine):
            with self.assertRaisesRegex(CommandError, "removed-revision"):
                command.upgrade(config, "head")
        with engine.connect() as db:
            self.assertEqual(
                db.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),
                "removed-revision",
            )
            self.assertEqual(
                {column["name"] for column in inspect(db).get_columns("youtube_contents")}, {"id"}
            )
            self.assertEqual(
                set(inspect(db).get_table_names()), {"alembic_version", "youtube_contents"}
            )
