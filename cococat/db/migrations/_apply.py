import logging
import os

logger = logging.getLogger("cococat.db.migrations")

_MIGRATIONS_DIR = os.path.dirname(__file__)


def _migration_files():
    files = [f for f in os.listdir(_MIGRATIONS_DIR) if f.endswith(".sql")]
    files.sort()
    return files


def _version_from_filename(filename):
    return int(filename.split("_")[0])


def apply_migrations(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS __migrations__ ("
        "    version INTEGER PRIMARY KEY,"
        "    applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )

    rows = conn.execute("SELECT version FROM __migrations__").fetchall()
    applied = {row[0] for row in rows}

    for filename in _migration_files():
        version = _version_from_filename(filename)
        if version in applied:
            continue

        filepath = os.path.join(_MIGRATIONS_DIR, filename)
        with open(filepath) as f:
            sql = f.read()

        for stmt in (s.strip() for s in sql.split(";") if s.strip()):
            try:
                conn.execute(stmt)
            except Exception as e:
                logger.debug("Migration %d (%s) statement skipped: %s", version, filename, e)

        conn.execute(
            "INSERT OR IGNORE INTO __migrations__ (version) VALUES (?)",
            (version,),
        )
        conn.commit()

        logger.info("Applied migration %d (%s)", version, filename)
