"""
Text normalization utilities for Korean golf product name parsing.
"""
import re


def normalize_for_matching(text: str) -> str:
    """Lowercase and strip the text for case-insensitive matching."""
    if not text:
        return ""
    return text.lower().strip()


def extract_bracket_contents(text: str):
    """
    Extract all contents from bracket patterns: [xxx], (xxx)
    Returns a list of strings found inside brackets.
    """
    if not text:
        return []
    contents = []
    # Square brackets
    square = re.findall(r'\[([^\]]+)\]', text)
    contents.extend(square)
    # Round brackets
    round_ = re.findall(r'\(([^)]+)\)', text)
    contents.extend(round_)
    return contents


def remove_brackets_noise(text: str) -> str:
    """
    Remove bracket patterns that are noise (정품 markers, etc.)
    but preserve the text for brand hint extraction before calling this.

    Patterns removed:
    - [xxx정품], [xxx정품xxx] - square bracket with 정품
    - (xxx정품) - round bracket with 정품
    - [임직원몰전용] etc. - tag brackets (caller handles tags first)
    - Standalone [...] and (...) wrappers around brand names
    """
    if not text:
        return text

    # Remove [xxx정품] and [xxx정품xxx] patterns
    text = re.sub(r'\[[^\]]*정품[^\]]*\]', '', text)
    # Remove (xxx정품) patterns
    text = re.sub(r'\([^)]*정품[^)]*\)', '', text)
    # Remove [임직원xxx] tag brackets
    text = re.sub(r'\[임직원[^\]]*\]', '', text)

    return text.strip()


def clean_parenthetical_duplicates(text: str) -> str:
    """
    Handle Korean/English duplicates in parens like 어반(URBAN) → 어반.
    Keeps the Korean term and removes the English duplicate in parens
    (or keeps both tokens for matching purposes by flattening).
    We simply remove the parens so both terms are visible in the string.
    e.g., 어반(URBAN) → 어반 URBAN
    """
    if not text:
        return text
    # Replace (ENGLISH) after Korean word: keep content, remove parens
    text = re.sub(r'\(([A-Za-z0-9\-\s]+)\)', r' \1 ', text)
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def remove_year_patterns(text: str) -> str:
    """Remove year patterns like 25년, 26년 from text."""
    if not text:
        return text
    text = re.sub(r'\b\d{2}년\b', '', text)
    return text.strip()


def remove_gf_suffix(text: str) -> str:
    """Remove _GF and GF suffixes from the end of text."""
    if not text:
        return text
    text = re.sub(r'[_\s]*GF\s*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def remove_vbdp_prefix(text: str) -> str:
    """Remove VBDP- type prefixes."""
    if not text:
        return text
    text = re.sub(r'\bVBDP-', '', text, flags=re.IGNORECASE)
    return text.strip()


def remove_leading_noise(text: str) -> str:
    """Remove noise words from the beginning of the text."""
    if not text:
        return text
    # Remove leading 증정
    text = re.sub(r'^증정\s*', '', text)
    return text.strip()


def full_normalize_pipeline(text: str) -> str:
    """
    Apply all noise removal steps in order.
    Returns cleaned text (still in original case for display,
    but with noise removed).
    """
    if not text:
        return text
    text = remove_leading_noise(text)
    text = remove_gf_suffix(text)
    text = remove_vbdp_prefix(text)
    text = remove_year_patterns(text)
    # Normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text
