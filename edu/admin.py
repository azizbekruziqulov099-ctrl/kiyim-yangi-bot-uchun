"""Admin paneli: statistika, reklama, miya (tayyor darslar), sozlamalar, AI holati."""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes

from . import miya, pipeline, settings, subjects, tts
from . import lesson as L
from .db import fmt_date

log = logging.getLogger(__name__)
HTML = ParseMode.HTML


def deps(context: ContextTypes.DEFAULT_TYPE):
    return pipeline.deps(context.application.bot_data)


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg, _, _ = deps(context)
    return cfg.is_admin(update.effective_user.id if update.effective_user else None)


def panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [B("📊 Statistika", callback_data="adm:stats"), B("📢 Reklama", callback_data="adm:bc")],
        [B("🧠 Miya (tayyor darslar)", callback_data="adm:miya")],
        [B("📚 Oxirgi AI darslar", callback_data="adm:last:0"), B("⚙️ Sozlamalar", callback_data="adm:set")],
        [B("🩺 AI holati", callback_data="adm:ai")],
    ])


def _back(target: str = "adm:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[B("🔙 Admin panel", callback_data=target)]])


async def _edit_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup=None) -> None:
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
            return
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        return
    context.user_data.pop("adm", None)
    name = html.escape(update.effective_user.first_name or "admin")
    await _edit_or_send(update, context, f"👑 <b>Admin panel</b>\nAssalomu alaykum, {name}!", panel_markup())


def stats_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    _, db, _ = deps(context)
    s = db.stats()
    top_pairs = "\n".join(f"   • {html.escape(subjects.pair_label(k))}: {n}" for k, n in s["top_pairs"]
                          if subjects.is_valid_pair(k)) or "   —"
    grades = ", ".join(f"{g}-sinf: {n}" for g, n in s["grades"]) or "—"
    top_ready = "\n".join(f"   • {html.escape(t)} ({g}-sinf): {v}" for t, g, v in db.top_catalog(5)) or "   —"
    return (
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"   bugun yangi: {s['users_today']} · 7 kunda: {s['users_week']} · bugun faol: {s['active_today']}\n"
        f"   bloklangan: {s['blocked']}\n\n"
        f"📗 Miya: <b>{s['catalog']}</b> ta tayyor dars · ochilgan: {s['catalog_views']} marta\n"
        f"   AI rasmi bor: {s['catalog_images']} ta\n"
        f"   eng ko‘p ochilganlar:\n{top_ready}\n\n"
        f"🤖 AI darslar: <b>{s['lessons']}</b> · bugun: {s['lessons_today']} · 7 kunda: {s['lessons_week']}\n"
        f"🎨 AI rasmlar: {s['images']} · bugun: {s['images_today']}\n"
        f"👍 {s['likes']} · 👎 {s['dislikes']}\n\n"
        f"📚 AI darslarda ko‘p tanlangan juftliklar:\n{top_pairs}\n"
        f"🏫 Sinflar: {grades}"
    )


