"""Rasmlar bilan yordamchi amallar (Telegram va Word uchun tayyorlash)."""
from __future__ import annotations

import io

from PIL import Image


def to_jpeg(data: bytes, max_side: int = 1600, quality: int = 88) -> bytes:
    """Har qanday rasmni (PNG/WEBP/JPEG) Telegram uchun qulay JPEG ga aylantiradi."""
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            im = background
        elif im.mode != "RGB":
            im = im.convert("RGB")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        return out.getvalue()


def is_image(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        return True
    except Exception:
        return False
