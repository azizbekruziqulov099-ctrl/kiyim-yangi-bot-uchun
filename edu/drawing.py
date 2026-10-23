"""🎨 Rasm chizish — darsdan alohida: o‘qituvchi janr/uslub tanlaydi, nimani chizishni yozadi, AI chizib beradi.

Bosqichlar:  uslub → format (yotiq/tik/kvadrat) va tavsif → orqa fonda chizish → rasm + «qayta chizish» tugmalari.
Kunlik «rasm» limitidan foydalanadi (dars rasmlari bilan umumiy), xato bo‘lsa limit qaytariladi.
"""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from . import imaging, pipeline, settings
from .ai import AIError

log = logging.getLogger(__name__)
HTML = ParseMode.HTML

# key: (tugma nomi, inglizcha uslub tavsifi, standart format)
STYLES: dict[str, tuple[str, str, str]] = {
    "cartoon": ("🧸 Multfilm", "bright 2D cartoon illustration, bold clean outlines, flat vivid colours, "
                              "cute friendly characters with expressive faces", "3:2"),
    "3d": ("🧊 3D multfilm", "3D animated feature film style render, soft cinematic lighting, rounded cute "
                            "characters, rich colours, shallow depth of field", "3:2"),
    "book": ("📖 Kitob illyustratsiyasi", "children's picture-book illustration, gouache and soft textures, "
                                         "warm storybook atmosphere", "3:2"),
    "watercolor": ("🎨 Akvarel", "delicate watercolour painting on textured paper, soft washes, gentle "
                                 "colour bleeding, light airy palette", "3:2"),
    "pencil": ("✏️ Rangli qalam", "hand-drawn coloured pencil drawing on white paper, visible pencil strokes, "
                                 "warm and simple like a skilled teacher's drawing", "3:2"),
    "coloring": ("🖍 Bo‘yash uchun (kontur)", "black-and-white colouring page for children: thick clean black "
                                              "outlines only, pure white background, large simple areas to colour, "
                                              "no shading, no grey, no filled colour", "2:3"),
    "poster": ("🖼 Ko‘rgazma / plakat", "clean educational classroom poster illustration, simple clear shapes, "
                                       "strong composition, high contrast, easy to see from the back of a class",
               "2:3"),
    "folk": ("🏺 Milliy uslub", "Uzbek national art style inspired by Eastern miniature painting and traditional "
                               "ornaments (islimi patterns), rich blues, turquoise and gold", "3:2"),
    "anime": ("🌸 Anime", "anime illustration style, clean line art, soft cel shading, bright expressive eyes, "
                         "vibrant background", "3:2"),
    "realistic": ("📷 Realistik", "photorealistic image, natural lighting, sharp details, like a high-quality "
                                 "photograph", "3:2"),
}

ASPECTS = {"3:2": "🖼 Yotiq", "2:3": "📄 Tik (A4)", "1:1": "⬛ Kvadrat"}

BASE_RULES = (
    "The image is made by a primary-school teacher in Uzbekistan for children: keep it wholesome, kind and "
    "age-appropriate; people are modestly dressed; Central Asian (Uzbek) setting and faces where it fits. "
    "Do not add any text, letters, numbers, captions, labels, watermarks or logos unless the request explicitly "
    "asks for written text."
)

TRANSLATE_SYSTEM = (
    "You turn a teacher's short picture request written in Uzbek (Latin or Cyrillic, possibly with spelling "
    "mistakes or Russian words) into one clear English prompt for an image-generation model. Keep every object, "
    "number, colour and detail the teacher asked for; add a little helpful scene detail if the request is very "
    "short, but do not change its meaning. Do not mention any art style — the style is added separately. "
    "Return JSON: {\"prompt_en\": \"...\"}"
)


def _schema() -> dict:
    return {"type": "object", "properties": {"prompt_en": {"type": "string"}},
            "required": ["prompt_en"], "additionalProperties": False}


def build_prompt(style: str, subject_en: str) -> str:
    style_text = STYLES.get(style, STYLES["cartoon"])[1]
    return f"{subject_en.strip()}\nStyle: {style_text}.\n{BASE_RULES}"


# ───────────────────────── Tugmalar ─────────────────────────

def styles_kb() -> InlineKeyboardMarkup:
    keys = list(STYLES)
    rows = [[B(STYLES[k][0], callback_data=f"d:s:{k}") for k in keys[i:i + 2]] for i in range(0, len(keys), 2)]
    rows.append([B("❌ Bekor qilish", callback_data="d:cancel")])
    return InlineKeyboardMarkup(rows)


def desc_kb(aspect: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [B(("✅ " if a == aspect else "") + label, callback_data=f"d:a:{a}") for a, label in ASPECTS.items()],
        [B("⬅️ Uslubni o‘zgartirish", callback_data="d:back"), B("❌ Bekor qilish", callback_data="d:cancel")],
    ])


def result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [B("🔁 Qayta chizish", callback_data="d:again"), B("🎨 Boshqa uslubda", callback_data="d:restyle")],
        [B("✍️ Yangi rasm", callback_data="d:new")],
    ])


