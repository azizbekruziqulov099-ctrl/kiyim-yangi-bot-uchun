"""
"Hisob kartasi" — sanaladigan buyumlar ANIQ sonda chiziladigan rasm.

AI rasm chizuvchilar ba’zan buyumlar sonini adashtiradi (6 o‘rniga 7 ta olma).
Shuning uchun matematik topshiriqlar uchun bot bu kartani o‘zi chizadi:
har bir guruhdagi buyum soni darsdagi son bilan 100% bir xil bo‘ladi.
Buyumlar beshtadan qatorga terib chiziladi (sanash oson bo‘lishi uchun).
"""
from __future__ import annotations

import io
import math
import os
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from . import objects

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

WIDTH = 1600
MARGIN = 48
GAP = 32
MAX_ICONS = 20          # bundan ko‘p bo‘lsa: bitta rasm + "× N"
PER_ROW = 5             # beshlik qatorlar

PALETTE = [
    ((255, 246, 214), (236, 170, 30)),
    ((224, 245, 226), (67, 160, 71)),
    ((222, 237, 255), (52, 120, 230)),
    ((255, 230, 238), (216, 27, 96)),
    ((238, 230, 255), (120, 80, 200)),
    ((255, 236, 222), (240, 108, 50)),
]
INK = (40, 44, 62)
MUTED = (110, 116, 135)
BACKGROUND = (252, 251, 247)


@lru_cache(maxsize=32)
def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    name = "Poppins-Bold.ttf" if bold else "Poppins-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default(size)


@lru_cache(maxsize=256)
def _icon(key: str, size: int) -> Image.Image | None:
    path = objects.image_path(key)
    if not path:
        return None
    with Image.open(path) as im:
        return im.convert("RGBA").resize((size, size), Image.LANCZOS)


