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
        'brands_priority': {},
        'models': {},
        'sub_models': {},
        'categories': {},
        'categories_priority': {},
        'tags': {}
    }

    # Build brand lookup
    # List order = priority: index 0 is highest priority
    for b_idx, brand in enumerate(dictionary.get('brands', [])):
        brand_name = brand['name']
        # Add canonical name itself
        tables['brands'][brand_name.lower()] = brand_name
        tables['brands_priority'][brand_name.lower()] = (brand_name, b_idx)
        for alias in brand.get('aliases', []):
            tables['brands'][alias.lower()] = brand_name
            tables['brands_priority'][alias.lower()] = (brand_name, b_idx)

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

    # Build category lookup (two tables: one for removal, one for order-aware matching)
    # List order = priority: index 0 is highest priority
    for idx, cat in enumerate(dictionary.get('categories', [])):
        cat_name = cat['name']
        tables['categories'][cat_name.lower()] = cat_name
        tables['categories_priority'][cat_name.lower()] = (cat_name, idx)
        for alias in cat.get('aliases', []):
            tables['categories'][alias.lower()] = cat_name
            tables['categories_priority'][alias.lower()] = (cat_name, idx)

    # Build tag lookup (tags are patterns, not exact word matches)
    for tag_name, patterns in dictionary.get('tags', {}).items():
        tables['tags'][tag_name] = [p.lower() for p in patterns]

    return tables


def _boundary_pattern(key_escaped: str, key: str) -> str:
    return r'(?<![가-힣a-zA-Z0-9])' + key_escaped + r'(?![가-힣a-zA-Z0-9])'


def _is_permissive_key(key: str) -> bool:
    """
    Return True if this key should use permissive (substring) matching.
    Korean aliases with ≥2 characters: allow substring match to handle
    compound patterns like '테일러메이드코리아' containing '테일러메이드'.
    Single-character Korean aliases (e.g. '핑') stay strict to avoid
    false positives like '핑크' matching the 핑 brand.
    """
    korean_chars = [c for c in key if '\uAC00' <= c <= '\uD7A3']
    return len(korean_chars) >= 2


def find_longest_match(text_lower: str, lookup_table: dict, strict: bool = True):
    """
    Find the longest matching alias/key in text_lower from the lookup table.

    Returns (matched_key, canonical_value, start_pos, end_pos) or (None, None, -1, -1)

    strict=True  (default): word-boundary aware matching for all aliases.
    strict=False           : Korean aliases with ≥2 chars use substring matching
                             so that e.g. '테일러메이드' is found inside '테일러메이드코리아'.
                             Latin aliases and single-Korean-char aliases stay strict.
    """
    best_key = None
    best_value = None
    best_start = -1
    best_end = -1
    best_len = 0

    for key, value in lookup_table.items():
        # Escape key for regex
        key_escaped = re.escape(key)
        # Choose pattern based on strictness setting
        if not strict and _is_permissive_key(key):
            pattern = key_escaped  # substring match
        else:
            pattern = _boundary_pattern(key_escaped, key)
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
        pattern = _boundary_pattern(key_escaped, key)
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
            regex = _boundary_pattern(key_escaped, pattern)
            if re.search(regex, text_lower):
                found_tags.append(tag_name)
                break  # Found this tag, move to next
    return found_tags


def find_brand_by_priority(text_lower: str, lookup_with_priority: dict):
    """
    Find the best brand match using list-order priority with permissive Korean matching.

    Korean aliases with >= 2 chars use substring (permissive) matching so that
    e.g. '테일러메이드' is found inside '테일러메이드코리아'.

    When multiple brands match, the one with the lowest position_index wins
    (earlier in the brands list = higher priority).
    Ties in position are broken by longest alias length.

    Returns (matched_key, canonical_value, start_pos, end_pos) or (None, None, -1, -1)
    """
    candidates = []
    for key, (value, position) in lookup_with_priority.items():
        key_escaped = re.escape(key)
        if _is_permissive_key(key):
            pattern = key_escaped  # substring match for Korean >= 2 chars
        else:
            pattern = _boundary_pattern(key_escaped, key)
        for m in re.finditer(pattern, text_lower):
            candidates.append((key, value, position, m.start(), m.end()))

    if not candidates:
        return None, None, -1, -1

    # Sort by position ASC (lower index = higher priority), then alias length DESC
    candidates.sort(key=lambda x: (x[2], -len(x[0])))
    best = candidates[0]
    return best[0], best[1], best[3], best[4]


def find_best_match_by_priority(text_lower: str, lookup_with_priority: dict):
    """
    Find the best match considering list-order priority.
    lookup_with_priority: {alias_lower: (canonical_name, position_index)}

    When multiple categories match, the one with the lowest position_index wins
    (earlier in the categories list = higher priority).
    Ties in position are broken by longest alias length (more specific wins).

    Returns (matched_key, canonical_value, start_pos, end_pos) or (None, None, -1, -1)
    """
    candidates = []
    for key, (value, position) in lookup_with_priority.items():
        key_escaped = re.escape(key)
        pattern = _boundary_pattern(key_escaped, key)
        for m in re.finditer(pattern, text_lower):
            candidates.append((key, value, position, m.start(), m.end()))

    if not candidates:
        return None, None, -1, -1

    # Sort by position ASC (lower index = higher priority), then alias length DESC
    candidates.sort(key=lambda x: (x[2], -len(x[0])))
    best = candidates[0]
    return best[0], best[1], best[3], best[4]


def remove_span_from_text(text: str, start: int, end: int) -> str:
    """Remove a span [start:end] from text and normalize whitespace."""
    result = (text[:start] + ' ' + text[end:]).strip()
    result = re.sub(r'\s+', ' ', result)
    return result
