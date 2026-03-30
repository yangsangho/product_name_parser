"""
상품명 파서 - Main Streamlit Application
"""
import io
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Path setup ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DICT_PATH = BASE_DIR / "data" / "dictionary.json"

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="상품명 파서",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a5c2a; margin-bottom: 0.2rem; }
    .sub-header { color: #555; margin-bottom: 1.5rem; }
    .stDataFrame { font-size: 0.85rem; }
    div[data-testid="stSidebar"] { background: #f8faf8; }
</style>
""", unsafe_allow_html=True)


# ── Parser initialization ────────────────────────────────────────────────────
def get_parser():
    """Get or create parser instance in session state."""
    if 'parser' not in st.session_state or st.session_state.get('reload_parser', False):
        from golf_parser.parser import ProductNameParser
        st.session_state['parser'] = ProductNameParser(str(DICT_PATH))
        st.session_state['reload_parser'] = False
    return st.session_state['parser']


# ── Utility functions ────────────────────────────────────────────────────────
def run_parsing(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Parse a column and return results dataframe."""
    parser = get_parser()
    results = []
    progress = st.progress(0, text="파싱 중...")
    total = len(df)

    for i, val in enumerate(df[col]):
        parsed = parser.parse(str(val) if pd.notna(val) else "")
        results.append({
            '원본상품명': val,
            '브랜드': parsed['brand'] or '',
            '메인모델': parsed['main_model'] or '',
            '서브모델': parsed['sub_model'] or '',
            '카테고리': parsed['category'] or '',
            '태그': ', '.join(parsed['tags']),
            '잔여텍스트': parsed['residual'],
            '분류상태': parsed['status'],
        })
        if total > 0:
            progress.progress((i + 1) / total, text=f"파싱 중... {i+1}/{total}")

    progress.empty()
    result_df = pd.DataFrame(results)

    # Merge with original df (other columns)
    other_cols = [c for c in df.columns if c != col]
    if other_cols:
        merged = pd.concat([df[other_cols].reset_index(drop=True), result_df], axis=1)
        return merged
    return result_df


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Convert dataframe to Excel bytes for download."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='파싱결과')
    return buf.getvalue()


def detect_product_name_column(df: pd.DataFrame):
    """Auto-detect the product name column."""
    candidates = ['상품명', '품명', 'product_name', 'name', '제품명', '상품 명', '아이템명']
    for col in df.columns:
        if str(col).strip() in candidates:
            return str(col).strip()
        for cand in candidates:
            if cand in str(col).lower():
                return str(col)
    return None


def show_results(result_df: pd.DataFrame, key_suffix: str = ''):
    """Render the results section with filters, dataframe and download."""
    st.divider()
    st.markdown("### 파싱 결과")

    # ── Summary metrics ──────────────────────────────────────────────────
    total = len(result_df)
    done_col = '분류상태'
    cnt_done = (result_df[done_col] == '완료').sum() if done_col in result_df.columns else 0
    cnt_partial = (result_df[done_col] == '부분').sum() if done_col in result_df.columns else 0
    cnt_undone = (result_df[done_col] == '미분류').sum() if done_col in result_df.columns else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체", total)
    m2.metric("완료", int(cnt_done),
              delta=f"{cnt_done/total*100:.1f}%" if total else None)
    m3.metric("부분", int(cnt_partial))
    m4.metric("미분류", int(cnt_undone),
              delta=f"-{cnt_undone/total*100:.1f}%" if total and cnt_undone else None,
              delta_color="inverse")

    if cnt_undone > 0:
        st.warning(
            f"미분류 상품이 {int(cnt_undone)}개 있습니다. "
            "사이드바의 **미분류검토** 페이지에서 확인하세요."
        )

    # ── Filters ──────────────────────────────────────────────────────────
    with st.expander("🔍 필터 옵션", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns(4)

        brand_opts = ['전체'] + sorted([b for b in result_df['브랜드'].dropna().unique() if b])
        cat_opts = ['전체'] + sorted([c for c in result_df['카테고리'].dropna().unique() if c])
        status_opts = ['전체', '완료', '부분', '미분류']

        sel_brand = fc1.selectbox("브랜드", brand_opts, key=f'f_brand{key_suffix}')
        sel_cat = fc2.selectbox("카테고리", cat_opts, key=f'f_cat{key_suffix}')
        sel_status = fc3.selectbox("분류상태", status_opts, key=f'f_status{key_suffix}')
        tag_input = fc4.text_input(
            "태그 포함", placeholder="예: 남성", key=f'f_tag{key_suffix}'
        )

    # Apply filters
    filtered = result_df.copy()
    if sel_brand != '전체':
        filtered = filtered[filtered['브랜드'] == sel_brand]
    if sel_cat != '전체':
        filtered = filtered[filtered['카테고리'] == sel_cat]
    if sel_status != '전체':
        filtered = filtered[filtered['분류상태'] == sel_status]
    if tag_input.strip():
        filtered = filtered[filtered['태그'].str.contains(tag_input.strip(), na=False)]

    # ── Dataframe display ─────────────────────────────────────────────────
    def highlight_status(val):
        colors = {'완료': 'color: #1a7a3a', '부분': 'color: #b87a00', '미분류': 'color: #c0392b'}
        return colors.get(val, '')

    styled = filtered.style.map(highlight_status, subset=['분류상태'])
    st.dataframe(styled, use_container_width=True, height=450)
    st.caption(f"표시: {len(filtered)}행 / 전체: {len(result_df)}행")

    # ── Download ──────────────────────────────────────────────────────────
    dl_col, _ = st.columns([1, 3])
    with dl_col:
        excel_bytes = to_excel_bytes(filtered)
        st.download_button(
            label="📥 Excel 다운로드",
            data=excel_bytes,
            file_name="파싱결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f'dl_btn{key_suffix}',
        )


# ── Main header ───────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">⛳ 상품명 파서</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">골프 상품명에서 브랜드·모델·카테고리·태그를 자동 추출합니다.</div>',
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 메뉴")
    st.page_link("app.py", label="상품명 파서", icon="⛳")
    st.page_link("pages/1_사전관리.py", label="사전 관리", icon="📚")
    st.page_link("pages/2_미분류검토.py", label="미분류 검토", icon="🔎")
    st.divider()
    st.markdown("### 파서 상태")
    try:
        parser = get_parser()
        brand_count = len(parser.dictionary.get('brands', []))
        cat_count = len(parser.dictionary.get('categories', []))
        st.success(f"로드 완료  \n브랜드 **{brand_count}**개 / 카테고리 **{cat_count}**개")
    except Exception as e:
        st.error(f"파서 오류: {e}")
    if st.button("🔄 파서 새로고침", use_container_width=True):
        st.session_state['reload_parser'] = True
        st.rerun()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_upload, tab_manual = st.tabs(["📁 파일 업로드", "✏️ 직접 입력"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: File Upload
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("#### Excel 파일 업로드")
    uploaded_file = st.file_uploader(
        "상품명이 포함된 Excel 파일을 업로드하세요 (.xlsx, .xls)",
        type=['xlsx', 'xls'],
        key='file_uploader',
    )

    if uploaded_file is not None:
        try:
            df_raw = pd.read_excel(uploaded_file)
            st.success(f"파일 로드 완료: **{len(df_raw)}행** × **{len(df_raw.columns)}열**")

            auto_col = detect_product_name_column(df_raw)
            col_options = list(df_raw.columns)
            default_idx = col_options.index(auto_col) if auto_col and auto_col in col_options else 0

            col_left, col_right = st.columns([2, 1])
            with col_left:
                selected_col = st.selectbox(
                    "상품명 컬럼 선택",
                    options=col_options,
                    index=default_idx,
                    help="파싱할 상품명이 들어있는 컬럼을 선택하세요.",
                    key='col_select',
                )
            with col_right:
                st.markdown("<br>", unsafe_allow_html=True)
                if auto_col:
                    st.info(f"자동 감지: `{auto_col}`")

            with st.expander("원본 데이터 미리보기", expanded=False):
                st.dataframe(df_raw.head(10), use_container_width=True)

            if st.button("🚀 파싱 시작", type="primary", use_container_width=True, key='parse_btn'):
                result_df = run_parsing(df_raw, selected_col)
                st.session_state['result_df'] = result_df
                st.session_state['parsed_file'] = True
                st.rerun()

        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")

    if st.session_state.get('parsed_file') and 'result_df' in st.session_state:
        show_results(st.session_state['result_df'], key_suffix='_file')

# ════════════════════════════════════════════════════════════════════════════
# TAB 2: Manual Input
# ════════════════════════════════════════════════════════════════════════════
with tab_manual:
    st.markdown("#### 상품명 직접 입력")
    st.markdown("한 줄에 하나씩 상품명을 입력하세요.")

    default_samples = (
        "핑 남성 솔리드 버킷햇 골프 모자\n"
        "캘러웨이 어반(URBAN) 바퀴형 휠 보스턴백 GF\n"
        "[넥센] 세인트나인 25년 퀀텀(QUANTUM) 골프공 컬러 GF\n"
        "증정 필레오정품 파크골프 필레오 더블백 체크 GF 필레오 파크골프\n"
        "[던롭코리아 정품] 스릭슨 Q-STAR 투어 5 디바이드 골프볼 GF\n"
        "[임직원몰전용][한국캘러웨이정품] 오딧세이 25년 AI-ONE LE 라인 익스텐션 퍼터\n"
        "(시타채) (케이디엑스골프 정품) 고반발 도깨비 TI-21 여성 드라이버_GF\n"
        "증정 [한국캘러웨이정품] 26년 캘러웨이 TT 맥스 (TT MAX) 남성용 파우치 GF\n"
        "증정 [볼빅정품] VBDP-볼빅 여성 스퀘어로고 볼캡 GF"
    )

    text_input = st.text_area(
        "상품명 목록",
        value=default_samples,
        height=200,
        key='manual_input',
    )

    if st.button("🚀 파싱 시작", type="primary", key='parse_manual_btn'):
        lines = [l.strip() for l in text_input.split('\n') if l.strip()]
        if lines:
            df_manual = pd.DataFrame({'상품명': lines})
            result_df_manual = run_parsing(df_manual, '상품명')
            st.session_state['result_df_manual'] = result_df_manual
            st.session_state['parsed_manual'] = True
            st.rerun()
        else:
            st.warning("입력된 상품명이 없습니다.")

    if st.session_state.get('parsed_manual') and 'result_df_manual' in st.session_state:
        show_results(st.session_state['result_df_manual'], key_suffix='_manual')
