"""
Blogy — Prompt Flow Module
Central prompt management for all pipeline stages.
Each prompt is a structured template with system message, user message, and expected output format.
"""

PROMPTS = {

    # ── Stage 1: Keyword Intelligence ──────────────────────────────────────
    "keyword_intelligence": {
        "system": (
            "You are an expert SEO keyword research analyst. "
            "You analyze keywords with the precision of a search systems engineer. "
            "You never fabricate search volume numbers — instead you reason about "
            "relative competition and relevance qualitatively. "
            "You always return valid JSON."
        ),
        "user": """Analyze the keyword: "{keyword}"

Return a JSON object with EXACTLY this structure (no markdown fences, pure JSON):
{{
  "primary_keyword": "{keyword}",
  "semantic_clusters": {{
    "core_topic": ["keyword1", "keyword2", "keyword3"],
    "related_concepts": ["keyword4", "keyword5", "keyword6"],
    "use_cases": ["keyword7", "keyword8", "keyword9"]
  }},
  "long_tail_variations": ["5-8 realistic long-tail search queries"],
  "lsi_keywords": ["8-12 latent semantic indexing keywords that co-occur naturally"],
  "question_queries": ["6-8 question-based queries real users would search"],
  "intent_classification": "informational|commercial|transactional",
  "intent_reasoning": "2-3 sentence explanation of why this intent was chosen",
  "ranking_feasibility": [
    {{
      "keyword": "specific keyword",
      "competition": "low|medium|high",
      "relevance": "high|medium|low",
      "score": 0.0-1.0,
      "reasoning": "why this keyword is feasible to rank for"
    }}
  ]
}}

Rules:
- Clusters must reflect realistic search behavior, not generic expansions
- Long-tail variations must be specific queries a real person would type
- LSI keywords must naturally co-occur in high-quality content about this topic
- Question queries must reflect genuine search intent
- Ranking feasibility should prioritize low-competition, high-relevance keywords
- Every score must have reasoning""",
    },

    # ── Stage 2: SERP Reverse Engineering ──────────────────────────────────
    "serp_analysis": {
        "system": (
            "You are a SERP analysis specialist who reverse-engineers why pages rank. "
            "You do NOT hallucinate competitor URLs or specific websites. "
            "Instead, you infer structural patterns based on how top-ranking SEO pages "
            "are typically structured for a given keyword cluster. "
            "You always return valid JSON."
        ),
        "user": """Based on this keyword intelligence, reverse-engineer the typical SERP structure:

Primary Keyword: {primary_keyword}
Semantic Clusters: {semantic_clusters}
Intent: {intent_classification}
Top Feasible Keywords: {top_keywords}

Return a JSON object with EXACTLY this structure (no markdown fences, pure JSON):
{{
  "typical_heading_structure": [
    {{"level": "H1", "pattern": "descriptive pattern", "example": "example heading"}},
    {{"level": "H2", "pattern": "descriptive pattern", "example": "example heading"}},
    {{"level": "H3", "pattern": "descriptive pattern", "example": "example heading"}}
  ],
  "content_depth_patterns": {{
    "typical_word_count": "1500-2500",
    "sections_count": "6-10",
    "includes_examples": true,
    "includes_data": true,
    "includes_visuals_described": true,
    "content_format_mix": ["paragraphs", "lists", "tables", "code blocks"]
  }},
  "keyword_positioning": {{
    "title_placement": "description of how keywords appear in titles",
    "intro_placement": "description of keyword usage in first 100 words",
    "heading_placement": "how keywords are woven into H2/H3 headings",
    "conclusion_placement": "keyword reinforcement patterns in conclusions"
  }},
  "content_gaps": [
    {{
      "gap": "specific missing subtopic or weakness",
      "severity": "high|medium|low",
      "opportunity": "how addressing this gap creates ranking advantage",
      "gap_type": "missing_subtopic|weak_explanation|outdated_content|missing_format"
    }}
  ],
  "gap_report_summary": "3-5 sentence executive summary of the biggest content gaps and the strategy to exploit them"
}}

Rules:
- Do NOT reference specific competitor URLs or brand names
- Infer patterns from how high-quality SEO content is typically structured
- Content gaps must be actionable and specific
- Each gap must have a clear exploitation strategy
- Include at least 5-7 content gaps""",
    },

    # ── Stage 3: Content Strategy ──────────────────────────────────────────
    "content_strategy": {
        "system": (
            "You are a senior content strategist who builds SEO content blueprints. "
            "You think in terms of search intent satisfaction, CTR optimization, "
            "and content architecture. You design content that is easily extractable "
            "by AI answer engines (GEO optimization). "
            "You always return valid JSON."
        ),
        "user": """Build a complete content strategy based on:

Primary Keyword: {primary_keyword}
Intent: {intent_classification}
Content Gaps to Exploit: {content_gaps}
Top Keywords to Target: {top_keywords}
LSI Keywords: {lsi_keywords}
Question Queries: {question_queries}

Return a JSON object with EXACTLY this structure (no markdown fences, pure JSON):
{{
  "seo_title": "CTR-optimized title (50-60 chars, compelling, not robotic)",
  "meta_description": "compelling meta description (150-160 chars) with primary keyword",
  "outline": [
    {{
      "level": "H1",
      "heading": "the main title",
      "target_keywords": ["kw1", "kw2"],
      "section_notes": "what this section should accomplish",
      "geo_format": "paragraph|definition|list|table|qa|process"
    }},
    {{
      "level": "H2",
      "heading": "section heading",
      "target_keywords": ["kw3", "kw4"],
      "section_notes": "content guidance for this section",
      "geo_format": "paragraph|definition|list|table|qa|process"
    }}
  ],
  "section_keyword_map": {{
    "Section Heading": ["target", "keywords", "for", "this", "section"]
  }},
  "tone_strategy": {{
    "voice": "authority-driven|conversational|technical",
    "positioning": "description of the content's angle",
    "differentiation": "what makes this content unique vs typical results",
    "conversion_hooks": ["where and how to subtly guide toward conversion"]
  }},
  "geo_optimization": {{
    "definition_blocks": ["topics that need clear, extractable definitions"],
    "numbered_processes": ["processes that should be structured as numbered steps"],
    "comparison_tables": ["comparisons that should be formatted as tables"],
    "qa_sections": ["questions that should be answered in FAQ format"],
    "key_takeaway_boxes": ["sections that need summary callout boxes"]
  }}
}}

Rules:
- Title must be compelling for humans AND optimized for search
- Title MUST contain the primary keyword naturally
- Meta description MUST contain the primary keyword in the first half
- Outline must have 8-12 sections (H1 + H2s + H3s)
- Include the primary keyword naturally in at least 2-3 H2 headings (not forced, must read naturally)
- Every section must map to specific target keywords
- GEO optimization must identify at least 3 AI-extractable content blocks
- Tone MUST be conversational — write section_notes that instruct the writer to use simple, direct language
- Voice should be "conversational" — like an expert friend, not a textbook
- Include at least one section with geo_format "list" and one with "qa" for snippet readiness
- Section notes should guide the writer to use real examples and data points""",
    },

    # ── Stage 4: Blog Generation (per-section) ────────────────────────────
    "blog_section": {
        "system": (
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
            "\n\nKEYWORD DENSITY RULES (critical — violations cause SEO penalties):\n"
            "- You will be told the primary keyword and how many times it has been used so far.\n"
            "- Follow the DENSITY INSTRUCTION provided in the user message — it tells you exactly how many times to use the keyword.\n"
            "- Target overall density is 1-2%. For a ~2000-word blog with a 3-word keyword, that means about 7-13 total mentions.\n"
            "- When NOT using the exact keyword, use synonyms, pronouns (it, this, these), or rephrase naturally.\n"
            "- Never stuff keywords. Google penalizes keyword density above 2.5%.\n"
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
            '- "Furthermore" / "Moreover" / "Additionally" (use simpler connectors)\n'
            '- "Consequently" / "Subsequently" / "Nevertheless"\n'
            "\n\nWrite like a knowledgeable friend explaining something over coffee, not a textbook."
        ),
        "user": """Write the following section of a blog post:

Section Heading: {heading} (Level: {level})
Target Keywords for this section: {target_keywords}
Section Guidance: {section_notes}
GEO Format Requirement: {geo_format}
Tone: {tone}

Previous sections written so far (maintain narrative continuity):
{previous_content}

Overall blog topic: {primary_keyword}

KEYWORD DENSITY STATUS:
- Primary keyword "{primary_keyword}" has been used {keyword_count_so_far} times so far across all previous sections.
- {density_instruction}

Rules:
- Write 150-300 words for this section
- Use the heading as provided (include the markdown heading syntax: # for H1, ## for H2, ### for H3)
- READABILITY IS CRITICAL: Write short, clear sentences. Average 12-18 words per sentence. Use simple vocabulary a teenager could understand.
- KEYWORD USAGE: Follow the density instruction above exactly. When you use the primary keyword, place it where it flows naturally.
- Integrate secondary/target keywords naturally — never force them
- Match the GEO format requirement:
  - "definition": Start with a clear, one-sentence definition
  - "list": Use bullet points or numbered lists
  - "table": Include a markdown table
  - "qa": Format as question and answer
  - "process": Use numbered steps
  - "paragraph": Standard prose paragraphs
- Include at least one specific example, data point, or insight
- Use short paragraphs (2-4 sentences each)
- Do NOT repeat ideas from previous sections
- Do NOT use any forbidden phrases
- Write ONLY the section content, nothing else""",
    },

    # ── Stage 6: Internal Linking ──────────────────────────────────────────
    "internal_linking": {
        "system": (
            "You are an internal linking specialist. You identify natural anchor text "
            "opportunities within content to link to relevant internal pages. "
            "Links must be contextually justified, not forced. "
            "You always return valid JSON."
        ),
        "user": """Analyze this blog content and suggest internal links:

Blog Content:
{blog_content}

Available Internal Pages:
{internal_pages}

Return a JSON object with EXACTLY this structure (no markdown fences, pure JSON):
{{
  "suggestions": [
    {{
      "anchor_text": "the exact text from the blog to hyperlink",
      "url": "/target-page-url",
      "page_title": "Target Page Title",
      "section": "which blog section this appears in",
      "reasoning": "why this link is contextually relevant and valuable",
      "placement_type": "natural_mention|call_to_action|reference"
    }}
  ]
}}

Rules:
- Suggest 3-6 internal links maximum
- Anchor text must exist naturally in the blog content
- Each link must have a clear contextual justification
- Do not force links — only suggest where they genuinely fit
- Vary placement types for natural linking patterns""",
    },
}
