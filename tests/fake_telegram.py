"""Telegram serverining soxta nusxasi: bot so‘rovlarini yozib oladi va javob qaytaradi (internetsiz sinov)."""
from __future__ import annotations

import io
import json

from PIL import Image
from telegram.request import BaseRequest

BOT = {"id": 999, "is_bot": True, "first_name": "Fanlar", "username": "fanlar_test_bot",
       "can_join_groups": True, "can_read_all_group_messages": False, "supports_inline_queries": False}


def jpeg_bytes(color=(200, 230, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "JPEG")
    return buf.getvalue()


class FakeTelegram(BaseRequest):
    def __init__(self):
        self.calls: list[tuple[str, dict, dict]] = []
        self._id = 1000
        self.fail_methods: set[str] = set()

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @property
    def read_timeout(self):
        return 5.0

    def _next(self) -> int:
        self._id += 1
        return self._id

    def _message(self, params: dict, **extra) -> dict:
        chat_id = params.get("chat_id", 1)
        try:
            chat_id = int(chat_id)
        except (TypeError, ValueError):
            chat_id = 1
        msg = {"message_id": self._next(), "date": 0, "chat": {"id": chat_id, "type": "private"},
               "from": BOT}
        if "text" in params:
            msg["text"] = params["text"]
        if "caption" in params:
            msg["caption"] = params["caption"]
        msg.update(extra)
        return msg

    async def do_request(self, url, method, request_data=None, read_timeout=None, write_timeout=None,
                         connect_timeout=None, pool_timeout=None):
        if "/file/bot" in url:
            return 200, jpeg_bytes()
        api = url.rsplit("/", 1)[-1]
        params = dict(request_data.parameters) if request_data else {}
        files = {}
        if request_data and request_data.contains_files:
            files = dict(request_data.multipart_data or {})
        self.calls.append((api, params, files))
        if api in self.fail_methods:
            return 400, json.dumps({"ok": False, "error_code": 400, "description": "Bad Request: test"}).encode()
        n = self._id + 1
        result: object = True
        if api == "getMe":
            result = BOT
        elif api in ("sendMessage", "editMessageText", "editMessageReplyMarkup"):
            result = self._message(params)
        elif api == "sendPhoto":
            result = self._message(params, photo=[{"file_id": f"PHOTO{n}", "file_unique_id": f"u{n}", "width": 64,
                                                   "height": 48}])
        elif api == "sendDocument":
            result = self._message(params, document={"file_id": f"DOC{n}", "file_unique_id": f"d{n}",
                                                      "file_name": "x"})
        elif api == "sendVoice":
            result = self._message(params, voice={"file_id": f"VOICE{n}", "file_unique_id": f"v{n}", "duration": 3})
        elif api == "copyMessage":
            result = {"message_id": self._next()}
        elif api == "getFile":
            result = {"file_id": params.get("file_id"), "file_unique_id": "f", "file_size": 100,
                      "file_path": f"files/{params.get('file_id')}.jpg"}
        elif api == "getUpdates":
            result = []
        return 200, json.dumps({"ok": True, "result": result}).encode()

    # yordamchilar
    def methods(self) -> list[str]:
        return [c[0] for c in self.calls]

    def last(self, method: str) -> tuple[dict, dict]:
        for api, params, files in reversed(self.calls):
            if api == method:
                return params, files
        raise AssertionError(f"{method} chaqirilmagan; bor: {self.methods()[-15:]}")

    def texts(self) -> list[str]:
        return [str(p.get("text") or p.get("caption") or "") for a, p, _ in self.calls
                if a in ("sendMessage", "editMessageText", "sendPhoto", "sendDocument", "sendVoice")]

    def clear(self) -> None:
        self.calls.clear()


def user(uid: int, name: str = "Ustoz") -> dict:
    return {"id": uid, "is_bot": False, "first_name": name, "username": f"user{uid}", "language_code": "uz"}


_counter = [0]


def _uid() -> int:
    _counter[0] += 1
    return _counter[0]


def text_update(uid: int, text: str) -> dict:
    msg = {"message_id": _uid() + 50000, "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid),
           "text": text}
    if text.startswith("/"):
        msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return {"update_id": _uid(), "message": msg}


def callback_update(uid: int, data: str, message_id: int = 777) -> dict:
    msg = {"message_id": message_id, "date": 0, "chat": {"id": uid, "type": "private"}, "from": BOT, "text": "x"}
    return {"update_id": _uid(), "callback_query": {"id": str(_uid()), "from": user(uid), "chat_instance": "ci",
                                                    "message": msg, "data": data}}


def voice_update(uid: int, duration: int = 3) -> dict:
    msg = {"message_id": _uid() + 50000, "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid),
           "voice": {"file_id": "VOICE_IN", "file_unique_id": "vin", "duration": duration, "mime_type": "audio/ogg",
                     "file_size": 2000}}
    return {"update_id": _uid(), "message": msg}


def document_update(uid: int, file_name: str, size: int = 1000) -> dict:
    msg = {"message_id": _uid() + 50000, "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid),
           "document": {"file_id": "DOC_IN", "file_unique_id": "din", "file_name": file_name, "file_size": size}}
    return {"update_id": _uid(), "message": msg}


def photo_update(uid: int) -> dict:
    msg = {"message_id": _uid() + 50000, "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid),
           "photo": [{"file_id": "P_IN", "file_unique_id": "pin", "width": 10, "height": 10}]}
    return {"update_id": _uid(), "message": msg}
