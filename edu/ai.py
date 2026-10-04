"""
AI xizmatlari: OpenAI va Google Gemini (matn, rasm, rasmni tekshirish).

- Kalit qaysi biri qo‘yilgan bo‘lsa, o‘sha ishlaydi (ikkalasi bo‘lsa AI_PROVIDER tanlaydi).
- Model nomlari tez o‘zgaradi, shuning uchun bot hisobdagi mavjud modellar ro‘yxatini
  so‘rab, eng mosini o‘zi tanlaydi. Qo‘lda tanlash: EDU_TEXT_MODEL / EDU_IMAGE_MODEL.
- Model biror parametrni qo‘llamasa (masalan "reasoning"), o‘sha parametr olib tashlanib
  so‘rov qayta yuboriladi.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import logging
import re
import time
from typing import Any, Awaitable, Callable

import httpx

from .config import Config

log = logging.getLogger(__name__)

OPENAI_BASE = "https://api.openai.com/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

USER_MESSAGES = {
    "not_configured": "AI kaliti sozlanmagan. Admin serverga OPENAI_API_KEY yoki GEMINI_API_KEY qo‘shishi kerak.",
    "auth": "AI kaliti noto‘g‘ri yoki bu kalitga ruxsat berilmagan.",
    "quota": "AI hisobidagi mablag‘ yoki limit tugagan.",
    "rate": "AI xizmati hozir band. Bir-ikki daqiqadan so‘ng qayta urinib ko‘ring.",
    "safety": "AI bu so‘rovni xavfsizlik qoidalari sababli bajarmadi. Mavzuni boshqacha yozib ko‘ring.",
    "model": "AI modeli topilmadi yoki bu hisobda ishlamaydi.",
    "bad_request": "AI so‘rovni qabul qilmadi.",
    "server": "AI serverida vaqtinchalik nosozlik. Birozdan so‘ng qayta urinib ko‘ring.",
    "network": "AI serveriga ulanib bo‘lmadi (tarmoq muammosi).",
    "invalid_output": "AI javobi buzilgan holda keldi. Qayta urinib ko‘ring.",
    "incomplete": "AI javobi chala qoldi. Qayta urinib ko‘ring.",
    "error": "AI bilan ishlashda xato yuz berdi.",
}


class AIError(Exception):
    def __init__(self, message: str, kind: str = "error", status: int | None = None, detail: str = ""):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.detail = detail or message

    @property
    def user_message(self) -> str:
        return USER_MESSAGES.get(self.kind, USER_MESSAGES["error"])


def parse_json_loose(text: str) -> dict:
    """AI javobidan JSON obyektni ajratib oladi (```json ... ``` bo‘lsa ham)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    for candidate in (t, t[t.find("{"): t.rfind("}") + 1] if "{" in t and "}" in t else ""):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise AIError("AI javobi JSON emas", kind="invalid_output", detail=t[:300])


def _version_key(model_id: str, pattern: str) -> tuple | None:
    m = re.match(pattern, model_id)
    if not m:
        return None
    try:
        return tuple(int(x) for x in m.group(1).split("."))
    except ValueError:
        return None


def _newest(available: list[str], pattern: str) -> list[str]:
    found = [(_version_key(mid, pattern), mid) for mid in available]
    found = [(v, mid) for v, mid in found if v is not None]
    found.sort(reverse=True)
    return [mid for _, mid in found]


