"""
Matching utilities for brand, model, category lookups.
"""
import re


def build_lookup_table(dictionary: dict) -> dict:
    """
    Build lookup tables from the dictionary for fast matching.

    Returns a dict with:
        'brands': {alias_lower: canonical_name}
        'models': {brand_name: {alias_lower: canonical_model_name}}
        'sub_models': {brand_name: {model_name: {alias_lower: canonical_sub_model_name}}}
        'categories': {alias_lower: canonical_category_name}
        'tags': {tag_name: [pattern_lower, ...]}
    """
    tables = {
        'brands': {},
        'models': {},
        'sub_models': {},
        'categories': {},
        'categories_priority': {},
        'tags': {}
    }

    # Build brand lookup
    for brand in dictionary.get('brands', []):
        brand_name = brand['name']
        # Add canonical name itself
        tables['brands'][brand_name.lower()] = brand_name
        for alias in brand.get('aliases', []):
            tables['brands'][alias.lower()] = brand_name

        # Build model lookup for this brand
        tables['models'][brand_name] = {}
        tables['sub_models'][brand_name] = {}

        for model in brand.get('models', []):
            model_name = model['name']
            tables['models'][brand_name][model_name.lower()] = model_name
            for alias in model.get('aliases', []):
                tables['models'][brand_name][alias.lower()] = model_name

            # Build sub-model lookup
            tables['sub_models'][brand_name][model_name] = {}
            for sub in model.get('sub_models', []):
                sub_name = sub['name']
                tables['sub_models'][brand_name][model_name][sub_name.lower()] = sub_name
                for alias in sub.get('aliases', []):
                    tables['sub_models'][brand_name][model_name][alias.lower()] = sub_name

    # Build category lookup (two tables: one for removal, one for priority-aware matching)
    for cat in dictionary.get('categories', []):
        cat_name = cat['name']
        priority = cat.get('priority', 5)
        tables['categories'][cat_name.lower()] = cat_name
        tables['categories_priority'][cat_name.lower()] = (cat_name, priority)
        for alias in cat.get('aliases', []):
            tables['categories'][alias.lower()] = cat_name
            tables['categories_priority'][alias.lower()] = (cat_name, priority)

    # Build tag lookup (tags are patterns, not exact word matches)
    for tag_name, patterns in dictionary.get('tags', {}).items():
        tables['tags'][tag_name] = [p.lower() for p in patterns]

    return tables


def find_longest_match(text_lower: str, lookup_table: dict):
    """
    Find the longest matching alias/key in text_lower from the lookup table.

    Returns (matched_key, canonical_value, start_pos, end_pos) or (None, None, -1, -1)
    Uses word-boundary aware matching: a match must be surrounded by
    non-alphanumeric/non-Korean characters (spaces, brackets, punctuation, or string edges).
    """
    best_key = None
    best_value = None
    best_start = -1
    best_end = -1
    best_len = 0

    for key, value in lookup_table.items():
        # Escape key for regex
        key_escaped = re.escape(key)
        # Build word-boundary pattern (handles Korean + Latin)
        pattern = r'(?<![가-힣a-zA-Z0-9])' + key_escaped + r'(?![가-힣a-zA-Z0-9])'
        for m in re.finditer(pattern, text_lower):
            match_len = len(key)
            if match_len > best_len:
                best_len = match_len
                best_key = key
                best_value = value
                best_start = m.start()
                best_end = m.end()

    return best_key, best_value, best_start, best_end


def find_all_matches(text_lower: str, lookup_table: dict):
    """
    Find ALL non-overlapping matches in text_lower, sorted by position.
    Returns list of (matched_key, canonical_value, start_pos, end_pos).
    Longer matches at the same position win (greedy).
    """
    candidates = []

    for key, value in lookup_table.items():
        key_escaped = re.escape(key)
        pattern = r'(?<![가-힣a-zA-Z0-9])' + key_escaped + r'(?![가-힣a-zA-Z0-9])'
        for m in re.finditer(pattern, text_lower):
            candidates.append((key, value, m.start(), m.end()))

    if not candidates:
        return []

    # Sort by start position, then by length descending (longer match wins)
    candidates.sort(key=lambda x: (x[2], -(x[3] - x[2])))

    # Remove overlapping matches (keep longest at each position)
    result = []
    last_end = -1
    for key, value, start, end in candidates:
        if start >= last_end:
            result.append((key, value, start, end))
            last_end = end

    return result


def find_tag_matches(text_lower: str, tag_patterns: dict):
    """
    Find all tags present in text_lower.
    tag_patterns: {tag_name: [pattern1_lower, pattern2_lower, ...]}
    Returns list of matched tag names.
    """
    found_tags = []
    for tag_name, patterns in tag_patterns.items():
        for pattern in patterns:
            key_escaped = re.escape(pattern)
            # Word-boundary aware
            regex = r'(?<![가-힣a-zA-Z0-9])' + key_escaped + r'(?![가-힣a-zA-Z0-9])'
            if re.search(regex, text_lower):
                found_tags.append(tag_name)
                break  # Found this tag, move to next
    return found_tags


def find_best_match_by_priority(text_lower: str, lookup_with_priority: dict):
    """
    Find the best match considering priority.
    lookup_with_priority: {alias_lower: (canonical_name, priority)}

    When multiple categories match, the one with highest priority wins.
    Ties in priority are broken by longest alias length (more specific wins).

    Returns (matched_key, canonical_value, start_pos, end_pos) or (None, None, -1, -1)
    """
    candidates = []
    for key, (value, priority) in lookup_with_priority.items():
        key_escaped = re.escape(key)
        pattern = r'(?<![가-힣a-zA-Z0-9])' + key_escaped + r'(?![가-힣a-zA-Z0-9])'
        for m in re.finditer(pattern, text_lower):
            candidates.append((key, value, priority, m.start(), m.end()))

    if not candidates:
        return None, None, -1, -1

    # Sort by priority desc, then by alias length desc (more specific alias wins)
    candidates.sort(key=lambda x: (x[2], len(x[0])), reverse=True)
    best = candidates[0]
    return best[0], best[1], best[3], best[4]


def remove_span_from_text(text: str, start: int, end: int) -> str:
    """Remove a span [start:end] from text and normalize whitespace."""
    result = (text[:start] + ' ' + text[end:]).strip()
    result = re.sub(r'\s+', ' ', result)
    return result
