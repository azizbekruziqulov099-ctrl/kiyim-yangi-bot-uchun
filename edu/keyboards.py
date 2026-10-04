"""Tugmalar (klaviaturalar)."""
from __future__ import annotations

from telegram import InlineKeyboardButton as B
from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

from . import subjects

BTN_NEW = "📚 Dars tayyorlash"
BTN_ARCHIVE = "🗂 Mening darslarim"
BTN_HELP = "ℹ️ Yordam"
BTN_ADMIN = "👑 Admin panel"


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[BTN_NEW], [BTN_ARCHIVE, BTN_HELP]]
    if is_admin:
        rows.append([BTN_ADMIN])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder="Mavzu yozing yoki tugmani bosing…")


def _cancel_row(back: str | None = None) -> list:
    row = []
    if back:
        row.append(B("⬅️ Orqaga", callback_data=back))
    row.append(B("❌ Bekor qilish", callback_data="w:cancel"))
    return row


def grades() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [B("1-sinf", callback_data="w:g:1"), B("2-sinf", callback_data="w:g:2")],
        [B("3-sinf", callback_data="w:g:3"), B("4-sinf", callback_data="w:g:4")],
        _cancel_row(),
    ])


def pairs() -> InlineKeyboardMarkup:
    rows = [[B(subjects.pair_label(key, emoji=True), callback_data=f"w:p:{key}")] for key, _, _ in subjects.PAIRS]
    rows.append(_cancel_row("w:back:grade"))
    return InlineKeyboardMarkup(rows)


def topics(ready: list[tuple[int, str]], suggestions: list[str]) -> InlineKeyboardMarkup:
    """ready: miyadagi tayyor darslar [(id, mavzu)]; suggestions: tayyor dars bo‘lmasa — AI uchun tavsiyalar."""
    rows = [[B(f"📗 {title}", callback_data=f"w:c:{cid}")] for cid, title in ready]
    if not ready:
        row = []
        for i, topic in enumerate(suggestions):
            row.append(B(topic, callback_data=f"w:t:{i}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append(_cancel_row("w:back:pair"))
    return InlineKeyboardMarkup(rows)


def confirm(wiz: dict, images_enabled: bool) -> InlineKeyboardMarkup:
    minutes = wiz.get("minutes", 45)
    rows = [[
        B(("✅ " if minutes == m else "") + f"{m} daqiqa", callback_data=f"w:m:{m}") for m in subjects.DURATIONS
    ]]
    if images_enabled:
        on = wiz.get("image", True)
        rows.append([B("🖼 AI rasm: " + ("ha ✅" if on else "yo‘q"), callback_data=f"w:img:{0 if on else 1}")])
    rows.append([B("✍️ Qo‘shimcha istak yozish", callback_data="w:extra")])
    rows.append([B("🚀 Darsni tayyorlash", callback_data="w:go")])
    rows.append(_cancel_row("w:back:topic"))
    return InlineKeyboardMarkup(rows)


def ready_or_ai(catalog_id: int, ai_ready: bool) -> InlineKeyboardMarkup:
    rows = [[B("📗 Tayyor darsni ochish", callback_data=f"w:c:{catalog_id}")]]
    if ai_ready:
        rows.append([B("🤖 Baribir AI bilan yangi dars", callback_data="w:ai")])
    return InlineKeyboardMarkup(rows)


def lesson_actions(kind: str, ref_id: int, *, has_image: bool, can_draw: bool, is_admin: bool = False,
                   archive: bool = False, back: str = "a:0") -> InlineKeyboardMarkup:
    """kind: 'c' — miyadagi tayyor dars, 'l' — foydalanuvchining AI darsi."""
    p = f"x:{kind}"
    rows = [
        [B("✅ Javoblar", callback_data=f"{p}:ans:{ref_id}"), B("📄 Word fayl", callback_data=f"{p}:doc:{ref_id}")],
        [B("🔊 Matnni o‘qish", callback_data=f"{p}:tts:{ref_id}:text"),
         B("🔊 Topshiriqlar", callback_data=f"{p}:tts:{ref_id}:tasks")],
    ]
    picture = []
    if has_image:
        picture.append(B("🖼 Dars rasmi", callback_data=f"{p}:pic:{ref_id}"))
        if can_draw and (kind == "l" or is_admin):
            picture.append(B("🎨 Qayta chizish", callback_data=f"{p}:img:{ref_id}"))
    elif can_draw:
        picture.append(B("🎨 AI rasm chizish", callback_data=f"{p}:img:{ref_id}"))
    if picture:
        rows.append(picture)
    if archive:
        rows.append([B("📤 To‘liq ko‘rsatish", callback_data=f"{p}:show:{ref_id}")])
        if kind == "l":
            rows.append([B("🗑 O‘chirish", callback_data=f"{p}:del:{ref_id}"), B("⬅️ Ro‘yxat", callback_data=back)])
        else:
            rows.append([B("⬅️ Ro‘yxat", callback_data=back)])
    else:
        rows.append([B("👍 Foydali", callback_data=f"{p}:rate:{ref_id}:1"),
                     B("👎 Yaxshilash kerak", callback_data=f"{p}:rate:{ref_id}:-1")])
        rows.append([B("📚 Yangi dars", callback_data="w:new")])
    if is_admin and kind == "l":
        rows.append([B("🧠 Miyaga qo‘shish", callback_data=f"adm:tomiya:{ref_id}")])
    return InlineKeyboardMarkup(rows)


def confirm_delete(ref_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[B("🗑 Ha, o‘chirish", callback_data=f"x:l:delok:{ref_id}"),
                                  B("↩️ Yo‘q", callback_data=f"x:l:open:{ref_id}")]])