def _get_path(body: dict, path: str) -> Any:
    cur: Any = body
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _del_path(body: dict, path: str) -> None:
    parts = path.split(".")
    cur: Any = body
    for part in parts[:-1]:
        cur = cur.get(part, {})
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class Provider:
    name = ""
    STATIC: dict[str, list[str]] = {}

    def __init__(self, key: str, client: httpx.AsyncClient, cfg: Config):
        self.key = key
        self.client = client
        self.cfg = cfg

    # --- har bir provayder o‘zi yozadi ---
    def headers(self) -> dict:
        raise NotImplementedError

    def classify(self, response: httpx.Response) -> AIError:
        raise NotImplementedError

    async def list_models(self) -> list[str]:
        raise NotImplementedError

    def preferences(self, kind: str, available: list[str] | None) -> list[str]:
        static = list(self.STATIC.get(kind, []))
        if available is None:
            return static
        dynamic = self.dynamic(kind, available)
        ordered: list[str] = []
        for mid in dynamic + [m for m in static if m in available]:
            if mid not in ordered:
                ordered.append(mid)
        return ordered or static

    def dynamic(self, kind: str, available: list[str]) -> list[str]:
        return []

    # --- umumiy HTTP qismi ---
    async def _send(self, method: str, url: str, body: dict | None = None) -> dict:
        last_exc: AIError | None = None
        for attempt in range(3):
            try:
                if method == "GET":
                    response = await self.client.get(url, headers=self.headers())
                else:
                    response = await self.client.post(url, headers=self.headers(), json=body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = AIError(f"{type(exc).__name__}: {exc}", kind="network")
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise last_exc from exc
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise AIError("JSON emas javob", kind="invalid_output", detail=response.text[:300]) from exc
            err = self.classify(response)
            if err.kind in ("rate", "server") and attempt < 2:
                last_exc = err
                await asyncio.sleep(4 * (attempt + 1))
                continue
            raise err
        raise last_exc or AIError("noma’lum xato")

    async def _post_degrading(self, url: str, body: dict, optional: dict[str, tuple[str, ...]]) -> dict:
        """400 xatoda model qo‘llamaydigan ixtiyoriy parametrni olib tashlab qayta yuboradi."""
        body = copy.deepcopy(body)
        tried: set[str] = set()
        while True:
            try:
                return await self._send("POST", url, body)
            except AIError as err:
                if err.kind not in ("bad_request", "model"):
                    raise
                text = err.detail.lower()
                dropped = None
                for path, words in optional.items():
                    if path in tried or _get_path(body, path) is None:
                        continue
                    if any(w.lower() in text for w in words):
                        dropped = path
                        break
                if dropped is None:
                    raise
                tried.add(dropped)
                self.degrade(body, dropped)
                log.info("%s: '%s' parametri qo‘llanmadi — usiz qayta yuborilmoqda", self.name, dropped)

    def degrade(self, body: dict, path: str) -> None:
        _del_path(body, path)


# ───────────────────────────── OpenAI ─────────────────────────────

class OpenAIProvider(Provider):
    name = "openai"
    STATIC = {
        "text": ["gpt-5.4-mini", "gpt-6-luna", "gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini"],
        "image": ["gpt-image-2", "gpt-image-2.5-flare", "gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"],
        "vision": ["gpt-5.4-mini", "gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-6-sol"],
        "transcribe": ["gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1"],
    }

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def transcribe(self, model: str, audio: bytes, mime: str = "audio/ogg") -> str:
        """Ovozli xabarni matnga aylantiradi (o‘zbek tili)."""
        url = f"{OPENAI_BASE}/audio/transcriptions"
        form = {"model": model, "language": "uz", "response_format": "json"}
        ext = {"audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
               "audio/wav": "wav", "audio/webm": "webm"}.get(mime, "ogg")
        for attempt in range(3):
            try:
                response = await self.client.post(
                    url, headers={"Authorization": f"Bearer {self.key}"}, data=form,
                    files={"file": (f"voice.{ext}", audio, mime)})
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue
                raise AIError(str(exc), kind="network") from exc
            if response.status_code == 200:
                try:
                    return str(response.json().get("text") or "").strip()
                except ValueError:
                    return response.text.strip()
            err = self.classify(response)
            if err.kind == "bad_request" and "language" in err.detail.lower() and "language" in form:
                form.pop("language")
                continue
            if err.kind in ("rate", "server") and attempt < 2:
                await asyncio.sleep(3)
                continue
            raise err
        raise AIError("transkripsiya bo‘lmadi", kind="error")

    def dynamic(self, kind: str, available: list[str]) -> list[str]:
        if kind == "transcribe":
            return [m for m in available if m.endswith("-transcribe") and "diarize" not in m][:3]
        if kind in ("text", "vision"):
            return _newest(available, r"^gpt-(\d+(?:\.\d+)?)-mini$")
        if kind == "image":
            return _newest(available, r"^gpt-image-(\d+(?:\.\d+)?)$")
        return []

    async def list_models(self) -> list[str]:
        data = await self._send("GET", f"{OPENAI_BASE}/models")
        return sorted({item.get("id", "") for item in data.get("data", []) if item.get("id")})

    def classify(self, response: httpx.Response) -> AIError:
        try:
            err = response.json().get("error") or {}
        except ValueError:
            err = {}
        if not isinstance(err, dict):
            err = {"message": str(err)}
        msg = str(err.get("message") or response.text[:300])
        code = str(err.get("code") or "")
        param = str(err.get("param") or "")
        low = msg.lower()
        status = response.status_code
        if status in (401, 403):
            kind = "auth"
        elif status == 429:
            kind = "quota" if (code == "insufficient_quota" or "quota" in low or "billing" in low) else "rate"
        elif status == 404:
            kind = "model" if "model" in low else "bad_request"
        elif status == 400:
            if code in ("content_policy_violation", "moderation_blocked") or "safety system" in low:
                kind = "safety"
            elif code == "model_not_found" or ("model" in low and ("does not exist" in low or "not found" in low)):
                kind = "model"
            else:
                kind = "bad_request"
        elif status >= 500:
            kind = "server"
        else:
            kind = "bad_request"
        return AIError(f"OpenAI {status}: {msg}", kind=kind, status=status, detail=f"{msg} {param} {code}")

    def degrade(self, body: dict, path: str) -> None:
        if path == "text.format":
            # qat’iy JSON schema qo‘llanmasa — oddiy JSON rejimi
            body["text"] = {"format": {"type": "json_object"}}
        else:
            _del_path(body, path)

    @staticmethod
    def _is_reasoning(model: str) -> bool:
        return bool(re.match(r"^(gpt-(?:[5-9]|\d{2,})|o\d)", model))

    @staticmethod
    def _output_text(data: dict) -> str:
        texts: list[str] = []
        for item in data.get("output") or []:
            if item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                elif part.get("type") == "refusal":
                    raise AIError("AI rad etdi", kind="safety", detail=part.get("refusal") or "")
        if not texts and isinstance(data.get("output_text"), str):
            texts.append(data["output_text"])
        return "".join(texts)

    _JSON_OPTIONAL = {
        "reasoning": ("reasoning",),
        "store": ("'store'", "store"),
        "text.format": ("json_schema", "text.format", "response_format", "schema", "strict"),
    }

    async def generate_json(self, model: str, system: str, user: str | list, schema: dict,
                            max_tokens: int = 16000, name: str = "result") -> dict:
        body: dict = {
            "model": model,
            "instructions": system,
            "input": user,
            "max_output_tokens": max_tokens,
            "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
            "store": False,
        }
        if self.cfg.reasoning_effort and self._is_reasoning(model):
            body["reasoning"] = {"effort": self.cfg.reasoning_effort}
        data = await self._post_degrading(f"{OPENAI_BASE}/responses", body, self._JSON_OPTIONAL)
        if data.get("status") == "incomplete":
            reason = (data.get("incomplete_details") or {}).get("reason", "")
            if reason == "max_output_tokens" and max_tokens < 32000:
                return await self.generate_json(model, system, user, schema, 32000, name)
            if reason == "content_filter":
                raise AIError("content_filter", kind="safety")
            raise AIError(f"incomplete: {reason}", kind="incomplete")
        return parse_json_loose(self._output_text(data))

    async def generate_image(self, model: str, prompt: str) -> bytes:
        body = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1536x1024",
            "quality": self.cfg.image_quality,
            "output_format": "jpeg",
            "output_compression": 90,
        }
        optional = {
            "output_compression": ("output_compression",),
            "output_format": ("output_format",),
            "quality": ("quality",),
            "size": ("size",),
        }
        data = await self._post_degrading(f"{OPENAI_BASE}/images/generations", body, optional)
        items = data.get("data") or []
        if not items:
            raise AIError("rasm qaytmadi", kind="invalid_output")
        item = items[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            response = await self.client.get(item["url"])
            if response.status_code == 200:
                return response.content
        raise AIError("rasm qaytmadi", kind="invalid_output")

    async def check_image(self, model: str, prompt: str, image: bytes, schema: dict) -> dict:
        b64 = base64.b64encode(image).decode()
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
        ]
        return await self.generate_json(
            model, "You are a careful visual checker. Answer with JSON only.",
            [{"role": "user", "content": content}], schema, max_tokens=4000, name="check",
        )