def settings_markup(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, InlineKeyboardMarkup]:
    cfg, db, _ = deps(context)
    lessons = settings.daily_lessons(db, cfg)
    images = settings.daily_images(db, cfg)
    img_on = settings.images_enabled(db, cfg)
    check_on = settings.image_check(db, cfg)
    voice_key = db.get_setting("tts_voice") or ("sardor" if cfg.tts_voice == tts.VOICES["sardor"] else "madina")
    text = (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🤖 Kunlik AI dars limiti (1 kishi): <b>{lessons}</b>\n"
        f"🎨 Kunlik AI rasm limiti (1 kishi): <b>{images}</b>\n"
        f"🖼 AI rasm chizish: <b>{'yoqilgan' if img_on else 'o‘chirilgan'}</b>\n"
        f"🔍 Rasmdagi sonlarni tekshirish: <b>{'yoqilgan' if check_on else 'o‘chirilgan'}</b>\n"
        f"🎙 Ovoz: <b>{'Sardor (erkak)' if voice_key == 'sardor' else 'Madina (ayol)'}</b>\n\n"
        "<i>📗 Tayyor darslar limitsiz. Admin uchun limit yo‘q.</i>"
    )
    markup = InlineKeyboardMarkup([
        [B("➖", callback_data="adm:set:lessons:-1"), B(f"Dars: {lessons}", callback_data="adm:set"),
         B("➕", callback_data="adm:set:lessons:1")],
        [B("➖", callback_data="adm:set:images:-1"), B(f"Rasm: {images}", callback_data="adm:set"),
         B("➕", callback_data="adm:set:images:1")],
        [B(("🖼 Rasmni o‘chirish" if img_on else "🖼 Rasmni yoqish"), callback_data="adm:set:img")],
        [B(("🔍 Tekshiruvni o‘chirish" if check_on else "🔍 Tekshiruvni yoqish"), callback_data="adm:set:check")],
        [B("🎙 Ovozni almashtirish", callback_data="adm:set:voice")],
        [B("🔙 Admin panel", callback_data="adm:home")],
    ])
    return text, markup


def miya_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    _, db, _ = deps(context)
    counts: dict[str, dict[int, int]] = {}
    for pair, grade, n in db.catalog_counts():
        counts.setdefault(pair, {})[grade] = n
    lines = []
    for key, _, _ in subjects.PAIRS:
        by_grade = counts.get(key, {})
        total = sum(by_grade.values())
        cells = " ".join(f"{g}:{by_grade.get(g, 0)}" for g in subjects.GRADES)
        lines.append(f"• {html.escape(subjects.pair_label(key))} — {total} ({cells})")
    seed = db.get_setting("miya_seed_hash") or "—"
    return ("🧠 <b>Miya — tayyor darslar</b>\n\n"
            f"Jami: <b>{db.count_catalog()}</b> ta dars\n" + "\n".join(lines) +
            f"\n\n<i>Git fayli: data/Fanlar_Miya.xlsx (hash {html.escape(seed)})</i>\n"
            "📥 Yangilash: /miya_import → Excel faylni yuboring.\n"
            "📤 Hozirgi miyani Excel qilib olish: /miya_export")


def miya_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [B("📥 Excel yuklash", callback_data="adm:miya:import"), B("📤 Excel olish", callback_data="adm:miya:export")],
        [B("♻️ Git fayldan qayta yuklash", callback_data="adm:miya:reseed")],
        [B("🔙 Admin panel", callback_data="adm:home")],
    ])


