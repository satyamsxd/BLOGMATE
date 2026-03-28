"""
Blogy — JSON Parser Utility
Robust JSON parsing that handles common LLM output issues:
- Markdown code fences (```json ... ```)
- Trailing commas
- Single quotes instead of double
- Truncated JSON (attempts to close brackets)
- Control characters and invalid escapes
"""

import json
import re
from typing import Optional


def parse_llm_json(raw: str) -> dict:
    """
    Parse JSON from LLM output with multiple repair strategies.

    Args:
        raw: Raw LLM output string that should contain JSON.

    Returns:
        Parsed dict.

    Raises:
        ValueError: If JSON cannot be parsed after all repair attempts.
    """
    # Step 1: Strip markdown code fences
    text = strip_code_fences(raw)

    # Step 2: Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Step 3: Try with trailing comma removal
    try:
        cleaned = remove_trailing_commas(text)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 4: Try with control character removal
    try:
        cleaned = remove_control_chars(text)
        cleaned = remove_trailing_commas(cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 5: Try to extract JSON object from text
    try:
        extracted = extract_json_object(text)
        if extracted:
            cleaned = remove_trailing_commas(extracted)
            return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 6: Try closing unclosed brackets
    try:
        fixed = attempt_close_json(text)
        cleaned = remove_trailing_commas(fixed)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 7: Try replacing single quotes with double
    try:
        replaced = text.replace("'", '"')
        cleaned = remove_trailing_commas(replaced)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # All attempts failed
    # Show first 500 chars of the problematic text for debugging
    preview = text[:500].replace('\n', '\\n')
    raise ValueError(
        f"Failed to parse JSON from LLM output after all repair attempts. "
        f"Preview: {preview}"
    )


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json, ```, etc.)."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (```json, ```JSON, ```, etc.)
        text = re.sub(r'^```\w*\s*\n?', '', text, count=1)
        # Remove closing fence
        text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def remove_trailing_commas(text: str) -> str:
    """Remove trailing commas before closing brackets/braces."""
    # Remove comma followed by whitespace and closing bracket/brace
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def remove_control_chars(text: str) -> str:
    """Remove control characters that break JSON parsing."""
    # Keep newlines, tabs, and carriage returns but remove other control chars
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


def extract_json_object(text: str) -> Optional[str]:
    """Try to extract the first complete JSON object from text."""
    # Find the first { and try to find its matching }
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        c = text[i]

        if escape:
            escape = False
            continue

        if c == '\\' and in_string:
            escape = True
            continue

        if c == '"' and not escape:
            in_string = not in_string
            continue

        if in_string:
            continue

        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    # If we get here, brackets aren't balanced — return from start to end
    return text[start:]


def attempt_close_json(text: str) -> str:
    """Attempt to close unclosed JSON brackets and braces."""
    text = text.strip()

    # Count unclosed brackets
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape = False

    for c in text:
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            open_braces += 1
        elif c == '}':
            open_braces -= 1
        elif c == '[':
            open_brackets += 1
        elif c == ']':
            open_brackets -= 1

    # Remove any trailing partial content after the last complete value
    # (e.g. truncated string)
    if in_string:
        # Close the unclosed string
        text += '"'

    # Close any unclosed brackets/braces
    text += ']' * max(0, open_brackets)
    text += '}' * max(0, open_braces)

    return text
