"""Foydalanuvchi handlerlari: /start, dars tanlash bosqichlari, tayyor darslar (miya), AI darslar, ovoz."""
from __future__ import annotations

import asyncio
import difflib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from . import docx_export, miya, pipeline, settings, subjects, tts
from . import keyboards as kb
from . import lesson as L
from .ai import AIError
from .db import fmt_date

log = logging.getLogger(__name__)
HTML = ParseMode.HTML

WELCOME = (
    "Assalomu alaykum, {name}! 👋\n\n"
    "Men — <b>«Fanlar integratsiyasi»</b> yordamchisiman. Boshlang‘ich sinflar (1–4) uchun ikki fanni "
    "bitta mavzu orqali bog‘lab, darsga tayyorlab beraman:\n\n"
    "📗 <b>{ready} ta tayyor dars</b> — darhol ochiladi\n"
    "📘 mavzu bo‘yicha ma’lumot va 🔗 fanlar bog‘lanishi\n"
    "🧮 aniq ko‘rgazma kartasi, 🖼 mavzuga mos rasm\n"
    "✍️ topshiriqlar va ✅ javoblar, 🧑‍🏫 dars rejasi\n"
    "📄 Word fayl (dars ishlanmasi) va 🔊 ovozli o‘qish\n"
    "{ai_line}\n"
    "Boshlash uchun <b>«📚 Dars tayyorlash»</b> tugmasini bosing yoki mavzuni yozib yuboring."
)

HELP_HOME = (
    "ℹ️ <b>Yordam</b>\n\n"
    "Bot boshlang‘ich sinf (1–4) uchun ikki fanni bitta mavzuda bog‘lab, darsga tayyorlab beradi.\n\n"
    "<b>3 qadam:</b>\n"
    "1️⃣ «📚 Dars tayyorlash» → sinfni tanlang\n"
    "2️⃣ Fanlar juftligini tanlang\n"
    "3️⃣ 📗 Tayyor mavzuni tanlang — dars darhol ochiladi{ai_hint}\n\n"
    "Batafsil ma’lumot uchun bo‘limni tanlang 👇"
)

HELP_SECTIONS = {
    "ready": (
        "📗 <b>Tayyor darslar</b>\n\n"
        "Botda <b>{ready} ta tayyor dars</b> bor: 9 ta fan juftligi, har birida 6 ta mavzu, har bir mavzu 1–4-sinflar "
        "uchun alohida.\n\n"
        "• Tayyor dars AI’siz, bepul va darhol ochiladi — limit yo‘q.\n"
        "• Ichida: ma’lumot, fanlar bog‘lanishi, ko‘rgazma kartasi, 6 ta topshiriq, javoblar, 45 daqiqalik dars "
        "rejasi va uyga vazifa.\n"
        "• Mavzuni shunchaki yozib yuborsangiz ham bo‘ladi: masalan «bog‘dagi hosil» — bot shu mavzudagi barcha "
        "sinflar uchun tayyor darslarni topib beradi.\n\n"
        "<b>Fanlar juftliklari:</b>\n{pairs}"
    ),
    "ai": (
        "🤖 <b>AI bilan yangi dars</b>\n\n"
        "Ro‘yxatda yo‘q mavzu kerak bo‘lsa:\n"
        "1. Sinf va juftlikni tanlang, mavzuni yozib yuboring (yoki 🎤 ovozli xabar bilan ayting).\n"
        "2. Dars vaqti (45 yoki 90 daqiqa), AI rasm va qo‘shimcha istakni belgilang.\n"
        "3. «🚀 Darsni tayyorlash» — 1–2 daqiqada tayyor bo‘ladi.\n\n"
        "• Kunlik limit (bir kishi uchun): {lessons} ta dars, {images} ta rasm.\n"
        "• Tayyorlangan darslar «🗂 Mening darslarim» bo‘limida saqlanadi.\n"
        "• Xato yuz bersa, limit hisobiga yozilmaydi."
    ),
    "tools": (
        "✅ <b>Javoblar, Word va baho</b>\n\n"
        "• <b>✅ Javoblar</b> — har topshiriq javobi va baholash mezoni. Hisoblarni bot qayta tekshiradi "
        "(🧮 6 + 4 = 10 ✅); farq bo‘lsa ⚠️ bilan ko‘rsatadi.\n"
        "• <b>📄 Word fayl</b> — «dars ishlanmasi»: maqsadlar, ma’lumot, karta va rasm, dars borishi jadvali, "
        "topshiriqlar; javoblar oxirgi sahifada. Chop etsa bo‘ladi.\n"
        "• <b>👍 / 👎</b> — darsga baho bering, bu sifatni yaxshilashga yordam beradi."
    ),
    "voice": (
        "🔊 <b>Ovoz</b>\n\n"
        "• <b>🔊 Matnni o‘qish</b> — hikoya yoki vaziyat matnini bolalarga o‘qib beradi.\n"
        "• <b>🔊 Topshiriqlar</b> — topshiriqlarni tartib bilan o‘qiydi.\n"
        "• Sonlar va belgilar to‘g‘ri o‘qiladi: «6+4=10» → «6 qo‘shuv 4 teng 10», «12 cm» → «12 santimetr», "
        "«1-sinf» → «birinchi sinf».\n"
        "• Ovoz birinchi marta 5–15 soniyada tayyorlanadi, keyin darhol yuboriladi.\n"
        "• 🎤 Mavzuni ovozli xabar bilan ayting — bot eshitganini yozib ko‘rsatadi va darsni topadi{voice_ai}."
    ),
    "pics": (
        "🖼 <b>Kartalar va rasm</b>\n\n"
        "• <b>🧮 Ko‘rgazma kartasi</b> — bot o‘zi chizadi: «6 ta olma» bo‘lsa, aniq 6 ta olma rasmi; o‘lchovlar "
        "bo‘lsa, diagramma. Sonlar doim aniq.\n"
        "• <b>🎨 AI rasm</b> — mavzuga mos sahna rasmi (ixtiyoriy, 30–90 soniya). AI rasmda buyumlar soni ba’zan "
        "farq qilishi mumkin; bot tekshirib, izohda yozadi. Sanash uchun kartadan foydalaning.\n"
        "• Tayyor dars uchun chizilgan rasm saqlanadi — keyingi o‘qituvchilar uni darhol oladi."
    ),
    "faq": (
        "❓ <b>Ko‘p so‘raladigan savollar</b>\n\n"
        "• <b>Tugma ishlamayapti?</b> /start ni bosing — menyu yangilanadi.\n"
        "• <b>Bekor qilish?</b> /bekor yoki «❌ Bekor qilish».\n"
        "• <b>Limit tugadi?</b> Ertaga yangilanadi; tayyor darslar limitsiz.\n"
        "• <b>Material rasmiy darslikmi?</b> Yo‘q — mualliflik namunasi. Darsdan oldin sinfingizga moslab ko‘rib "
        "chiqing.\n"
        "• <b>Taklif yoki xato?</b> 👎 tugmasini bosing yoki admin bilan bog‘laning.\n\n"
        "<b>Buyruqlar:</b> /dars — yangi dars · /darslar — mening darslarim · /bekor — bekor qilish · /yordam"
    ),
    "admin": (
        "👑 <b>Admin uchun</b>\n\n"
        "• /admin — panel: 📊 statistika, 📢 reklama, 🧠 miya, ⚙️ sozlamalar, 🩺 AI holati.\n"
        "• <b>Miyani yangilash:</b> data/Fanlar_Miya.xlsx faylini GitHub’ga yuklang — bot qayta ishga tushganda o‘zi "
        "yangilaydi. Yoki /miya_import → Excel yuboring → tasdiqlang. Hozirgi miya: /miya_export.\n"
        "• <b>⚙️ Sozlamalar:</b> kunlik limitlar, AI rasmni yoqish/o‘chirish, sonlar tekshiruvi, ovoz "
        "(Madina yoki Sardor).\n"
        "• /block &lt;id&gt; va /unblock &lt;id&gt; — foydalanuvchini cheklash.\n"
        "• AI kaliti yoki balans muammosida bot sizga o‘zi xabar beradi."
    ),
}