async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(update, context):
        await query.answer("Faqat admin uchun.", show_alert=True)
        return
    cfg, db, ai = deps(context)
    data = query.data or ""
    parts = data.split(":")

    if data == "adm:home":
        await query.answer()
        await panel(update, context)
    elif data == "adm:stats":
        await query.answer()
        await _edit_or_send(update, context, stats_text(context), InlineKeyboardMarkup(
            [[B("🔄 Yangilash", callback_data="adm:stats")], [B("🔙 Admin panel", callback_data="adm:home")]]))
    elif data == "adm:bc":
        await query.answer()
        context.user_data["adm"] = "broadcast"
        await _edit_or_send(update, context,
                            "📢 <b>Reklama</b>\n\nHamma foydalanuvchilarga yuboriladigan xabarni yuboring "
                            "(matn, rasm, video, ovoz — istalgan turdagi).", InlineKeyboardMarkup(
                                [[B("❌ Bekor", callback_data="adm:bc:no")]]))
    elif data == "adm:bc:no":
        await query.answer("Bekor qilindi")
        context.user_data.pop("adm", None)
        context.user_data.pop("bc_ref", None)
        await panel(update, context)
    elif data == "adm:bc:go":
        ref = context.user_data.pop("bc_ref", None)
        context.user_data.pop("adm", None)
        if not ref:
            await query.answer("Xabar topilmadi", show_alert=True)
            return
        await query.answer("Yuborish boshlandi")
        status = await context.bot.send_message(update.effective_chat.id, "📢 Yuborilmoqda…")
        app = context.application
        pipeline.start_task(app, broadcast_job(context.bot, db, update.effective_chat.id, status.message_id, ref),
                            app.bot_data)
    elif data.startswith("adm:last:"):
        await query.answer()
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        rows = db.list_lessons(None, 8, page * 8)
        total = db.count_lessons(None)
        buttons = []
        for r in rows:
            label = L.short_label(r["topic"] or "", r["grade"] or 0, r["pair_key"] or "", fmt_date(r["created_at"]))
            buttons.append([B(label, callback_data=f"x:l:open:{r['id']}")])
        nav = []
        if page > 0:
            nav.append(B("⬅️", callback_data=f"adm:last:{page - 1}"))
        if (page + 1) * 8 < total:
            nav.append(B("➡️", callback_data=f"adm:last:{page + 1}"))
        if nav:
            buttons.append(nav)
        buttons.append([B("🔙 Admin panel", callback_data="adm:home")])
        await _edit_or_send(update, context, f"📚 <b>Oxirgi AI darslar</b> (jami {total})", InlineKeyboardMarkup(buttons))
    elif data.startswith("adm:set"):
        await query.answer()
        if len(parts) >= 4 and parts[2] in ("lessons", "images"):
            key = "daily_lessons" if parts[2] == "lessons" else "daily_images"
            current = settings.daily_lessons(db, cfg) if parts[2] == "lessons" else settings.daily_images(db, cfg)
            settings.set_int(db, key, current + int(parts[3]))
        elif len(parts) == 3 and parts[2] == "img":
            settings.set_bool(db, "images_enabled", not settings.images_enabled(db, cfg))
        elif len(parts) == 3 and parts[2] == "check":
            settings.set_bool(db, "image_check", not settings.image_check(db, cfg))
        elif len(parts) == 3 and parts[2] == "voice":
            current = db.get_setting("tts_voice") or ("sardor" if cfg.tts_voice == tts.VOICES["sardor"] else "madina")
            db.set_setting("tts_voice", "madina" if current == "sardor" else "sardor")
            db.execute("UPDATE edu_catalog SET voice_file_ids = NULL")
            db.execute("UPDATE edu_lessons SET voice_file_id = NULL")
        text, markup = settings_markup(context)
        await _edit_or_send(update, context, text, markup)
    elif data == "adm:ai":
        await query.answer("Tekshirilmoqda…")
        await _edit_or_send(update, context, "🩺 AI holati tekshirilmoqda…", None)
        info = await ai.status()
        keys = ", ".join(f"{k}: {'✅' if v else '—'}" for k, v in info["keys"].items())
        models = "\n".join(f"• {k}: <code>{html.escape(v)}</code>" for k, v in info["models"].items())
        text = (f"🩺 <b>AI holati</b>\n\nKalitlar: {keys}\nMatn: {info['text_provider']} · Rasm: {info['image_provider']}\n\n"
                f"<b>Tanlangan modellar:</b>\n{models}")
        if info.get("error"):
            text += f"\n\n⚠️ {html.escape(info['error'])}"
        if info.get("last_error"):
            text += f"\n\n<i>Oxirgi xato: {html.escape(info['last_error'])}</i>"
        if not cfg.ai_ready:
            text += "\n\nℹ️ AI kaliti yo‘q — faqat tayyor darslar ishlaydi."
        await _edit_or_send(update, context, text, _back())
    elif data == "adm:miya":
        await query.answer()
        await _edit_or_send(update, context, miya_text(context), miya_markup())
    elif data == "adm:miya:import":
        await query.answer()
        context.user_data["adm"] = "miya_import"
        await _edit_or_send(update, context, "📥 Fanlar_Miya.xlsx faylini yuboring (varaq nomi «Miya»).",
                            InlineKeyboardMarkup([[B("❌ Bekor", callback_data="adm:miya")]]))
    elif data == "adm:miya:export":
        await query.answer("Excel tayyorlanmoqda…")
        await send_miya_export(update, context)
    elif data == "adm:miya:reseed":
        await query.answer("Qayta yuklanmoqda…")
        result = await asyncio.to_thread(miya.seed_from_bundle, db, miya.BUNDLED_PATH, True)
        await _edit_or_send(update, context, f"♻️ {html.escape(result)}\n\n" + miya_text(context), miya_markup())
    elif data == "adm:miya:ok":
        pending = context.user_data.pop("miya_pending", None)
        context.user_data.pop("adm", None)
        if not pending:
            await query.answer("Ma’lumot eskirgan, faylni qayta yuboring.", show_alert=True)
            return
        await query.answer("Yozilmoqda…")
        new, updated = await asyncio.to_thread(miya.import_lessons, db, pending, "import")
        await _edit_or_send(update, context, f"✅ Miya yangilandi: yangi {new} ta, yangilangan {updated} ta.\n\n"
                            + miya_text(context), miya_markup())
    elif data == "adm:miya:no":
        await query.answer("Bekor qilindi")
        context.user_data.pop("miya_pending", None)
        context.user_data.pop("adm", None)
        await _edit_or_send(update, context, miya_text(context), miya_markup())
    elif data.startswith("adm:tomiya:"):
        lesson_id = int(parts[2])
        row = db.get_lesson(lesson_id)
        if not row:
            await query.answer("Dars topilmadi", show_alert=True)
            return
        lesson = row["lesson"]
        meta = lesson["meta"]
        raw = miya.lesson_to_row(lesson)
        state = db.upsert_catalog(meta["grade"], meta["pair"], meta["topic"], miya.topic_key(meta["topic"]),
                                  meta["minutes"], lesson, raw, "ai")
        if row.get("image_file_id"):
            found = db.find_catalog(meta["grade"], meta["pair"], miya.topic_key(meta["topic"]))
            if found and not found.get("image_file_id"):
                db.update_catalog(found["id"], image_file_id=row["image_file_id"], image_note=row.get("image_note"))
        await query.answer("🧠 Miyaga qo‘shildi" if state == "new" else "🧠 Miyada yangilandi", show_alert=True)
    else:
        await query.answer()


