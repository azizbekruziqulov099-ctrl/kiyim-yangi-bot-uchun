"""
Matnni o‘zbekcha ovozga aylantirish (Microsoft Edge TTS — kiyim botidagi Madina ovozi).

Ishonchli bo‘lishi uchun:
  • matn ovoz uchun tayyorlanadi: «6+4=10» → «6 qoʻshuv 4 teng 10», «12 cm» → «12 santimetr», «1-sinf» → «birinchi sinf»;
  • uzun matn bo‘laklarga bo‘linadi, har bo‘lak 2 marta urinib ko‘riladi;
  • bir ovoz ishlamasa ikkinchisi (Madina ↔ Sardor) sinaladi;
  • bir vaqtda ko‘pi bilan 3 ta ovoz tayyorlanadi (bot qotib qolmasligi uchun).
"""
from __future__ import annotations

import asyncio
import logging
import re

log = logging.getLogger(__name__)

VOICES = {"madina": "uz-UZ-MadinaNeural", "sardor": "uz-UZ-SardorNeural"}
MAX_CHARS = 3500
CHUNK_CHARS = 900
_SEM = asyncio.Semaphore(3)

_ORDINALS = ["", "birinchi", "ikkinchi", "uchinchi", "toʻrtinchi", "beshinchi", "oltinchi", "yettinchi",
             "sakkizinchi", "toʻqqizinchi", "oʻninchi", "oʻn birinchi", "oʻn ikkinchi", "oʻn uchinchi",
             "oʻn toʻrtinchi", "oʻn beshinchi", "oʻn oltinchi", "oʻn yettinchi", "oʻn sakkizinchi",
             "oʻn toʻqqizinchi", "yigirmanchi"]
_UNITS = [
    (r"cm²|sm²", "kvadrat santimetr"), (r"m²", "kvadrat metr"),
    (r"cm|sm", "santimetr"), (r"mm", "millimetr"), (r"dm", "detsimetr"), (r"km", "kilometr"),
    (r"kg", "kilogramm"), (r"m", "metr"), (r"g", "gramm"), (r"l", "litr"), (r"°C|°", "daraja"), (r"%", "foiz"),
]
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def prepare(text: str) -> str:
    """Matnni ovozli o‘qish uchun tozalaydi va o‘qilishi qiyin belgilarni so‘z bilan almashtiradi."""
    s = re.sub(r"<[^>]+>", " ", text or "")
    s = _EMOJI.sub(" ", s)
    # rasmiy yozuv: oʻ gʻ va tutuq belgisi ʼ
    s = re.sub(r"([oOgG])[‘’'`ʼ]", lambda m: m.group(1) + "ʻ", s)
    s = re.sub(r"(?<=[A-Za-zʻ])[’'`‘](?=[A-Za-z])", "ʼ", s)
    # vaqt: 14:00 → soat 14
    s = re.sub(r"(?:\bsoat\s+)?\b([01]?\d|2[0-3]):00\b", r"soat \1", s)
    s = re.sub(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", r"\1 \2", s)
    # oraliq: 1–3-topshiriq → 1 dan 3 gacha topshiriq
    s = re.sub(r"\b(\d+)\s*–\s*(\d+)-(?=[A-Za-zʻ])", r"\1 dan \2 gacha ", s)
    s = re.sub(r"\b(\d+)\s*–\s*(\d+)\b", r"\1 dan \2 gacha", s)
    # tartib son: 1-sinf → birinchi sinf
    s = re.sub(r"\b(\d{1,2})-(?=[A-Za-zʻ])",
               lambda m: (_ORDINALS[int(m.group(1))] + " ") if 0 < int(m.group(1)) <= 20 else m.group(1) + " ", s)
    # o‘lchov birliklari
    for pattern, word in _UNITS:
        s = re.sub(rf"(?<=\d)\s*(?:{pattern})(?![A-Za-zʻ])", f" {word}", s)
    # 1 260 → 1260
    s = re.sub(r"(?<=\d)[  ](?=\d{3}\b)", "", s)
    # amallar
    s = re.sub(r"(?<=[\d)])\s*[×xX*·∙]\s*(?=[\d(])", " koʻpaytiruv ", s)
    s = re.sub(r"(?<=[\d)])\s*[:÷/]\s*(?=[\d(])", " boʻluv ", s)
    s = re.sub(r"(?<=[\d)])\s*\+\s*(?=[\d(])", " qoʻshuv ", s)
    s = re.sub(r"(?<=[\d)])\s*[−-]\s*(?=[\d(])", " ayiruv ", s)
    s = re.sub(r"\s*=\s*", " teng ", s)
    s = s.replace("(", " ").replace(")", " ")
    # tinish belgilari
    s = s.replace("«", "").replace("»", "").replace("“", "").replace("”", "").replace('"', "")
    s = s.replace("→", ", keyin ").replace("|", ", ").replace("—", ", ").replace("…", ".").replace("•", ". ")
    s = re.sub(r"_{2,}", " ", s)
    s = re.sub(r"\s+([,.;!?])", r"\1", s)
    s = re.sub(r"([,;])(?:\s*[,;])+", r"\1", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    if len(s) > MAX_CHARS:
        cut = s[:MAX_CHARS]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("\n"))
        s = cut[: end + 1] if end > 300 else cut
    return s


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 50 else limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if len(current) + len(sentence) + 1 > limit and current:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


async def _speak(text: str, voice: str, timeout: float) -> bytes:
    import edge_tts

    async def run() -> bytes:
        audio = bytearray()
        communicate = edge_tts.Communicate(text, voice=voice)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                audio.extend(chunk["data"])
        return bytes(audio)

    data = await asyncio.wait_for(run(), timeout=timeout)
    if not data:
        raise RuntimeError("bo‘sh audio")
    return data


def _other(voice: str) -> str:
    return VOICES["sardor"] if voice == VOICES["madina"] else VOICES["madina"]


async def synthesize(text: str, voice: str = VOICES["madina"], timeout: float = 45) -> bytes:
    """MP3 baytlarini qaytaradi. Bo‘lmasa RuntimeError (foydalanuvchiga tushunarli xabar chiqariladi)."""
    clean = prepare(text)
    if not clean:
        raise RuntimeError("ovoz uchun matn bo‘sh")
    parts = split_chunks(clean)
    audio = bytearray()
    async with _SEM:
        for part in parts:
            last_error: Exception | None = None
            for attempt, use_voice in enumerate((voice, voice, _other(voice))):
                try:
                    audio.extend(await _speak(part, use_voice, timeout))
                    last_error = None
                    break
                except Exception as exc:  # tarmoq, xizmat yoki vaqt tugashi
                    last_error = exc
                    log.warning("TTS urinish %s (%s) bo‘lmadi: %s", attempt + 1, use_voice, exc)
                    await asyncio.sleep(1.0 + attempt)
            if last_error is not None:
                raise RuntimeError(f"ovoz yaratilmadi: {last_error}")
    return bytes(audio)
