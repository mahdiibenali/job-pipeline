import tempfile
from pathlib import Path

import pytest

from db.connection import configure, close_all
from db.migrations import migrate


@pytest.fixture(autouse=True)
def setup_db():
    tmp = tempfile.mktemp(suffix=".db")
    db_path = Path(tmp)
    configure(db_path)
    migrate()
    yield
    close_all()
    if db_path.exists():
        db_path.unlink()