async def capture_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    context.user_data["bc_ref"] = {"chat_id": msg.chat_id, "message_id": msg.message_id}
    context.user_data["adm"] = "broadcast_confirm"
    _, db, _ = deps(context)
    count = len(db.user_ids())
    await msg.reply_text(f"📢 Shu xabar <b>{count}</b> ta foydalanuvchiga yuborilsinmi?", parse_mode=HTML,
                         reply_markup=InlineKeyboardMarkup([[B("✅ Yuborish", callback_data="adm:bc:go"),
                                                             B("❌ Bekor", callback_data="adm:bc:no")]]))


async def broadcast_job(bot, db, chat_id: int, status_id: int, ref: dict) -> None:
    users = db.user_ids()
    ok = failed = 0
    for i, uid in enumerate(users, start=1):
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=ref["chat_id"], message_id=ref["message_id"])
            ok += 1
        except Forbidden:
            failed += 1
        except TelegramError as exc:
            failed += 1
            log.debug("Reklama %s ga ketmadi: %s", uid, exc)
        await asyncio.sleep(0.05)
        if i % 50 == 0:
            await pipeline.safe_edit(bot, chat_id, status_id, f"📢 Yuborilmoqda… {i}/{len(users)}")
    await pipeline.safe_edit(bot, chat_id, status_id,
                             f"✅ Reklama tugadi.\nYetkazildi: <b>{ok}</b>\nYetmadi (botni bloklagan va h.k.): {failed}")


