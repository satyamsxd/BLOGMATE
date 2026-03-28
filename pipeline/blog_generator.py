"""
Blogy — Stage 4: Controlled Blog Generation Layer
Generates the blog in batches of 2-3 sections per API call to reduce total calls.
Includes keyword count tracking to prevent over-stuffing.
Uses the ProviderManager for automatic multi-provider fallback with round-robin.
"""

import json
import re
from config import settings
from pipeline.prompt_flow import PROMPTS
from providers.manager import get_manager


def _count_keyword_occurrences(text: str, keyword: str) -> int:
    """Count exact occurrences of the primary keyword in text (case-insensitive)."""
    if not keyword or not text:
        return 0
    return len(re.findall(re.escape(keyword.lower()), text.lower()))


def _get_density_instruction(keyword_count: int, section_index: int, total_sections: int) -> str:
    """
    Generate a dynamic density instruction based on how many times
    the keyword has already been used. Target: 1-2% density.
    For a ~2000-word blog with a 3-word keyword, that means ~7-13 mentions total.
    """
    is_last_section = (section_index == total_sections - 1)
    is_second_last = (section_index == total_sections - 2)

    if section_index == 0:
        return (
            "This is the introduction. You MUST use the exact primary keyword ONCE within the "
            "first 2-3 sentences to establish the topic. This is critical for SEO."
        )
    elif is_last_section or is_second_last:
        if keyword_count < 6:
            return (
                "This is near the conclusion. You MUST use the exact primary keyword ONCE in this section "
                "to reinforce the topic for SEO. Place it naturally in the closing paragraph."
            )
        else:
            return (
                "This is near the conclusion. Use the exact primary keyword ONCE for SEO reinforcement. "
                "Keep it natural — a single mention is enough."
            )
    elif keyword_count <= 2:
        return "Keyword usage is still low. Use the exact primary keyword ONCE in this section."
    elif keyword_count <= 5:
        return (
            "Keyword usage is moderate. You may use the exact primary keyword ONCE in this section. "
            "Also mix in synonyms and related phrases."
        )
    elif keyword_count <= 8:
        return (
            "Keyword count is healthy. Use the exact keyword ZERO or ONE time in this section. "
            "Prefer synonyms, related phrases, or pronouns instead."
        )
    else:
        return (
            f"The keyword has been used {keyword_count} times — approaching the upper limit. "
            "Do NOT use the exact primary keyword in this section. "
            "Use synonyms, rephrase it, or refer to the concept with pronouns like 'it', 'this approach', 'these strategies'."
        )


def _batch_sections(outline: list, batch_size: int = 2) -> list[list[tuple[int, dict]]]:
    """
    Split outline into batches of sections for combined generation.
    First section (intro) is always solo for quality. Conclusion is always solo.
    Middle sections are batched in groups of batch_size.
    """
    if len(outline) <= 3:
        # Very short outlines: generate each section individually
        return [[(i, s)] for i, s in enumerate(outline)]

    batches = []

    # Intro section — solo (quality matters most here)
    batches.append([(0, outline[0])])

    # Middle sections — batch in groups
    middle = list(enumerate(outline))[1:-1]
    for i in range(0, len(middle), batch_size):
        batch = middle[i:i + batch_size]
        batches.append(batch)

    # Conclusion — solo (quality matters)
    batches.append([(len(outline) - 1, outline[-1])])

    return batches


