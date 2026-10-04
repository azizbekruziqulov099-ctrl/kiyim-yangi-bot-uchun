"""Admin bot ichidan o‘zgartira oladigan sozlamalar (bazada saqlanadi, bo‘lmasa server qiymati)."""
from __future__ import annotations

from .config import Config
from .db import Database


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def daily_lessons(db: Database, cfg: Config) -> int:
    return _int(db.get_setting("daily_lessons"), cfg.daily_lessons)


def daily_images(db: Database, cfg: Config) -> int:
    return _int(db.get_setting("daily_images"), cfg.daily_images)


def images_enabled(db: Database, cfg: Config) -> bool:
    value = db.get_setting("images_enabled")
    return cfg.images_enabled if value is None else value == "1"


def image_check(db: Database, cfg: Config) -> bool:
    value = db.get_setting("image_check")
    return cfg.image_check if value is None else value == "1"


def set_int(db: Database, key: str, value: int) -> None:
    db.set_setting(key, str(max(0, min(1000, value))))


def set_bool(db: Database, key: str, value: bool) -> None:
    db.set_setting(key, "1" if value else "0")
