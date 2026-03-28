"""
Blogy — Grok (xAI) Provider
Uses OpenAI-compatible API at api.x.ai.
"""

import os
from openai import OpenAI
from providers.base import BaseProvider


class GrokProvider(BaseProvider):
    name = "grok"
    is_free_tier = False

    def __init__(self):
        self.api_key = os.getenv("GROK_API_KEY", "")
        self.model = os.getenv("GROK_MODEL", "grok-3")

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-grok-key-here"

    def chat_completion(self, messages, temperature=0.7, max_tokens=4096) -> str:
        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1",
        )
        response = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise Exception("Grok returned empty response")
        return content
