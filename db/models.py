import logging

from db.connection import configure, get_connection
from db.migrations import migrate

log = logging.getLogger(__name__)


def init_db(db_path: str | None = None) -> None:
    from pathlib import Path

    from config.settings import get_settings

    settings = get_settings()
    path = Path(db_path) if db_path else settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)

    configure(path)
    migrate()

    log.info("Database initialized at: %s", path)
