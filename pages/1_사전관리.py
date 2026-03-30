"""
사전 관리 페이지 - Brand, Category, Tag CRUD
"""
import json
from pathlib import Path

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DICT_PATH = BASE_DIR / "data" / "dictionary.json"

st.set_page_config(
    page_title="사전 관리 | 상품명 파서",
    page_icon="📚",
    layout="wide",
)

st.markdown("""
<style>
    .page-title { font-size: 1.8rem; font-weight: 700; color: #1a5c2a; }
    .section-header { font-size: 1.1rem; font-weight: 600; color: #2d4a2d; margin-top: 1rem; }
    .brand-card {
        background: #f8faf8;
        border: 1px solid #c8e0c8;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
    }
    .alias-tag {
        display: inline-block;
        background: #e0f0e0;
        border-radius: 4px;
        padding: 2px 8px;
        margin: 2px;
        font-size: 0.8rem;
        color: #1a5c2a;
    }
</style>
""", unsafe_allow_html=True)


# ── Dictionary IO ─────────────────────────────────────────────────────────────
def load_dict() -> dict:
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_dict(data: dict):
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Signal parser reload
    st.session_state['reload_parser'] = True


def aliases_to_str(aliases: list) -> str:
    return ', '.join(aliases)


def str_to_aliases(s: str) -> list:
    return [a.strip() for a in s.split(',') if a.strip()]


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">📚 사전 관리</div>', unsafe_allow_html=True)
st.markdown("브랜드·모델·카테고리·태그 패턴을 관리합니다. 변경사항은 즉시 저장됩니다.")

with st.sidebar:
    st.markdown("### 메뉴")
    st.page_link("app.py", label="상품명 파서", icon="⛳")
    st.page_link("pages/1_사전관리.py", label="사전 관리", icon="📚")
    st.page_link("pages/2_미분류검토.py", label="미분류 검토", icon="🔎")

# Load dictionary
try:
    dictionary = load_dict()
except Exception as e:
    st.error(f"사전 파일 로드 실패: {e}")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_brand, tab_cat, tab_tag, tab_noise = st.tabs(
    ["🏷️ 브랜드 / 모델", "🗂️ 카테고리", "🏷️ 태그", "🔇 노이즈 패턴"]
)