HELP_BUTTONS = [
    [("📗 Tayyor darslar", "ready"), ("🤖 AI bilan dars", "ai")],
    [("✅ Javoblar va Word", "tools"), ("🔊 Ovoz", "voice")],
    [("🖼 Kartalar va rasm", "pics"), ("❓ Savollar", "faq")],
]

ARCHIVE_PAGE = 8


def deps(context: ContextTypes.DEFAULT_TYPE):
    return pipeline.deps(context.application.bot_data)


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Foydalanuvchini bazaga yozadi va bloklanmaganini tekshiradi."""
    user = update.effective_user
    if user is None or user.is_bot:
        return False
    cfg, db, _ = deps(context)
    try:
        db.touch_user(user.id, user.full_name or "", user.username or "")
        if not cfg.is_admin(user.id) and db.is_blocked(user.id):
            if update.callback_query:
                await update.callback_query.answer("Sizga botdan foydalanish cheklangan.", show_alert=True)
            return False
    except Exception:
        log.exception("Foydalanuvchini yozib bo‘lmadi")
    return True


# ───────────────────────── Asosiy buyruqlar ─────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    cfg, db, _ = deps(context)
    context.user_data.pop("wiz", None)
    user = update.effective_user
    ai_line = ("🤖 Ro‘yxatda yo‘q mavzu bo‘lsa — AI yangi dars tayyorlaydi\n" if cfg.ai_ready else "")
    await update.effective_message.reply_text(
        WELCOME.format(name=L.h(user.first_name or "ustoz"), ready=db.count_catalog(), ai_line=ai_line),
        parse_mode=HTML, reply_markup=kb.main_menu(cfg.is_admin(user.id)),
    )
    if cfg.is_admin(user.id) and not cfg.ai_ready:
        await update.effective_message.reply_text(
            "ℹ️ Admin uchun: AI kaliti qo‘shilmagan. Tayyor darslar ishlaydi; o‘z mavzusi bo‘yicha AI dars va AI rasm "
            "uchun serverga OPENAI_API_KEY yoki GEMINI_API_KEY qo‘shing.")


def _help_markup(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text, callback_data=f"h:{key}") for text, key in row] for row in HELP_BUTTONS]
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin uchun", callback_data="h:admin")])
    return InlineKeyboardMarkup(rows)


def _help_home(context: ContextTypes.DEFAULT_TYPE) -> str:
    cfg, _, _ = deps(context)
    hint = "\n   (yoki o‘z mavzuingizni yozing — AI yangi dars tayyorlaydi)" if cfg.ai_ready else ""
    return HELP_HOME.format(ai_hint=hint)


def _help_section(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    cfg, db, _ = deps(context)
    pairs = "\n".join(f"• {L.h(subjects.pair_label(k, emoji=True))}" for k, _, _ in subjects.PAIRS)
    text = HELP_SECTIONS[key].format(
        ready=db.count_catalog(), pairs=pairs, lessons=settings.daily_lessons(db, cfg),
        images=settings.daily_images(db, cfg), voice_ai="" if cfg.ai_ready else " (AI ulanganda ishlaydi)")
    if key == "ai" and not cfg.ai_ready:
        text += "\n\n<i>Hozircha AI ulanmagan — tayyor darslardan foydalaning.</i>"
    return text


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    cfg, _, _ = deps(context)
    await update.effective_message.reply_text(_help_home(context), parse_mode=HTML,
                                              reply_markup=_help_markup(cfg.is_admin(update.effective_user.id)))


async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await guard(update, context):
        return
    await query.answer()
    cfg, _, _ = deps(context)
    is_admin = cfg.is_admin(update.effective_user.id)
    key = (query.data or "h:home").split(":", 1)[1]
    if key not in HELP_SECTIONS or (key == "admin" and not is_admin):
        text, markup = _help_home(context), _help_markup(is_admin)
    else:
        text = _help_section(context, key)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Yordam", callback_data="h:home"),
                                        InlineKeyboardButton("📚 Dars tayyorlash", callback_data="w:new")]])
    try:
        await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
    except BadRequest:
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    cfg, _, _ = deps(context)
    for key in ("wiz", "adm", "pending_topic", "miya_pending", "bc_ref"):
        context.user_data.pop(key, None)
    await update.effective_message.reply_text("Bekor qilindi.",
                                              reply_markup=kb.main_menu(cfg.is_admin(update.effective_user.id)))


# ───────────────────────── Dars tanlash bosqichlari ─────────────────────────

def _usage_line(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    cfg, db, _ = deps(context)
    if cfg.is_admin(user_id):
        return "♾ Admin uchun limit yo‘q."
    used_lessons, used_images = db.usage_today(user_id)
    return (f"📊 Bugun AI: {used_lessons}/{settings.daily_lessons(db, cfg)} dars, "
            f"{used_images}/{settings.daily_images(db, cfg)} rasm.")


def confirm_text(context: ContextTypes.DEFAULT_TYPE, wiz: dict, user_id: int) -> str:
    cfg, db, _ = deps(context)
    lines = [
        "<b>🤖 AI bilan yangi dars · tekshirib oling</b>",
        "",
        f"🏫 Sinf: <b>{wiz['grade']}-sinf</b>",
        f"📚 Fanlar: <b>{L.h(subjects.pair_label(wiz['pair']))}</b>",
        f"📝 Mavzu: <b>«{L.h(wiz['topic'])}»</b>",
        f"⏱ Davomiyligi: {wiz.get('minutes', 45)} daqiqa",
    ]
    if settings.images_enabled(db, cfg):
        lines.append(f"🖼 AI rasm: {'ha' if wiz.get('image', True) else 'yo‘q'}")
    lines.append(f"✍️ Qo‘shimcha istak: {L.h(wiz['extra']) if wiz.get('extra') else '—'}")
    lines += ["", _usage_line(context, user_id), "", "Hammasi to‘g‘ri bo‘lsa — <b>«🚀 Darsni tayyorlash»</b>."]
    return "\n".join(lines)


def _topic_view(context: ContextTypes.DEFAULT_TYPE, wiz: dict):
    cfg, db, _ = deps(context)
    ready = [(cid, title) for cid, title, _ in db.catalog_topics(wiz["grade"], wiz["pair"])]
    suggestions = [] if ready else (subjects.TOPIC_SUGGESTIONS.get(wiz["pair"], []) if cfg.ai_ready else [])
    lines = ["<b>3/3 · Mavzuni tanlang</b>",
             f"🏫 {wiz['grade']}-sinf · {L.h(subjects.pair_label(wiz['pair']))}", ""]
    if ready:
        lines.append(f"📗 <b>Tayyor darslar ({len(ready)} ta)</b> — darhol ochiladi.")
    if cfg.ai_ready:
        lines.append("✍️ Yoki o‘z mavzuingizni yozib yuboring (🎤 ovozli xabar ham bo‘ladi) — AI yangi dars "
                     "tayyorlaydi.")
    elif not ready:
        lines.append("Bu juftlik va sinf uchun hozircha tayyor dars yo‘q.")
    return "\n".join(lines), kb.topics(ready, suggestions)


async def _show(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup) -> None:
    """Tugma bosilgan bo‘lsa — o‘sha xabarni tahrirlaydi, aks holda yangi xabar yuboradi."""
    query = update.callback_query
    wiz = context.user_data.get("wiz")
    if query and query.message:
        try:
            await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
            if wiz is not None:
                wiz["msg_id"] = query.message.message_id
            return
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return
    msg = await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)
    if wiz is not None:
        wiz["msg_id"] = msg.message_id


async def _hide_old_keyboard(context: ContextTypes.DEFAULT_TYPE, chat_id: int, wiz: dict | None) -> None:
    msg_id = (wiz or {}).get("msg_id")
    if msg_id:
        try:
            await context.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
        except TelegramError:
            pass


async def new_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str = "") -> None:
    if not await guard(update, context):
        return
    await _hide_old_keyboard(context, update.effective_chat.id, context.user_data.get("wiz"))
    context.user_data["wiz"] = {"step": "grade", "minutes": 45, "image": True, "extra": "", "topic": topic}
    head = f"📝 Mavzu: <b>«{L.h(topic)}»</b>\n\n" if topic else ""
    text = head + "<b>1/3 · Sinfni tanlang</b>\nDars qaysi sinf uchun?"
    if update.callback_query and (update.callback_query.data or "").startswith(("w:new", "w:topic")):
        msg = await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=kb.grades())
        context.user_data["wiz"]["msg_id"] = msg.message_id
    else:
        await _show(update, context, text, kb.grades())


async def open_ready(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog_id: int) -> None:
    """Tayyor darsni ochadi (AI so‘rovisiz, darhol)."""
    row = deps(context)[1].get_catalog(catalog_id)
    query = update.callback_query
    if query and query.message and row:
        try:
            await query.edit_message_text(
                f"📗 <b>Tayyor dars:</b> «{L.h(row['topic'])}»\n🏫 {row['grade']}-sinf · "
                f"{L.h(subjects.pair_label(row['pair_key']))}", parse_mode=HTML)
        except TelegramError:
            pass
    context.user_data.pop("wiz", None)
    await pipeline.deliver_ready(context.bot, context.application.bot_data, update.effective_chat.id,
                                 update.effective_user.id, catalog_id)


async def wizard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await guard(update, context):
        return
    data = query.data or ""
    cfg, db, _ = deps(context)
    user_id = update.effective_user.id

    if data == "w:new":
        await query.answer()
        await new_lesson(update, context)
        return
    if data == "w:topic":
        await query.answer()
        topic = context.user_data.pop("pending_topic", "")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        await new_lesson(update, context, topic=topic)
        return
    if data.startswith("w:c:"):
        await query.answer("📗 Tayyor dars ochilmoqda…")
        try:
            await open_ready(update, context, int(data.split(":")[2]))
        except ValueError:
            pass
        return
    wiz = context.user_data.get("wiz")
    if data == "w:cancel":
        await query.answer("Bekor qilindi")
        context.user_data.pop("wiz", None)
        try:
            await query.edit_message_text("❌ Bekor qilindi. Yangi dars uchun «📚 Dars tayyorlash» tugmasini bosing.")
        except TelegramError:
            pass
        return
    if not wiz:
        await query.answer("Bu tugma eskirgan — qaytadan boshlaymiz.")
        await new_lesson(update, context)
        return
    await query.answer()

    if data.startswith("w:g:"):
        grade = int(data.split(":")[2])
        if grade not in subjects.GRADES:
            return
        wiz.update(grade=grade, step="pair")
        await _show(update, context, f"🏫 {grade}-sinf\n\n<b>2/3 · Fanlar juftligini tanlang</b>\n"
                                     f"Qaysi ikki fan bog‘lansin?", kb.pairs())
    elif data.startswith("w:p:"):
        pair_key = data[4:]
        if not subjects.is_valid_pair(pair_key) or "grade" not in wiz:
            return
        wiz["pair"] = pair_key
        if wiz.get("topic"):
            await _route_topic(update, context, wiz["topic"])
            return
        wiz.update(step="topic", await_text="topic")
        text, markup = _topic_view(context, wiz)
        await _show(update, context, text, markup)
    elif data.startswith("w:t:"):
        items = subjects.TOPIC_SUGGESTIONS.get(wiz.get("pair", ""), [])
        idx = int(data.split(":")[2])
        if 0 <= idx < len(items):
            await _route_topic(update, context, items[idx])
    elif data == "w:ai":
        if not cfg.ai_ready or not wiz.get("topic"):
            return
        wiz.update(step="confirm", await_text=None)
        await _show(update, context, confirm_text(context, wiz, user_id), kb.confirm(wiz, settings.images_enabled(db, cfg)))
    elif data.startswith("w:m:"):
        minutes = int(data.split(":")[2])
        if minutes in subjects.DURATIONS:
            wiz["minutes"] = minutes
        await _show(update, context, confirm_text(context, wiz, user_id), kb.confirm(wiz, settings.images_enabled(db, cfg)))
    elif data.startswith("w:img:"):
        wiz["image"] = data.endswith(":1")
        await _show(update, context, confirm_text(context, wiz, user_id), kb.confirm(wiz, settings.images_enabled(db, cfg)))
    elif data == "w:extra":
        wiz["await_text"] = "extra"
        await _show(update, context,
                    "✍️ <b>Qo‘shimcha istagingizni yozing</b> (ixtiyoriy)\n\n<i>Masalan: guruhda ishlash bo‘lsin; "
                    "o‘yin elementi qo‘shilsin; topshiriqlar sodda bo‘lsin; she’r ham bo‘lsin.</i>",
                    InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="w:back:confirm")]]))
    elif data == "w:go":
        if not all(k in wiz for k in ("grade", "pair")) or not wiz.get("topic"):
            await new_lesson(update, context)
            return
        await start_generation(update, context, wiz)
    elif data.startswith("w:back:"):
        target = data.split(":")[2]
        if target == "grade":
            wiz.update(step="grade", await_text=None)
            await _show(update, context, "<b>1/3 · Sinfni tanlang</b>\nDars qaysi sinf uchun?", kb.grades())
        elif target == "pair":
            wiz.update(step="pair", await_text=None)
            await _show(update, context, f"🏫 {wiz.get('grade', '')}-sinf\n\n<b>2/3 · Fanlar juftligini tanlang</b>",
                        kb.pairs())
        elif target == "topic" and wiz.get("pair"):
            wiz.update(step="topic", await_text="topic", topic="")
            text, markup = _topic_view(context, wiz)
            await _show(update, context, text, markup)
        elif target == "confirm":
            wiz.update(step="confirm", await_text=None)
            await _show(update, context, confirm_text(context, wiz, user_id),
                        kb.confirm(wiz, settings.images_enabled(db, cfg)))


def _match_catalog(db, grade: int, pair: str, topic: str):
    key = miya.topic_key(topic)
    row = db.find_catalog(grade, pair, key)
    if row:
        return row["id"], row["topic"]
    best, best_ratio = None, 0.0
    for cid, title, tkey in db.catalog_topics(grade, pair):
        ratio = difflib.SequenceMatcher(None, key, tkey).ratio()
        if ratio > best_ratio:
            best, best_ratio = (cid, title), ratio
    return best if best_ratio >= 0.8 else None


async def _route_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str) -> None:
    """Sinf va juftlik tanlangan, mavzu ma’lum: tayyor dars bo‘lsa — taklif, bo‘lmasa — AI tasdiqlash."""
    cfg, db, _ = deps(context)
    wiz = context.user_data["wiz"]
    wiz["topic"] = topic
    match = _match_catalog(db, wiz["grade"], wiz["pair"], topic)
    if match and miya.topic_key(match[1]) == miya.topic_key(topic):
        await open_ready(update, context, match[0])
        return
    if match:
        wiz.update(step="choose", await_text=None)
        await _show(update, context,
                    f"📗 «{L.h(match[1])}» mavzusida tayyor dars bor — u darhol ochiladi.\n"
                    f"Siz yozgan mavzu: «{L.h(topic)}».", kb.ready_or_ai(match[0], cfg.ai_ready))
        return
    if not cfg.ai_ready:
        wiz.update(step="topic", await_text="topic")
        text, markup = _topic_view(context, wiz)
        await _show(update, context, f"«{L.h(topic)}» bo‘yicha tayyor dars topilmadi. AI hozircha ulanmagan, "
                                     f"shuning uchun tayyor mavzulardan birini tanlang.\n\n{text}", markup)
        return
    wiz.update(step="confirm", await_text=None)
    await _show(update, context, confirm_text(context, wiz, update.effective_user.id),
                kb.confirm(wiz, settings.images_enabled(db, cfg)))


async def start_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, wiz: dict) -> None:
    cfg, db, _ = deps(context)
    app = context.application
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not cfg.ai_ready:
        await context.bot.send_message(chat_id, "AI ulanmagan — tayyor darslardan foydalaning.")
        return
    running: set = app.bot_data["running"]
    if user_id in running:
        await context.bot.send_message(chat_id, "⏳ Oldingi ish hali tugamadi. Iltimos, biroz kuting.")
        return
    unlimited = cfg.is_admin(user_id)
    if unlimited:
        db.add_usage(user_id, "lessons")
    elif not db.try_consume(user_id, "lessons", settings.daily_lessons(db, cfg)):
        await context.bot.send_message(
            chat_id, f"⛔️ Bugungi AI limiti tugadi (kuniga {settings.daily_lessons(db, cfg)} ta dars). "
                     f"📗 Tayyor darslar esa cheklovsiz ochiladi.")
        return
    running.add(user_id)
    context.user_data.pop("wiz", None)
    job = dict(wiz)
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(
                f"🚀 <b>Tayyorlanmoqda:</b> «{L.h(job['topic'])}»\n🏫 {job['grade']}-sinf · "
                f"{L.h(subjects.pair_label(job['pair']))} · ⏱ {job['minutes']} daqiqa", parse_mode=HTML)
        except TelegramError:
            pass
    try:
        status = await context.bot.send_message(chat_id, "⏳ Navbatga qo‘yildi…")
    except Exception:
        running.discard(user_id)
        if not unlimited:
            db.refund(user_id, "lessons")
        raise
    pipeline.start_task(app, pipeline.lesson_job(context.bot, app.bot_data, chat_id, user_id, job,
                                                 status.message_id, unlimited), app.bot_data)


# ───────────────────────── Matn va ovozli xabarlar ─────────────────────────

async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Bosqichlarda kutilgan matn (mavzu, istak) yoki shunchaki yozilgan mavzu."""
    cfg, db, _ = deps(context)
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    wiz = context.user_data.get("wiz")
    topic = L.uz_fix(text)

    if wiz and wiz.get("await_text") == "topic" and wiz.get("pair"):
        if not 3 <= len(topic) <= 150:
            await update.effective_message.reply_text("Mavzu 3–150 belgidan iborat bo‘lsin. Qaytadan yozing.")
            return
        await _hide_old_keyboard(context, chat_id, wiz)
        wiz.pop("msg_id", None)
        await _route_topic(update, context, topic)
        return
    if wiz and wiz.get("await_text") == "extra":
        await _hide_old_keyboard(context, chat_id, wiz)
        wiz.update(extra=topic[:400], step="confirm", await_text=None)
        msg = await update.effective_message.reply_text(
            confirm_text(context, wiz, user_id), parse_mode=HTML,
            reply_markup=kb.confirm(wiz, settings.images_enabled(db, cfg)))
        wiz["msg_id"] = msg.message_id
        return

    if not 3 <= len(topic) <= 150:
        await update.effective_message.reply_text("Dars tayyorlash uchun «📚 Dars tayyorlash» tugmasini bosing.",
                                                  reply_markup=kb.main_menu(cfg.is_admin(user_id)))
        return
    # Miyadan izlash: mavzu bir nechta sinf/juftlikda bo‘lishi mumkin
    key = miya.topic_key(topic)
    rows = db.catalog_topics_all()
    exact = [r for r in rows if r[4] == key]
    if not exact:
        scored = sorted(((difflib.SequenceMatcher(None, key, r[4]).ratio(), r) for r in rows), reverse=True)
        exact = [r for ratio, r in scored if ratio >= 0.8][:8]
    if exact:
        buttons = [[InlineKeyboardButton(f"📗 {r[1]}-sinf · {subjects.pair_label(r[2])} · {r[3]}"[:60],
                                         callback_data=f"w:c:{r[0]}")] for r in exact[:8]]
        if cfg.ai_ready:
            context.user_data["pending_topic"] = topic
            buttons.append([InlineKeyboardButton("🤖 Boshqa sinf/juftlik uchun AI bilan", callback_data="w:topic")])
        await update.effective_message.reply_text(f"📗 «{L.h(topic)}» bo‘yicha tayyor darslar topildi:",
                                                  parse_mode=HTML, reply_markup=InlineKeyboardMarkup(buttons))
        return
    if cfg.ai_ready:
        context.user_data["pending_topic"] = topic
        await update.effective_message.reply_text(
            f"«{L.h(topic)}» mavzusida tayyor dars yo‘q. AI bilan yangi dars tayyorlaymizmi?", parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Ha, sinfni tanlash", callback_data="w:topic")]]))
        return
    await update.effective_message.reply_text(
        f"«{L.h(topic)}» bo‘yicha tayyor dars topilmadi. «📚 Dars tayyorlash» orqali tayyor mavzulardan tanlang.",
        parse_mode=HTML, reply_markup=kb.main_menu(cfg.is_admin(user_id)))


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    from . import admin  # aylanma importdan qochish

    cfg, _, _ = deps(context)
    text = (update.effective_message.text or "").strip()
    user_id = update.effective_user.id
    if cfg.is_admin(user_id) and context.user_data.get("adm") == "broadcast":
        await admin.capture_broadcast(update, context)
        return
    if text == kb.BTN_NEW:
        await new_lesson(update, context)
    elif text == kb.BTN_ARCHIVE:
        await archive(update, context)
    elif text == kb.BTN_HELP:
        await help_cmd(update, context)
    elif text == kb.BTN_ADMIN and cfg.is_admin(user_id):
        await admin.panel(update, context)
    else:
        await handle_free_text(update, context, text)


async def voice_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ovozli xabar: mavzuni ovoz bilan aytish mumkin (AI matnga aylantiradi)."""
    if not await guard(update, context):
        return
    from . import admin

    cfg, _, ai = deps(context)
    msg = update.effective_message
    if cfg.is_admin(update.effective_user.id) and context.user_data.get("adm") == "broadcast":
        await admin.capture_broadcast(update, context)
        return
    media = msg.voice or msg.audio
    if media is None:
        return
    if not cfg.ai_ready:
        await msg.reply_text("🎤 Ovozli xabarni tushunish uchun AI ulanmagan. Mavzuni yozib yuboring.")
        return
    if (media.duration or 0) > 90 or (media.file_size or 0) > 8 * 1024 * 1024:
        await msg.reply_text("🎤 Ovozli xabar 1,5 daqiqadan oshmasin. Mavzuni qisqa ayting yoki yozib yuboring.")
        return
    wait = await msg.reply_text("🎤 Tinglayapman…")
    try:
        tg_file = await media.get_file()
        audio = bytes(await tg_file.download_as_bytearray())
        text = await ai.transcribe(audio, getattr(media, "mime_type", None) or "audio/ogg")
    except AIError as err:
        log.warning("Ovozni matnga aylantirib bo‘lmadi: %s", err)
        await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id,
                                 "🎤 Ovozni tushunib bo‘lmadi. Iltimos, mavzuni yozib yuboring.")
        return
    except TelegramError as err:
        log.warning("Ovoz faylini yuklab bo‘lmadi: %s", err)
        await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id, "🎤 Ovoz faylini olib bo‘lmadi.")
        return
    text = L.uz_fix(L.cyr_to_lat(text)).strip(" .")
    if len(text) < 3:
        await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id,
                                 "🎤 Ovozdan matn chiqmadi. Iltimos, aniqroq ayting yoki yozib yuboring.")
        return
    await pipeline.safe_edit(context.bot, msg.chat_id, wait.message_id, f"🎤 Eshitganim: «{L.h(text)}»")
    await handle_free_text(update, context, text)


async def document_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update, context):
        return
    from . import admin

    cfg, _, _ = deps(context)
    user_id = update.effective_user.id
    if cfg.is_admin(user_id) and context.user_data.get("adm") == "broadcast":
        await admin.capture_broadcast(update, context)
        return
    if cfg.is_admin(user_id):
        await admin.miya_document(update, context)
        return
    await update.effective_message.reply_text("Men faylni qabul qilmayman. Mavzuni yozing yoki «📚 Dars tayyorlash».")


async def other_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rasm, video, stiker va boshqa xabarlar."""
    if not await guard(update, context):
        return
    from . import admin

    cfg, _, _ = deps(context)
    if cfg.is_admin(update.effective_user.id) and context.user_data.get("adm") == "broadcast":
        await admin.capture_broadcast(update, context)
        return
    if update.effective_message:
        await update.effective_message.reply_text(
            "Mavzuni yozib yoki ovozli xabar bilan yuboring, yoki «📚 Dars tayyorlash» tugmasini bosing.")


# ───────────────────────── AI darslar arxivi ─────────────────────────

def _archive_markup(rows: list[dict], page: int, total: int, prefix: str = "a") -> InlineKeyboardMarkup:
    buttons = []
    for r in rows:
        label = L.short_label(r["topic"] or "", r["grade"] or 0, r["pair_key"] or "", fmt_date(r["created_at"]))
        buttons.append([InlineKeyboardButton(label, callback_data=f"x:l:open:{r['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}:{page - 1}"))
    if (page + 1) * ARCHIVE_PAGE < total:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}:{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


async def archive(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    if not await guard(update, context):
        return
    _, db, _ = deps(context)
    user_id = update.effective_user.id
    total = db.count_lessons(user_id)
    if total == 0:
        text, markup = ("🗂 AI bilan tayyorlangan darslaringiz hozircha yo‘q.\n📗 Tayyor darslar har doim "
                        "«📚 Dars tayyorlash» bo‘limida."), None
    else:
        rows = db.list_lessons(user_id, ARCHIVE_PAGE, page * ARCHIVE_PAGE)
        text = f"🗂 <b>Mening darslarim</b> (AI bilan, {total} ta)\nKerakli darsni tanlang:"
        markup = _archive_markup(rows, page, total)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
            return
        except BadRequest:
            pass
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)


async def archive_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        page = max(0, int(query.data.split(":")[1]))
    except (IndexError, ValueError):
        page = 0
    await archive(update, context, page)


# ───────────────────────── Dars bilan amallar (AI darsi va tayyor dars uchun umumiy) ─────────────────────────

def _card_text(row: dict) -> str:
    lesson = row["lesson"]
    parts = [L.header(lesson)]
    if lesson.get("summary"):
        parts.append(L.h(lesson["summary"]))
    created = fmt_date(row.get("created_at") or row.get("updated_at"))
    parts.append(f"🗓 {created} · ✍️ {len(lesson.get('tasks', []))} ta topshiriq"
                 + (" · 🖼 rasm bor" if row.get("image_file_id") else ""))
    return "\n\n".join(parts)


async def _download(context: ContextTypes.DEFAULT_TYPE, file_id: str | None) -> bytes | None:
    if not file_id:
        return None
    try:
        tg_file = await context.bot.get_file(file_id)
        return bytes(await tg_file.download_as_bytearray())
    except TelegramError as exc:
        log.warning("Faylni yuklab bo‘lmadi: %s", exc)
        return None


async def send_voice(context: ContextTypes.DEFAULT_TYPE, chat_id: int, row: dict, part: str) -> None:
    """Ovozli o‘qish: 'text' — hikoya/matn, 'tasks' — topshiriqlar. Bir marta tayyorlanadi, keyin darhol yuboriladi."""
    cfg, db, _ = deps(context)
    lesson = row["lesson"]
    cache = dict(row.get("voice_file_ids") or {})
    title = f"🔊 {lesson['title']} — " + ("matn" if part == "text" else "topshiriqlar")
    if cache.get(part):
        try:
            await context.bot.send_voice(chat_id, voice=cache[part], caption=title)
            return
        except TelegramError:
            cache.pop(part, None)
    if part == "tasks":
        source = L.tasks_voice_text(lesson)
    else:
        source = lesson.get("voice_text") or lesson.get("child_text") or lesson.get("teacher_info") or ""
        source = f"{lesson['title']}. {source}"
    wait = await context.bot.send_message(chat_id, "🔊 Ovoz tayyorlanmoqda…")
    voice_name = tts.VOICES.get(db.get_setting("tts_voice") or "", cfg.tts_voice)
    try:
        audio = await tts.synthesize(source, voice_name)
    except RuntimeError as exc:
        log.warning("TTS: %s", exc)
        await pipeline.safe_edit(context.bot, chat_id, wait.message_id,
                                 "⚠️ Ovoz tayyorlanmadi (ovoz xizmati javob bermadi). Birozdan so‘ng qayta bosing.")
        return
    sent = await context.bot.send_voice(chat_id, voice=audio, caption=title)
    if sent.voice:
        cache[part] = sent.voice.file_id
        pipeline.save_ref(db, row, voice_file_ids=cache)
    await pipeline.safe_delete(context.bot, chat_id, wait.message_id)


async def action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """x:{c|l}:{amal}:{id}[:qo‘shimcha]"""
    query = update.callback_query
    if not await guard(update, context):
        return
    cfg, db, _ = deps(context)
    parts = (query.data or "").split(":")
    if len(parts) < 4 or parts[1] not in ("c", "l"):
        await query.answer()
        return
    kind, action = parts[1], parts[2]
    try:
        ref_id = int(parts[3])
    except ValueError:
        await query.answer()
        return
    extra = parts[4] if len(parts) > 4 else ""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    row = pipeline.load_ref(db, kind, ref_id)
    if not row:
        await query.answer("Dars topilmadi yoki o‘chirilgan.", show_alert=True)
        return
    is_owner = kind == "c" or row.get("user_id") == user_id
    if not is_owner and not cfg.is_admin(user_id):
        await query.answer("Bu dars sizga tegishli emas.", show_alert=True)
        return
    lesson = row["lesson"]

    if action == "rate":
        value = 1 if extra == "1" else -1
        if kind == "c":
            db.vote_catalog(user_id, ref_id, value)
        elif row.get("user_id") == user_id:
            db.update_lesson(ref_id, rating=value)
        await query.answer("Rahmat! Fikringiz saqlandi." if value > 0 else
                           "Rahmat! Fikringiz saqlandi — sifatni yaxshilaymiz.")
        return

    if action == "ans":
        await query.answer()
        for chunk in L.split_message(L.fmt_answers(lesson)):
            await context.bot.send_message(chat_id, chunk, parse_mode=HTML)
        return

    if action == "doc":
        await query.answer("📄 Word fayl tayyorlanmoqda…")
        image = await _download(context, row.get("image_file_id"))
        card_png = await pipeline.render_card(lesson)
        try:
            data = await asyncio.to_thread(docx_export.build_docx, lesson, image, card_png, "",
                                           row.get("image_note") or "")
        except Exception:
            log.exception("Word fayl yaratilmadi")
            await context.bot.send_message(chat_id, "❌ Word faylni yaratib bo‘lmadi.")
            return
        await context.bot.send_document(chat_id, document=data, filename=docx_export.file_name(lesson),
                                        caption=f"📄 Dars ishlanmasi: {lesson['title']}")
        return

    if action == "tts":
        await query.answer("🔊 Ovoz tayyorlanmoqda…")
        await send_voice(context, chat_id, row, "tasks" if extra == "tasks" else "text")
        return

    if action == "pic":
        await query.answer()
        if row.get("image_file_id"):
            try:
                await pipeline.send_image(context.bot, chat_id, lesson, row["image_file_id"],
                                          row.get("image_note") or "")
                return
            except TelegramError:
                pipeline.save_ref(db, row, image_file_id=None, image_note=None)
        await context.bot.send_message(chat_id, "Rasm topilmadi — «🎨 AI rasm chizish» tugmasi bilan qayta chizing.")
        return

    if action == "img":
        if not pipeline.can_draw(cfg, db):
            await query.answer("AI rasm hozircha o‘chirilgan.", show_alert=True)
            return
        if kind == "c" and row.get("image_file_id") and not cfg.is_admin(user_id):
            await query.answer()
            await pipeline.send_image(context.bot, chat_id, lesson, row["image_file_id"], row.get("image_note") or "")
            return
        running: set = context.application.bot_data["running"]
        if user_id in running:
            await query.answer("⏳ Oldingi ish hali tugamadi.", show_alert=True)
            return
        unlimited = cfg.is_admin(user_id)
        if unlimited:
            db.add_usage(user_id, "images")
        elif not db.try_consume(user_id, "images", settings.daily_images(db, cfg)):
            await query.answer(f"Bugungi rasm limiti tugadi (kuniga {settings.daily_images(db, cfg)} ta).",
                               show_alert=True)
            return
        await query.answer("🎨 Rasm chizish boshlandi")
        running.add(user_id)
        status = await context.bot.send_message(chat_id, "⏳ Navbatga qo‘yildi…")
        app = context.application
        pipeline.start_task(app, pipeline.image_job(context.bot, app.bot_data, chat_id, user_id, kind, ref_id,
                                                    status.message_id, unlimited), app.bot_data)
        return

    if action == "show":
        await query.answer()
        await pipeline.show_full(context.bot, context.application.bot_data, chat_id, user_id, row)
        return

    if action == "open":
        await query.answer()
        back = "a:0" if row.get("user_id") == user_id else "adm:last:0"
        markup = pipeline.actions_markup(cfg, db, row, user_id, archive=True, back=back)
        text = _card_text(row)
        if kind == "l" and row.get("user_id") != user_id:
            text += f"\n\n👤 {L.h(db.user_name(row['user_id']))}"
        try:
            await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
        except BadRequest:
            await context.bot.send_message(chat_id, text, parse_mode=HTML, reply_markup=markup)
        return

    if action == "del" and kind == "l":
        await query.answer()
        try:
            await query.edit_message_reply_markup(reply_markup=kb.confirm_delete(ref_id))
        except BadRequest:
            pass
        return

    if action == "delok" and kind == "l":
        db.delete_lesson(ref_id)
        await query.answer("O‘chirildi")
        try:
            await query.edit_message_text("🗑 Dars o‘chirildi.", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Ro‘yxat", callback_data="a:0")]]))
        except BadRequest:
            pass
        return

    await query.answer()


async def unknown_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Bu tugma eskirgan. /start ni bosing.")
