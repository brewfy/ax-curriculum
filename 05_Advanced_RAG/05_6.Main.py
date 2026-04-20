"""
AX Advanced RAG — Streamlit 메인 앱 (대화형 인터페이스)
"""
import importlib.util
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── 형제 모듈 로드 ────────────────────────────────────────────
def _load_sibling(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent / filename
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


schemas   = _load_sibling("schemas",   "05_2.Schemas.py")
auth      = _load_sibling("auth",      "05_3.Auth.py")
indexing  = _load_sibling("indexing",  "05_4.Indexing.py")
retrieval = _load_sibling("retrieval", "05_5.Retrieval.py")

# ── 경로 설정 ─────────────────────────────────────────────────
_BASE      = Path(__file__).parent
DATA_DIR   = Path(os.getenv("DATA_DIR",   str(_BASE.parent / "Data")))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(_BASE / "chroma_db")))
PDF_PATH   = DATA_DIR / "AXCompass.pdf"
_ENV_KEY   = os.getenv("OPENAI_API_KEY", "")

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="AX Advanced RAG",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #111111; }
    [data-testid="stSidebar"] {
        background-color: #f5f5f5;
        border-right: 1px solid #e0e0e0;
    }
    .stButton > button {
        background-color: #f5f5f5 !important;
        color: #111111 !important;
        border: 1px solid #d0d0d0 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background-color: #111111 !important;
        color: #ffffff !important;
        border-color: #111111 !important;
        transform: translateY(-1px);
    }
    button[kind="primary"] {
        background-color: #111111 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="primary"]:hover {
        background-color: #333 !important;
    }
    [data-testid="chat-message-user"] {
        background-color: #f0f0f0 !important;
        border: 1px solid #e0e0e0;
        border-radius: 12px !important;
    }
    [data-testid="chat-message-assistant"] {
        background-color: #fafafa !important;
        border: 1px solid #ebebeb;
        border-radius: 12px !important;
    }
    [data-testid="stChatInput"] > div {
        background-color: #f5f5f5 !important;
        border: 1px solid #d0d0d0 !important;
        border-radius: 12px !important;
    }
    [data-testid="stChatInput"] textarea { color: #111 !important; }
    .section-header {
        font-size: 0.72rem; font-weight: 700;
        letter-spacing: 0.15em; text-transform: uppercase;
        color: #999; margin: 1rem 0 0.6rem;
        padding-bottom: 0.4rem; border-bottom: 1px solid #e0e0e0;
    }
    .info-box {
        background-color: #fff; border: 1px solid #e0e0e0;
        border-radius: 10px; padding: 0.8rem 1rem;
    }
    .info-row {
        display: flex; gap: 0.5rem; padding: 0.22rem 0;
        border-bottom: 1px solid #f0f0f0; font-size: 0.83rem;
    }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #999; min-width: 80px; font-weight: 500; }
    .info-value { color: #111; }
    .tag {
        display: inline-block; background-color: #f0f0f0;
        color: #444; border: 1px solid #ddd; border-radius: 4px;
        padding: 0.1rem 0.4rem; font-size: 0.72rem; margin: 0.1rem;
    }
    .group-badge {
        display: inline-block; border-radius: 5px;
        padding: 0.2rem 0.5rem; font-size: 0.75rem; font-weight: 600; margin: 0.1rem;
    }
    .group-a { background-color: #e8f5ee; color: #1a7a4a; border: 1px solid #b8ddc8; }
    .group-b { background-color: #fff4e6; color: #b45a00; border: 1px solid #f0c88a; }
    .group-c { background-color: #e8eef8; color: #1a4a8a; border: 1px solid #b0c4e8; }
    .step-dot {
        display: inline-block; width: 8px; height: 8px;
        border-radius: 50%; margin: 0 2px;
    }
    .step-done { background-color: #111; }
    .step-cur  { background-color: #aaa; }
    .step-todo { background-color: #ddd; }
    .rag-badge {
        display: inline-block; background-color: #f0f0f0;
        border: 1px solid #ddd; border-radius: 20px;
        padding: 0.2rem 0.7rem; font-size: 0.75rem; color: #555; margin-bottom: 0.5rem;
    }
    .type-progress {
        background-color: #f9f9f9; border: 1px solid #e8e8e8;
        border-radius: 10px; padding: 0.8rem 1rem; margin: 0.5rem 0;
        font-size: 0.83rem;
    }
    .type-row {
        display: flex; justify-content: space-between;
        padding: 0.18rem 0; color: #777;
    }
    .type-row.done { color: #111; font-weight: 500; }
    .type-row.cur  { color: #1a7a4a; font-weight: 600; }
    hr { border-color: #e0e0e0 !important; }
    h1, h2, h3 { color: #111 !important; }
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #f5f5f5; }
    ::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── 대화 단계 상수 ────────────────────────────────────────────
TYPES_ORDER = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
TYPE_GROUP  = {"균형형": "A", "이해형": "A", "과신형": "B", "실행형": "B", "판단형": "C", "조심형": "C"}
SKIP_WORDS  = {"없음", "없어요", "없습니다", "-", "skip", "pass", "none", "n/a", "아니요", "아니"}

_ALL_STEPS = [
    "api_key", "company", "goal", "audience", 
    "level", "duration", "topics", "extra", "type_counts",
]
STEPS = [s for s in _ALL_STEPS if not (s == "api_key" and _ENV_KEY)]

# 버튼 선택 단계 (chat_input 대신 st.button 사용)
BUTTON_STEPS  = set()
TOPICS_STEP   = None
TYPECOUNT_STEP = "type_counts"

STEP_LABELS = {
    "api_key": "API 키", "company": "회사명", "goal": "교육 목표",
    "audience": "교육 대상", "level": "교육 수준", "duration": "교육 기간",
    "topics": "교육 주제", "extra": "조건/제한사항",
    "type_counts": "AX Compass",
}


# ── 질문 생성 ─────────────────────────────────────────────────
def _type_count_question(idx: int) -> str:
    tp    = TYPES_ORDER[idx]
    grp   = TYPE_GROUP[tp]
    badge = {"A": "A그룹", "B": "B그룹", "C": "C그룹"}[grp]
    remain = len(TYPES_ORDER) - idx
    return (
        f"**{tp}** ({badge}) 인원수를 입력해주세요.\n"
        f"*(숫자 입력, 없으면 0 — 남은 유형 {remain}개)*"
    )


def _bot_question(step: str) -> str:
    if step == "api_key":
        return (
            "안녕하세요! 👋 AX Advanced RAG 커리큘럼 설계 챗봇입니다.\n\n"
            "시작하려면 **OpenAI API 키**를 입력해주세요.\n"
            "*(입력한 키는 세션 내에서만 사용됩니다)*"
        )
    if step == "company":
        if "api_key" not in STEPS:
            return (
                "안녕하세요! 👋 AX Advanced RAG 커리큘럼 설계 챗봇입니다.\n\n"
                "몇 가지 정보를 여쭤볼게요. **1. 회사명 또는 팀 이름**을 알려주세요."
            )
        return "**1. 회사명 또는 팀 이름**을 알려주세요."
    if step == "goal":
        return "**2. 교육 목표**는 무엇인가요?"
    if step == "audience":
        return "**3. 교육 대상자**를 선택하거나 입력해주세요."
    if step == "level":
        return "**4. 현재 AI 활용 수준**을 선택해주세요.\n*(입문, 초급, 중급, 고급 등)*"
    if step == "duration":
        return "**5. 교육 기간 또는 총 시간**을 선택하거나 입력해주세요."
    if step == "topics":
        return "**6. 원하는 핵심 주제**를 입력해주세요."
    if step == "extra":
        return "**7. 꼭 반영해야 할 조건 또는 제한사항**이 있으신가요?\n*(없으면 '없음' 입력)*"
    if step == "type_counts":
        return _type_count_question(0)
    return ""


# ── 단계 전환 ────────────────────────────────────────────────
def _advance(step: str):
    """현재 단계를 완료하고 다음 단계로 이동한다."""
    next_idx = STEPS.index(step) + 1
    if next_idx < len(STEPS):
        next_step = STEPS[next_idx]
        st.session_state.step = next_step

        if step == "api_key" and next_step == "company":
            db_note = " RAG DB도 준비되었습니다." if st.session_state.db_ready else ""
            bot_reply = (
                f"API 키 확인 완료! ✅{db_note}\n\n"
                "**교육 대상 회사명 또는 기관명**을 알려주세요."
            )
        elif next_step == "type_counts":
            st.session_state.type_idx = 0
            st.session_state.type_wip = {}
            bot_reply = _type_count_question(0)
        else:
            bot_reply = _bot_question(next_step)

        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    else:
        company = st.session_state.info.get("company", "")
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"완벽합니다! 🎉 **{company}** 의 맞춤형 커리큘럼을 설계하겠습니다.\n\n"
                "잠시만 기다려주세요..."
            ),
        })
        st.session_state.step = "generating"


# ── 입력 파싱 (텍스트 전용 단계) ─────────────────────────────
def process_text_input(step: str, text: str) -> tuple[object, str | None]:
    t = text.strip()
    if step == "api_key":
        if not t.startswith("sk-") or len(t) < 20:
            return None, "올바른 OpenAI API 키 형식이 아닙니다. (sk-로 시작해야 합니다)"
        return t, None
    if step == "company":
        return (t or None, "회사명을 입력해주세요." if not t else None)
    if step == "goal":
        return (t or None, "교육 목표를 입력해주세요." if not t else None)
    if step == "extra":
        return ("" if t.lower() in SKIP_WORDS else t), None
    return t, None # Default for other steps if handled via chat_input


# ── 벡터 DB 초기화 ────────────────────────────────────────────
def ensure_vector_db(api_key: str):
    if st.session_state.db_ready:
        return
    try:
        logs: list[str] = []
        col = indexing.init_vector_db(api_key, CHROMA_DIR, PDF_PATH, lambda m: logs.append(m))
        st.session_state.collection = col
        st.session_state.db_status  = logs[-1] if logs else "준비 완료"
        st.session_state.db_ready   = True
    except Exception as e:
        st.session_state.db_status = f"오류: {e}"


# ── LLM 헬퍼 ────────────────────────────────────────────────
def _stream_llm(messages: list[dict]):
    from openai import OpenAI
    api_key = st.session_state.info.get("api_key") or _ENV_KEY
    client  = OpenAI(api_key=api_key)
    api_msgs = [{"role": "system", "content": schemas.SYSTEM_PROMPT}] + messages
    return client.chat.completions.create(
        model="gpt-4o", messages=api_msgs,
        stream=True, temperature=0.7, max_tokens=6000,
    )

def _write_stream(stream) -> str:
    return st.write_stream(
        chunk.choices[0].delta.content or ""
        for chunk in stream
        if chunk.choices[0].delta.content
    )

def _make_edu_info() -> schemas.EducationInfo:
    d = st.session_state.info
    return schemas.EducationInfo(
        company=d.get("company", ""),
        goal=d.get("goal", ""),
        audience=d.get("audience", ""),
        level=d.get("level", ""),
        duration=d.get("duration", ""),
        topics=d.get("topics", []),
        extra=d.get("extra", ""),
        type_counts=d.get("type_counts", {}),
    )


# ── 세션 초기화 ──────────────────────────────────────────────
for _k, _v in {
    "step": STEPS[0],
    "info": {},
    "messages": [],
    "llm_messages": [],
    "collection": None,
    "db_status": "",
    "db_ready": False,
    "type_idx": 0,
    "type_wip": {},
    "pending_topics": [],
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# 환경변수에 API 키가 있으면 DB 초기화
if _ENV_KEY and not st.session_state.db_ready:
    ensure_vector_db(_ENV_KEY)

# 최초 웰컴 메시지
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": _bot_question(STEPS[0]),
    })


# ── 메인 실행 로직 ───────────────────────────────────────────
def run_app():
    # 진행 단계 계산
    def _step_index() -> int:
        step = st.session_state.step
        return STEPS.index(step) if step in STEPS else len(STEPS)

    # ── 사이드바 ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div style="padding:1rem 0 0.5rem;">
          <div style="font-size:0.7rem;letter-spacing:0.18em;color:#999;text-transform:uppercase;">AI Transformation · RAG</div>
          <div style="font-size:1.2rem;font-weight:800;color:#111;margin-top:0.3rem;">AX Advanced RAG</div>
        </div>
        """, unsafe_allow_html=True)

        cur_idx  = _step_index()
        cur_step = st.session_state.step

        # 진행 도트
        dots_html = "".join(
            f'<span class="step-dot {"step-done" if i < cur_idx else ("step-cur" if i == cur_idx else "step-todo")}"></span>'
            for i in range(len(STEPS))
        )
        progress_label = (
            f"{cur_idx}/{len(STEPS)} 단계 완료"
            if cur_step in STEPS
            else "정보 수집 완료"
        )
        st.markdown(
            f'<div style="margin:0.3rem 0 0.8rem;">{dots_html}'
            f'<span style="font-size:0.75rem;color:#999;margin-left:0.5rem;">{progress_label}</span></div>',
            unsafe_allow_html=True,
        )

        # RAG 상태
        if st.session_state.db_ready:
            st.markdown(
                '<div style="color:#1a7a4a;font-size:0.78rem;padding:0.2rem 0 0.5rem;">✓ RAG 활성화</div>',
                unsafe_allow_html=True,
            )
        elif st.session_state.db_status:
            st.markdown(
                f'<div style="color:#b45a00;font-size:0.78rem;padding:0.2rem 0 0.5rem;">⚠ {st.session_state.db_status}</div>',
                unsafe_allow_html=True,
            )

        # type_counts 진행 중이면 유형별 입력 현황 표시
        if cur_step == "type_counts":
            st.markdown('<div class="section-header">AX Compass 입력 중</div>', unsafe_allow_html=True)
            wip = st.session_state.type_wip
            idx = st.session_state.type_idx
            rows = ""
            for i, tp in enumerate(TYPES_ORDER):
                grp = TYPE_GROUP[tp]
                grp_cls = {"A": "group-a", "B": "group-b", "C": "group-c"}[grp]
                if i < idx:
                    rows += f'<div class="type-row done">✓ {tp} <span>{wip.get(tp, 0)}명</span></div>'
                elif i == idx:
                    rows += f'<div class="type-row cur">▶ {tp} <span style="color:#999;">입력 중...</span></div>'
                else:
                    rows += f'<div class="type-row">· {tp}</div>'
            st.markdown(f'<div class="type-progress">{rows}</div>', unsafe_allow_html=True)

        # 수집된 정보 요약
        info_d = st.session_state.info
        if any(k in info_d for k in ("company", "goal", "audience")):
            st.markdown('<div class="section-header">수집된 정보</div>', unsafe_allow_html=True)
            rows = ""
            for key, label in [
                ("company", "회사명"), ("goal", "목표"),
                ("audience", "대상"), ("level", "수준"),
                ("duration", "기간"),
            ]:
                if key in info_d:
                    rows += (
                        f'<div class="info-row">'
                        f'<span class="info-label">{label}</span>'
                        f'<span class="info-value">{info_d[key]}</span>'
                        f'</div>'
                    )
            if "topics" in info_d:
                tags = "".join(f'<span class="tag">{t}</span>' for t in info_d["topics"])
                if info_d.get("extra"):
                    tags += f'<span class="tag">{info_d["extra"]}</span>'
                rows += (
                    f'<div class="info-row"><span class="info-label">주제</span>'
                    f'<span class="info-value">{tags}</span></div>'
                )
            if "type_counts" in info_d:
                tc    = info_d["type_counts"]
                ga    = tc.get("균형형", 0) + tc.get("이해형", 0)
                gb    = tc.get("과신형", 0) + tc.get("실행형", 0)
                gc    = tc.get("판단형", 0) + tc.get("조심형", 0)
                total = ga + gb + gc
                if total > 0:
                    rows += (
                        f'<div class="info-row"><span class="info-label">그룹</span>'
                        f'<span class="info-value">'
                        f'<span class="group-badge group-a">A {ga}명</span>'
                        f'<span class="group-badge group-b">B {gb}명</span>'
                        f'<span class="group-badge group-c">C {gc}명</span>'
                        f'<span style="color:#999;font-size:0.75rem;"> 총 {total}명</span>'
                        f'</span></div>'
                    )
            if rows:
                st.markdown(f'<div class="info-box">{rows}</div>', unsafe_allow_html=True)

        # 하단 버튼들
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("초기화", use_container_width=True):
                for k in ["step", "info", "messages", "llm_messages", "type_idx", "type_wip"]:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
        with c2:
            if st.button("로그아웃", use_container_width=True):
                auth.logout()

    # ── 헤더 ─────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:1.5rem 0 0.8rem;">
      <h1 style="font-size:1.7rem;font-weight:800;margin:0;color:#111;">AX Advanced RAG 챗봇</h1>
      <p style="color:#777;margin:0.3rem 0 0;font-size:0.88rem;">AX Compass 진단 결과 기반 그룹 맞춤형 커리큘럼 설계</p>
    </div><hr>
    """, unsafe_allow_html=True)

    # ── 메시지 렌더링 ────────────────────────────────────────────
    for msg in st.session_state.messages:
        avatar = "🧠" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])


# ── 메인 흐름 제어 ─────────────────────────────────────────────
if not auth.is_logged_in():
    auth.login_page()
else:
    run_app()

    # ════════════════════════════════════════════════════════════
    #  커리큘럼 생성 단계
    # ════════════════════════════════════════════════════════════
    if st.session_state.step == "generating":
        edu_info   = _make_edu_info()
        collection = st.session_state.collection
        active     = edu_info.active_types()

        rag_ctx = ""
        if collection:
            with st.spinner("RAG 검색 중..."):
                rag_ctx = retrieval.retrieve_type_info(collection, active, n_results=6)

        user_msg = retrieval.build_user_message(edu_info, rag_ctx)
        st.session_state.llm_messages.append({"role": "user", "content": user_msg})

        if collection and rag_ctx:
            st.markdown('<div class="rag-badge">🔍 RAG 컨텍스트 적용됨</div>', unsafe_allow_html=True)

        with st.chat_message("assistant", avatar="🧠"):
            response = _write_stream(_stream_llm(st.session_state.llm_messages))

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.llm_messages.append({"role": "assistant", "content": response})
        st.session_state.step = "chat"


    # ── 입력 처리 준비 ─────────────────────────────────────────────
    placeholder = "메시지를 입력하세요..."
    if st.session_state.step in STEPS:
        step = st.session_state.step
        if step == TYPECOUNT_STEP:
            placeholder = f"{TYPES_ORDER[st.session_state.type_idx]} 인원수 입력..."
        else:
            p_map = {
                "api_key": "sk-...", "company": "회사명 입력", "goal": "교육 목표 입력",
                "audience": "대상자 입력", "level": "AI 수준 입력", "duration": "기간 입력",
                "topics": "핵심 주제 입력", "extra": "조건/제한사항 입력"
            }
            placeholder = p_map.get(step, "입력하세요...")

    if st.session_state.step == "chat":
        st.markdown('<div style="color:#999;font-size:0.82rem;text-align:center;padding:0.5rem 0;">'
                    '수정·보완 요청이나 추가 질문을 입력하세요</div>', unsafe_allow_html=True)

    # ── 단일 입력창 (포커스 유지의 핵심) ───────────────────────────
    user_input = st.chat_input(placeholder, key="main_chat_input")
    
    if user_input:
        cur_step = st.session_state.step
        
        # [A] 후속 채팅 단계 처리
        if cur_step == "chat":
            collection = st.session_state.collection
            enriched = prompt = user_input
            if collection:
                edu_info = _make_edu_info()
                enriched = retrieval.enrich_followup(prompt, collection, edu_info.active_types())
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.llm_messages.append({"role": "user", "content": enriched})
            st.rerun()

        # [B] 정보 수집 단계 처리
        elif cur_step in STEPS:
            display_input = "sk-●●●●●●●●●●●●●●●●" if cur_step == "api_key" else user_input
            st.session_state.messages.append({"role": "user", "content": display_input})

            if cur_step == TYPECOUNT_STEP:
                try:
                    n = int(user_input.strip()); 
                    if n < 0: raise ValueError
                    tp = TYPES_ORDER[st.session_state.type_idx]
                    st.session_state.type_wip[tp] = n
                    st.session_state.messages[-1]["content"] = f"{tp}: {n}명"
                    if st.session_state.type_idx + 1 < len(TYPES_ORDER):
                        st.session_state.type_idx += 1
                        st.session_state.messages.append({"role": "assistant", "content": _type_count_question(st.session_state.type_idx)})
                    else:
                        wip = st.session_state.type_wip
                        st.session_state.info["type_counts"] = dict(wip)
                        ga, gb, gc = 0, 0, 0
                        for k, v in wip.items():
                            if TYPE_GROUP[k] == "A": ga += v
                            elif TYPE_GROUP[k] == "B": gb += v
                            else: gc += v
                        st.session_state.messages.append({"role": "assistant", "content": f"AX Compass 입력 완료! ✅\n\n설계를 시작합니다."})
                        st.session_state.step = "generating"
                except ValueError:
                    st.session_state.messages.append({"role": "assistant", "content": "⚠️ 0 이상의 숫자를 입력해주세요."})
            else:
                value, error = process_text_input(cur_step, user_input)
                if error:
                    st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error}"})
                else:
                    st.session_state.info[cur_step] = [value] if cur_step == "topics" else value
                    if cur_step == "api_key":
                        with st.spinner("벡터 DB 초기화 중..."): ensure_vector_db(value)
                    _advance(cur_step)
            st.rerun()