def _clean(text: str) -> str:
    # Poppins shriftida ʻ yo‘q — ‘ bilan almashtiramiz
    return (text or "").replace("ʻ", "‘").replace("ʼ", "’").strip()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _fit_lines(draw, text: str, max_w: int, bold: bool, start: int, minimum: int, max_lines: int = 2):
    """Matnni berilgan kenglikka sig‘diradi: avval shriftni kichraytiradi, keyin qatorlarga bo‘ladi."""
    size = start
    while size >= minimum:
        font = _font(bold, size)
        if _text_w(draw, text, font) <= max_w:
            return font, [text]
        size -= 4
    font = _font(bold, minimum)
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if _text_w(draw, trial, font) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and _text_w(draw, lines[-1] + "…", font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return font, lines


def _layout_cols(n: int) -> int:
    return {1: 1, 2: 2, 3: 3, 4: 2}.get(n, 3)


def render_count_card(title: str, groups: list[dict], footer: str = "") -> tuple[bytes, list[int]]:
    """
    groups: [{"label": "1-savat", "object_key": "apple", "object_uz": "olma", "count": 6}, ...]
    Qaytaradi: (PNG baytlar, har bir guruhda chizilgan rasmlar soni).
    """
    groups = [g for g in groups if g.get("count", 0) >= 1][:6]
    if not groups:
        raise ValueError("guruhlar yo‘q")
    cols = _layout_cols(len(groups))
    panel_w = (WIDTH - 2 * MARGIN - (cols - 1) * GAP) // cols
    inner_w = panel_w - 2 * 28
    icon_cols = min(PER_ROW, max(min(g["count"], PER_ROW) if g["count"] <= MAX_ICONS else 1 for g in groups))
    cell = max(56, min(170, inner_w // max(icon_cols, 1)))
    icon_size = int(cell * 0.86)

    rows_of_panels = [groups[i:i + cols] for i in range(0, len(groups), cols)]
    label_h = 92

    def icon_rows(g: dict) -> int:
        return 1 if g["count"] > MAX_ICONS else math.ceil(g["count"] / PER_ROW)

    panel_heights = [label_h + max(icon_rows(g) for g in row) * cell + 40 for row in rows_of_panels]

    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    title_font, title_lines = _fit_lines(scratch, _clean(title), WIDTH - 2 * MARGIN, True, 68, 44)
    title_h = len(title_lines) * int(title_font.size * 1.25)
    sub_font = _font(False, 32)
    header_h = MARGIN + title_h + 52 + 28
    footer_h = 70 if footer else 30
    height = header_h + sum(panel_heights) + GAP * (len(rows_of_panels) - 1) + footer_h

    img = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    y = MARGIN
    for line in title_lines:
        draw.text(((WIDTH - _text_w(draw, line, title_font)) // 2, y), line, font=title_font, fill=INK)
        y += int(title_font.size * 1.25)
    subtitle = "Hisob kartasi · Sanang va taqqoslang"
    draw.text(((WIDTH - _text_w(draw, subtitle, sub_font)) // 2, y + 4), subtitle, font=sub_font, fill=MUTED)

    drawn: list[int] = []
    y = header_h
    index = 0
    for row, row_h in zip(rows_of_panels, panel_heights):
        row_w = len(row) * panel_w + (len(row) - 1) * GAP
        x = (WIDTH - row_w) // 2
        for g in row:
            fill, border = PALETTE[index % len(PALETTE)]
            draw.rounded_rectangle((x, y, x + panel_w, y + row_h), radius=36, fill=fill, outline=border, width=5)
            label_font, label_lines = _fit_lines(draw, _clean(g.get("label") or ""), panel_w - 48, True, 46, 28, 1)
            label = label_lines[0] if label_lines else ""
            draw.text((x + (panel_w - _text_w(draw, label, label_font)) // 2, y + 22), label, font=label_font, fill=border)

            area_top = y + label_h
            area_h = row_h - label_h - 24
            icon = _icon(g["object_key"], icon_size)
            count = g["count"]
            n_drawn = 0
            if count > MAX_ICONS:
                big = _icon(g["object_key"], min(int(cell * 1.1), area_h - 10)) if icon else None
                num_font = _font(True, 72)
                text = f"× {count}"
                tw = _text_w(draw, text, num_font)
                total_w = (big.width + 24 if big else 0) + tw
                cx = x + (panel_w - total_w) // 2
                cy = area_top + area_h // 2
                if big:
                    img.paste(big, (cx, cy - big.height // 2), big)
                    cx += big.width + 24
                    n_drawn = 1
                draw.text((cx, cy - 50), text, font=num_font, fill=INK)
            else:
                rows_needed = math.ceil(count / PER_ROW)
                grid_h = rows_needed * cell
                top = area_top + max(0, (area_h - grid_h) // 2)
                for r in range(rows_needed):
                    in_row = min(PER_ROW, count - r * PER_ROW)
                    row_w_px = in_row * cell
                    left = x + (panel_w - row_w_px) // 2
                    for c in range(in_row):
                        cx = left + c * cell + (cell - icon_size) // 2
                        cy = top + r * cell + (cell - icon_size) // 2
                        if icon is not None:
                            img.paste(icon, (cx, cy), icon)
                        else:
                            draw.ellipse((cx, cy, cx + icon_size, cy + icon_size), fill=border)
                        n_drawn += 1
            drawn.append(n_drawn)
            index += 1
            x += panel_w + GAP
        y += row_h + GAP

    if footer:
        foot_font = _font(False, 28)
        text = _clean(footer)
        draw.text(((WIDTH - _text_w(draw, text, foot_font)) // 2, height - 56), text, font=foot_font, fill=MUTED)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue(), drawn


# ───────────────────────── Jadval-karta (ko‘rgazma) ─────────────────────────

TEAL = (21, 79, 96)
ROW_FILLS = [(244, 250, 249), (228, 242, 241)]
_NUM_UNIT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(cm|sm|mm|dm|m|km|kg|g|l|litr|°C|ta|daqiqa|kun|soat|so‘m)?\s*$")


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for paragraph in (text or "").split("\n"):
        words, current = paragraph.split(), ""
        for word in words:
            trial = f"{current} {word}".strip()
            if _text_w(draw, trial, font) <= max_w or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return [line for line in lines if line is not None] or [""]


def _numeric_values(rows: list[list[str]]) -> list[float] | None:
    values, units = [], set()
    for _, value in rows:
        m = _NUM_UNIT.match(_clean(value))
        if not m:
            return None
        values.append(float(m.group(1).replace(",", ".")))
        units.add(m.group(2) or "")
    if len(units) != 1 or len(values) < 2 or max(values) <= 0:
        return None
    return values


def render_table_card(title: str, columns: list[str], rows: list[list[str]], note: str = "",
                      footer: str = "") -> bytes:
    """Ko‘rgazma jadvalini chiroyli karta-rasmga aylantiradi (sonli qiymatlar bo‘lsa — ustunli diagramma bilan)."""
    rows = [[_clean(a), _clean(b)] for a, b in rows][:12]
    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    title_font, title_lines = _fit_lines(scratch, _clean(title), WIDTH - 2 * MARGIN, True, 64, 42)
    head_font = _font(True, 36)
    cell_bold = _font(True, 34)
    cell_font = _font(False, 34)
    note_font = _font(False, 28)
    table_w = WIDTH - 2 * MARGIN
    col1 = int(table_w * 0.36)
    col2 = table_w - col1
    pad = 24
    line_h = 46
    values = _numeric_values(rows)
    bar_h = 26 if values else 0

    row_layout = []
    for a, b in rows:
        la = _wrap(scratch, a, cell_bold, col1 - 2 * pad)
        lb = _wrap(scratch, b, cell_font, col2 - 2 * pad)
        height = max(len(la), len(lb)) * line_h + 2 * pad + (bar_h + 14 if values else 0)
        row_layout.append((la, lb, height))
    note_lines = _wrap(scratch, _clean(note), note_font, table_w) if note else []

    title_h = len(title_lines) * int(title_font.size * 1.25)
    header_h = MARGIN + title_h + 60
    head_row_h = 80
    table_h = head_row_h + sum(r[2] for r in row_layout)
    height = header_h + table_h + 30 + len(note_lines) * 40 + (70 if footer else 40)

    img = Image.new("RGB", (WIDTH, height), BACKGROUND)
    draw = ImageDraw.Draw(img)
    y = MARGIN
    for line in title_lines:
        draw.text(((WIDTH - _text_w(draw, line, title_font)) // 2, y), line, font=title_font, fill=INK)
        y += int(title_font.size * 1.25)
    sub = _font(False, 32)
    subtitle = "Ko‘rgazma kartasi"
    draw.text(((WIDTH - _text_w(draw, subtitle, sub)) // 2, y + 4), subtitle, font=sub, fill=MUTED)

    x0, y0 = MARGIN, header_h
    draw.rounded_rectangle((x0, y0, x0 + table_w, y0 + table_h), radius=28, fill=ROW_FILLS[0], outline=TEAL, width=4)
    draw.rounded_rectangle((x0, y0, x0 + table_w, y0 + head_row_h), radius=28, fill=TEAL)
    draw.rectangle((x0, y0 + head_row_h - 30, x0 + table_w, y0 + head_row_h), fill=TEAL)
    cols = [(_clean(c) if c else "") for c in (columns + ["", ""])[:2]]
    draw.text((x0 + pad, y0 + 20), cols[0], font=head_font, fill=(255, 255, 255))
    draw.text((x0 + col1 + pad, y0 + 20), cols[1], font=head_font, fill=(255, 255, 255))

    y = y0 + head_row_h
    vmax = max(values) if values else 0
    for idx, (la, lb, rh) in enumerate(row_layout):
        fill = ROW_FILLS[idx % 2]
        bottom = y + rh
        if idx == len(row_layout) - 1:
            draw.rounded_rectangle((x0 + 4, y, x0 + table_w - 4, bottom - 4), radius=24, fill=fill)
            draw.rectangle((x0 + 4, y, x0 + table_w - 4, y + 30), fill=fill)
        else:
            draw.rectangle((x0 + 4, y, x0 + table_w - 4, bottom), fill=fill)
            draw.line((x0 + 4, bottom, x0 + table_w - 4, bottom), fill=(201, 214, 216), width=2)
        draw.line((x0 + col1, y, x0 + col1, bottom - 4), fill=(201, 214, 216), width=2)
        ty = y + pad
        for line in la:
            draw.text((x0 + pad, ty), line, font=cell_bold, fill=TEAL)
            ty += line_h
        ty = y + pad
        for line in lb:
            draw.text((x0 + col1 + pad, ty), line, font=cell_font, fill=INK)
            ty += line_h
        if values:
            bar_w = col2 - 2 * pad
            length = max(8, int(bar_w * values[idx] / vmax))
            by = bottom - pad - bar_h
            draw.rounded_rectangle((x0 + col1 + pad, by, x0 + col1 + pad + bar_w, by + bar_h), radius=13,
                                   fill=(222, 232, 234))
            color = PALETTE[idx % len(PALETTE)][1]
            draw.rounded_rectangle((x0 + col1 + pad, by, x0 + col1 + pad + length, by + bar_h), radius=13, fill=color)
        y = bottom

    y = y0 + table_h + 24
    for line in note_lines:
        draw.text((MARGIN, y), line, font=note_font, fill=MUTED)
        y += 40
    if footer:
        foot_font = _font(False, 28)
        text = _clean(footer)
        draw.text(((WIDTH - _text_w(draw, text, foot_font)) // 2, height - 56), text, font=foot_font, fill=MUTED)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render_lesson_card(lesson: dict, footer: str = "") -> bytes | None:
    """Dars uchun aniq karta: sanaladigan buyumlar bo‘lsa — rasmli hisob kartasi, aks holda jadval."""
    groups = lesson.get("image", {}).get("count_groups") or []
    exhibit = lesson.get("exhibit")
    title = (exhibit or {}).get("title") or lesson.get("title", "")
    if groups:
        png, _ = render_count_card(title, groups, footer)
        return png
    if exhibit and exhibit.get("rows"):
        return render_table_card(title, exhibit.get("columns") or ["Belgi", "Ma’lumot"], exhibit["rows"],
                                 exhibit.get("note", ""), footer)
    return None