# ───────────────────────────── Gemini ─────────────────────────────

_GEMINI_BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY",
                   "IMAGE_PROHIBITED_CONTENT", "RECITATION", "IMAGE_RECITATION"}


class GeminiProvider(Provider):
    name = "gemini"
    STATIC = {
        "text": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"],
        "image": ["gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image",
                  "gemini-2.5-flash-image"],
        "vision": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"],
        "transcribe": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"],
    }

    def headers(self) -> dict:
        return {"x-goog-api-key": self.key, "Content-Type": "application/json"}

    async def transcribe(self, model: str, audio: bytes, mime: str = "audio/ogg") -> str:
        parts = [
            {"inlineData": {"mimeType": mime or "audio/ogg", "data": base64.b64encode(audio).decode()}},
            {"text": "Transcribe this voice message exactly. The speaker speaks Uzbek. Write the transcription "
                     "in Uzbek Latin script (use oʻ and gʻ). Return only the transcribed text, nothing else."},
        ]
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"maxOutputTokens": 2000}}
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        data = await self._post_degrading(url, body, {})
        return self._text(data).strip()

    def dynamic(self, kind: str, available: list[str]) -> list[str]:
        if kind in ("text", "vision", "transcribe"):
            return _newest(available, r"^gemini-(\d+(?:\.\d+)?)-flash$")
        if kind == "image":
            return _newest(available, r"^gemini-(\d+(?:\.\d+)?)-flash-image$")
        return []

    async def list_models(self) -> list[str]:
        names: set[str] = set()
        token = ""
        for _ in range(5):
            url = f"{GEMINI_BASE}/models?pageSize=1000" + (f"&pageToken={token}" if token else "")
            data = await self._send("GET", url)
            for item in data.get("models", []):
                methods = item.get("supportedGenerationMethods") or []
                name = str(item.get("name", "")).replace("models/", "")
                if name and (not methods or "generateContent" in methods):
                    names.add(name)
            token = data.get("nextPageToken") or ""
            if not token:
                break
        return sorted(names)

    def classify(self, response: httpx.Response) -> AIError:
        try:
            err = response.json().get("error") or {}
        except ValueError:
            err = {}
        if not isinstance(err, dict):
            err = {"message": str(err)}
        msg = str(err.get("message") or response.text[:300])
        status_text = str(err.get("status") or "")
        low = msg.lower()
        status = response.status_code
        if status in (401, 403) or "api key not valid" in low or "api_key_invalid" in low:
            kind = "auth"
        elif status == 429:
            kind = "quota" if ("billing" in low or "per day" in low or "perday" in low) else "rate"
        elif status == 404:
            kind = "model"
        elif status == 400:
            if "model" in low and ("not found" in low or "not supported" in low or "does not support" in low):
                kind = "model"
            elif "location is not supported" in low or "user location" in low:
                kind = "auth"
            else:
                kind = "bad_request"
        elif status >= 500:
            kind = "server"
        else:
            kind = "bad_request"
        return AIError(f"Gemini {status}: {msg}", kind=kind, status=status, detail=f"{msg} {status_text}")

    @staticmethod
    def _candidate(data: dict) -> dict:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            if reason:
                raise AIError(f"blocked: {reason}", kind="safety")
            raise AIError("bo‘sh javob", kind="invalid_output")
        return candidates[0]

    @classmethod
    def _text(cls, data: dict) -> str:
        cand = cls._candidate(data)
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p and not p.get("thought"))
        if not text.strip():
            reason = cand.get("finishReason", "")
            if reason in _GEMINI_BLOCKED:
                raise AIError(f"blocked: {reason}", kind="safety")
            if reason == "MAX_TOKENS":
                raise AIError("MAX_TOKENS", kind="incomplete")
            raise AIError(f"matn yo‘q ({reason})", kind="invalid_output")
        return text

    _JSON_OPTIONAL = {
        "generationConfig.responseJsonSchema": ("responseJsonSchema", "response_json_schema", "schema"),
        "generationConfig.thinkingConfig": ("thinkingConfig", "thinking_config", "thinking"),
    }

    async def generate_json(self, model: str, system: str, user: str | list, schema: dict,
                            max_tokens: int = 24000, name: str = "result") -> dict:
        parts = user if isinstance(user, list) else [{"text": user}]
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
                "maxOutputTokens": max_tokens,
            },
        }
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        data = await self._post_degrading(url, body, self._JSON_OPTIONAL)
        return parse_json_loose(self._text(data))

    async def generate_image(self, model: str, prompt: str) -> bytes:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": "3:2"},
            },
        }
        optional = {"generationConfig.imageConfig": ("imageConfig", "image_config", "aspect")}
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        data = await self._post_degrading(url, body, optional)
        cand = self._candidate(data)
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") if isinstance(part, dict) else None
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
        reason = cand.get("finishReason", "")
        if reason in _GEMINI_BLOCKED:
            raise AIError(f"blocked: {reason}", kind="safety")
        raise AIError(f"rasm qaytmadi ({reason})", kind="invalid_output")

    async def check_image(self, model: str, prompt: str, image: bytes, schema: dict) -> dict:
        parts = [
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(image).decode()}},
            {"text": prompt},
        ]
        return await self.generate_json(model, "You are a careful visual checker. Answer with JSON only.",
                                        parts, schema, max_tokens=4000, name="check")


