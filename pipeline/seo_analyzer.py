"""
Blogy — Stage 5: SEO + Quality Validation Engine
Pure Python analysis engine — no LLM calls.
Computes SEO score, readability, naturalness, snippet readiness, and keyword density.
"""

import re
import math
from collections import Counter


# ── Known AI cliché phrases (multi-word only — avoids false positives) ─────
AI_PHRASES = [
    "in today's", "it's important to note", "in the ever-evolving",
    "dive into", "deep dive", "unlock the power", "navigate the complexities",
    "game-changer", "at the end of the day", "it goes without saying",
    "needless to say", "in a nutshell", "moving forward",
    "let's explore", "without further ado", "look no further",
    "paradigm shift", "holistic approach", "delve into",
    "in this article we will", "in this blog post",
    "in this comprehensive guide", "it's worth noting",
    "first and foremost", "it is essential", "play a crucial role",
    "a wide range of", "on the other hand", "in order to",
    "take your .* to the next level", "when it comes to",
]

# ── Single-word AI clichés (tracked but penalized less) ───────────────────
AI_SINGLE_WORDS = [
    "leverage", "utilize", "revolutionize", "synergy",
    "empower", "seamlessly", "cutting-edge", "delve",
    "harness", "robust", "landscape", "crucial",
    "pivotal", "comprehensive", "streamline",
]

