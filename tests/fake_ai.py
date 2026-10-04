"""OpenAI va Gemini API’larining soxta javoblari (httpx.MockTransport)."""
from __future__ import annotations

import base64
import json

import httpx

from .fake_telegram import jpeg_bytes


def openai_transport(state: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        state.setdefault("calls", []).append((request.method, path))
        if state.get("fail_status"):
            return httpx.Response(state["fail_status"], json={"error": {"message": state.get("fail_message", "x"),
                                                                        "code": state.get("fail_code", "")}})
        if path == "/v1/models":
            models = state.get("models", ["gpt-5.4-mini", "gpt-image-2", "gpt-4o-mini-transcribe", "gpt-6-luna"])
            return httpx.Response(200, json={"data": [{"id": m} for m in models]})
        if path == "/v1/responses":
            body = json.loads(request.content)
            state.setdefault("bodies", []).append(body)
            name = (body.get("text") or {}).get("format", {}).get("name")
            if name == "check":
                payload = state.get("check", {"groups": [{"index": 1, "counted": 6}, {"index": 2, "counted": 4}],
                                              "has_text": False})
            else:
                payload = state["lesson"]
            return httpx.Response(200, json={"status": "completed", "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text",
                                                 "text": json.dumps(payload, ensure_ascii=False)}]}]})
        if path == "/v1/images/generations":
            state.setdefault("image_bodies", []).append(json.loads(request.content))
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(jpeg_bytes((250, 200, 120))).decode()}]})
        if path == "/v1/audio/transcriptions":
            return httpx.Response(200, json={"text": state.get("transcript", "Bog'dagi hosil")})
        return httpx.Response(404, json={"error": {"message": "unknown path"}})
    return httpx.MockTransport(handler)


def gemini_transport(state: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        state.setdefault("calls", []).append((request.method, path))
        if path.endswith("/models"):
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.1-flash-image", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]})
        if path.endswith(":generateContent"):
            body = json.loads(request.content)
            state.setdefault("bodies", []).append((path, body))
            gen = body.get("generationConfig") or {}
            if "IMAGE" in (gen.get("responseModalities") or []):
                return httpx.Response(200, json={"candidates": [{"content": {"parts": [
                    {"text": "Mana rasm"},
                    {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(jpeg_bytes()).decode()}}]},
                    "finishReason": "STOP"}]})
            parts = body["contents"][0]["parts"]
            if any("inlineData" in p and p["inlineData"]["mimeType"].startswith("audio") for p in parts):
                text = state.get("transcript", "Qishki tabiat")
            elif any("inlineData" in p for p in parts):
                text = json.dumps(state.get("check", {"groups": [{"index": 1, "counted": 6}, {"index": 2, "counted": 4}],
                                                      "has_text": False}))
            else:
                text = json.dumps(state["lesson"], ensure_ascii=False)
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [
                {"text": "o‘ylanyapman", "thought": True}, {"text": text}]}, "finishReason": "STOP"}]})
        return httpx.Response(404, json={"error": {"message": "not found", "status": "NOT_FOUND"}})
    return httpx.MockTransport(handler)