async def send_miya_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, db, _ = deps(context)
    items = db.catalog_raw_rows()

    def build() -> bytes:
        rows = []
        for item in items:
            raw = item["raw"]
            rows.append(raw if raw.get("Mavzu") else miya.lesson_to_row(item["lesson"]))
        return miya.build_workbook(rows)

    data = await asyncio.to_thread(build)
    await context.bot.send_document(update.effective_chat.id, document=data, filename="Fanlar_Miya.xlsx",
                                    caption=f"🧠 Miya: {len(items)} ta tayyor dars. Tahrirlab /miya_import orqali "
                                            f"qaytarishingiz yoki data/ papkasiga qo‘yib Git’ga yuklashingiz mumkin.")


async def miya_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin Excel yuborganda: miya importi."""
    msg = update.effective_message
    doc = msg.document
    if not doc:
        return
    name = (doc.file_name or "").lower()
    if not name.endswith(".xlsx"):
        await msg.reply_text("Miya uchun .xlsx fayl yuboring (Fanlar_Miya.xlsx).")
        return
    if (doc.file_size or 0) > miya.MAX_BYTES:
        await msg.reply_text("Fayl 6 MB dan katta.")
        return
    wait = await msg.reply_text("⏳ Excel tekshirilmoqda…")
    try:
        tg_file = await doc.get_file()
        data = bytes(await tg_file.download_as_bytearray())
    except TelegramError as exc:
        await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id, f"Faylni olib bo‘lmadi: {html.escape(str(exc))}")
        return
    result = await asyncio.to_thread(miya.parse_workbook, data)
    _, db, _ = deps(context)
    if not result.lessons:
        errors = "\n".join(f"• {html.escape(e)}" for e in result.errors[:10]) or "—"
        await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id, f"❌ Darslar topilmadi.\n{errors}")
        return
    existing = {(g, p, k) for _, g, p, _, k in db.catalog_topics_all()}
    new = sum(1 for l in result.lessons
              if (l["meta"]["grade"], l["meta"]["pair"], miya.topic_key(l["meta"]["topic"])) not in existing)
    text = (f"📥 <b>Tekshiruv natijasi</b>\n\nTo‘g‘ri darslar: <b>{len(result.lessons)}</b>\n"
            f"   yangi: {new} · yangilanadi: {len(result.lessons) - new}\n"
            f"Xato qatorlar: {len(result.errors)}")
    if result.errors:
        text += "\n" + "\n".join(f"• {html.escape(e)}" for e in result.errors[:8])
    if result.warnings:
        text += "\n\n⚠️ Ogohlantirishlar:\n" + "\n".join(f"• {html.escape(w)}" for w in result.warnings[:6])
    text += "\n\nMiyaga yozilsinmi? (boshqa darslar o‘chmaydi)"
    context.user_data["miya_pending"] = result
    context.user_data["adm"] = "miya_confirm"
    await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id, L.trim_caption(text, 4000),
                             InlineKeyboardMarkup([[B("✅ Tasdiqlash", callback_data="adm:miya:ok"),
                                                    B("❌ Bekor", callback_data="adm:miya:no")]]))


# ───────────────────────── Buyruqlar ─────────────────────────

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await panel(update, context)


async def stat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_admin(update, context):
        await update.effective_message.reply_text(stats_text(context), parse_mode=HTML)


async def miya_import_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        return
    context.user_data["adm"] = "miya_import"
    await update.effective_message.reply_text(
        "📥 Fanlar_Miya.xlsx faylini yuboring. Faqat «Miya» varag‘i o‘qiladi; bir xil sinf + fanlar + mavzu "
        "yangilanadi, qolganlari o‘chmaydi.")


async def miya_export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_admin(update, context):
        await send_miya_export(update, context)


async def _set_block(update: Update, context: ContextTypes.DEFAULT_TYPE, value: bool) -> None:
    if not _is_admin(update, context):
        return
    _, db, _ = deps(context)
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text(f"Foydalanish: /{'block' if value else 'unblock'} <user_id>")
        return
    ok = db.set_blocked(int(args[0]), value)
    await update.effective_message.reply_text(("✅ Bajarildi." if ok else "Foydalanuvchi topilmadi."))


async def block_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_block(update, context, True)


async def unblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_block(update, context, False)

