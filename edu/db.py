"""
Ma’lumotlar bazasi: PostgreSQL (serverda, DATABASE_URL) yoki SQLite (kompyuterda sinash uchun).

Jadvallar "edu_" bilan boshlanadi — kiyim botining "shop_" jadvallari bilan aralashmaydi,
ikkala bot bitta bazadan foydalansa ham bo‘ladi.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

TASHKENT = timezone(timedelta(hours=5))   # O‘zbekiston vaqti (yozgi vaqt yo‘q)


def today() -> str:
    return datetime.now(TASHKENT).strftime("%Y-%m-%d")


def fmt_date(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%d.%m")


def fmt_datetime(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%d.%m.%Y %H:%M")


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS edu_users (
        user_id BIGINT PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        created_at DOUBLE PRECISION,
        last_seen DOUBLE PRECISION,
        blocked INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS edu_lessons (
        id {AUTOID},
        user_id BIGINT NOT NULL,
        grade INTEGER,
        pair_key TEXT,
        topic TEXT,
        extra TEXT,
        minutes INTEGER,
        data TEXT,
        image_file_id TEXT,
        card_file_id TEXT,
        voice_file_id TEXT,
        image_note TEXT,
        rating INTEGER DEFAULT 0,
        model TEXT,
        created_at DOUBLE PRECISION,
        deleted INTEGER DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS edu_lessons_user_idx ON edu_lessons (user_id, id)",
    """CREATE TABLE IF NOT EXISTS edu_usage (
        user_id BIGINT NOT NULL,
        day TEXT NOT NULL,
        lessons INTEGER DEFAULT 0,
        images INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, day)
    )""",
    """CREATE TABLE IF NOT EXISTS edu_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS edu_catalog (
        id {AUTOID},
        grade INTEGER NOT NULL,
        pair_key TEXT NOT NULL,
        topic TEXT NOT NULL,
        topic_key TEXT NOT NULL,
        minutes INTEGER,
        data TEXT NOT NULL,
        raw TEXT,
        source TEXT,
        image_file_id TEXT,
        image_note TEXT,
        card_file_id TEXT,
        voice_file_ids TEXT,
        views INTEGER DEFAULT 0,
        updated_at DOUBLE PRECISION,
        UNIQUE (grade, pair_key, topic_key)
    )""",
    """CREATE TABLE IF NOT EXISTS edu_catalog_votes (
        user_id BIGINT NOT NULL,
        catalog_id INTEGER NOT NULL,
        value INTEGER NOT NULL,
        PRIMARY KEY (user_id, catalog_id)
    )""",
]

LESSON_FIELDS = ("id", "user_id", "grade", "pair_key", "topic", "extra", "minutes", "data",
                 "image_file_id", "card_file_id", "voice_file_id", "image_note", "rating", "model",
                 "created_at")


class Database:
    def __init__(self, url: str = "", sqlite_path: str = "bot.db"):
        self.url = url or ""
        self.sqlite_path = sqlite_path
        self.kind = "pg" if self.url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._lock = threading.RLock()
        self._conn = None
        self._connect()
        self.init_schema()

    # ─────────────── ulanish ───────────────
    def _connect(self) -> None:
        if self.kind == "pg":
            import psycopg2
            self._conn = psycopg2.connect(self.url, connect_timeout=15)
            self._conn.autocommit = True
        else:
            self._conn = sqlite3.connect(self.sqlite_path, check_same_thread=False, isolation_level=None)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        log.info("Baza: %s", "PostgreSQL" if self.kind == "pg" else f"SQLite ({self.sqlite_path})")

    def _reconnect(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._connect()

    def _sql(self, sql: str) -> str:
        return sql if self.kind == "pg" else sql.replace("%s", "?")

    def _is_conn_error(self, exc: Exception) -> bool:
        if self.kind != "pg":
            return False
        import psycopg2
        return isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))

    def execute(self, sql: str, params: tuple = (), fetch: str | None = None):
        """fetch: None (o‘zgargan qatorlar soni), 'one', 'all'."""
        with self._lock:
            for attempt in (1, 2):
                try:
                    cur = self._conn.cursor()
                    try:
                        cur.execute(self._sql(sql), params)
                        if fetch == "one":
                            return cur.fetchone()
                        if fetch == "lastrowid":
                            return cur.lastrowid
                        if fetch == "all":
                            return cur.fetchall()
                        return cur.rowcount
                    finally:
                        cur.close()
                except Exception as exc:
                    if attempt == 1 and self._is_conn_error(exc):
                        log.warning("Baza ulanishi uzildi, qayta ulanmoqda: %s", exc)
                        self._reconnect()
                        continue
                    raise

    def init_schema(self) -> None:
        autoid = "SERIAL PRIMARY KEY" if self.kind == "pg" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for statement in SCHEMA:
            self.execute(statement.replace("{AUTOID}", autoid))

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # ─────────────── foydalanuvchilar ───────────────
    def touch_user(self, user_id: int, full_name: str = "", username: str = "") -> None:
        now = time.time()
        self.execute(
            """INSERT INTO edu_users (user_id, full_name, username, created_at, last_seen, blocked)
               VALUES (%s, %s, %s, %s, %s, 0)
               ON CONFLICT (user_id) DO UPDATE SET full_name = EXCLUDED.full_name,
                   username = EXCLUDED.username, last_seen = EXCLUDED.last_seen""",
            (user_id, full_name[:200], (username or "")[:100], now, now),
        )

    def is_blocked(self, user_id: int) -> bool:
        row = self.execute("SELECT blocked FROM edu_users WHERE user_id = %s", (user_id,), fetch="one")
        return bool(row and row[0])

    def set_blocked(self, user_id: int, blocked: bool) -> bool:
        return self.execute("UPDATE edu_users SET blocked = %s WHERE user_id = %s",
                            (1 if blocked else 0, user_id)) > 0

    def user_ids(self) -> list[int]:
        rows = self.execute("SELECT user_id FROM edu_users WHERE blocked = 0", fetch="all")
        return [r[0] for r in rows]

    def user_name(self, user_id: int) -> str:
        row = self.execute("SELECT full_name, username FROM edu_users WHERE user_id = %s", (user_id,), fetch="one")
        if not row:
            return str(user_id)
        name, username = row
        return f"{name or user_id}" + (f" (@{username})" if username else "")

    # ─────────────── darslar ───────────────
    def save_lesson(self, user_id: int, grade: int, pair_key: str, topic: str, extra: str,
                    minutes: int, lesson: dict, model: str = "") -> int:
        sql = """INSERT INTO edu_lessons (user_id, grade, pair_key, topic, extra, minutes, data, model, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        params = (user_id, grade, pair_key, topic, extra, minutes, json.dumps(lesson, ensure_ascii=False),
                  model, time.time())
        if self.kind == "pg":
            return int(self.execute(sql + " RETURNING id", params, fetch="one")[0])
        return int(self.execute(sql, params, fetch="lastrowid"))

    def _row_to_lesson(self, row) -> dict | None:
        if not row:
            return None
        item = dict(zip(LESSON_FIELDS, row))
        try:
            item["lesson"] = json.loads(item.pop("data") or "{}")
        except ValueError:
            item["lesson"] = {}
        return item

    def get_lesson(self, lesson_id: int) -> dict | None:
        row = self.execute(f"SELECT {', '.join(LESSON_FIELDS)} FROM edu_lessons WHERE id = %s AND deleted = 0",
                           (lesson_id,), fetch="one")
        return self._row_to_lesson(row)

    def update_lesson(self, lesson_id: int, **fields) -> None:
        allowed = {"image_file_id", "card_file_id", "voice_file_id", "image_note", "rating", "data"}
        sets, params = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(key)
            if key == "data" and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            sets.append(f"{key} = %s")
            params.append(value)
        if sets:
            self.execute(f"UPDATE edu_lessons SET {', '.join(sets)} WHERE id = %s", (*params, lesson_id))

    def list_lessons(self, user_id: int | None, limit: int = 8, offset: int = 0) -> list[dict]:
        cols = "id, user_id, grade, pair_key, topic, created_at, rating"
        if user_id is None:
            rows = self.execute(f"SELECT {cols} FROM edu_lessons WHERE deleted = 0 ORDER BY id DESC LIMIT %s OFFSET %s",
                                (limit, offset), fetch="all")
        else:
            rows = self.execute(f"SELECT {cols} FROM edu_lessons WHERE user_id = %s AND deleted = 0 "
                                f"ORDER BY id DESC LIMIT %s OFFSET %s", (user_id, limit, offset), fetch="all")
        keys = ("id", "user_id", "grade", "pair_key", "topic", "created_at", "rating")
        return [dict(zip(keys, r)) for r in rows]

    def count_lessons(self, user_id: int | None = None) -> int:
        if user_id is None:
            row = self.execute("SELECT COUNT(*) FROM edu_lessons WHERE deleted = 0", fetch="one")
        else:
            row = self.execute("SELECT COUNT(*) FROM edu_lessons WHERE user_id = %s AND deleted = 0",
                               (user_id,), fetch="one")
        return int(row[0]) if row else 0

    def delete_lesson(self, lesson_id: int) -> None:
        self.execute("UPDATE edu_lessons SET deleted = 1 WHERE id = %s", (lesson_id,))

    # ─────────────── kunlik limitlar ───────────────
    def try_consume(self, user_id: int, kind: str, limit: int) -> bool:
        """Limit bo‘yicha bitta urinishni band qiladi. Limit tugagan bo‘lsa False."""
        if kind not in ("lessons", "images"):
            raise ValueError(kind)
        day = today()
        self.execute("INSERT INTO edu_usage (user_id, day, lessons, images) VALUES (%s, %s, 0, 0) "
                     "ON CONFLICT (user_id, day) DO NOTHING", (user_id, day))
        changed = self.execute(f"UPDATE edu_usage SET {kind} = {kind} + 1 "
                               f"WHERE user_id = %s AND day = %s AND {kind} < %s", (user_id, day, limit))
        return changed == 1

    def add_usage(self, user_id: int, kind: str) -> None:
        """Limitsiz (admin) foydalanuvchi uchun faqat statistikaga yozadi."""
        if kind not in ("lessons", "images"):
            raise ValueError(kind)
        day = today()
        self.execute("INSERT INTO edu_usage (user_id, day, lessons, images) VALUES (%s, %s, 0, 0) "
                     "ON CONFLICT (user_id, day) DO NOTHING", (user_id, day))
        self.execute(f"UPDATE edu_usage SET {kind} = {kind} + 1 WHERE user_id = %s AND day = %s", (user_id, day))

    def refund(self, user_id: int, kind: str) -> None:
        if kind not in ("lessons", "images"):
            raise ValueError(kind)
        self.execute(f"UPDATE edu_usage SET {kind} = {kind} - 1 WHERE user_id = %s AND day = %s AND {kind} > 0",
                     (user_id, today()))

    def usage_today(self, user_id: int) -> tuple[int, int]:
        row = self.execute("SELECT lessons, images FROM edu_usage WHERE user_id = %s AND day = %s",
                           (user_id, today()), fetch="one")
        return (int(row[0]), int(row[1])) if row else (0, 0)

    # ─────────────── sozlamalar ───────────────
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.execute("SELECT value FROM edu_settings WHERE key = %s", (key,), fetch="one")
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute("INSERT INTO edu_settings (key, value) VALUES (%s, %s) "
                     "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, str(value)))

    # ─────────────── miya (tayyor darslar katalogi) ───────────────
    CATALOG_FIELDS = ("id", "grade", "pair_key", "topic", "topic_key", "minutes", "data", "raw", "source",
                      "image_file_id", "image_note", "card_file_id", "voice_file_ids", "views", "updated_at")

    def _catalog_row(self, row) -> dict | None:
        if not row:
            return None
        item = dict(zip(self.CATALOG_FIELDS, row))
        try:
            item["lesson"] = json.loads(item.pop("data") or "{}")
        except ValueError:
            item["lesson"] = {}
        try:
            item["raw"] = json.loads(item["raw"]) if item.get("raw") else {}
        except ValueError:
            item["raw"] = {}
        try:
            item["voice_file_ids"] = json.loads(item["voice_file_ids"]) if item.get("voice_file_ids") else {}
        except ValueError:
            item["voice_file_ids"] = {}
        return item

    def upsert_catalog(self, grade: int, pair_key: str, topic: str, topic_key: str, minutes: int,
                       lesson: dict, raw: dict, source: str) -> str:
        """Tayyor darsni qo‘shadi yoki yangilaydi. Qaytaradi: 'new' | 'updated' | 'same'."""
        data = json.dumps(lesson, ensure_ascii=False)
        raw_json = json.dumps(raw, ensure_ascii=False, default=str)
        row = self.execute("SELECT id, raw, data FROM edu_catalog WHERE grade = %s AND pair_key = %s AND topic_key = %s",
                           (grade, pair_key, topic_key), fetch="one")
        now = time.time()
        if row is None:
            self.execute("""INSERT INTO edu_catalog (grade, pair_key, topic, topic_key, minutes, data, raw, source, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                         (grade, pair_key, topic, topic_key, minutes, data, raw_json, source, now))
            return "new"
        cat_id, old_raw, old_data = row
        if old_raw == raw_json and old_data == data:
            return "same"
        try:
            old = json.loads(old_data or "{}")
        except ValueError:
            old = {}
        picture_changed = (old.get("image", {}).get("scene_en") != lesson.get("image", {}).get("scene_en")
                           or old.get("exhibit") != lesson.get("exhibit"))
        extra = ", image_file_id = NULL, image_note = NULL" if picture_changed else ""
        self.execute(f"""UPDATE edu_catalog SET topic = %s, minutes = %s, data = %s, raw = %s, source = %s,
                         updated_at = %s, card_file_id = NULL, voice_file_ids = NULL{extra} WHERE id = %s""",
                     (topic, minutes, data, raw_json, source, now, cat_id))
        return "updated"

    def get_catalog(self, catalog_id: int) -> dict | None:
        row = self.execute(f"SELECT {', '.join(self.CATALOG_FIELDS)} FROM edu_catalog WHERE id = %s",
                           (catalog_id,), fetch="one")
        return self._catalog_row(row)

    def find_catalog(self, grade: int, pair_key: str, topic_key: str) -> dict | None:
        row = self.execute(f"SELECT {', '.join(self.CATALOG_FIELDS)} FROM edu_catalog "
                           f"WHERE grade = %s AND pair_key = %s AND topic_key = %s", (grade, pair_key, topic_key),
                           fetch="one")
        return self._catalog_row(row)

    def catalog_topics(self, grade: int, pair_key: str) -> list[tuple[int, str, str]]:
        """[(id, mavzu, topic_key)] — sinf va fan juftligi bo‘yicha."""
        rows = self.execute("SELECT id, topic, topic_key FROM edu_catalog WHERE grade = %s AND pair_key = %s "
                            "ORDER BY id", (grade, pair_key), fetch="all")
        return [(r[0], r[1], r[2]) for r in rows]

    def catalog_topics_all(self) -> list[tuple[int, int, str, str, str]]:
        rows = self.execute("SELECT id, grade, pair_key, topic, topic_key FROM edu_catalog ORDER BY id", fetch="all")
        return [tuple(r) for r in rows]

    def update_catalog(self, catalog_id: int, **fields) -> None:
        allowed = {"image_file_id", "image_note", "card_file_id", "voice_file_ids"}
        sets, params = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(key)
            if key == "voice_file_ids" and not isinstance(value, (str, type(None))):
                value = json.dumps(value)
            sets.append(f"{key} = %s")
            params.append(value)
        if sets:
            self.execute(f"UPDATE edu_catalog SET {', '.join(sets)} WHERE id = %s", (*params, catalog_id))

    def add_catalog_view(self, catalog_id: int) -> None:
        self.execute("UPDATE edu_catalog SET views = views + 1 WHERE id = %s", (catalog_id,))

    def count_catalog(self) -> int:
        row = self.execute("SELECT COUNT(*) FROM edu_catalog", fetch="one")
        return int(row[0]) if row else 0

    def catalog_counts(self) -> list[tuple[str, int, int]]:
        rows = self.execute("SELECT pair_key, grade, COUNT(*) FROM edu_catalog GROUP BY pair_key, grade", fetch="all")
        return [(r[0], int(r[1]), int(r[2])) for r in rows]

    def catalog_raw_rows(self) -> list[dict]:
        rows = self.execute("SELECT raw, data FROM edu_catalog ORDER BY id", fetch="all")
        out = []
        for raw, data in rows:
            try:
                out.append({"raw": json.loads(raw) if raw else {}, "lesson": json.loads(data or "{}")})
            except ValueError:
                continue
        return out

    def delete_catalog(self, catalog_id: int) -> None:
        self.execute("DELETE FROM edu_catalog WHERE id = %s", (catalog_id,))
        self.execute("DELETE FROM edu_catalog_votes WHERE catalog_id = %s", (catalog_id,))

    def vote_catalog(self, user_id: int, catalog_id: int, value: int) -> None:
        self.execute("INSERT INTO edu_catalog_votes (user_id, catalog_id, value) VALUES (%s, %s, %s) "
                     "ON CONFLICT (user_id, catalog_id) DO UPDATE SET value = EXCLUDED.value",
                     (user_id, catalog_id, value))

    def top_catalog(self, limit: int = 5) -> list[tuple[str, int, int]]:
        rows = self.execute("SELECT topic, grade, views FROM edu_catalog WHERE views > 0 ORDER BY views DESC LIMIT %s",
                            (limit,), fetch="all")
        return [(r[0], int(r[1]), int(r[2])) for r in rows]

    # ─────────────── statistika ───────────────
    def stats(self) -> dict:
        now = time.time()
        day_start = datetime.now(TASHKENT).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        week = now - 7 * 86400

        def one(sql: str, params: tuple = ()) -> int:
            row = self.execute(sql, params, fetch="one")
            return int(row[0] or 0) if row else 0

        result = {
            "users": one("SELECT COUNT(*) FROM edu_users"),
            "users_today": one("SELECT COUNT(*) FROM edu_users WHERE created_at >= %s", (day_start,)),
            "users_week": one("SELECT COUNT(*) FROM edu_users WHERE created_at >= %s", (week,)),
            "active_today": one("SELECT COUNT(*) FROM edu_users WHERE last_seen >= %s", (day_start,)),
            "blocked": one("SELECT COUNT(*) FROM edu_users WHERE blocked = 1"),
            "lessons": one("SELECT COUNT(*) FROM edu_lessons"),
            "lessons_today": one("SELECT COUNT(*) FROM edu_lessons WHERE created_at >= %s", (day_start,)),
            "lessons_week": one("SELECT COUNT(*) FROM edu_lessons WHERE created_at >= %s", (week,)),
            "images": one("SELECT COALESCE(SUM(images), 0) FROM edu_usage"),
            "images_today": one("SELECT COALESCE(SUM(images), 0) FROM edu_usage WHERE day = %s", (today(),)),
            "likes": one("SELECT COUNT(*) FROM edu_lessons WHERE rating > 0")
                     + one("SELECT COUNT(*) FROM edu_catalog_votes WHERE value > 0"),
            "dislikes": one("SELECT COUNT(*) FROM edu_lessons WHERE rating < 0")
                        + one("SELECT COUNT(*) FROM edu_catalog_votes WHERE value < 0"),
            "catalog": one("SELECT COUNT(*) FROM edu_catalog"),
            "catalog_views": one("SELECT COALESCE(SUM(views), 0) FROM edu_catalog"),
            "catalog_images": one("SELECT COUNT(*) FROM edu_catalog WHERE image_file_id IS NOT NULL"),
        }
        result["top_pairs"] = self.execute(
            "SELECT pair_key, COUNT(*) AS n FROM edu_lessons GROUP BY pair_key ORDER BY n DESC LIMIT 3", fetch="all")
        result["grades"] = self.execute(
            "SELECT grade, COUNT(*) AS n FROM edu_lessons GROUP BY grade ORDER BY grade", fetch="all")
        return result
