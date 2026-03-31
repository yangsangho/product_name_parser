"""
Main product name parser for Korean golf product names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, List, Tuple

from golf_parser.normalizer import (
    normalize_for_matching,
    extract_bracket_contents,
    remove_brackets_noise,
    clean_parenthetical_duplicates,
    full_normalize_pipeline,
    strip_inline_jungpum,
)
from golf_parser.matcher import (
    build_lookup_table,
    find_longest_match,
    find_all_matches,
    find_tag_matches,
    find_brand_by_priority,
    find_best_match_by_priority,
    remove_span_from_text,
    _boundary_pattern,
)


class ProductNameParser:
    def __init__(self, dictionary_path: str):
        self.dictionary_path = dictionary_path
        self.dictionary = {}
        self.tables = {}
        self.reload_dictionary()

    def reload_dictionary(self):
        """Load (or reload) the dictionary from disk and rebuild lookup tables."""
        with open(self.dictionary_path, 'r', encoding='utf-8') as f:
            self.dictionary = json.load(f)
        self.tables = build_lookup_table(self.dictionary)

    def parse(self, product_name: str) -> dict:
        """
        Parse a Korean golf product name into structured fields.

        Returns:
            {
                'brand': str | None,
                'main_model': str | None,
                'sub_model': str | None,
                'category': str | None,
                'tags': list[str],
                'residual': str,
                'confidence': 'confirmed' | 'partial' | 'unclassified',
                'status': '완료' | '부분' | '미분류'
            }
        """
        if not product_name or not str(product_name).strip():
            return self._empty_result()

        original = str(product_name).strip()

        # --- Step 1: Extract tag hints from bracket contents before anything else ---
        bracket_contents = extract_bracket_contents(original)

        # --- Step 2: Extract tags from full original text (case-insensitive) ---
        text_lower = normalize_for_matching(original)
        tags = find_tag_matches(text_lower, self.tables['tags'])

        # --- Step 3: Build a working text for brand/model/category extraction ---
        # Start with the original, strip leading noise and GF suffix
        working = full_normalize_pipeline(original)

        # Flatten parenthetical duplicates: 어반(URBAN) → 어반 URBAN
        working = clean_parenthetical_duplicates(working)

        # Extract bracket contents for brand hints, then remove bracket wrappers
        # First collect any brand hints from inside brackets
        brand_hint = self._extract_brand_hint_from_brackets(bracket_contents)

        # Remove bracket noise wrappers from working text
        working = remove_brackets_noise(working)
        # Also remove leftover [] and () wrappers (non-정품 ones that held brand names)
        working = re.sub(r'\[[^\]]+\]', ' ', working)
        working = re.sub(r'\([^)]+\)', ' ', working)
        # Strip inline 'BrandName정품' → 'BrandName' (e.g., 테일러메이드정품 → 테일러메이드)
        working = strip_inline_jungpum(working)
        working = re.sub(r'\s+', ' ', working).strip()

        # --- Step 4: Brand extraction ---
        working_lower = normalize_for_matching(working)
        brand, brand_start, brand_end = self._extract_brand(working_lower, brand_hint)

        # Remove brand span from working text
        if brand and brand_start >= 0:
            working = remove_span_from_text(working, brand_start, brand_end)
            working = re.sub(r'\s+', ' ', working).strip()

        # --- Step 5: Category extraction ---
        working_lower = normalize_for_matching(working)
        category, cat_start, cat_end = self._extract_category(working_lower)

        if category and cat_start >= 0:
            working = remove_span_from_text(working, cat_start, cat_end)
            working = re.sub(r'\s+', ' ', working).strip()

        # --- Step 6: Model extraction (only if brand found) ---
        main_model = None
        sub_model = None

        if brand and brand in self.tables['models']:
            working_lower = normalize_for_matching(working)
            main_model, sub_model, working = self._extract_model(
                working, working_lower, brand
            )

        # --- Step 7: Remove tag words from residual ---
        working = self._remove_tag_words(working, tags)

        # --- Step 7b: Remove all aliases of brand/model/sub-model from residual ---
        # (handles the case where clean_parenthetical_duplicates left extra copies)
        if brand:
            working = self._remove_entity_aliases(working, brand, 'brand')
        if main_model and brand:
            working = self._remove_entity_aliases(working, main_model, 'model', brand)
        if sub_model and brand and main_model:
            working = self._remove_entity_aliases(working, sub_model, 'sub_model', brand, main_model)
        if category:
            working = self._remove_entity_aliases(working, category, 'category')
        working = re.sub(r'\s+', ' ', working).strip()

        # --- Step 8: Remove remaining noise words ---
        working = self._remove_noise_words(working)
        working = re.sub(r'\s+', ' ', working).strip()

        # --- Step 9: Compute confidence / status ---
        confidence, status = self._compute_status(brand, main_model, category, sub_model, working)

        return {
            'brand': brand,
            'main_model': main_model,
            'sub_model': sub_model,
            'category': category,
            'tags': tags,
            'residual': working,
            'confidence': confidence,
            'status': status,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _empty_result(self) -> dict:
        return {
            'brand': None,
            'main_model': None,
            'sub_model': None,
            'category': None,
            'tags': [],
            'residual': '',
            'confidence': 'unclassified',
            'status': '미분류',
        }

    def _extract_brand_hint_from_brackets(self, bracket_contents: list) -> Optional[str]:
        """
        Look inside bracket contents for brand names.
        e.g., ['한국캘러웨이정품'] → 캘러웨이
        Returns canonical brand name or None.
        """
        for content in bracket_contents:
            content_lower = content.lower()
            # Remove 정품 suffix and other noise for matching
            cleaned = re.sub(r'정품', '', content_lower)
            cleaned = re.sub(r'코리아', '', cleaned)
            cleaned = re.sub(r'한국', '', cleaned)
            cleaned = cleaned.strip()
            if not cleaned:
                continue
            # Try to match brand
            _, brand_val, _, _ = find_longest_match(cleaned, self.tables['brands'])
            if brand_val:
                return brand_val
            # Try direct substring match
            for alias, brand_name in self.tables['brands'].items():
                if alias in content_lower:
                    return brand_name
        return None

    def _extract_brand(self, text_lower: str, brand_hint: Optional[str]):
        """
        Extract brand from text using list-order priority.
        Earlier brands in the dictionary list have higher priority.
        Korean aliases use permissive (substring) matching.
        Body text takes priority over bracket hint.
        Returns (brand_name, start, end).
        """
        # Try body text with list-order priority
        _, body_brand_val, body_start, body_end = find_brand_by_priority(
            text_lower, self.tables['brands_priority']
        )

        if body_brand_val:
            return body_brand_val, body_start, body_end

        # No brand in body text; fall back to bracket hint
        if brand_hint:
            return brand_hint, -1, -1

        return None, -1, -1

    def _extract_category(self, text_lower: str):
        """
        Extract category using priority-aware matching.
        When multiple categories match (e.g. "드라이버 커버"), the highest-priority
        category wins (커버=20 beats 드라이버=5).
        Ties in priority resolved by longest alias length.

        Returns (category_name, start, end).
        """
        _, cat_val, start, end = find_best_match_by_priority(
            text_lower, self.tables['categories_priority']
        )
        return cat_val, start, end

    def _extract_model(
        self,
        working: str,
        working_lower: str,
        brand: str
    ):
        """
        Extract main model and sub-model for the given brand from working text.
        Returns (main_model, sub_model, updated_working_text).
        """
        model_table = self.tables['models'].get(brand, {})
        if not model_table:
            return None, None, working

        _, model_val, m_start, m_end = find_longest_match(working_lower, model_table)
        if not model_val:
            return None, None, working

        # Remove model from working text
        working = remove_span_from_text(working, m_start, m_end)
        working = re.sub(r'\s+', ' ', working).strip()

        # Now look for sub-model
        sub_model = None
        sub_table = self.tables['sub_models'].get(brand, {}).get(model_val, {})
        if sub_table:
            working_lower2 = normalize_for_matching(working)
            _, sub_val, s_start, s_end = find_longest_match(working_lower2, sub_table)
            if sub_val:
                sub_model = sub_val
                working = remove_span_from_text(working, s_start, s_end)
                working = re.sub(r'\s+', ' ', working).strip()

        return model_val, sub_model, working

    def _remove_entity_aliases(
        self, text: str, entity_name: str, entity_type: str,
        brand: str = None, model: str = None
    ) -> str:
        """
        Remove all aliases of a found entity (brand/model/category) from residual text.
        This cleans up duplicate forms left by parenthetical expansion.
        """
        if not text:
            return text

        # Get all aliases for this entity
        aliases = []
        if entity_type == 'brand':
            for alias, name in self.tables['brands'].items():
                if name == entity_name:
                    aliases.append(alias)
        elif entity_type == 'model' and brand:
            for alias, name in self.tables['models'].get(brand, {}).items():
                if name == entity_name:
                    aliases.append(alias)
        elif entity_type == 'sub_model' and brand and model:
            for alias, name in self.tables['sub_models'].get(brand, {}).get(model, {}).items():
                if name == entity_name:
                    aliases.append(alias)
        elif entity_type == 'category':
            for alias, name in self.tables['categories'].items():
                if name == entity_name:
                    aliases.append(alias)

        # Also add the canonical name itself
        aliases.append(entity_name.lower())
        # Sort longest first
        aliases = sorted(set(aliases), key=len, reverse=True)

        result = text
        for alias in aliases:
            key_escaped = re.escape(alias)
            regex = _boundary_pattern(key_escaped, alias)
            result = re.sub(regex, ' ', result, flags=re.IGNORECASE)

        result = re.sub(r'\s+', ' ', result).strip()
        return result

    def _remove_tag_words(self, text: str, found_tags: list) -> str:
        """Remove the actual tag pattern words from text."""
        if not text or not found_tags:
            return text

        text_lower = text.lower()
        result = text

        for tag_name in found_tags:
            patterns = self.tables['tags'].get(tag_name, [])
            for pattern in patterns:
                key_escaped = re.escape(pattern)
                regex = _boundary_pattern(key_escaped, pattern)
                result = re.sub(regex, ' ', result, flags=re.IGNORECASE)

        result = re.sub(r'\s+', ' ', result).strip()
        return result

    def _remove_noise_words(self, text: str) -> str:
        """Remove configured noise patterns from text."""
        if not text:
            return text

        noise_patterns = self.dictionary.get('noise_patterns', [])

        # Sort longest first to avoid partial removal
        noise_patterns_sorted = sorted(noise_patterns, key=len, reverse=True)

        for noise in noise_patterns_sorted:
            # Special case: don't remove "골프" if it's part of "골프공", "골프볼", "골프백", "파크골프"
            if noise == '골프':
                # Only remove standalone 골프
                text = re.sub(
                    r'(?<![가-힣])골프(?!공|볼|백|화|장|채|복|화|용품|클럽)',
                    ' ',
                    text
                )
                continue
            key_escaped = re.escape(noise)
            text = re.sub(
                _boundary_pattern(key_escaped, noise),
                ' ',
                text,
                flags=re.IGNORECASE,
            )

        # Remove inline xxxxx정품 patterns (not inside brackets - those are handled earlier)
        text = re.sub(r'[가-힣a-zA-Z]+정품', ' ', text)
        # Remove year patterns
        text = re.sub(r'\b\d{2}년\b', ' ', text)
        # Remove leading/trailing punctuation and dashes
        text = re.sub(r'^[\s\-_]+|[\s\-_]+$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _compute_status(
        self, brand: Optional[str], main_model: Optional[str], category: Optional[str],
        sub_model: Optional[str], residual: str
    ):
        """
        Compute confidence and status label.
        완료: 브랜드 + 메인모델 + 카테고리 모두 매칭, 잔여텍스트 없음
        서브모델미분류: 브랜드 + 메인모델 + 카테고리 매칭, 서브모델 없음, 잔여텍스트 있음
        부분: 브랜드 또는 카테고리 중 일부만 매칭
        미분류: 브랜드·카테고리 모두 미매칭
        confidence: 'confirmed' | 'sub_unclassified' | 'partial' | 'unclassified'
        status: '완료' | '서브모델미분류' | '부분' | '미분류'
        """
        has_brand = brand is not None
        has_model = main_model is not None
        has_category = category is not None
        has_sub = sub_model is not None
        has_residual = bool(residual and residual.strip())

        if has_brand and has_model and has_category:
            if not has_sub and has_residual:
                return 'sub_unclassified', '서브모델미분류'
            return 'confirmed', '완료'
        elif has_brand or has_category:
            return 'partial', '부분'
        else:
            return 'unclassified', '미분류'