# ───────────────────────── Matnlar ─────────────────────────

def _style_text(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    return ("🎨 <b>Rasm chizish · 1/2 — uslubni tanlang</b>\n\n"
            "Qaysi janr yoki uslubda chizay?\n<i>🖍 «Bo‘yash uchun» — bolalar bo‘yaydigan kontur rasm, "
            "chop etishga qulay.</i>\n\n" + _limit_line(context, user_id))


def _desc_text(draw: dict) -> str:
    return (f"🎨 Uslub: <b>{STYLES[draw['style']][0]}</b>\n\n"
            "<b>2/2 · Nimani chizay?</b>\nTavsifni yozib yuboring yoki 🎤 ovozli xabar bilan ayting "
            "(3–500 belgi). Formatni pastdan tanlang.\n\n"
            "<i>Masalan: bog‘da 5 ta olma terayotgan qizcha va bobosi; qishki qishloq, qorbobo yasayotgan "
            "bolalar; Amir Temur maydoni bahorda.</i>")


def _limit_line(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    cfg, db, _ = pipeline.deps(context.application.bot_data)
    if cfg.is_admin(user_id):
        return "♾ Admin uchun limit yo‘q."
    _, used = db.usage_today(user_id)
    return f"📊 Bugun: {used}/{settings.daily_images(db, cfg)} rasm (dars rasmlari bilan umumiy)."


async def _show(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, markup) -> None:
    query = update.callback_query
    if query and query.message and query.message.text:
        try:
            await query.edit_message_text(text, parse_mode=HTML, reply_markup=markup)
            return
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                return
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)


# ───────────────────────── Handlerlar ─────────────────────────

def available(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Rasm chizib bo‘lmasa — sababini qaytaradi."""
    cfg, db, _ = pipeline.deps(context.application.bot_data)
    if not cfg.ai_ready:
        return "🎨 Rasm chizish uchun AI ulanmagan."
    if not settings.images_enabled(db, cfg):
        return "🎨 AI rasm hozircha admin tomonidan o‘chirilgan."
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«🎨 Rasm chizish» tugmasi yoki /rasm buyrug‘i."""
    reason = available(context)
    if reason:
        await context.bot.send_message(update.effective_chat.id, reason)
        return
    context.user_data.pop("wiz", None)  # dars tayyorlash bosqichi bilan aralashmasin
    context.user_data["draw"] = {"step": "style"}
    await _show(update, context, _style_text(context, update.effective_user.id), styles_kb())


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    draw = context.user_data.get("draw")
    last = context.user_data.get("draw_last")

    if data == "d:cancel":
        await query.answer("Bekor qilindi")
        context.user_data.pop("draw", None)
        try:
            await query.edit_message_text("❌ Rasm chizish bekor qilindi.")
        except TelegramError:
            pass
        return
    if data == "d:new":
        await query.answer()
        await _send_new(update, context, {"step": "style"}, _style_text(context, update.effective_user.id),
                        styles_kb())
        return
    if data == "d:again":
        if not last:
            await query.answer("Oldingi so‘rov topilmadi — yangidan boshlang.", show_alert=True)
            return
        await query.answer("🔁 Qayta chiziladi")
        await run(update, context, dict(last))
        return
    if data == "d:restyle":
        await query.answer()
        if not last:
            await _send_new(update, context, {"step": "style"}, _style_text(context, update.effective_user.id),
                            styles_kb())
            return
        new = {"step": "style", "desc": last["desc"]}
        await _send_new(update, context, new,
                        f"🎨 <b>Boshqa uslubni tanlang</b>\n📝 «{html.escape(last['desc'][:200])}»", styles_kb())
        return

    if draw is None:
        await query.answer("Bu tugma eskirgan — qaytadan boshlaymiz.")
        await start(update, context)
        return
    await query.answer()

    if data.startswith("d:s:"):
        style = data[4:]
        if style not in STYLES:
            return
        draw.update(style=style, aspect=STYLES[style][2])
        if draw.get("desc"):  # «Boshqa uslubda» — tavsif bor, darhol chiziladi
            job = {"style": style, "aspect": draw["aspect"], "desc": draw["desc"]}
            try:
                await query.edit_message_text(f"🎨 Uslub: <b>{STYLES[style][0]}</b>", parse_mode=HTML)
            except TelegramError:
                pass
            await run(update, context, job)
            return
        draw.update(step="desc")
        await _show(update, context, _desc_text(draw), desc_kb(draw["aspect"]))
    elif data.startswith("d:a:"):
        aspect = data[4:]
        if aspect in ASPECTS and draw.get("style"):
            draw["aspect"] = aspect
            await _show(update, context, _desc_text(draw), desc_kb(aspect))
    elif data == "d:back":
        draw.update(step="style")
        draw.pop("desc", None)
        await _show(update, context, _style_text(context, update.effective_user.id), styles_kb())


async def _send_new(update: Update, context: ContextTypes.DEFAULT_TYPE, draw: dict, text: str, markup) -> None:
    """Natija rasmi ostidagi tugmalardan — rasm saqlanib qolishi uchun yangi xabar yuboriladi."""
    reason = available(context)
    if reason:
        await context.bot.send_message(update.effective_chat.id, reason)
        return
    context.user_data.pop("wiz", None)
    context.user_data["draw"] = draw
    await context.bot.send_message(update.effective_chat.id, text, parse_mode=HTML, reply_markup=markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Tavsif kutilayotgan bo‘lsa — qabul qiladi va True qaytaradi."""
    draw = context.user_data.get("draw")
    if not draw or draw.get("step") != "desc" or not draw.get("style"):
        return False
    desc = " ".join(text.split())
    if not 3 <= len(desc) <= 500:
        await update.effective_message.reply_text("Tavsif 3–500 belgidan iborat bo‘lsin. Qaytadan yozing.")
        return True
    await run(update, context, {"style": draw["style"], "aspect": draw.get("aspect", "3:2"), "desc": desc})
    return True


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE, job: dict) -> None:
    """Limitni tekshiradi va chizishni orqa fonda boshlaydi."""
    app = context.application
    cfg, db, _ = pipeline.deps(app.bot_data)
    chat_id, user_id = update.effective_chat.id, update.effective_user.id
    reason = available(context)
    if reason:
        await context.bot.send_message(chat_id, reason)
        return
    running: set = app.bot_data["running"]
    if user_id in running:
        await context.bot.send_message(chat_id, "⏳ Oldingi ish hali tugamadi. Iltimos, biroz kuting.")
        return
    unlimited = cfg.is_admin(user_id)
    if unlimited:
        db.add_usage(user_id, "images")
    elif not db.try_consume(user_id, "images", settings.daily_images(db, cfg)):
        await context.bot.send_message(
            chat_id, f"⛔️ Bugungi rasm limiti tugadi (kuniga {settings.daily_images(db, cfg)} ta). Ertaga qayta "
                     "urinib ko‘ring.")
        return
    context.user_data.pop("draw", None)
    context.user_data["draw_last"] = dict(job)
    running.add(user_id)
    try:
        status = await context.bot.send_message(
            chat_id, f"🎨 <b>Chizilmoqda…</b> {STYLES[job['style']][0]} · {ASPECTS[job['aspect']]}\n"
                     f"<i>30–90 soniya.</i>", parse_mode=HTML)
    except Exception:
        running.discard(user_id)
        if not unlimited:
            db.refund(user_id, "images")
        raise
    pipeline.start_task(app, draw_job(context.bot, app.bot_data, chat_id, user_id, job, status.message_id, unlimited),
                        app.bot_data)


async def draw_job(bot, bot_data: dict, chat_id: int, user_id: int, job: dict, status_id: int,
                   unlimited: bool) -> None:
    cfg, db, ai = pipeline.deps(bot_data)
    running: set = bot_data["running"]
    try:
        async with bot_data["sem"]:
            subject = job["desc"]
            try:
                result = await ai.image_prompt_en(TRANSLATE_SYSTEM, job["desc"], _schema())
                subject = (result.get("prompt_en") or "").strip() or job["desc"]
            except AIError as err:  # tarjima bo‘lmasa ham o‘zbekcha tavsif bilan chiziladi
                log.warning("Rasm tavsifi tarjima qilinmadi: %s", err)
            raw, model = await ai.image(build_prompt(job["style"], subject), job["aspect"])
            image = await asyncio.to_thread(imaging.to_jpeg, raw, 2048)
            caption = (f"🎨 <b>{STYLES[job['style']][0]}</b> · {ASPECTS[job['aspect']]}\n"
                       f"📝 {html.escape(job['desc'][:800])}")
            await bot.send_photo(chat_id, photo=image, caption=caption, parse_mode=HTML, reply_markup=result_kb())
            try:  # sifatini yo‘qotmasdan saqlash/chop etish uchun fayl ko‘rinishida ham
                await bot.send_document(chat_id, document=image, filename=f"rasm_{job['style']}.jpg",
                                        caption="📎 Chop etish uchun to‘liq sifatli fayl")
            except TelegramError:
                log.warning("Rasm faylini yuborib bo‘lmadi")
            await pipeline.safe_delete(bot, chat_id, status_id)
    except AIError as err:
        if not unlimited:
            db.refund(user_id, "images")
        msg = err.user_message
        if err.kind == "safety":
            msg = "AI bu tavsif bo‘yicha rasm chizishdan bosh tortdi. Tavsifni boshqacharoq yozib ko‘ring."
        await pipeline.safe_edit(bot, chat_id, status_id, f"⚠️ Rasm chizilmadi: {html.escape(msg)}\n"
                                                          "Limit hisobiga yozilmadi.", reply_markup=result_kb())
        await pipeline.notify_admins(bot, bot_data, err)
    except Exception:
        log.exception("Rasm chizishda kutilmagan xato")
        if not unlimited:
            db.refund(user_id, "images")
        await pipeline.safe_edit(bot, chat_id, status_id, "❌ Rasm chizishda kutilmagan xato yuz berdi.",
                                 reply_markup=result_kb())
    finally:
        running.discard(user_id)
