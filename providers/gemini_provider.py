"""
Blogy — Google Gemini Provider
Uses the Gemini REST API via httpx (already installed as openai dependency).
Free tier: 15 RPM / 1M TPM on gemini-2.0-flash.
"""

import os
import json
import httpx
from providers.base import BaseProvider


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(BaseProvider):
    name = "gemini"
    is_free_tier = True

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-gemini-key-here"

    def chat_completion(self, messages, temperature=0.7, max_tokens=4096) -> str:
        url = GEMINI_API_URL.format(model=self.model) + f"?key={self.api_key}"

        # Convert OpenAI-style messages to Gemini format
        contents = []
        system_text = ""

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_text = content
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        # Add system instruction if present
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }

        response = httpx.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120.0,
        )
        response.raise_for_status()

        data = response.json()

        # Extract text from Gemini response
        candidates = data.get("candidates", [])
        if not candidates:
            raise Exception(f"Gemini returned no candidates: {json.dumps(data)[:200]}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise Exception("Gemini returned empty parts")

        text = parts[0].get("text", "")
        if not text:
            raise Exception("Gemini returned empty text")
        return text