# ── Overused transitions ─────────────────────────────────────────────────
OVERUSED_TRANSITIONS = [
    "furthermore", "moreover", "additionally", "consequently",
    "nevertheless", "nonetheless", "therefore",
    "thus", "hence", "accordingly", "subsequently",
]


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting to get clean prose for analysis."""
    clean = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    clean = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', clean)
    clean = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', clean)
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
    clean = re.sub(r'`[^`]+`', '', clean)
    clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
    clean = re.sub(r'^[-*_]{3,}\s*$', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\|?[\s\-:]+\|[\s\-:|]+$', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'\|', ' ', clean)
    clean = re.sub(r'^[\s]*[-*+]\s+', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^[\s]*\d+[.)]\s+', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean.strip()


def _count_syllables(word: str) -> int:
    """Estimate syllable count for a word using improved heuristics."""
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1

    vowels = re.findall(r'[aeiouy]+', word)
    count = len(vowels)

    if word.endswith('e') and count > 1:
        count -= 1
    if word.endswith('le') and len(word) > 3 and word[-3] not in 'aeiouy':
        count += 1
    if word.endswith('ed') and len(word) > 3 and word[-3] not in 'td' and count > 1:
        count -= 1
    if word.endswith('es') and len(word) > 4 and count > 1:
        if word[-3] not in 'szxgcaeiouy' and not word.endswith('shes') and not word.endswith('ches'):
            count -= 1

    for suffix in ['ment', 'ness', 'ful', 'less', 'ly']:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            pos = len(word) - len(suffix) - 1
            if pos > 0 and word[pos] == 'e' and word[pos - 1] not in 'aeiouy' and count > 1:
                count -= 1
            break

    return max(count, 1)


def _flesch_reading_ease(text: str) -> float:
    """Calculate Flesch Reading Ease score on clean prose."""
    clean = _strip_markdown(text)
    sentences = re.split(r'[.!?]+|\n+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 2]
    words = re.findall(r"\b[a-zA-Z']+\b", clean)

    if not sentences or not words:
        return 0.0

    total_sentences = len(sentences)
    total_words = len(words)
    total_syllables = sum(_count_syllables(w) for w in words)
    total_syllables = int(total_syllables * 0.9)

    score = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
    return round(max(0, min(100, score)), 1)


def _keyword_density(text: str, keyword: str) -> float:
    """Calculate keyword density as percentage."""
    clean = _strip_markdown(text)
    text_lower = clean.lower()
    keyword_lower = keyword.lower().strip()
    words = re.findall(r"\b[a-zA-Z']+\b", text_lower)
    total_words = len(words)

    if total_words == 0 or not keyword_lower:
        return 0.0

    count = text_lower.count(keyword_lower)
    keyword_word_count = len(keyword_lower.split())

    density = (count * keyword_word_count / total_words) * 100
    return round(density, 2)


# ── Multi-word keyword matching helpers ────────────────────────────────────

def _keyword_words(keyword: str) -> list[str]:
    """Split a keyword into its component words (lowercased)."""
    return [w.lower().strip() for w in keyword.split() if w.strip()]


def _check_keyword_in_text(text: str, keyword: str) -> tuple[bool, bool]:
    """
    Check for keyword presence in text. Returns (exact_match, partial_match).
    Exact: full phrase found. Partial: all individual words found close together.
    """
    text_lower = text.lower()
    pk_lower = keyword.lower().strip()

    # Exact match
    if pk_lower in text_lower:
        return True, True

    # For single-word keywords, no partial match possible
    kw_words = _keyword_words(keyword)
    if len(kw_words) <= 1:
        return False, False

    # Partial match: check if all keyword words exist in the text
    all_words_present = all(w in text_lower for w in kw_words)
    return False, all_words_present


def _count_keyword_in_headings(headings: list[str], keyword: str) -> tuple[int, int]:
    """
    Count headings with exact keyword match and partial keyword match.
    Returns (exact_count, partial_count).
    """
    exact = 0
    partial = 0
    kw_words = _keyword_words(keyword)

    for h in headings:
        h_lower = h.lower()
        if keyword.lower() in h_lower:
            exact += 1
        elif len(kw_words) > 1 and sum(1 for w in kw_words if w in h_lower) >= len(kw_words) - 1:
            # At least N-1 of N keyword words present in heading
            partial += 1

    return exact, partial


def _detect_repetition(text: str) -> list:
    """Detect repetitive trigram patterns."""
    clean = _strip_markdown(text)
    words = re.findall(r"\b[a-zA-Z]+\b", clean.lower())
    if len(words) < 3:
        return []

    trigrams = [" ".join(words[i: i + 3]) for i in range(len(words) - 2)]
    counter = Counter(trigrams)
    flags = []
    for trigram, count in counter.most_common(10):
        if count >= 4:
            flags.append({"phrase": trigram, "count": count})
    return flags


def _detect_ai_phrases(text: str) -> list:
    """Detect known AI cliché phrases."""
    text_lower = text.lower()
    found = []
    for phrase in AI_PHRASES:
        if '*' in phrase:
            # Regex pattern
            matches = re.findall(phrase, text_lower)
            if matches:
                found.append({"phrase": phrase, "count": len(matches)})
        else:
            count = text_lower.count(phrase)
            if count > 0:
                found.append({"phrase": phrase, "count": count})
    for word in AI_SINGLE_WORDS:
        count = len(re.findall(r"\b" + word + r"\b", text_lower))
        if count >= 2:
            found.append({"phrase": word, "count": count})
    return found


def _detect_transition_overuse(text: str) -> list:
    """Detect overused transition words."""
    text_lower = text.lower()
    found = []
    for word in OVERUSED_TRANSITIONS:
        count = len(re.findall(r"\b" + word + r"\b", text_lower))
        if count >= 3:
            found.append({"word": word, "count": count})
    return found


# ── Real Naturalness Analysis (multi-signal, produces varied scores) ───────

def _sentence_length_variance(text: str) -> dict:
    """
    Measure sentence length variation. Natural writing has varied sentence lengths.
    Monotonous length = robotic. Returns score 0-100 and details.
    """
    clean = _strip_markdown(text)
    sentences = re.split(r'[.!?]+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 3]

    if len(sentences) < 5:
        return {"score": 70, "std_dev": 0, "detail": "Too few sentences to assess variation"}

    lengths = [len(s.split()) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_len if mean_len > 0 else 0  # coefficient of variation

    # CV > 0.5 = very varied (great), 0.3-0.5 = good, 0.15-0.3 = moderate, < 0.15 = monotonous
    if cv >= 0.5:
        score = 100
        detail = f"Excellent sentence variety (CV={cv:.2f}, σ={std_dev:.1f})"
    elif cv >= 0.35:
        score = 85
        detail = f"Good sentence variety (CV={cv:.2f}, σ={std_dev:.1f})"
    elif cv >= 0.25:
        score = 70
        detail = f"Moderate variety — could mix more short/long sentences (CV={cv:.2f})"
    elif cv >= 0.15:
        score = 50
        detail = f"Low variety — sentences are similar length (CV={cv:.2f})"
    else:
        score = 30
        detail = f"Monotonous — almost all sentences are the same length (CV={cv:.2f})"

    return {"score": score, "std_dev": round(std_dev, 1), "cv": round(cv, 2), "detail": detail}


def _vocabulary_diversity(text: str) -> dict:
    """
    Measure vocabulary richness using type-token ratio (TTR).
    High TTR = diverse vocabulary = more natural.
    """
    clean = _strip_markdown(text)
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z']+\b", clean) if len(w) > 2]

    if len(words) < 50:
        return {"score": 70, "ttr": 0, "detail": "Too few words to assess diversity"}

    # Use a moving window TTR to avoid length bias (MATTR)
    window_size = min(100, len(words))
    ttrs = []
    for i in range(0, len(words) - window_size + 1, window_size // 2):
        window = words[i:i + window_size]
        ttrs.append(len(set(window)) / len(window))

    avg_ttr = sum(ttrs) / len(ttrs) if ttrs else 0

    if avg_ttr >= 0.72:
        score = 100
        detail = f"Rich vocabulary (TTR={avg_ttr:.2f})"
    elif avg_ttr >= 0.62:
        score = 85
        detail = f"Good vocabulary diversity (TTR={avg_ttr:.2f})"
    elif avg_ttr >= 0.52:
        score = 70
        detail = f"Moderate vocabulary — some word repetition (TTR={avg_ttr:.2f})"
    elif avg_ttr >= 0.42:
        score = 50
        detail = f"Limited vocabulary — notable repetition (TTR={avg_ttr:.2f})"
    else:
        score = 30
        detail = f"Poor vocabulary diversity (TTR={avg_ttr:.2f})"

    return {"score": score, "ttr": round(avg_ttr, 3), "detail": detail}


def _sentence_opener_variety(text: str) -> dict:
    """
    Check if sentences start with the same words too often.
    Natural writing varies sentence openings.
    """
    clean = _strip_markdown(text)
    sentences = re.split(r'[.!?]+|\n+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 3]

    if len(sentences) < 8:
        return {"score": 70, "repeated_openers": [], "detail": "Too few sentences to assess"}

    # Get first word of each sentence
    openers = [s.split()[0].lower() for s in sentences if s.strip()]
    opener_counts = Counter(openers)
    total = len(openers)

    # Find openers used more than 15% of the time
    repeated = []
    penalty = 0
    for word, count in opener_counts.most_common():
        ratio = count / total
        if ratio > 0.15 and count >= 3:
            repeated.append({"word": word, "count": count, "ratio": round(ratio * 100, 1)})
            penalty += (ratio - 0.15) * 100  # Penalty proportional to overuse

    score = max(0, min(100, round(100 - penalty * 3)))

    if score >= 85:
        detail = "Good variety in sentence openings"
    elif score >= 60:
        detail = f"Some repetitive openers: {', '.join(r['word'] for r in repeated[:3])}"
    else:
        detail = f"Monotonous openings — too many sentences start with: {', '.join(r['word'] for r in repeated[:3])}"

    return {"score": score, "repeated_openers": repeated, "detail": detail}


def _passive_voice_ratio(text: str) -> dict:
    """
    Estimate passive voice usage. Too much passive = less engaging.
    Heuristic based on common passive patterns.
    """
    clean = _strip_markdown(text)
    sentences = re.split(r'[.!?]+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 3]

    if len(sentences) < 5:
        return {"score": 70, "passive_pct": 0, "detail": "Too few sentences to assess"}

    # Simple heuristic: "is/are/was/were/been/being + past participle (word ending in -ed/-en)"
    passive_pattern = re.compile(
        r'\b(?:is|are|was|were|been|being|be)\s+(?:\w+\s+)?(?:\w+(?:ed|en|t))\b',
        re.IGNORECASE
    )

    passive_count = 0
    for sent in sentences:
        if passive_pattern.search(sent):
            passive_count += 1

    passive_pct = round((passive_count / len(sentences)) * 100, 1)

    # Up to 20% passive is fine, 20-35% is moderate, >35% is heavy
    if passive_pct <= 15:
        score = 100
        detail = f"Active voice dominant ({passive_pct}% passive)"
    elif passive_pct <= 25:
        score = 80
        detail = f"Mostly active voice ({passive_pct}% passive)"
    elif passive_pct <= 35:
        score = 60
        detail = f"Moderate passive voice ({passive_pct}% passive)"
    elif passive_pct <= 50:
        score = 40
        detail = f"Heavy passive voice ({passive_pct}% passive) — sounds less engaging"
    else:
        score = 20
        detail = f"Excessive passive voice ({passive_pct}% passive) — feels robotic"

    return {"score": score, "passive_pct": passive_pct, "detail": detail}


def _paragraph_length_check(text: str) -> dict:
    """
    Check paragraph lengths. Very long paragraphs = wall of text = bad UX.
    """
    clean = _strip_markdown(text)
    paragraphs = [p.strip() for p in clean.split('\n\n') if len(p.strip().split()) >= 5]

    if len(paragraphs) < 3:
        return {"score": 70, "detail": "Too few paragraphs to assess"}

    lengths = [len(p.split()) for p in paragraphs]
    long_paragraphs = sum(1 for l in lengths if l > 80)
    very_long = sum(1 for l in lengths if l > 120)

    if very_long > 0:
        score = max(30, 80 - very_long * 20)
        detail = f"{very_long} very long paragraph(s) (>120 words) — break these up"
    elif long_paragraphs > 0:
        score = max(50, 90 - long_paragraphs * 10)
        detail = f"{long_paragraphs} long paragraph(s) (>80 words) — consider splitting"
    else:
        score = 95
        detail = "Good paragraph lengths — easy to scan"

    return {"score": score, "detail": detail}


def _check_snippet_readiness(text: str) -> dict:
    """Check if content is structured for featured snippets / AI extraction."""
    has_definitions = bool(re.search(r"\b(?:is defined as|refers to|is a |is the |means that)\b", text.lower()))
    has_bullet_lists = bool(re.search(r"^[\s]*[-*•]\s", text, re.MULTILINE))
    has_numbered_lists = bool(re.search(r"^[\s]*\d+[.)]\s", text, re.MULTILINE))
    has_tables = "|" in text and "---" in text
    has_qa = bool(re.search(r"\?\s*\n", text)) or bool(re.search(r"^#{1,3}\s+.*\?", text, re.MULTILINE))
    has_headings = bool(re.search(r"^#{1,3}\s", text, re.MULTILINE))

    elements = [has_definitions, has_bullet_lists or has_numbered_lists, has_tables, has_qa, has_headings]
    score = round((sum(elements) / len(elements)) * 100)

    return {
        "score": score,
        "has_definitions": has_definitions,
        "has_lists": has_bullet_lists or has_numbered_lists,
        "has_tables": has_tables,
        "has_qa": has_qa,
        "has_headings": has_headings,
        "elements_present": sum(elements),
        "elements_total": len(elements),
    }


def _seo_score(text: str, primary_keyword: str, strategy: dict) -> dict:
    """
    Compute SEO score (0-100) with breakdown.
    Categories: keyword_placement, keyword_density, heading_structure, meta_quality.
    Supports both single-word and multi-word keywords with partial matching.
    """
    text_lower = text.lower()
    pk_lower = primary_keyword.lower().strip()
    title = strategy.get("seo_title", "").lower()
    meta_desc = strategy.get("meta_description", "").lower()
    kw_words = _keyword_words(primary_keyword)
    is_multi_word = len(kw_words) > 1

    breakdown = {}

    # ── Keyword Placement (30 pts) ──
    placement_score = 0
    placement_details = []

    # Title check (8 pts)
    title_exact, title_partial = _check_keyword_in_text(title, primary_keyword)
    if title_exact:
        placement_score += 8
        placement_details.append("✓ Primary keyword in title")
    elif title_partial and is_multi_word:
        placement_score += 6
        placement_details.append("◐ Keyword words present in title (not exact phrase)")
    else:
        placement_details.append("✗ Primary keyword missing from title")

    # Meta description check (5 pts)
    meta_exact, meta_partial = _check_keyword_in_text(meta_desc, primary_keyword)
    if meta_exact:
        placement_score += 5
        placement_details.append("✓ Primary keyword in meta description")
    elif meta_partial and is_multi_word:
        placement_score += 3
        placement_details.append("◐ Keyword words present in meta description")
    else:
        placement_details.append("✗ Primary keyword missing from meta description")

    # Introduction check (7 pts)
    first_100 = " ".join(text_lower.split()[:100])
    intro_exact, intro_partial = _check_keyword_in_text(first_100, primary_keyword)
    if intro_exact:
        placement_score += 7
        placement_details.append("✓ Primary keyword in introduction")
    elif intro_partial and is_multi_word:
        placement_score += 5
        placement_details.append("◐ Keyword words present in introduction")
    else:
        placement_details.append("✗ Primary keyword missing from introduction")

    # Headings check (7 pts)
    headings = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
    exact_h, partial_h = _count_keyword_in_headings(headings, primary_keyword)
    total_h = exact_h + partial_h
    if exact_h >= 2:
        placement_score += 7
        placement_details.append(f"✓ Primary keyword in {exact_h} headings")
    elif total_h >= 2:
        placement_score += 6
        placement_details.append(f"◐ Keyword words in {total_h} headings ({exact_h} exact)")
    elif total_h == 1:
        placement_score += 4
        placement_details.append("◐ Primary keyword in 1 heading (aim for 2+)")
    else:
        placement_details.append("✗ Primary keyword missing from headings")

    # Conclusion check (3 pts)
    last_100 = " ".join(text_lower.split()[-100:])
    concl_exact, concl_partial = _check_keyword_in_text(last_100, primary_keyword)
    if concl_exact:
        placement_score += 3
        placement_details.append("✓ Primary keyword in conclusion")
    elif concl_partial and is_multi_word:
        placement_score += 2
        placement_details.append("◐ Keyword words present in conclusion")
    else:
        placement_details.append("✗ Primary keyword missing from conclusion")

    breakdown["keyword_placement"] = {"score": placement_score, "max": 30, "details": placement_details}

    # ── Keyword Density (25 pts) ──
    density = _keyword_density(text, primary_keyword)

    # For multi-word keywords, also check individual word density
    # If exact density is low but individual words are well-distributed, give partial credit
    density_score = 0
    density_details = []
    if 1.0 <= density <= 2.5:
        density_score = 25
        density_details.append(f"✓ Keyword density {density}% (optimal: 1-2.5%)")
    elif 0.5 <= density < 1.0 or 2.5 < density <= 3.5:
        density_score = 15
        density_details.append(f"◐ Keyword density {density}% (slightly outside 1-2.5% target)")
    elif density > 3.5:
        density_score = 5
        density_details.append(f"✗ Keyword density {density}% (over-optimized, risk of penalty)")
    else:
        # Low exact density — check if individual words are present for multi-word keywords
        if is_multi_word:
            word_densities = [_keyword_density(text, w) for w in kw_words if len(w) > 3]
            avg_word_density = sum(word_densities) / len(word_densities) if word_densities else 0
            if avg_word_density >= 1.0:
                density_score = 18
                density_details.append(
                    f"◐ Exact keyword density {density}% is low, but individual words are well-distributed "
                    f"(avg {avg_word_density:.1f}%)"
                )
            else:
                density_score = 10
                density_details.append(f"◐ Keyword density {density}% (could be higher)")
        else:
            density_score = 8
            density_details.append(f"◐ Keyword density {density}% (could be higher)")

    breakdown["keyword_density"] = {"score": density_score, "max": 25, "details": density_details}

    # ── Heading Structure (25 pts) ──
    heading_score = 0
    heading_details = []
    h1_count = len(re.findall(r"^# [^#]", text, re.MULTILINE))
    h2_count = len(re.findall(r"^## [^#]", text, re.MULTILINE))
    h3_count = len(re.findall(r"^### ", text, re.MULTILINE))

    if h1_count == 1:
        heading_score += 8
        heading_details.append("✓ Single H1 tag present")
    elif h1_count == 0:
        heading_score += 3
        heading_details.append("◐ No explicit H1 tag (title may serve as H1)")
    else:
        heading_score += 3
        heading_details.append(f"✗ Multiple H1 tags ({h1_count}) — should be exactly 1")

    if h2_count >= 4:
        heading_score += 10
        heading_details.append(f"✓ {h2_count} H2 sections (good depth)")
    elif h2_count >= 2:
        heading_score += 6
        heading_details.append(f"◐ {h2_count} H2 sections (could use more)")
    elif h2_count >= 1:
        heading_score += 3
        heading_details.append(f"◐ {h2_count} H2 section (needs more)")
    else:
        heading_details.append("✗ No H2 sections")

    if h3_count >= 2:
        heading_score += 7
        heading_details.append(f"✓ {h3_count} H3 subsections (good granularity)")
    elif h3_count >= 1:
        heading_score += 4
        heading_details.append(f"◐ {h3_count} H3 subsection")
    else:
        heading_score += 1
        heading_details.append("◐ No H3 subsections")

    breakdown["heading_structure"] = {"score": heading_score, "max": 25, "details": heading_details}

    # ── Meta Quality (20 pts) ──
    meta_score = 0
    meta_details = []

    title_len = len(strategy.get("seo_title", ""))
    if 50 <= title_len <= 60:
        meta_score += 10
        meta_details.append(f"✓ Title length {title_len} chars (optimal)")
    elif 30 <= title_len <= 70:
        meta_score += 6
        meta_details.append(f"◐ Title length {title_len} chars (acceptable)")
    else:
        meta_score += 2
        meta_details.append(f"✗ Title length {title_len} chars (outside recommended range)")

    desc_len = len(strategy.get("meta_description", ""))
    if 140 <= desc_len <= 160:
        meta_score += 10
        meta_details.append(f"✓ Meta description {desc_len} chars (optimal)")
    elif 100 <= desc_len <= 170:
        meta_score += 6
        meta_details.append(f"◐ Meta description {desc_len} chars (acceptable)")
    else:
        meta_score += 2
        meta_details.append(f"✗ Meta description {desc_len} chars (outside recommended range)")

    breakdown["meta_quality"] = {"score": meta_score, "max": 20, "details": meta_details}

    total = sum(cat["score"] for cat in breakdown.values())

    return {"total_score": total, "max_score": 100, "breakdown": breakdown}


def run(blog_content: dict, keyword_intel: dict, content_strategy: dict) -> dict:
    """
    Run full SEO + quality analysis on generated blog content.
    """
    text = blog_content.get("full_markdown", "")
    primary_kw = keyword_intel.get("primary_keyword", "")
    lsi_keywords = keyword_intel.get("lsi_keywords", [])

    # ── SEO Score ──
    seo = _seo_score(text, primary_kw, content_strategy)

    # ── Readability ──
    flesch = _flesch_reading_ease(text)
    clean = _strip_markdown(text)
    words = re.findall(r"\b[a-zA-Z']+\b", clean)
    sentences = re.split(r'[.!?]+', clean)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 3]
    avg_sentence_len = round(len(words) / max(len(sentences), 1), 1)

    readability = {
        "flesch_score": flesch,
        "flesch_grade": (
            "Very Easy" if flesch >= 80 else
            "Easy" if flesch >= 70 else
            "Fairly Easy" if flesch >= 60 else
            "Standard" if flesch >= 50 else
            "Fairly Difficult" if flesch >= 40 else
            "Difficult" if flesch >= 30 else
            "Very Difficult"
        ),
        "avg_sentence_length": avg_sentence_len,
        "total_words": len(words),
        "total_sentences": len(sentences),
        "complexity": "low" if avg_sentence_len < 15 else "medium" if avg_sentence_len < 22 else "high",
    }

    # ── Naturalness (multi-signal, content-aware scoring) ──
    repetition_flags = _detect_repetition(text)
    ai_phrases = _detect_ai_phrases(text)
    transition_overuse = _detect_transition_overuse(text)
    sent_variance = _sentence_length_variance(text)
    vocab_diversity = _vocabulary_diversity(text)
    opener_variety = _sentence_opener_variety(text)
    passive_check = _passive_voice_ratio(text)
    para_check = _paragraph_length_check(text)

    # Weighted composite naturalness score
    # Penalty signals (clichés, repetition, transitions) — max 35 pts penalty
    penalty = 0
    multi_word_count = len([p for p in ai_phrases if len(p["phrase"].split()) > 1])
    single_word_count = len([p for p in ai_phrases if len(p["phrase"].split()) == 1])
    penalty += min(multi_word_count * 5, 20)
    penalty += min(single_word_count * 2, 8)
    penalty += min(len(repetition_flags) * 3, 12)
    penalty += min(len(transition_overuse) * 3, 10)
    cliche_base = max(0, 100 - penalty)

    # Positive signals (weighted average)
    positive_score = (
        sent_variance["score"] * 0.25 +
        vocab_diversity["score"] * 0.25 +
        opener_variety["score"] * 0.20 +
        passive_check["score"] * 0.15 +
        para_check["score"] * 0.15
    )

    # Final score: blend of penalty-based and positive signals
    # 40% weight on cliché penalties, 60% on positive writing quality signals
    naturalness_score = round(cliche_base * 0.40 + positive_score * 0.60)
    naturalness_score = max(0, min(100, naturalness_score))

    naturalness = {
        "score": naturalness_score,
        "signals": {
            "sentence_variance": sent_variance,
            "vocabulary_diversity": vocab_diversity,
            "opener_variety": opener_variety,
            "passive_voice": passive_check,
            "paragraph_quality": para_check,
        },
        "repetition_flags": repetition_flags,
        "ai_cliche_phrases": ai_phrases,
        "transition_overuse": transition_overuse,
        "assessment": (
            "Excellent — reads naturally with varied, engaging prose" if naturalness_score >= 90 else
            "Very good — natural writing with minor patterns" if naturalness_score >= 80 else
            "Good — mostly natural, some areas could improve" if naturalness_score >= 70 else
            "Fair — noticeable patterns, could use more variation" if naturalness_score >= 55 else
            "Needs work — repeated patterns and limited variety" if naturalness_score >= 40 else
            "Poor — significant AI patterns and monotonous writing"
        ),
    }

    # ── Snippet Readiness ──
    snippet = _check_snippet_readiness(text)

    # ── Keyword Density Report ──
    primary_density = _keyword_density(text, primary_kw)
    secondary_densities = {}
    warnings = []
    for kw in lsi_keywords[:10]:
        d = _keyword_density(text, kw)
        secondary_densities[kw] = d
        if d > 3.5:
            warnings.append(f"'{kw}' density {d}% exceeds 3.5% threshold")

    if primary_density < 0.5:
        warnings.insert(0, f"Primary keyword density {primary_density}% is below 0.5% minimum")
    elif primary_density > 3.5:
        warnings.insert(0, f"Primary keyword density {primary_density}% exceeds 3.5% — risk of keyword stuffing")

    keyword_density_report = {
        "primary_keyword": primary_kw,
        "primary_density": primary_density,
        "secondary_keywords": secondary_densities,
        "warnings": warnings,
    }

    return {
        "seo_score": seo,
        "readability": readability,
        "naturalness": naturalness,
        "snippet_readiness": snippet,
        "keyword_density": keyword_density_report,
    }
