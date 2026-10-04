"""
Dars va rasm tayyorlash jarayoni (orqa fonda ishlaydi, boshqa foydalanuvchilarni kuttirmaydi).

AI dars: 1) AI matn → 2) matn bo‘limlari → 3) aniq karta → 4) AI rasm (+ sonlarni tekshirish) → 5) tugmalar.
Tayyor dars (miya): hammasi bazadan darhol olinadi, AI chaqirilmaydi.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError

from . import card, imaging, prompts, settings, subjects
from . import keyboards as kb
from . import lesson as L
from .ai import AIError, AIService
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

HTML = ParseMode.HTML


def deps(bot_data: dict) -> tuple[Config, Database, AIService]:
    return bot_data["cfg"], bot_data["db"], bot_data["ai"]


async def safe_edit(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, parse_mode=HTML,
                                    reply_markup=reply_markup)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            log.debug("Xabarni tahrirlab bo‘lmadi: %s", exc)
    except TelegramError as exc:
        log.debug("Xabarni tahrirlab bo‘lmadi: %s", exc)


async def safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError:
        pass


async def notify_admins(bot: Bot, bot_data: dict, err: AIError) -> None:
    """Kalit/limit muammolari haqida adminni ogohlantiradi (15 daqiqada bir martadan ko‘p emas)."""
    if err.kind not in ("auth", "quota", "not_configured", "model"):
        return
    cfg: Config = bot_data["cfg"]
    last: dict = bot_data.setdefault("admin_notified", {})
    now = time.time()
    if now - last.get(err.kind, 0) < 900:
        return
    last[err.kind] = now
    text = (f"⚠️ <b>AI xatosi</b> ({html.escape(err.kind)})\n{html.escape(err.user_message)}\n\n"
            f"<code>{html.escape(err.detail[:500])}</code>")
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text, parse_mode=HTML)
        except TelegramError:
            pass


def track(bot_data: dict, task: asyncio.Task) -> None:
    jobs: set = bot_data.setdefault("jobs", set())
    jobs.add(task)
    task.add_done_callback(jobs.discard)


def start_task(app: Any, coro, bot_data: dict) -> asyncio.Task:
    task = app.create_task(coro)
    track(bot_data, task)
    return task


# ───────────────────────── Dars manbasi (AI darsi yoki miya) ─────────────────────────

def load_ref(db: Database, kind: str, ref_id: int) -> dict | None:
    """'l' — foydalanuvchining AI darsi, 'c' — miyadagi tayyor dars. Ikkalasi bir xil ko‘rinishda qaytadi."""
    row = db.get_lesson(ref_id) if kind == "l" else db.get_catalog(ref_id)
    if not row:
        return None
    row["kind"] = kind
    if kind == "l":
        voice = row.get("voice_file_id")
        try:
            row["voice_file_ids"] = json.loads(voice) if voice and voice.startswith("{") else {}
        except ValueError:
            row["voice_file_ids"] = {}
    return row


def save_ref(db: Database, row: dict, **fields) -> None:
    if row["kind"] == "l":
        if "voice_file_ids" in fields:
            fields["voice_file_id"] = json.dumps(fields.pop("voice_file_ids"))
        db.update_lesson(row["id"], **fields)
    else:
        db.update_catalog(row["id"], **fields)
    row.update(fields)


def can_draw(cfg: Config, db: Database) -> bool:
    return bool(cfg.ai_ready and settings.images_enabled(db, cfg))


def actions_markup(cfg: Config, db: Database, row: dict, user_id: int, archive: bool = False,
                   back: str = "a:0"):
    return kb.lesson_actions(row["kind"], row["id"], has_image=bool(row.get("image_file_id")),
                             can_draw=can_draw(cfg, db), is_admin=cfg.is_admin(user_id), archive=archive, back=back)


# ───────────────────────── Rasm ─────────────────────────

async def check_counts(ai: AIService, image: bytes, groups: list[dict]) -> dict | None:
    result = await ai.check_image(prompts.build_vision_prompt(groups), image, prompts.vision_schema())
    if not isinstance(result, dict):
        return None
    counted: dict[int, int] = {}
    for item in result.get("groups") or []:
        if isinstance(item, dict):
            try:
                counted[int(item.get("index", 0))] = int(item.get("counted", -1))
            except (TypeError, ValueError):
                continue
    rows, errors = [], 0
    for i, g in enumerate(groups, start=1):
        seen = counted.get(i)
        ok = seen == g["count"]
        errors += 0 if ok else 1
        rows.append({"label": g["label"], "expected": g["count"], "seen": seen, "ok": ok})
    has_text = bool(result.get("has_text"))
    return {"ok": errors == 0, "score": errors + (1 if has_text else 0), "rows": rows, "has_text": has_text}


def check_note(result: dict | None, groups: list[dict]) -> str:
    if not groups:
        return ""
    if result is None:
        return "ℹ️ Aniq sanash uchun 🧮 kartadan foydalaning."
    if result["ok"]:
        parts = ", ".join(f"{r['label']} — {r['expected']}" for r in result["rows"])
        return f"✅ Rasm tekshirildi: sonlar mos ({parts})."
    bad = [r for r in result["rows"] if not r["ok"]]
    parts = "; ".join(
        f"{r['label']}: kerak {r['expected']}, rasmda {r['seen'] if r['seen'] is not None else '?'}" for r in bad)
    return f"⚠️ Rasmdagi sonlar farq qilishi mumkin ({parts}). Sanash uchun 🧮 kartadan foydalaning."


async def make_image(ai: AIService, lesson: dict, do_check: bool, retry: bool) -> tuple[bytes, str, str]:
    """AI rasm chizadi va (kerak bo‘lsa) sonlarini tekshiradi. Qaytaradi: (jpeg, izoh, model)."""
    grade = lesson["meta"]["grade"]
    raw, model = await ai.image(prompts.build_image_prompt(lesson, grade))
    image = await asyncio.to_thread(imaging.to_jpeg, raw)
    groups = prompts.drawable_groups(lesson)
    result = None
    if groups and do_check:
        result = await check_counts(ai, image, groups)
        if result is not None and (not result["ok"] or result["has_text"]) and retry:
            log.info("Rasm sonlari mos emas (%s) — qayta chiziladi", result["rows"])
            try:
                raw2, _ = await ai.image(prompts.build_image_prompt(lesson, grade, strict=True))
                image2 = await asyncio.to_thread(imaging.to_jpeg, raw2)
                result2 = await check_counts(ai, image2, groups)
                if result2 is not None and result2["score"] < result["score"]:
                    image, result = image2, result2
            except AIError as err:
                log.warning("Qayta chizish bo‘lmadi: %s", err)
    return image, check_note(result if do_check else None, groups), model


async def send_image(bot: Bot, chat_id: int, lesson: dict, image, note: str, reply_markup=None) -> str:
    """Rasmni yuboradi (bayt yoki file_id). Qaytaradi: file_id."""
    caption, questions_included = L.fmt_image_caption(lesson, html.escape(note or "", quote=False))
    msg = await bot.send_photo(chat_id, photo=image, caption=caption, parse_mode=HTML, reply_markup=reply_markup)
    if not questions_included:
        text = L.image_questions_text(lesson)
        if text:
            await bot.send_message(chat_id, text, parse_mode=HTML)
    return msg.photo[-1].file_id


def card_footer(lesson: dict) -> str:
    meta = lesson["meta"]
    return f"Fanlar integratsiyasi · {meta['grade']}-sinf · {subjects.pair_label(meta['pair'])}"


async def render_card(lesson: dict) -> bytes | None:
    if not L.has_card(lesson):
        return None
    return await asyncio.to_thread(card.render_lesson_card, lesson, card_footer(lesson))


async def send_card(bot: Bot, db: Database, chat_id: int, row: dict) -> None:
    """Ko‘rgazma/hisob kartasini yuboradi (avval chizilgan bo‘lsa — darhol file_id orqali)."""
    lesson = row["lesson"]
    if not L.has_card(lesson):
        return
    caption = L.fmt_card_caption(lesson)
    if row.get("card_file_id"):
        try:
            await bot.send_photo(chat_id, photo=row["card_file_id"], caption=caption, parse_mode=HTML)
            return
        except TelegramError:
            log.info("Karta file_id eskirgan — qayta chiziladi")
    png = await render_card(lesson)
    if png is None:
        return
    msg = await bot.send_photo(chat_id, photo=png, caption=caption, parse_mode=HTML)
    save_ref(db, row, card_file_id=msg.photo[-1].file_id)


async def send_lesson_text(bot: Bot, chat_id: int, lesson: dict) -> None:
    for chunk in L.lesson_messages(lesson):
        await bot.send_message(chat_id, chunk, parse_mode=HTML)


def final_text(lesson: dict, has_image: bool, can_draw_image: bool) -> str:
    lines = [f"✅ <b>Dars tayyor:</b> {L.h(lesson['title'])}",
             "",
             "✅ Javoblar — topshiriqlar javoblari (o‘qituvchi uchun)",
             "📄 Word fayl — dars ishlanmasi (kartasi va rasmi bilan)",
             "🔊 Ovozli o‘qish — matn yoki topshiriqlarni bolalarga eshittirish"]
    if has_image:
        lines.append("🖼 Dars rasmi — AI chizgan rasm")
    elif can_draw_image:
        lines.append("🎨 AI rasm chizish — darsga sahna rasmi qo‘shish")
    problems = L.math_problems(lesson)
    if problems:
        nums = ", ".join(str(n) for n in problems)
        lines += ["", f"⚠️ {nums}-topshiriq javobida hisob farqi bor — «✅ Javoblar»da ko‘rsatilgan, tekshirib oling."]
    lines += ["", "<i>Darsdan oldin material va sonlarni bir ko‘rib chiqing.</i>"]
    return "\n".join(lines)


# ───────────────────────── Tayyor dars (miya) ─────────────────────────

async def deliver_ready(bot: Bot, bot_data: dict, chat_id: int, user_id: int, catalog_id: int) -> bool:
    cfg, db, _ = deps(bot_data)
    row = load_ref(db, "c", catalog_id)
    if not row:
        await bot.send_message(chat_id, "Bu tayyor dars topilmadi (miya yangilangan bo‘lishi mumkin).")
        return False
    lesson = row["lesson"]
    await send_lesson_text(bot, chat_id, lesson)
    try:
        await send_card(bot, db, chat_id, row)
    except Exception:
        log.exception("Karta yuborilmadi")
    if row.get("image_file_id"):
        try:
            await send_image(bot, chat_id, lesson, row["image_file_id"], row.get("image_note") or "")
        except TelegramError:
            save_ref(db, row, image_file_id=None, image_note=None)
    await bot.send_message(chat_id, final_text(lesson, bool(row.get("image_file_id")), can_draw(cfg, db)),
                           parse_mode=HTML, reply_markup=actions_markup(cfg, db, row, user_id))
    db.add_catalog_view(catalog_id)
    return True


async def show_full(bot: Bot, bot_data: dict, chat_id: int, user_id: int, row: dict) -> None:
    """Saqlangan darsni (AI yoki tayyor) qayta to‘liq ko‘rsatadi."""
    cfg, db, _ = deps(bot_data)
    lesson = row["lesson"]
    await send_lesson_text(bot, chat_id, lesson)
    await send_card(bot, db, chat_id, row)
    if row.get("image_file_id"):
        await send_image(bot, chat_id, lesson, row["image_file_id"], row.get("image_note") or "")
    await bot.send_message(chat_id, final_text(lesson, bool(row.get("image_file_id")), can_draw(cfg, db)),
                           parse_mode=HTML, reply_markup=actions_markup(cfg, db, row, user_id))


# ───────────────────────── AI bilan yangi dars ─────────────────────────

async def lesson_job(bot: Bot, bot_data: dict, chat_id: int, user_id: int, wiz: dict, status_id: int,
                     unlimited: bool) -> None:
    cfg, db, ai = deps(bot_data)
    running: set = bot_data["running"]
    delivered = False
    try:
        async with bot_data["sem"]:
            await safe_edit(bot, chat_id, status_id,
                            "⏳ <b>1/3</b> · Dars matni tayyorlanmoqda…\n<i>Odatda 1–2 daqiqa davom etadi.</i>")
            user_prompt = prompts.build_lesson_prompt(wiz["grade"], wiz["pair"], wiz["topic"], wiz["minutes"],
                                                      wiz.get("extra", ""), wiz.get("image", True))
            raw, model = await ai.lesson(prompts.SYSTEM_PROMPT, user_prompt, prompts.lesson_schema())
            lesson = L.normalize_lesson(raw, grade=wiz["grade"], pair_key=wiz["pair"], topic=wiz["topic"],
                                        minutes=wiz["minutes"])
            lesson_id = db.save_lesson(user_id, wiz["grade"], wiz["pair"], wiz["topic"], wiz.get("extra", ""),
                                       wiz["minutes"], lesson, model)
            row = load_ref(db, "l", lesson_id)
            await send_lesson_text(bot, chat_id, lesson)
            delivered = True
            try:
                await send_card(bot, db, chat_id, row)
            except Exception:
                log.exception("Hisob kartasini yuborib bo‘lmadi")

            if wiz.get("image", True) and can_draw(cfg, db):
                if unlimited or db.try_consume(user_id, "images", settings.daily_images(db, cfg)):
                    if unlimited:
                        db.add_usage(user_id, "images")
                    await safe_edit(bot, chat_id, status_id,
                                    "🎨 <b>2/3</b> · Dars rasmi chizilmoqda…\n<i>30–90 soniya.</i>")
                    try:
                        image, note, _ = await make_image(ai, lesson, settings.image_check(db, cfg), cfg.image_retry)
                        await safe_edit(bot, chat_id, status_id, "📤 <b>3/3</b> · Yuborilmoqda…")
                        file_id = await send_image(bot, chat_id, lesson, image, note)
                        save_ref(db, row, image_file_id=file_id, image_note=note)
                    except AIError as err:
                        if not unlimited:
                            db.refund(user_id, "images")
                        await bot.send_message(
                            chat_id, f"⚠️ Rasm chizilmadi: {L.h(err.user_message)}\n"
                                     f"Dars tayyor — keyinroq «🎨 AI rasm chizish» tugmasi bilan qayta urinib ko‘ring.",
                            parse_mode=HTML)
                        await notify_admins(bot, bot_data, err)
                else:
                    await bot.send_message(chat_id, "ℹ️ Bugungi rasm limiti tugagan, shuning uchun AI rasm "
                                                    "chizilmadi. Kartadan foydalanishingiz mumkin.")
            await bot.send_message(chat_id, final_text(lesson, bool(row.get("image_file_id")), can_draw(cfg, db)),
                                   parse_mode=HTML, reply_markup=actions_markup(cfg, db, row, user_id))
            await safe_delete(bot, chat_id, status_id)
    except AIError as err:
        log.warning("Dars tayyorlanmadi: %s", err)
        if not delivered and not unlimited:
            db.refund(user_id, "lessons")
        await safe_edit(bot, chat_id, status_id,
                        f"❌ <b>Dars tayyorlanmadi.</b>\n{L.h(err.user_message)}\n\n"
                        f"Qayta urinish: «📚 Dars tayyorlash». Limit hisobiga yozilmadi.")
        await notify_admins(bot, bot_data, err)
    except L.LessonError as err:
        log.warning("AI javobi to‘liq emas: %s", err)
        if not delivered and not unlimited:
            db.refund(user_id, "lessons")
        await safe_edit(bot, chat_id, status_id, "❌ AI javobi to‘liq kelmadi. Iltimos, qayta urinib ko‘ring "
                                                 "(limit hisobiga yozilmadi).")
    except Exception:
        log.exception("Dars tayyorlashda kutilmagan xato")
        if not delivered and not unlimited:
            db.refund(user_id, "lessons")
        await safe_edit(bot, chat_id, status_id, "❌ Kutilmagan xato yuz berdi. Birozdan so‘ng qayta urinib ko‘ring.")
    finally:
        running.discard(user_id)


async def image_job(bot: Bot, bot_data: dict, chat_id: int, user_id: int, kind: str, ref_id: int, status_id: int,
                    unlimited: bool) -> None:
    """AI rasm chizish. Tayyor dars uchun chizilgan rasm saqlanadi va keyingi o‘qituvchilarga bepul ko‘rsatiladi."""
    cfg, db, ai = deps(bot_data)
    running: set = bot_data["running"]
    try:
        row = load_ref(db, kind, ref_id)
        if not row:
            await safe_edit(bot, chat_id, status_id, "Dars topilmadi.")
            if not unlimited:
                db.refund(user_id, "images")
            return
        lesson = row["lesson"]
        async with bot_data["sem"]:
            await safe_edit(bot, chat_id, status_id, "🎨 Rasm chizilmoqda…\n<i>30–90 soniya.</i>")
            image, note, _ = await make_image(ai, lesson, settings.image_check(db, cfg), cfg.image_retry)
            row["image_file_id"] = "pending"
            file_id = await send_image(bot, chat_id, lesson, image, note,
                                       reply_markup=actions_markup(cfg, db, row, user_id))
            save_ref(db, row, image_file_id=file_id, image_note=note)
            await safe_delete(bot, chat_id, status_id)
    except AIError as err:
        if not unlimited:
            db.refund(user_id, "images")
        await safe_edit(bot, chat_id, status_id, f"⚠️ Rasm chizilmadi: {L.h(err.user_message)}")
        await notify_admins(bot, bot_data, err)
    except Exception:
        log.exception("Rasm chizishda kutilmagan xato")
        if not unlimited:
            db.refund(user_id, "images")
        await safe_edit(bot, chat_id, status_id, "❌ Rasm chizishda kutilmagan xato yuz berdi.")
    finally:
        running.discard(user_id)