BATCH_SYSTEM_PROMPT = (
    "You are an expert content writer who produces authoritative, insight-rich content. "
    "Your writing style is conversational, clear, and easy to read. "
    "You write at an 8th-grade reading level — short sentences, simple words, active voice. "
    "\n\nWRITING STYLE RULES (follow strictly):\n"
    "- Keep most sentences between 8 and 20 words. Mix in a few shorter ones for punch.\n"
    "- Use common, everyday words. Say 'use' not 'utilize', 'get' not 'obtain', 'help' not 'facilitate'.\n"
    "- Prefer active voice: 'Teams send emails' not 'Emails are sent by teams'.\n"
    "- Break up long ideas into multiple short sentences.\n"
    "- Use contractions naturally (don't, it's, you'll, that's).\n"
    "- Address the reader directly with 'you' and 'your'.\n"
    "- One idea per sentence. One theme per paragraph.\n"
    "\n\nSTRICTLY FORBIDDEN phrases (never use these):\n"
    '- "In today\'s [anything]..."\n'
    '- "It\'s important to note..."\n'
    '- "In the ever-evolving..."\n'
    '- "Landscape"\n'
    '- "Dive into" / "Deep dive"\n'
    '- "Leverage" (use "use" instead)\n'
    '- "Utilize" (use "use" instead)\n'
    '- "Game-changer"\n'
    '- "Unlock the power"\n'
    '- "Navigate the complexities"\n'
    '- "Harness"\n'
    '- "Seamless" / "Seamlessly"\n'
    '- "Robust"\n'
    '- "Cutting-edge"\n'
    '- "Furthermore" / "Moreover" / "Additionally"\n'
    '- "Consequently" / "Subsequently" / "Nevertheless"\n'
    "\n\nWrite like a knowledgeable friend explaining something over coffee, not a textbook."
)


def _build_batch_prompt(batch: list[tuple[int, dict]], primary_keyword: str,
                        tone_str: str, prev_snippet: str,
                        keyword_count_so_far: int, total_sections: int) -> str:
    """Build a combined prompt for multiple sections in one API call."""
    sections_desc = []
    for idx, section in batch:
        heading = section.get("heading", "Untitled Section")
        level = section.get("level", "H2")
        target_keywords = section.get("target_keywords", [])
        section_notes = section.get("section_notes", "")
        geo_format = section.get("geo_format", "paragraph")

        density_instruction = _get_density_instruction(keyword_count_so_far, idx, total_sections)

        sections_desc.append(f"""--- SECTION {idx + 1} ---
Heading: {heading} (Level: {level})
Target Keywords: {json.dumps(target_keywords)}
Section Guidance: {section_notes}
GEO Format: {geo_format}
Keyword Instruction: {density_instruction}""")

    sections_text = "\n\n".join(sections_desc)

    if len(batch) == 1:
        # Single section — use the original prompt format
        prompt_cfg = PROMPTS["blog_section"]
        idx, section = batch[0]
        density_instruction = _get_density_instruction(keyword_count_so_far, idx, total_sections)
        return prompt_cfg["user"].format(
            heading=section.get("heading", ""),
            level=section.get("level", "H2"),
            target_keywords=json.dumps(section.get("target_keywords", [])),
            section_notes=section.get("section_notes", ""),
            geo_format=section.get("geo_format", "paragraph"),
            tone=tone_str,
            previous_content=prev_snippet,
            primary_keyword=primary_keyword,
            keyword_count_so_far=keyword_count_so_far,
            density_instruction=density_instruction,
        )

    return f"""Write the following {len(batch)} sections of a blog post IN ORDER. 
Write each section completely with its heading before moving to the next section.

Overall blog topic: {primary_keyword}
Tone: {tone_str}

KEYWORD DENSITY STATUS:
- Primary keyword "{primary_keyword}" has been used {keyword_count_so_far} times so far.
- Follow each section's keyword instruction carefully.

Previous content (for continuity):
{prev_snippet}

{sections_text}

Rules for ALL sections:
- Write 150-300 words PER section
- Use each heading as provided (include the markdown heading syntax: # for H1, ## for H2, ### for H3)
- READABILITY IS CRITICAL: Write short, clear sentences. Average 12-18 words per sentence.
- Follow each section's keyword instruction precisely
- Match the GEO format requirement for each section
- Include at least one specific example, data point, or insight per section
- Use short paragraphs (2-4 sentences each)
- Do NOT repeat ideas between sections
- Do NOT use any forbidden phrases
- Write ONLY the section content, output all sections in order separated by their headings"""