# ════════════════════════════════════════════════════════════════════════════
# BRAND TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_brand:
    st.markdown("### 브랜드 목록")

    brands = dictionary.get('brands', [])

    # ── Add new brand ─────────────────────────────────────────────────────
    with st.expander("➕ 새 브랜드 추가", expanded=False):
        nb_col1, nb_col2 = st.columns(2)
        new_brand_name = nb_col1.text_input("브랜드명", key='new_brand_name', placeholder="예: 핑")
        new_brand_aliases = nb_col2.text_input(
            "별칭 (쉼표 구분)", key='new_brand_aliases', placeholder="예: ping, PING"
        )
        if st.button("브랜드 추가", key='add_brand_btn', type='primary'):
            if new_brand_name.strip():
                # Check duplicate
                existing_names = [b['name'] for b in brands]
                if new_brand_name.strip() in existing_names:
                    st.error(f"이미 존재하는 브랜드입니다: {new_brand_name.strip()}")
                else:
                    brands.append({
                        'name': new_brand_name.strip(),
                        'aliases': str_to_aliases(new_brand_aliases),
                        'models': []
                    })
                    dictionary['brands'] = brands
                    save_dict(dictionary)
                    st.success(f"브랜드 '{new_brand_name.strip()}' 추가 완료!")
                    st.rerun()
            else:
                st.warning("브랜드명을 입력하세요.")

    st.divider()

    # ── Brand list ────────────────────────────────────────────────────────
    if not brands:
        st.info("등록된 브랜드가 없습니다.")
    else:
        for b_idx, brand in enumerate(brands):
            with st.expander(
                f"**{brand['name']}** — 별칭: {aliases_to_str(brand.get('aliases', []))}",
                expanded=False
            ):
                # Edit brand
                ec1, ec2, ec3 = st.columns([2, 3, 1])
                edit_name = ec1.text_input(
                    "브랜드명", value=brand['name'], key=f'brand_name_{b_idx}'
                )
                edit_aliases = ec2.text_input(
                    "별칭 (쉼표 구분)",
                    value=aliases_to_str(brand.get('aliases', [])),
                    key=f'brand_aliases_{b_idx}'
                )
                ec3.markdown("<br>", unsafe_allow_html=True)

                col_save, col_del = ec3.columns(2)
                if col_save.button("저장", key=f'save_brand_{b_idx}'):
                    old_name = brand['name']
                    brands[b_idx]['name'] = edit_name.strip()
                    brands[b_idx]['aliases'] = str_to_aliases(edit_aliases)
                    dictionary['brands'] = brands
                    save_dict(dictionary)
                    st.success("저장 완료!")
                    st.rerun()

                if col_del.button("삭제", key=f'del_brand_{b_idx}'):
                    brands.pop(b_idx)
                    dictionary['brands'] = brands
                    save_dict(dictionary)
                    st.warning(f"브랜드 '{brand['name']}' 삭제됨")
                    st.rerun()

                st.markdown("---")
                st.markdown(f"**모델 목록** ({brand['name']})")

                models = brand.get('models', [])

                # Add model
                with st.expander(f"➕ '{brand['name']}' 모델 추가", expanded=False):
                    nm_c1, nm_c2 = st.columns(2)
                    new_model_name = nm_c1.text_input(
                        "모델명", key=f'new_model_name_{b_idx}', placeholder="예: QI4D"
                    )
                    new_model_aliases = nm_c2.text_input(
                        "별칭 (쉼표 구분)", key=f'new_model_aliases_{b_idx}', placeholder="예: qi4d"
                    )
                    if st.button("모델 추가", key=f'add_model_{b_idx}'):
                        if new_model_name.strip():
                            models.append({
                                'name': new_model_name.strip(),
                                'aliases': str_to_aliases(new_model_aliases),
                                'sub_models': []
                            })
                            brands[b_idx]['models'] = models
                            dictionary['brands'] = brands
                            save_dict(dictionary)
                            st.success("모델 추가 완료!")
                            st.rerun()
                        else:
                            st.warning("모델명을 입력하세요.")

                for m_idx, model in enumerate(models):
                    with st.expander(
                        f"└ **{model['name']}** — {aliases_to_str(model.get('aliases', []))}",
                        expanded=False
                    ):
                        # Edit model
                        me1, me2, me3 = st.columns([2, 3, 1])
                        em_name = me1.text_input(
                            "모델명", value=model['name'], key=f'model_name_{b_idx}_{m_idx}'
                        )
                        em_aliases = me2.text_input(
                            "별칭",
                            value=aliases_to_str(model.get('aliases', [])),
                            key=f'model_aliases_{b_idx}_{m_idx}'
                        )
                        me3.markdown("<br>", unsafe_allow_html=True)
                        ms_col, md_col = me3.columns(2)
                        if ms_col.button("저장", key=f'save_model_{b_idx}_{m_idx}'):
                            brands[b_idx]['models'][m_idx]['name'] = em_name.strip()
                            brands[b_idx]['models'][m_idx]['aliases'] = str_to_aliases(em_aliases)
                            dictionary['brands'] = brands
                            save_dict(dictionary)
                            st.success("저장 완료!")
                            st.rerun()
                        if md_col.button("삭제", key=f'del_model_{b_idx}_{m_idx}'):
                            brands[b_idx]['models'].pop(m_idx)
                            dictionary['brands'] = brands
                            save_dict(dictionary)
                            st.rerun()

                        # Sub-models
                        st.markdown(f"**서브모델** ({model['name']})")
                        sub_models = model.get('sub_models', [])

                        # Add sub-model
                        nsm_c1, nsm_c2, nsm_c3 = st.columns([2, 3, 1])
                        new_sub_name = nsm_c1.text_input(
                            "서브모델명", key=f'new_sub_name_{b_idx}_{m_idx}',
                            placeholder="예: MAX"
                        )
                        new_sub_aliases = nsm_c2.text_input(
                            "별칭", key=f'new_sub_aliases_{b_idx}_{m_idx}',
                            placeholder="예: max, 맥스"
                        )
                        nsm_c3.markdown("<br>", unsafe_allow_html=True)
                        if nsm_c3.button("추가", key=f'add_sub_{b_idx}_{m_idx}'):
                            if new_sub_name.strip():
                                sub_models.append({
                                    'name': new_sub_name.strip(),
                                    'aliases': str_to_aliases(new_sub_aliases)
                                })
                                brands[b_idx]['models'][m_idx]['sub_models'] = sub_models
                                dictionary['brands'] = brands
                                save_dict(dictionary)
                                st.rerun()

                        for s_idx, sub in enumerate(sub_models):
                            sc1, sc2, sc3, sc4 = st.columns([2, 3, 1, 1])
                            se_name = sc1.text_input(
                                "서브모델명", value=sub['name'],
                                key=f'sub_name_{b_idx}_{m_idx}_{s_idx}'
                            )
                            se_aliases = sc2.text_input(
                                "별칭",
                                value=aliases_to_str(sub.get('aliases', [])),
                                key=f'sub_aliases_{b_idx}_{m_idx}_{s_idx}'
                            )
                            sc3.markdown("<br>", unsafe_allow_html=True)
                            sc4.markdown("<br>", unsafe_allow_html=True)
                            if sc3.button("저장", key=f'save_sub_{b_idx}_{m_idx}_{s_idx}'):
                                brands[b_idx]['models'][m_idx]['sub_models'][s_idx]['name'] = se_name.strip()
                                brands[b_idx]['models'][m_idx]['sub_models'][s_idx]['aliases'] = str_to_aliases(se_aliases)
                                dictionary['brands'] = brands
                                save_dict(dictionary)
                                st.rerun()
                            if sc4.button("삭제", key=f'del_sub_{b_idx}_{m_idx}_{s_idx}'):
                                brands[b_idx]['models'][m_idx]['sub_models'].pop(s_idx)
                                dictionary['brands'] = brands
                                save_dict(dictionary)
                                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# CATEGORY TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_cat:
    st.markdown("### 카테고리 목록")
    categories = dictionary.get('categories', [])

    # Add new category
    with st.expander("➕ 새 카테고리 추가", expanded=False):
        ncat_c1, ncat_c2 = st.columns(2)
        new_cat_name = ncat_c1.text_input("카테고리명", key='new_cat_name', placeholder="예: 드라이버")
        new_cat_aliases = ncat_c2.text_input(
            "별칭 (쉼표 구분)", key='new_cat_aliases', placeholder="예: driver, 드라이버"
        )
        if st.button("카테고리 추가", key='add_cat_btn', type='primary'):
            if new_cat_name.strip():
                existing = [c['name'] for c in categories]
                if new_cat_name.strip() in existing:
                    st.error("이미 존재하는 카테고리입니다.")
                else:
                    categories.append({
                        'name': new_cat_name.strip(),
                        'aliases': str_to_aliases(new_cat_aliases)
                    })
                    dictionary['categories'] = categories
                    save_dict(dictionary)
                    st.success("추가 완료!")
                    st.rerun()
            else:
                st.warning("카테고리명을 입력하세요.")

    st.divider()

    if not categories:
        st.info("등록된 카테고리가 없습니다.")
    else:
        for c_idx, cat in enumerate(categories):
            cc1, cc2, cc3, cc4 = st.columns([2, 4, 1, 1])
            edit_cat_name = cc1.text_input(
                "카테고리명", value=cat['name'], key=f'cat_name_{c_idx}', label_visibility='collapsed'
            )
            edit_cat_aliases = cc2.text_input(
                "별칭",
                value=aliases_to_str(cat.get('aliases', [])),
                key=f'cat_aliases_{c_idx}',
                label_visibility='collapsed'
            )
            if cc3.button("저장", key=f'save_cat_{c_idx}'):
                categories[c_idx]['name'] = edit_cat_name.strip()
                categories[c_idx]['aliases'] = str_to_aliases(edit_cat_aliases)
                dictionary['categories'] = categories
                save_dict(dictionary)
                st.success("저장 완료!")
                st.rerun()
            if cc4.button("삭제", key=f'del_cat_{c_idx}'):
                categories.pop(c_idx)
                dictionary['categories'] = categories
                save_dict(dictionary)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAG TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_tag:
    st.markdown("### 태그 패턴")
    st.markdown("각 태그에 대응하는 키워드 패턴 목록입니다. 상품명에 해당 키워드가 포함되면 태그로 분류됩니다.")

    tags = dictionary.get('tags', {})

    # Add new tag
    with st.expander("➕ 새 태그 추가", expanded=False):
        nt_c1, nt_c2 = st.columns(2)
        new_tag_name = nt_c1.text_input("태그명", key='new_tag_name', placeholder="예: 주니어")
        new_tag_patterns = nt_c2.text_input(
            "패턴 (쉼표 구분)", key='new_tag_patterns', placeholder="예: 주니어, junior"
        )
        if st.button("태그 추가", key='add_tag_btn', type='primary'):
            if new_tag_name.strip():
                if new_tag_name.strip() in tags:
                    st.error("이미 존재하는 태그입니다.")
                else:
                    tags[new_tag_name.strip()] = str_to_aliases(new_tag_patterns)
                    dictionary['tags'] = tags
                    save_dict(dictionary)
                    st.success("태그 추가 완료!")
                    st.rerun()
            else:
                st.warning("태그명을 입력하세요.")

    st.divider()

    tag_names = list(tags.keys())
    if not tag_names:
        st.info("등록된 태그가 없습니다.")
    else:
        for t_idx, tag_name in enumerate(tag_names):
            patterns = tags[tag_name]
            tc1, tc2, tc3, tc4 = st.columns([1.5, 4, 1, 1])
            tc1.markdown(f"**{tag_name}**")
            edit_patterns = tc2.text_input(
                "패턴",
                value=', '.join(patterns),
                key=f'tag_patterns_{t_idx}',
                label_visibility='collapsed'
            )
            if tc3.button("저장", key=f'save_tag_{t_idx}'):
                tags[tag_name] = str_to_aliases(edit_patterns)
                dictionary['tags'] = tags
                save_dict(dictionary)
                st.success("저장 완료!")
                st.rerun()
            if tc4.button("삭제", key=f'del_tag_{t_idx}'):
                del tags[tag_name]
                dictionary['tags'] = tags
                save_dict(dictionary)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# NOISE PATTERNS TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_noise:
    st.markdown("### 노이즈 패턴")
    st.markdown(
        "상품명 파싱 전 제거할 단어/패턴 목록입니다. "
        "이 패턴들은 브랜드·모델·카테고리 추출 전에 텍스트에서 제거됩니다."
    )

    noise = dictionary.get('noise_patterns', [])
    noise_text = st.text_area(
        "노이즈 패턴 (한 줄에 하나씩 또는 쉼표 구분)",
        value='\n'.join(noise),
        height=200,
        key='noise_textarea'
    )

    if st.button("노이즈 패턴 저장", type='primary', key='save_noise'):
        # Parse: split by newlines and commas
        raw = noise_text.replace(',', '\n')
        new_noise = [n.strip() for n in raw.split('\n') if n.strip()]
        dictionary['noise_patterns'] = new_noise
        save_dict(dictionary)
        st.success(f"노이즈 패턴 저장 완료! ({len(new_noise)}개)")
        st.rerun()

    st.markdown("**현재 패턴:**")
    if noise:
        cols = st.columns(6)
        for i, n in enumerate(noise):
            cols[i % 6].markdown(
                f'<span style="background:#ffe0e0;border-radius:4px;padding:2px 8px;'
                f'font-size:0.85rem;">{n}</span>',
                unsafe_allow_html=True
            )
    else:
        st.info("노이즈 패턴이 없습니다.")

    st.divider()
    st.markdown("##### 기본 제거 규칙 (코드에 내장, 수정 불가)")
    st.markdown("""
    - `_GF`, ` GF` — 상품명 끝의 GF 태그
    - `증정` — 상품명 앞의 증정 표시
    - `[xxx정품]`, `(xxx정품)` — 정품 표기 괄호
    - `25년`, `26년` 등 연도 패턴
    - `VBDP-` 형식의 코드 접두사
    """)
