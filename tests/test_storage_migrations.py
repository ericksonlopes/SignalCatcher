import importlib.util
import io
import unittest
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_DIRECTORY = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def load_migration(filename):
    spec = importlib.util.spec_from_file_location(filename, MIGRATION_DIRECTORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STORAGE = load_migration("e802d481a301_youtube_storage_destinations.py")
OAUTH = load_migration("f904d482b302_drive_browser_oauth.py")
REMOVE_OAUTH = load_migration("0a15e593c403_remove_drive_browser_oauth.py")
STORAGE_COLUMNS = {
    "storage_location",
    "storage_mode",
    "staging_path",
    "storage_size",
    "storage_verified_at",
    "drive_file_id",
    "drive_url",
}


class StorageMigrationTest(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)

    def upgrade(self, *migrations):
        context = MigrationContext.configure(self.connection)
        with Operations.context(context):
            for migration in migrations:
                migration.upgrade()

    def test_fresh_schema_upgrades_through_the_whole_storage_chain(self):
        self.connection.exec_driver_sql("CREATE TABLE youtube_contents (id INTEGER PRIMARY KEY)")
        self.upgrade(STORAGE, OAUTH, REMOVE_OAUTH)
        inspector = sa.inspect(self.connection)
        columns = {column["name"] for column in inspector.get_columns("youtube_contents")}
        self.assertTrue(STORAGE_COLUMNS <= columns)
        self.assertNotIn("youtube_drive_oauth_sessions", inspector.get_table_names())
        self.assertEqual(
            self.connection.exec_driver_sql(
                "SELECT id, mode, uploads_paused, drive_ready FROM youtube_storage_settings"
            ).one(),
            (1, "BOTH", 0, 0),
        )
        self.assertEqual(
            {index["name"] for index in inspector.get_indexes("youtube_storage_transfers")},
            {"ix_youtube_storage_transfer_queue", "uq_youtube_storage_transfer"},
        )

    def test_partial_schema_keeps_existing_video_and_adds_missing_columns(self):
        self.connection.exec_driver_sql(
            "CREATE TABLE youtube_contents "
            "(id INTEGER PRIMARY KEY, storage_location VARCHAR(10), storage_size BIGINT)"
        )
        self.connection.exec_driver_sql(
            "INSERT INTO youtube_contents (id, storage_location, storage_size) "
            "VALUES (42, 'LOCAL', 12345)"
        )
        self.upgrade(STORAGE, OAUTH, REMOVE_OAUTH)
        columns = {
            column["name"] for column in sa.inspect(self.connection).get_columns("youtube_contents")
        }
        self.assertTrue(STORAGE_COLUMNS <= columns)
        self.assertEqual(
            self.connection.exec_driver_sql(
                "SELECT id, storage_location, storage_size, drive_file_id FROM youtube_contents"
            ).one(),
            (42, "LOCAL", 12345, None),
        )

    def test_repeated_upgrade_preserves_settings_backups_transfers_and_history(self):
        self.connection.exec_driver_sql("CREATE TABLE youtube_contents (id INTEGER PRIMARY KEY)")
        self.upgrade(STORAGE)
        self.connection.exec_driver_sql(
            "UPDATE youtube_storage_settings SET mode = 'LOCAL', uploads_paused = true, "
            "max_upload_mib_per_second = 2, drive_ready = true, last_error = 'keep-error'"
        )
        self.connection.exec_driver_sql(
            "INSERT INTO youtube_drive_backups "
            "(content_id, external_id, title, origin, source_url, relative_path, size, verified) "
            "VALUES (42, 'video-id', 'Title', 'Channel', 'source-url', 'video.mp4', 12345, true)"
        )
        self.connection.exec_driver_sql(
            "INSERT INTO youtube_storage_transfers "
            "(id, content_id, operation, mode, status, bytes_transferred, total_bytes, "
            "session_uri, lease_token, attempts, updated_at) VALUES "
            "(1, 42, 'UPLOAD', 'BOTH', 'RUNNING', 123, 12345, 'keep-session', "
            "'keep-lease', 2, '2026-01-01 00:00:00')"
        )
        self.connection.exec_driver_sql(
            "INSERT INTO youtube_storage_events (id, content_id, action, created_at) "
            "VALUES (1, 42, 'UPLOAD_QUEUED', '2026-01-01 00:00:00')"
        )
        tables = (
            "youtube_storage_settings",
            "youtube_drive_backups",
            "youtube_storage_transfers",
            "youtube_storage_events",
        )
        before = {
            table: self.connection.exec_driver_sql(f"SELECT * FROM {table}").all()
            for table in tables
        }
        self.upgrade(STORAGE, OAUTH, REMOVE_OAUTH)
        for table in tables:
            self.assertEqual(
                self.connection.exec_driver_sql(f"SELECT * FROM {table}").all(), before[table]
            )

    def test_oauth_migrations_tolerate_existing_or_already_removed_table(self):
        self.upgrade(OAUTH, OAUTH, REMOVE_OAUTH, REMOVE_OAUTH)
        self.assertNotIn(
            "youtube_drive_oauth_sessions", sa.inspect(self.connection).get_table_names()
        )

    def test_offline_postgresql_sql_guards_existing_objects_and_settings(self):
        output = io.StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            STORAGE.upgrade()
            OAUTH.upgrade()
            REMOVE_OAUTH.upgrade()
        sql = output.getvalue()
        for name in STORAGE_COLUMNS:
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {name}", sql)
        self.assertEqual(sql.count("CREATE TABLE IF NOT EXISTS"), 5)
        self.assertEqual(sql.count("CREATE INDEX IF NOT EXISTS"), 3)
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_storage_transfer", sql)
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertIn("DROP TABLE IF EXISTS youtube_drive_oauth_sessions", sql)


if __name__ == "__main__":
    unittest.main()
