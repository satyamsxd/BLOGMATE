"""
Blogy — Groq Provider
Uses OpenAI-compatible API at api.groq.com.
Free tier: 30 RPM / 14,400 RPD on llama models.
"""

import os
from openai import OpenAI
from providers.base import BaseProvider


class GroqProvider(BaseProvider):
    name = "groq"
    is_free_tier = True

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-groq-key-here"

    def chat_completion(self, messages, temperature=0.7, max_tokens=4096) -> str:
        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise Exception("Groq returned empty response")
        return content
