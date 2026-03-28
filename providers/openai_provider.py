"""
Blogy — OpenAI Provider
Wraps the OpenAI API (gpt-4o-mini, gpt-4o, etc.)
"""

import os
from openai import OpenAI
from providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    name = "openai"
    is_free_tier = False

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your-api-key-here"

    def chat_completion(self, messages, temperature=0.7, max_tokens=4096) -> str:
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise Exception("OpenAI returned empty response")
        return content
