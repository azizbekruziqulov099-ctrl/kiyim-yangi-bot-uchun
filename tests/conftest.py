import json
import os

import pytest

from edu import miya
from edu.config import Config
from edu.db import Database

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def sample_lesson():
    with open(os.path.join(ROOT, "tests", "fixtures", "sample_lesson.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def db(tmp_path):
    """SQLite; TEST_DATABASE_URL berilsa — haqiqiy PostgreSQL (jadvallar har sinovda tozalanadi)."""
    url = os.getenv("TEST_DATABASE_URL", "")
    database = Database(url, str(tmp_path / "test.db"))
    if url:
        for table in ("edu_users", "edu_lessons", "edu_usage", "edu_settings", "edu_catalog", "edu_catalog_votes"):
            database.execute(f"TRUNCATE {table} RESTART IDENTITY")
    yield database
    database.close()


@pytest.fixture(scope="session")
def bundled_result():
    with open(miya.BUNDLED_PATH, "rb") as fh:
        return miya.parse_workbook(fh.read())


@pytest.fixture
def seeded_db(db, bundled_result):
    miya.import_lessons(db, bundled_result, "git")
    return db


def make_cfg(tmp_path, **kw) -> Config:
    base = dict(token="123456:TESTTOKEN", admin_ids={1}, sqlite_path=str(tmp_path / "bot.db"),
                openai_key="sk-test", text_provider="openai", image_provider="openai",
                daily_lessons=2, daily_images=2)
    base.update(kw)
    return Config(**base)
