"""
미분류 검토 페이지
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent.parent
DICT_PATH = BASE_DIR / "data" / "dictionary.json"

st.set_page_config(page_title="미분류 검토 | 상품명 파서", page_icon="🔎", layout="wide")

st.markdown("""
<style>
.residual-box {
    background: #fff8e1;
    border-left: 4px solid #f9a825;
    padding: 8px 14px;
    border-radius: 4px;
    margin: 8px 0 4px 0;
}
.residual-label { color: #7a5800; font-size: 0.78rem; font-weight: 600; }
.residual-text  { color: #222; font-size: 1.05rem; font-weight: 700; word-break: break-all; }
.parse-summary  { color: #555; font-size: 0.88rem; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)


# ── 사전 헬퍼 ─────────────────────────────────────────────────────────────────
def load_dict() -> dict:
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_dict(d: dict):
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    st.session_state['reload_parser'] = True

def brand_names(d):   return [b['name'] for b in d.get('brands', [])]
def cat_names(d):     return [c['name'] for c in d.get('categories', [])]
def tag_names(d):     return list(d.get('tags', {}).keys())
def model_names(d, brand):
    for b in d.get('brands', []):
        if b['name'] == brand:
            return [m['name'] for m in b.get('models', [])]
    return []

def _aliases(raw: str) -> list:
    return [a.strip() for a in raw.split(',') if a.strip()]

def do_add_brand(d, name, aliases_raw):
    if not name: return False
    existing = [b['name'] for b in d.get('brands', [])]
    if name not in existing:
        d.setdefault('brands', []).append({
            'name': name, 'aliases': _aliases(aliases_raw) or [name.lower()], 'models': []
        })
        return True
    return False

def do_add_model(d, brand, model, aliases_raw, sub='', sub_aliases_raw=''):
    if not brand or not model: return False
    # ensure brand exists
    b_entry = next((b for b in d.get('brands', []) if b['name'] == brand), None)
    if not b_entry:
        do_add_brand(d, brand, '')
        b_entry = next((b for b in d['brands'] if b['name'] == brand), None)
    existing_models = [m['name'] for m in b_entry.get('models', [])]
    if model not in existing_models:
        entry = {'name': model, 'aliases': _aliases(aliases_raw) or [model.lower()], 'sub_models': []}
        if sub:
            entry['sub_models'].append({
                'name': sub,
                'aliases': _aliases(sub_aliases_raw) or [sub.lower()]
            })
        b_entry.setdefault('models', []).append(entry)
    elif sub:
        m_entry = next(m for m in b_entry['models'] if m['name'] == model)
        existing_subs = [s['name'] for s in m_entry.get('sub_models', [])]
        if sub not in existing_subs:
            m_entry.setdefault('sub_models', []).append({
                'name': sub,
                'aliases': _aliases(sub_aliases_raw) or [sub.lower()]
            })
    return True

def do_add_submodel(d, brand, model, sub_name, aliases_raw):
    """기존 브랜드>모델에 서브모델을 추가합니다."""
    if not all([brand, model, sub_name]): return False
    for b in d.get('brands', []):
        if b['name'] == brand:
            for m in b.get('models', []):
                if m['name'] == model:
                    existing_subs = [s['name'] for s in m.get('sub_models', [])]
                    if sub_name in existing_subs:
                        return False
                    m.setdefault('sub_models', []).append({
                        'name': sub_name,
                        'aliases': _aliases(aliases_raw) or [sub_name.lower()]
                    })
                    return True
    return False

def do_add_category(d, name, aliases_raw):
    if not name: return False
    existing = [c['name'] for c in d.get('categories', [])]
    if name not in existing:
        # Appended at the end (lowest priority); user can reorder in 사전관리
        d.setdefault('categories', []).append({
            'name': name, 'aliases': _aliases(aliases_raw) or [name.lower()]
        })
        return True
    return False

def do_add_alias_brand(d, brand, alias):
    if not brand or not alias: return False
    for b in d.get('brands', []):
        if b['name'] == brand:
            al = alias.lower()
            if al not in [a.lower() for a in b.get('aliases', [])]:
                b.setdefault('aliases', []).append(alias)
                return True
    return False

def do_add_alias_model(d, brand, model, alias):
    if not brand or not model or not alias: return False
    for b in d.get('brands', []):
        if b['name'] == brand:
            for m in b.get('models', []):
                if m['name'] == model:
                    al = alias.lower()
                    if al not in [a.lower() for a in m.get('aliases', [])]:
                        m.setdefault('aliases', []).append(alias)
                        return True
    return False

def do_add_alias_category(d, cat, alias):
    if not cat or not alias: return False
    for c in d.get('categories', []):
        if c['name'] == cat:
            al = alias.lower()
            if al not in [a.lower() for a in c.get('aliases', [])]:
                c.setdefault('aliases', []).append(alias)
                return True
    return False

def do_add_alias_submodel(d, brand, model, sub, alias):
    if not all([brand, model, sub, alias]): return False
    for b in d.get('brands', []):
        if b['name'] == brand:
            for m in b.get('models', []):
                if m['name'] == model:
                    for s in m.get('sub_models', []):
                        if s['name'] == sub:
                            al = alias.lower()
                            if al not in [a.lower() for a in s.get('aliases', [])]:
                                s.setdefault('aliases', []).append(alias)
                                return True
    return False

def sub_model_names(d, brand, model):
    for b in d.get('brands', []):
        if b['name'] == brand:
            for m in b.get('models', []):
                if m['name'] == model:
                    return [s['name'] for s in m.get('sub_models', [])]
    return []

def do_add_tag(d, tag_name, aliases_raw):
    """기존 태그면 별칭 추가, 신규면 태그 생성."""
    if not tag_name: return False
    new_aliases = [a.strip() for a in aliases_raw.split(',') if a.strip()]
    if not new_aliases: return False
    tags = d.setdefault('tags', {})
    if tag_name not in tags:
        tags[tag_name] = new_aliases
    else:
        for a in new_aliases:
            if a.lower() not in [x.lower() for x in tags[tag_name]]:
                tags[tag_name].append(a)
    return True


# ── 파서 / 재분류 ──────────────────────────────────────────────────────────────
def get_parser():
    if 'parser' not in st.session_state or st.session_state.get('reload_parser', False):
        from golf_parser.parser import ProductNameParser
        st.session_state['parser'] = ProductNameParser(str(DICT_PATH))
        st.session_state['reload_parser'] = False
    return st.session_state['parser']

def reparse_all():
    parser = get_parser()
    for key in ['result_df', 'result_df_manual']:
        if key not in st.session_state: continue
        df = st.session_state[key].copy()
        if '원본상품명' not in df.columns: continue
        for i, val in enumerate(df['원본상품명']):
            p = parser.parse(str(val) if pd.notna(val) else "")
            df.at[i, '브랜드']     = p['brand'] or ''
            df.at[i, '메인모델']   = p['main_model'] or ''
            df.at[i, '서브모델']   = p['sub_model'] or ''
            df.at[i, '카테고리']   = p['category'] or ''
            df.at[i, '태그']       = ', '.join(p['tags'])
            df.at[i, '잔여텍스트'] = p['residual']
            df.at[i, '분류상태']   = p['status']
        st.session_state[key] = df

def save_and_reparse(d: dict, msg: str):
    save_dict(d)
    reparse_all()
    st.success(f"✅ {msg} — 전체 재분류 완료")
    st.rerun()


# ── 페이지 헤더 ───────────────────────────────────────────────────────────────
st.markdown("## 🔎 미분류 검토")
st.caption("잔여텍스트를 보며 사전을 보완하세요. 저장하면 전체 데이터가 즉시 재분류됩니다.")

with st.sidebar:
    st.markdown("### 메뉴")
    st.page_link("app.py",                   label="상품명 파서",  icon="⛳")
    st.page_link("pages/1_사전관리.py",       label="사전 관리",    icon="📚")
    st.page_link("pages/2_미분류검토.py",     label="미분류 검토",  icon="🔎")

# ── 데이터 확인 ───────────────────────────────────────────────────────────────
sources = []
if 'result_df'        in st.session_state: sources.append(('파일 업로드',  'result_df'))
if 'result_df_manual' in st.session_state: sources.append(('직접 입력',   'result_df_manual'))

if not sources:
    st.info("먼저 **상품명 파서** 페이지에서 파싱을 실행하세요.")
    st.stop()

if len(sources) > 1:
    sel = st.selectbox("데이터 소스", [s[0] for s in sources], key='rev_src')
    src_key = dict(sources)[sel]
else:
    src_key = sources[0][1]

result_df = st.session_state[src_key]

# ── 필터 ─────────────────────────────────────────────────────────────────────
filter_opt = st.radio("검토 대상",
                      ['미분류만', '미분류 + 부분', '서브모델미분류', '전체'],
                      horizontal=True, key='rev_filter')
if filter_opt == '미분류만':
    rev = result_df[result_df['분류상태'] == '미분류'].copy()
elif filter_opt == '미분류 + 부분':
    rev = result_df[result_df['분류상태'].isin(['미분류', '부분'])].copy()
elif filter_opt == '서브모델미분류':
    rev = result_df[result_df['분류상태'] == '서브모델미분류'].copy()
else:
    rev = result_df.copy()
rev = rev.reset_index(drop=True)

st.markdown(f"**검토 대상 {len(rev)}건** / 전체 {len(result_df)}건")
if rev.empty:
    st.success("미분류 항목이 없습니다! 🎉")
    st.stop()

st.divider()

# ── 사전 로드 ─────────────────────────────────────────────────────────────────
dic = load_dict()
brands  = sorted(brand_names(dic))
cats    = sorted(cat_names(dic))
tags    = tag_names(dic)

# ── 페이지네이션 ──────────────────────────────────────────────────────────────
PAGE = 10
total_pages = max(1, (len(rev) + PAGE - 1) // PAGE)
page = st.number_input("페이지", 1, total_pages, 1, key='rev_page')
s, e = (page - 1) * PAGE, min(page * PAGE, len(rev))
st.caption(f"{s+1}–{e} / {len(rev)}건")

# ── 아이템 카드 ───────────────────────────────────────────────────────────────
STATUS_COLOR = {'완료': '#1a7a3a', '서브모델미분류': '#7b5ea7', '부분': '#b87a00', '미분류': '#c0392b'}

for i in range(s, e):
    row      = rev.iloc[i]
    original = str(row.get('원본상품명', ''))
    b        = str(row.get('브랜드', ''))
    m        = str(row.get('메인모델', ''))
    sub      = str(row.get('서브모델', ''))
    cat      = str(row.get('카테고리', ''))
    tg       = str(row.get('태그', ''))
    res      = str(row.get('잔여텍스트', '')).strip()
    status   = str(row.get('분류상태', ''))
    sc       = STATUS_COLOR.get(status, '#888')

    with st.container(border=True):
        # 헤더
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"**{original}**")
        c2.markdown(f'<div style="text-align:right;color:{sc};font-weight:700">{status}</div>',
                    unsafe_allow_html=True)

        # 현재 분류 요약
        parts = []
        if b:   parts.append(f"브랜드 **{b}**")
        if m:   parts.append(f"모델 **{m}**")
        if sub: parts.append(f"서브모델 **{sub}**")
        if cat: parts.append(f"카테고리 **{cat}**")
        if tg:  parts.append(f"태그 {tg}")
        st.markdown(
            '<span class="parse-summary">' + (" &nbsp;|&nbsp; ".join(parts) if parts else "분류 없음") + '</span>',
            unsafe_allow_html=True
        )

        # 잔여텍스트 강조 (항상 표시)
        if res:
            st.markdown(
                f'<div class="residual-box">'
                f'<div class="residual-label">🔍 잔여텍스트 — 사전에 없어 분류되지 않은 텍스트</div>'
                f'<div class="residual-text">{res}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── 사전 추가 expander (기본 닫힘) ────────────────────────────────
        with st.expander("✏️ 사전에 추가하기"):
            tab_m, tab_sm, tab_b, tab_c, tab_al, tab_tg = st.tabs([
                "📦 모델 추가", "🧩 서브모델 추가", "🏷️ 브랜드 추가", "📁 카테고리 추가",
                "🔗 별칭 추가", "🔖 태그 추가"
            ])

            # ── 탭 1: 모델 추가 ──────────────────────────────────────────
            with tab_m:
                st.caption("잔여텍스트에 보이는 모델명을 특정 브랜드의 모델로 등록합니다.")
                bm_opts = ['선택하세요'] + brands
                bm_default = bm_opts.index(b) if b in bm_opts else 0
                bm_sel = st.selectbox("브랜드", bm_opts, index=bm_default, key=f'm_brand_{i}',
                                      help="모델이 속할 브랜드")
                mc1, mc2 = st.columns(2)
                m_name   = mc1.text_input("모델명 *", key=f'm_name_{i}',
                                          placeholder="예: 스파이더 레드")
                m_alias  = mc2.text_input("별칭 (쉼표 구분)", key=f'm_alias_{i}',
                                          placeholder="예: spider red, 스파이더레드")
                sm_c1, sm_c2 = st.columns(2)
                m_sub       = sm_c1.text_input("서브모델 (선택)", key=f'm_sub_{i}',
                                               placeholder="예: DB")
                m_sub_alias = sm_c2.text_input("서브모델 별칭 (선택, 쉼표 구분)", key=f'm_sub_alias_{i}',
                                               placeholder="예: db")

                if st.button("💾 모델 추가 & 재분류", key=f'sv_m_{i}', type='primary'):
                    final_brand = bm_sel if bm_sel != '선택하세요' else ''
                    if not final_brand:
                        st.warning("브랜드를 선택하세요.")
                    elif not m_name.strip():
                        st.warning("모델명을 입력하세요.")
                    else:
                        d = load_dict()
                        do_add_model(d, final_brand, m_name.strip(), m_alias,
                                     m_sub.strip(), m_sub_alias)
                        save_and_reparse(d, f"'{final_brand} > {m_name.strip()}' 추가")

            # ── 탭 2: 서브모델 추가 ──────────────────────────────────────
            with tab_sm:
                st.caption("기존 브랜드 > 모델에 서브모델을 추가합니다.")
                sm_b_opts = ['선택하세요'] + brands
                sm_b_default = sm_b_opts.index(b) if b in sm_b_opts else 0
                sm_b_sel = st.selectbox("브랜드 선택 *", sm_b_opts, index=sm_b_default,
                                        key=f'sm_brand_{i}')
                sm_m_list = model_names(dic, sm_b_sel) if sm_b_sel != '선택하세요' else []
                sm_m_default = (sm_m_list.index(m) if m in sm_m_list else 0)
                sm_m_sel = st.selectbox("모델 선택 *", ['선택하세요'] + sm_m_list,
                                        index=sm_m_default + 1 if sm_m_list and m in sm_m_list else 0,
                                        key=f'sm_model_{i}')
                sm_c1, sm_c2 = st.columns(2)
                sm_name  = sm_c1.text_input("서브모델명 *", key=f'sm_name_{i}',
                                             placeholder="예: MAX")
                sm_alias = sm_c2.text_input("별칭 (쉼표 구분)", key=f'sm_alias_{i}',
                                             placeholder="예: max, 맥스")

                if st.button("💾 서브모델 추가 & 재분류", key=f'sv_sm_{i}', type='primary'):
                    final_b = sm_b_sel if sm_b_sel != '선택하세요' else ''
                    final_m = sm_m_sel if sm_m_sel != '선택하세요' else ''
                    if not final_b or not final_m:
                        st.warning("브랜드와 모델을 선택하세요.")
                    elif not sm_name.strip():
                        st.warning("서브모델명을 입력하세요.")
                    else:
                        d = load_dict()
                        if do_add_submodel(d, final_b, final_m, sm_name.strip(), sm_alias):
                            save_and_reparse(d, f"'{final_b} > {final_m} > {sm_name.strip()}' 추가")
                        else:
                            st.warning(f"'{sm_name.strip()}'는 이미 등록된 서브모델입니다. **별칭 추가** 탭을 이용하세요.")

            # ── 탭 3: 브랜드 추가 ────────────────────────────────────────
            with tab_b:
                st.caption("사전에 없는 새 브랜드를 등록합니다.")
                b_name  = st.text_input("브랜드명 *", key=f'b_name_{i}',
                                         placeholder="예: 야마하")
                b_alias = st.text_input("별칭 (쉼표 구분)", key=f'b_alias_{i}',
                                         placeholder="예: yamaha, YAMAHA")

                if st.button("💾 브랜드 추가 & 재분류", key=f'sv_b_{i}', type='primary'):
                    if not b_name.strip():
                        st.warning("브랜드명을 입력하세요.")
                    else:
                        d = load_dict()
                        if do_add_brand(d, b_name.strip(), b_alias):
                            save_and_reparse(d, f"브랜드 '{b_name.strip()}' 추가")
                        else:
                            st.warning(f"'{b_name.strip()}'는 이미 사전에 있습니다. **별칭 추가** 탭을 이용하세요.")

            # ── 탭 3: 카테고리 추가 ──────────────────────────────────────
            with tab_c:
                st.caption("사전에 없는 새 카테고리를 등록합니다.")
                c_name  = st.text_input("카테고리명 *", key=f'c_name_{i}',
                                         placeholder="예: 헤드커버")
                c_alias = st.text_input("별칭 (쉼표 구분)", key=f'c_alias_{i}',
                                         placeholder="예: head cover, 헤드 커버")
                st.caption("목록 맨 아래(최저 우선순위)에 추가됩니다. 사전 관리 페이지에서 ▲▼로 순서를 조정하세요.")

                if st.button("💾 카테고리 추가 & 재분류", key=f'sv_c_{i}', type='primary'):
                    if not c_name.strip():
                        st.warning("카테고리명을 입력하세요.")
                    else:
                        d = load_dict()
                        if do_add_category(d, c_name.strip(), c_alias):
                            save_and_reparse(d, f"카테고리 '{c_name.strip()}' 추가")
                        else:
                            st.warning(f"'{c_name.strip()}'는 이미 있습니다. **별칭 추가** 탭을 이용하세요.")

            # ── 탭 4: 별칭 추가 ──────────────────────────────────────────
            with tab_al:
                st.caption("기존 항목이 다른 표현으로 적혀있을 때, 그 표현을 별칭으로 등록합니다.")
                al_type = st.radio("항목 유형",
                                   ["브랜드", "모델", "서브모델", "카테고리"],
                                   horizontal=True, key=f'al_type_{i}')

                # 선택 UI 먼저, 별칭 입력은 마지막
                if al_type == "브랜드":
                    al_b_sel = st.selectbox("브랜드 선택 *", ['선택하세요'] + brands,
                                            key=f'al_b_sel_{i}')
                    al_new = st.text_input("추가할 별칭 *", key=f'al_val_{i}',
                                           placeholder="예: 테일러메이드코리아")
                    if st.button("💾 별칭 추가 & 재분류", key=f'sv_al_b_{i}', type='primary'):
                        if al_b_sel == '선택하세요' or not al_new.strip():
                            st.warning("브랜드와 별칭을 모두 입력하세요.")
                        else:
                            d = load_dict()
                            if do_add_alias_brand(d, al_b_sel, al_new.strip()):
                                save_and_reparse(d, f"브랜드 '{al_b_sel}'에 별칭 '{al_new.strip()}' 추가")
                            else:
                                st.warning("이미 등록된 별칭입니다.")

                elif al_type == "모델":
                    al_b = st.selectbox("브랜드 선택 *", ['선택하세요'] + brands,
                                        key=f'al_m_brand_{i}')
                    m_list = model_names(dic, al_b) if al_b != '선택하세요' else []
                    al_m = st.selectbox("모델 선택 *", ['선택하세요'] + m_list,
                                        key=f'al_m_sel_{i}')
                    al_new = st.text_input("추가할 별칭 *", key=f'al_val_{i}',
                                           placeholder="예: spider red, 스파이더레드")
                    if st.button("💾 별칭 추가 & 재분류", key=f'sv_al_m_{i}', type='primary'):
                        if al_b == '선택하세요' or al_m == '선택하세요' or not al_new.strip():
                            st.warning("브랜드, 모델, 별칭을 모두 입력하세요.")
                        else:
                            d = load_dict()
                            if do_add_alias_model(d, al_b, al_m, al_new.strip()):
                                save_and_reparse(d, f"모델 '{al_b} > {al_m}'에 별칭 '{al_new.strip()}' 추가")
                            else:
                                st.warning("이미 등록된 별칭입니다.")

                elif al_type == "서브모델":
                    al_sb = st.selectbox("브랜드 선택 *", ['선택하세요'] + brands,
                                         key=f'al_sb_brand_{i}')
                    sm_list = model_names(dic, al_sb) if al_sb != '선택하세요' else []
                    al_sm = st.selectbox("모델 선택 *", ['선택하세요'] + sm_list,
                                         key=f'al_sm_sel_{i}')
                    sub_list = (sub_model_names(dic, al_sb, al_sm)
                                if al_sb != '선택하세요' and al_sm != '선택하세요' else [])
                    al_sub = st.selectbox("서브모델 선택 *", ['선택하세요'] + sub_list,
                                          key=f'al_sub_sel_{i}')
                    al_new = st.text_input("추가할 별칭 *", key=f'al_val_{i}',
                                           placeholder="예: 맥스, MAX")
                    if st.button("💾 별칭 추가 & 재분류", key=f'sv_al_sub_{i}', type='primary'):
                        if '선택하세요' in [al_sb, al_sm, al_sub] or not al_new.strip():
                            st.warning("브랜드, 모델, 서브모델, 별칭을 모두 선택/입력하세요.")
                        else:
                            d = load_dict()
                            if do_add_alias_submodel(d, al_sb, al_sm, al_sub, al_new.strip()):
                                save_and_reparse(d, f"서브모델 '{al_sm} > {al_sub}'에 별칭 '{al_new.strip()}' 추가")
                            else:
                                st.warning("이미 등록된 별칭입니다.")

                elif al_type == "카테고리":
                    al_c = st.selectbox("카테고리 선택 *", ['선택하세요'] + cats,
                                        key=f'al_c_sel_{i}')
                    al_new = st.text_input("추가할 별칭 *", key=f'al_val_{i}',
                                           placeholder="예: head cover, 헤드 커버")
                    if st.button("💾 별칭 추가 & 재분류", key=f'sv_al_c_{i}', type='primary'):
                        if al_c == '선택하세요' or not al_new.strip():
                            st.warning("카테고리와 별칭을 모두 입력하세요.")
                        else:
                            d = load_dict()
                            if do_add_alias_category(d, al_c, al_new.strip()):
                                save_and_reparse(d, f"카테고리 '{al_c}'에 별칭 '{al_new.strip()}' 추가")
                            else:
                                st.warning("이미 등록된 별칭입니다.")

            # ── 탭 5: 태그 추가 ──────────────────────────────────────────
            with tab_tg:
                st.caption(
                    "상품명에서 태그로 인식될 표현을 등록합니다. "
                    "기존 태그명을 입력하면 해당 태그에 별칭이 추가되고, "
                    "새 이름을 입력하면 태그가 새로 만들어집니다."
                )
                if tags:
                    st.caption(f"현재 태그: {', '.join(tags)}")
                tg_name  = st.text_input("태그명 *", key=f'tg_name_{i}',
                                          placeholder="예: 좌타  (기존) 또는 주니어 (신규)")
                tg_alias = st.text_input("별칭/패턴 (쉼표 구분) *", key=f'tg_alias_{i}',
                                          placeholder="예: 좌타자, left hand, LH")
                if st.button("💾 태그 추가 & 재분류", key=f'sv_tg_{i}', type='primary'):
                    if not tg_name.strip() or not tg_alias.strip():
                        st.warning("태그명과 별칭을 모두 입력하세요.")
                    else:
                        d = load_dict()
                        if do_add_tag(d, tg_name.strip(), tg_alias):
                            save_and_reparse(d, f"태그 '{tg_name.strip()}' 업데이트")
                        else:
                            st.warning("별칭을 입력하세요.")

st.divider()
with st.expander("📊 검토 대상 전체 목록"):
    cols = [c for c in ['원본상품명', '브랜드', '메인모델', '카테고리', '태그', '잔여텍스트', '분류상태']
            if c in rev.columns]
    st.dataframe(rev[cols], use_container_width=True)
