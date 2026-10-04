"""
Bot sozlamalari — hammasi server "Variables" (environment) bo‘limidan olinadi.

Majburiy:
    TOKEN            — BotFather bergan token
    ADMIN_ID         — admin Telegram ID raqami (bir nechta bo‘lsa ADMIN_IDS=1,2,3)
    OPENAI_API_KEY   yoki GEMINI_API_KEY — AI kaliti (kamida bittasi)

Ixtiyoriy:
    DATABASE_URL     — PostgreSQL (bo‘lmasa bot.db SQLite fayli ishlatiladi)
    AI_PROVIDER      — openai | gemini (ikkala kalit bo‘lsa qaysi biri ishlasin)
    EDU_TEXT_MODEL, EDU_IMAGE_MODEL, EDU_VISION_MODEL, EDU_STT_MODEL — modelni qo‘lda tanlash
    EDU_IMAGE_QUALITY — low | medium | high (OpenAI rasm sifati, standart: medium)
    EDU_DAILY_LESSONS, EDU_DAILY_IMAGES — bitta foydalanuvchi uchun kunlik limit
    EDU_MAX_PARALLEL — bir vaqtda nechta dars tayyorlanishi mumkin
    EDU_IMAGE_CHECK  — 1/0: AI rasmdagi sonlarni tekshirish
    EDU_IMAGE_RETRY  — 1/0: sonlar mos kelmasa rasmni bir marta qayta chizish
    EDU_TTS_VOICE    — ovoz: uz-UZ-MadinaNeural yoki uz-UZ-SardorNeural
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().strip('"').strip("'").strip()
    return value or default


def _int(name: str, default: int, minimum: int = 0, maximum: int = 10_000) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError:
        log.warning("%s noto‘g‘ri son: %r — standart %s olindi", name, raw, default)
        return default


def _bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "ha", "on")


def _ids(*names: str) -> set[int]:
    result: set[int] = set()
    for name in names:
        for part in _env(name).replace(";", ",").split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                result.add(int(part))
    return result


@dataclass
class Config:
    token: str = ""
    admin_ids: set[int] = field(default_factory=set)
    database_url: str = ""
    sqlite_path: str = "bot.db"

    openai_key: str = ""
    gemini_key: str = ""
    text_provider: str = ""
    image_provider: str = ""
    text_model: str = ""
    image_model: str = ""
    vision_model: str = ""
    stt_model: str = ""
    image_quality: str = "medium"
    reasoning_effort: str = "low"

    images_enabled: bool = True
    image_check: bool = True
    image_retry: bool = True
    daily_lessons: int = 5
    daily_images: int = 8
    max_parallel: int = 3
    tts_voice: str = "uz-UZ-MadinaNeural"

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    @property
    def ai_ready(self) -> bool:
        return bool(self.text_provider)


def load_config() -> Config:
    openai_key = _env("OPENAI_API_KEY")
    gemini_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")

    preferred = _env("AI_PROVIDER").lower()
    available = [name for name, key in (("openai", openai_key), ("gemini", gemini_key)) if key]
    if preferred in available:
        default_provider = preferred
    else:
        default_provider = available[0] if available else ""

    def provider(var: str) -> str:
        value = _env(var).lower()
        return value if value in available else default_provider

    quality = _env("EDU_IMAGE_QUALITY", "medium").lower()
    if quality not in ("low", "medium", "high", "auto"):
        quality = "medium"

    cfg = Config(
        token=_env("TOKEN") or _env("BOT_TOKEN"),
        admin_ids=_ids("ADMIN_ID", "ADMIN_IDS"),
        database_url=_env("DATABASE_URL"),
        sqlite_path=_env("SQLITE_PATH", "bot.db"),
        openai_key=openai_key,
        gemini_key=gemini_key,
        text_provider=provider("EDU_TEXT_PROVIDER"),
        image_provider=provider("EDU_IMAGE_PROVIDER"),
        text_model=_env("EDU_TEXT_MODEL"),
        image_model=_env("EDU_IMAGE_MODEL"),
        vision_model=_env("EDU_VISION_MODEL"),
        stt_model=_env("EDU_STT_MODEL"),
        image_quality=quality,
        reasoning_effort=_env("EDU_REASONING_EFFORT", "low").lower(),
        images_enabled=_bool("EDU_IMAGES", True),
        image_check=_bool("EDU_IMAGE_CHECK", True),
        image_retry=_bool("EDU_IMAGE_RETRY", True),
        daily_lessons=_int("EDU_DAILY_LESSONS", 5, 0, 1000),
        daily_images=_int("EDU_DAILY_IMAGES", 8, 0, 1000),
        max_parallel=_int("EDU_MAX_PARALLEL", 3, 1, 20),
        tts_voice=_env("EDU_TTS_VOICE", "uz-UZ-MadinaNeural"),
    )
    return cfg