def run(keyword_intel: dict, content_strategy: dict) -> dict:
    """
    Generate blog content using batched section generation to reduce API calls.
    10 sections → ~5-6 API calls instead of 10.
    """
    manager = get_manager()
    prompt_cfg = PROMPTS["blog_section"]
    outline = content_strategy.get("outline", [])
    tone = content_strategy.get("tone_strategy", {})
    tone_str = json.dumps(tone)
    primary_keyword = keyword_intel.get("primary_keyword", "")
    total_sections = len(outline)

    # Batch middle sections in groups of 2
    batches = _batch_sections(outline, batch_size=2)

    sections = []
    accumulated_content = ""
    keyword_count_so_far = 0

    for batch in batches:
        prev_snippet = accumulated_content[-500:] if accumulated_content else "(This is the first section)"

        # Build the prompt for this batch
        user_prompt = _build_batch_prompt(
            batch, primary_keyword, tone_str, prev_snippet,
            keyword_count_so_far, total_sections
        )

        # Use batch system prompt for multi-section calls, original for single
        system_prompt = prompt_cfg["system"] if len(batch) == 1 else BATCH_SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        batch_content = manager.complete(
            messages=messages,
            temperature=settings.TEMPERATURES["blog_generation"],
        ).strip()

        # For single section batches, just record directly
        if len(batch) == 1:
            idx, section = batch[0]
            word_count = len(batch_content.split())
            hits = _count_keyword_occurrences(batch_content, primary_keyword)
            keyword_count_so_far += hits

            sections.append({
                "heading": section.get("heading", "Untitled Section"),
                "level": section.get("level", "H2"),
                "content": batch_content,
                "word_count": word_count,
                "keyword_hits": hits,
            })
            accumulated_content += "\n\n" + batch_content
        else:
            # Split batch response by headings
            # Try to split by ## or ### markers
            section_parts = _split_batch_response(batch_content, batch)

            for (idx, section_def), content in zip(batch, section_parts):
                word_count = len(content.split())
                hits = _count_keyword_occurrences(content, primary_keyword)
                keyword_count_so_far += hits

                sections.append({
                    "heading": section_def.get("heading", "Untitled Section"),
                    "level": section_def.get("level", "H2"),
                    "content": content.strip(),
                    "word_count": word_count,
                    "keyword_hits": hits,
                })
                accumulated_content += "\n\n" + content

    full_markdown = accumulated_content.strip()
    total_word_count = len(full_markdown.split())

    return {
        "full_markdown": full_markdown,
        "sections": sections,
        "total_word_count": total_word_count,
        "total_keyword_mentions": keyword_count_so_far,
        "api_calls_used": len(batches),
    }


def _split_batch_response(response: str, batch: list[tuple[int, dict]]) -> list[str]:
    """
    Split a multi-section batch response into individual section contents.
    Uses heading markers to split.
    """
    if len(batch) <= 1:
        return [response]

    # Try splitting by heading markers (## or ###)
    parts = re.split(r'(?=^#{1,3}\s)', response, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]

    # If we got the right number of parts, return them
    if len(parts) == len(batch):
        return parts

    # If we got more parts than expected (subsections), merge extras into the last section
    if len(parts) > len(batch):
        merged = parts[:len(batch) - 1]
        merged.append("\n\n".join(parts[len(batch) - 1:]))
        return merged

    # If we got fewer parts, the LLM merged sections — split roughly by word count
    if len(parts) < len(batch):
        words = response.split()
        chunk_size = len(words) // len(batch)
        result = []
        for i in range(len(batch)):
            start = i * chunk_size
            end = start + chunk_size if i < len(batch) - 1 else len(words)
            result.append(" ".join(words[start:end]))
        return result

    return parts