# ───────────────────────────── Xizmat ─────────────────────────────

class AIService:
    """Bot shu obyekt orqali AI bilan ishlaydi."""

    MODEL_CACHE_SECONDS = 6 * 3600

    def __init__(self, cfg: Config, transport: httpx.AsyncBaseTransport | None = None):
        self.cfg = cfg
        self.client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(connect=20.0, read=240.0, write=60.0, pool=60.0),
        )
        self.providers: dict[str, Provider] = {}
        if cfg.openai_key:
            self.providers["openai"] = OpenAIProvider(cfg.openai_key, self.client, cfg)
        if cfg.gemini_key:
            self.providers["gemini"] = GeminiProvider(cfg.gemini_key, self.client, cfg)
        self._models_cache: dict[str, tuple[float, list[str] | None]] = {}
        self._bad: dict[str, set[str]] = {}
        self.last_error = ""
        self.last_models: dict[str, str] = {}

    async def close(self) -> None:
        await self.client.aclose()

    def provider_for(self, kind: str) -> Provider:
        name = self.cfg.image_provider if kind == "image" else self.cfg.text_provider
        provider = self.providers.get(name)
        if provider is None:
            raise AIError("AI sozlanmagan", kind="not_configured")
        return provider

    async def available_models(self, provider: Provider, force: bool = False) -> list[str] | None:
        cached = self._models_cache.get(provider.name)
        if cached and not force and time.time() - cached[0] < self.MODEL_CACHE_SECONDS:
            return cached[1]
        try:
            models = await provider.list_models()
        except AIError as err:
            if err.kind in ("auth", "quota"):
                raise
            log.warning("%s: modellar ro‘yxatini olib bo‘lmadi: %s", provider.name, err)
            models = None
        self._models_cache[provider.name] = (time.time(), models)
        return models

    def _override(self, kind: str) -> str:
        return {"text": self.cfg.text_model, "image": self.cfg.image_model,
                "vision": self.cfg.vision_model, "transcribe": self.cfg.stt_model}.get(kind, "")

    async def candidates(self, kind: str) -> list[str]:
        provider = self.provider_for(kind)
        override = self._override(kind)
        if override:
            return [override]
        available = await self.available_models(provider)
        prefs = provider.preferences(kind, available)
        bad = self._bad.get(f"{provider.name}:{kind}", set())
        good = [m for m in prefs if m not in bad]
        return good or prefs

    async def _run(self, kind: str, call: Callable[[Provider, str], Awaitable[Any]], max_models: int = 3):
        provider = self.provider_for(kind)
        last: AIError | None = None
        for model in (await self.candidates(kind))[:max_models]:
            try:
                result = await call(provider, model)
                self.last_models[kind] = f"{provider.name}: {model}"
                return result, model
            except AIError as err:
                last = err
                self.last_error = f"{time.strftime('%d.%m %H:%M')} {kind}/{model}: {err.detail[:200]}"
                if err.kind == "model":
                    self._bad.setdefault(f"{provider.name}:{kind}", set()).add(model)
                    log.warning("%s modeli ishlamadi (%s) — keyingisi sinaladi", model, err)
                    continue
                raise
        raise last or AIError("mos model topilmadi", kind="model")

    async def lesson(self, system: str, user: str, schema: dict) -> tuple[dict, str]:
        """Dars JSON. Qaytaradi: (json, model_nomi)."""
        async def call(p: Provider, m: str):
            try:
                return await p.generate_json(m, system, user, schema, name="lesson")
            except AIError as err:
                if err.kind in ("invalid_output", "incomplete"):
                    log.warning("AI javobi buzuq (%s) — bir marta qayta so‘raladi", err.kind)
                    return await p.generate_json(m, system, user, schema, name="lesson")
                raise
        return await self._run("text", call)

    async def image(self, prompt: str) -> tuple[bytes, str]:
        return await self._run("image", lambda p, m: p.generate_image(m, prompt))

    async def check_image(self, prompt: str, image: bytes, schema: dict) -> dict | None:
        """Rasmdagi sonlarni tekshiradi. Ishlamasa None (dars baribir tayyor bo‘ladi)."""
        try:
            provider = self.provider_for("vision")
            models = (await self.candidates("vision"))[:2]
        except AIError as err:
            log.warning("Rasm tekshiruvi o‘tkazilmadi: %s", err)
            return None
        for model in models:
            try:
                result = await provider.check_image(model, prompt, image, schema)
                self.last_models["vision"] = f"{provider.name}: {model}"
                return result
            except AIError as err:
                log.warning("Rasm tekshiruvi (%s) ishlamadi: %s", model, err)
                if err.kind in ("auth", "quota"):
                    return None
        return None

    async def transcribe(self, audio: bytes, mime: str = "audio/ogg") -> str:
        """Ovozli xabar → matn. Ishlamasa AIError."""
        text, _ = await self._run("transcribe", lambda p, m: p.transcribe(m, audio, mime), max_models=2)
        return text

    async def status(self) -> dict:
        """Admin uchun: qaysi kalit, qaysi model tanlanadi."""
        info: dict[str, Any] = {
            "text_provider": self.cfg.text_provider or "—",
            "image_provider": self.cfg.image_provider or "—",
            "keys": {name: bool(key) for name, key in (("openai", self.cfg.openai_key),
                                                          ("gemini", self.cfg.gemini_key))},
            "models": {},
            "error": "",
        }
        for kind in ("text", "image", "vision"):
            try:
                provider = self.provider_for(kind)
                if not self._override(kind):
                    await self.available_models(provider, force=True)
                cands = await self.candidates(kind)
                info["models"][kind] = f"{provider.name}: {cands[0] if cands else '—'}"
            except AIError as err:
                info["models"][kind] = "—"
                info["error"] = err.user_message + (f" ({err.detail[:150]})" if err.detail else "")
        info["last_error"] = self.last_error
        return info
