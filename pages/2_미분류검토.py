"""
미분류 검토 페이지 - Review and classify unclassified items
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DICT_PATH = BASE_DIR / "data" / "dictionary.json"

st.set_page_config(
    page_title="미분류 검토 | 상품명 파서",
    page_icon="🔎",
    layout="wide",
)

st.markdown("""
<style>
    .page-title { font-size: 1.8rem; font-weight: 700; color: #1a5c2a; }
    .item-card {
        background: #fff9f0;
        border: 1px solid #f0d080;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    .original-name {
        font-size: 1rem;
        font-weight: 600;
        color: #333;
        word-break: break-all;
    }
    .current-parse {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Dictionary helpers ────────────────────────────────────────────────────────
def load_dict() -> dict:
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_dict(data: dict):
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    st.session_state['reload_parser'] = True


def get_brand_names(d: dict) -> list:
    return [b['name'] for b in d.get('brands', [])]


def get_category_names(d: dict) -> list:
    return [c['name'] for c in d.get('categories', [])]


def get_model_names(d: dict, brand: str) -> list:
    for b in d.get('brands', []):
        if b['name'] == brand:
            return [m['name'] for m in b.get('models', [])]
    return []


def add_brand_if_missing(d: dict, brand_name: str):
    """Add brand to dictionary if not already present."""
    existing = [b['name'] for b in d.get('brands', [])]
    if brand_name and brand_name not in existing:
        d.setdefault('brands', []).append({
            'name': brand_name,
            'aliases': [brand_name.lower()],
            'models': []
        })


def add_category_if_missing(d: dict, cat_name: str):
    """Add category to dictionary if not already present."""
    existing = [c['name'] for c in d.get('categories', [])]
    if cat_name and cat_name not in existing:
        d.setdefault('categories', []).append({
            'name': cat_name,
            'aliases': [cat_name.lower()]
        })


def add_model_to_brand(d: dict, brand_name: str, model_name: str, aliases_str: str):
    """Add model to a brand. Creates brand if missing."""
    aliases = [a.strip() for a in aliases_str.split(',') if a.strip()]
    for b in d.get('brands', []):
        if b['name'] == brand_name:
            existing_models = [m['name'] for m in b.get('models', [])]
            if model_name not in existing_models:
                b.setdefault('models', []).append({
                    'name': model_name,
                    'aliases': aliases or [model_name.lower()],
                    'sub_models': []
                })
            return
    # Brand not found, create it
    add_brand_if_missing(d, brand_name)
    add_model_to_brand(d, brand_name, model_name, aliases_str)


# ── Parser helper ─────────────────────────────────────────────────────────────
def get_parser():
    if 'parser' not in st.session_state or st.session_state.get('reload_parser', False):
        from golf_parser.parser import ProductNameParser
        st.session_state['parser'] = ProductNameParser(str(DICT_PATH))
        st.session_state['reload_parser'] = False
    return st.session_state['parser']


# ── Page Header ───────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">🔎 미분류 검토</div>', unsafe_allow_html=True)
st.markdown("브랜드 또는 카테고리가 분류되지 않은 상품을 검토하고 사전에 추가합니다.")

with st.sidebar:
    st.markdown("### 메뉴")
    st.page_link("app.py", label="상품명 파서", icon="⛳")
    st.page_link("pages/1_사전관리.py", label="사전 관리", icon="📚")
    st.page_link("pages/2_미분류검토.py", label="미분류 검토", icon="🔎")

# ── Check for result data ─────────────────────────────────────────────────────
result_sources = []
if 'result_df' in st.session_state:
    result_sources.append(('파일 업로드 결과', st.session_state['result_df']))
if 'result_df_manual' in st.session_state:
    result_sources.append(('직접 입력 결과', st.session_state['result_df_manual']))

if not result_sources:
    st.info(
        "아직 파싱된 데이터가 없습니다. "
        "먼저 **상품명 파서** 페이지에서 상품명을 파싱해주세요."
    )
    st.stop()

# ── Select data source ────────────────────────────────────────────────────────
if len(result_sources) > 1:
    source_labels = [s[0] for s in result_sources]
    sel_source = st.selectbox("데이터 소스 선택", source_labels, key='review_source')
    result_df = dict(result_sources)[sel_source]
else:
    result_df = result_sources[0][1]
    st.info(f"데이터 소스: **{result_sources[0][0]}**")

# ── Filter unclassified ───────────────────────────────────────────────────────
status_filter = st.radio(
    "검토 대상",
    options=['미분류 + 부분', '미분류만', '전체'],
    horizontal=True,
    key='review_filter',
)

if status_filter == '미분류만':
    review_df = result_df[result_df['분류상태'] == '미분류'].copy()
elif status_filter == '미분류 + 부분':
    review_df = result_df[result_df['분류상태'].isin(['미분류', '부분'])].copy()
else:
    review_df = result_df.copy()

review_df = review_df.reset_index(drop=True)

st.markdown(f"**검토 대상: {len(review_df)}건** / 전체: {len(result_df)}건")

if review_df.empty:
    st.success("모든 상품이 분류되었습니다! 미분류 항목이 없습니다.")
    st.stop()

# ── Batch re-parse button ─────────────────────────────────────────────────────
if st.button("🔄 전체 재파싱 (사전 수정 후 반영)", key='reparse_all'):
    parser = get_parser()
    new_results = []
    for val in result_df.get('원본상품명', result_df.iloc[:, 0]):
        parsed = parser.parse(str(val) if pd.notna(val) else "")
        new_results.append({
            '원본상품명': val,
            '브랜드': parsed['brand'] or '',
            '메인모델': parsed['main_model'] or '',
            '서브모델': parsed['sub_model'] or '',
            '카테고리': parsed['category'] or '',
            '태그': ', '.join(parsed['tags']),
            '잔여텍스트': parsed['residual'],
            '분류상태': parsed['status'],
        })
    updated_df = pd.DataFrame(new_results)
    # Update whichever source is selected
    if len(result_sources) > 1 and sel_source == '파일 업로드 결과':
        st.session_state['result_df'] = updated_df
    elif len(result_sources) > 1:
        st.session_state['result_df_manual'] = updated_df
    elif 'result_df' in st.session_state:
        st.session_state['result_df'] = updated_df
    else:
        st.session_state['result_df_manual'] = updated_df
    st.success("재파싱 완료!")
    st.rerun()

st.divider()

# ── Load dictionary for corrections ──────────────────────────────────────────
try:
    dictionary = load_dict()
except Exception as e:
    st.error(f"사전 로드 실패: {e}")
    st.stop()

brand_names = get_brand_names(dictionary)
cat_names = get_category_names(dictionary)

# ── Pagination ────────────────────────────────────────────────────────────────
PAGE_SIZE = 10
total_pages = max(1, (len(review_df) + PAGE_SIZE - 1) // PAGE_SIZE)
page_num = st.number_input(
    "페이지", min_value=1, max_value=total_pages, value=1, step=1, key='review_page'
)
start_idx = (page_num - 1) * PAGE_SIZE
end_idx = min(start_idx + PAGE_SIZE, len(review_df))

st.markdown(f"**{start_idx+1} – {end_idx}** / {len(review_df)}건 표시 중")

# ── Item review cards ─────────────────────────────────────────────────────────
for row_idx in range(start_idx, end_idx):
    row = review_df.iloc[row_idx]
    original = str(row.get('원본상품명', ''))
    current_brand = str(row.get('브랜드', ''))
    current_model = str(row.get('메인모델', ''))
    current_sub = str(row.get('서브모델', ''))
    current_cat = str(row.get('카테고리', ''))
    current_tags = str(row.get('태그', ''))
    current_residual = str(row.get('잔여텍스트', ''))
    status = str(row.get('분류상태', ''))

    status_color = {'완료': '#1a7a3a', '부분': '#b87a00', '미분류': '#c0392b'}.get(status, '#888')

    with st.container(border=True):
        # Header row
        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.markdown(f"**{original}**")
        with hc2:
            st.markdown(
                f'<span style="color:{status_color};font-weight:700">{status}</span>',
                unsafe_allow_html=True
            )

        # Current parse summary
        parse_parts = []
        if current_brand:
            parse_parts.append(f"브랜드: **{current_brand}**")
        if current_model:
            parse_parts.append(f"모델: **{current_model}**")
        if current_sub:
            parse_parts.append(f"서브모델: **{current_sub}**")
        if current_cat:
            parse_parts.append(f"카테고리: **{current_cat}**")
        if current_tags:
            parse_parts.append(f"태그: {current_tags}")
        if current_residual:
            parse_parts.append(f"잔여: `{current_residual}`")

        if parse_parts:
            st.markdown(" | ".join(parse_parts))
        else:
            st.markdown("*파싱 결과 없음*")

        # Correction form
        with st.expander("✏️ 수정 / 사전 추가", expanded=(status == '미분류')):
            fc1, fc2, fc3, fc4 = st.columns(4)

            # Brand correction
            brand_options = [''] + sorted(brand_names)
            brand_default_idx = brand_options.index(current_brand) if current_brand in brand_options else 0
            corrected_brand = fc1.selectbox(
                "브랜드",
                brand_options,
                index=brand_default_idx,
                key=f'corr_brand_{row_idx}'
            )
            new_brand_input = fc1.text_input(
                "신규 브랜드명",
                key=f'new_brand_input_{row_idx}',
                placeholder="없으면 직접 입력"
            )

            # Category correction
            cat_options = [''] + sorted(cat_names)
            cat_default_idx = cat_options.index(current_cat) if current_cat in cat_options else 0
            corrected_cat = fc2.selectbox(
                "카테고리",
                cat_options,
                index=cat_default_idx,
                key=f'corr_cat_{row_idx}'
            )
            new_cat_input = fc2.text_input(
                "신규 카테고리명",
                key=f'new_cat_input_{row_idx}',
                placeholder="없으면 직접 입력"
            )

            # Model
            effective_brand = new_brand_input.strip() or corrected_brand
            model_options = [''] + get_model_names(dictionary, effective_brand)
            corrected_model = fc3.selectbox(
                "메인모델",
                model_options,
                key=f'corr_model_{row_idx}'
            )
            new_model_input = fc3.text_input(
                "신규 모델명",
                key=f'new_model_input_{row_idx}',
                placeholder="없으면 직접 입력"
            )
            model_aliases_input = fc3.text_input(
                "모델 별칭 (쉼표 구분)",
                key=f'model_aliases_{row_idx}',
                placeholder="예: qi4d, QI4D"
            )

            # Sub-model
            corrected_sub = fc4.text_input(
                "서브모델",
                value=current_sub if current_sub else '',
                key=f'corr_sub_{row_idx}'
            )

            # Apply button
            btn_col1, btn_col2, _ = st.columns([1, 1, 4])

            if btn_col1.button("💾 사전에 추가 & 저장", key=f'save_correction_{row_idx}', type='primary'):
                changed = False
                d = load_dict()  # Fresh load

                # Handle new brand
                final_brand = new_brand_input.strip() or corrected_brand
                if final_brand:
                    add_brand_if_missing(d, final_brand)
                    changed = True

                # Handle new category
                final_cat = new_cat_input.strip() or corrected_cat
                if final_cat:
                    add_category_if_missing(d, final_cat)
                    changed = True

                # Handle new model
                final_model = new_model_input.strip() or corrected_model
                if final_model and final_brand:
                    add_model_to_brand(d, final_brand, final_model, model_aliases_input)
                    changed = True

                if changed:
                    save_dict(d)
                    st.success(
                        f"사전 업데이트 완료: 브랜드='{final_brand}' | "
                        f"카테고리='{final_cat}' | 모델='{final_model}'"
                    )
                else:
                    st.warning("변경 사항이 없습니다.")

            if btn_col2.button("⏭️ 건너뛰기", key=f'skip_{row_idx}'):
                st.info("건너뜀")

st.divider()

# ── Summary table of unclassified ─────────────────────────────────────────────
with st.expander("📊 미분류 전체 목록 (테이블)", expanded=False):
    display_cols = [c for c in ['원본상품명', '브랜드', '카테고리', '메인모델', '태그', '잔여텍스트', '분류상태']
                    if c in review_df.columns]
    st.dataframe(review_df[display_cols], use_container_width=True)
