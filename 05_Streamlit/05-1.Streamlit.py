import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="AX 커리큘럼 설계 챗봇",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 라이트 테마 CSS ──────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #111111; }

    [data-testid="stSidebar"] {
        background-color: #f5f5f5;
        border-right: 1px solid #e0e0e0;
    }

    .stButton > button {
        background-color: #111111 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background-color: #333 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
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
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #999;
        margin: 1rem 0 0.6rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #e0e0e0;
    }
    .info-box {
        background-color: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    .info-row {
        display: flex;
        gap: 0.5rem;
        padding: 0.22rem 0;
        border-bottom: 1px solid #f0f0f0;
        font-size: 0.83rem;
    }
    .info-row:last-child { border-bottom: none; }
    .info-label { color: #999; min-width: 80px; font-weight: 500; }
    .info-value { color: #111; }
    .tag {
        display: inline-block;
        background-color: #f0f0f0;
        color: #444;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 0.1rem 0.4rem;
        font-size: 0.72rem;
        margin: 0.1rem;
    }
    .step-dot {
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        margin: 0 2px;
    }
    .step-done  { background-color: #111; }
    .step-cur   { background-color: #aaa; }
    .step-todo  { background-color: #ddd; }

    hr { border-color: #e0e0e0 !important; }
    h1, h2, h3 { color: #111 !important; }

    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #f5f5f5; }
    ::-webkit-scrollbar-thumb { background: #ccc; border-radius: 4px; }

    div[data-baseweb="select"] > div { background-color: #fff !important; border-color: #d0d0d0 !important; }
    li[role="option"] { color: #111 !important; }
    li[role="option"]:hover { background-color: #f5f5f5 !important; }
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """
당신은 20년 경력의 IT·AI 교육 전문가이자 교육 스타트업 대표입니다.

[강의 철학]
- 1시간이든 6개월이든, 수강생에게 실질적인 만족감과 업무 역량 향상을 제공합니다.
- 이론에 그치지 않고 현장에서 즉시 활용 가능한 실무 중심 커리큘럼을 설계합니다.
- 교육 대상자의 수준과 업무 맥락을 최우선으로 고려합니다.

[역할]
기업의 AX(AI Transformation) 교육을 위한 커리큘럼을 설계하는 챗봇입니다.
사용자가 제공한 정보를 바탕으로 맞춤형 커리큘럼을 생성합니다.

[커리큘럼 출력 형식]
## 📋 교육 개요
- 교육명 / 교육 대상 / 총 교육 시간 / 교육 방식

## 🎯 교육 목표
3~5개의 명확한 학습 성과 기술

## 🗂️ 모듈별 커리큘럼
각 모듈마다: 모듈 제목, 학습 목표, 세부 주제 목록, 실습/실무 적용 내용, 소요 시간

## 📝 평가 방법
평가 방식 및 기준

## 💼 기대 효과
수료 후 업무에서 기대되는 변화

정보가 부족하면 추가 질문을 통해 파악하고, 커리큘럼 생성 후에는 수정·보완 요청을 적극 반영합니다.
"""

AX_TOPICS = [
    "AI 기초 개념 및 트렌드",
    "ChatGPT / LLM 업무 활용",
    "프롬프트 엔지니어링",
    "AI 기반 데이터 분석",
    "RAG / 사내 지식 검색 AI",
    "AI 코딩 보조 (GitHub Copilot 등)",
    "이미지·영상 생성 AI",
    "AI 자동화 (RPA + AI)",
    "LLM API 활용 및 앱 개발",
    "AI 윤리 및 보안",
    "AI 전략 수립 / AX 로드맵",
    "업종별 AI 활용 사례",
]
AUDIENCE_OPTIONS = [
    "임원 / 경영진 (C-Level)", "팀장 / 중간관리자",
    "실무자 (비개발직군)", "개발자 / 엔지니어",
    "데이터 분석가", "혼합 (다양한 직군)",
]
LEVEL_OPTIONS = [
    "입문 (AI 완전 초보)", "기초 (기본 개념 이해)",
    "중급 (실무 활용)", "고급 (심화 / 개발)",
]
DURATION_OPTIONS = [
    "반일 (4시간)", "1일 (8시간)", "2일 (16시간)", "3일 (24시간)",
    "1주 (5일)", "1개월", "3개월", "6개월",
]
FORMAT_OPTIONS = [
    "집합 교육 (오프라인)", "온라인 라이브",
    "온·오프라인 혼합", "자기주도 학습 (비동기)",
]

# ── 대화 단계 정의 ────────────────────────────────────────────
STEPS = ["company", "industry", "audience", "level", "topics", "extra", "duration", "format"]
STEP_LABELS = {
    "company": "회사명", "industry": "업종", "audience": "교육 대상",
    "level": "교육 수준", "topics": "교육 주제", "extra": "추가 요청",
    "duration": "교육 기간", "format": "교육 방식",
}
SKIP_WORDS = {"없음", "없어요", "없습니다", "-", "skip", "pass", "none", "n/a", "아니요", "아니"}


def _fmt_options(options: list[str]) -> str:
    return "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))


def _fmt_multi_options(options: list[str]) -> str:
    return "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))


def _bot_question(step: str) -> str:
    if step == "company":
        return (
            "안녕하세요! 👋 저는 AX 커리큘럼 설계 전문가입니다.\n\n"
            "몇 가지 정보를 여쭤볼게요. 먼저 **교육 대상 회사명 또는 기관명**을 알려주세요."
        )
    if step == "industry":
        return "어떤 **업종 / 도메인**인가요?\n*(예: 제조, 금융, 의료, IT 서비스)*"
    if step == "audience":
        return (
            "**교육 대상**을 선택해주세요. 번호를 입력해주세요.\n\n"
            + _fmt_options(AUDIENCE_OPTIONS)
        )
    if step == "level":
        return (
            "**교육 수준**을 선택해주세요.\n\n"
            + _fmt_options(LEVEL_OPTIONS)
        )
    if step == "topics":
        return (
            "**다루고 싶은 주제**를 선택해주세요.\n"
            "번호를 쉼표로 구분해 입력하거나, 전체 선택은 **0** 을 입력하세요.\n\n"
            + _fmt_multi_options(AX_TOPICS)
        )
    if step == "extra":
        return (
            "**추가 주제나 특별 요청사항**이 있으신가요?\n"
            "*(없으면 '없음' 또는 '-' 입력)*"
        )
    if step == "duration":
        return (
            "**교육 기간**을 선택해주세요.\n\n"
            + _fmt_options(DURATION_OPTIONS)
        )
    if step == "format":
        return (
            "마지막으로 **교육 방식**을 선택해주세요.\n\n"
            + _fmt_options(FORMAT_OPTIONS)
        )
    return ""


def _parse_single(text: str, options: list[str]) -> tuple[str | None, str | None]:
    """단일 선택 파싱. (값, 오류) 반환."""
    t = text.strip()
    # 번호 입력
    try:
        idx = int(t)
        if 1 <= idx <= len(options):
            return options[idx - 1], None
        return None, f"1~{len(options)} 사이의 번호를 입력해주세요."
    except ValueError:
        pass
    # 텍스트 직접 매칭
    for opt in options:
        if t in opt or opt.startswith(t):
            return opt, None
    return None, f"올바른 번호(1~{len(options)})를 입력해주세요."


def _parse_multi(text: str, options: list[str]) -> tuple[list[str] | None, str | None]:
    """복수 선택 파싱. (값 리스트, 오류) 반환."""
    t = text.strip()
    if t == "0":
        return options[:], None
    try:
        indices = [int(x.strip()) for x in t.split(",") if x.strip()]
        if not indices:
            raise ValueError
        if all(1 <= i <= len(options) for i in indices):
            return [options[i - 1] for i in indices], None
        return None, f"1~{len(options)} 사이의 번호를 쉼표로 구분해 입력하세요."
    except ValueError:
        return None, "예: 1,3,5 또는 0 (전체 선택)"


def process_user_input(step: str, text: str) -> tuple[object, str | None]:
    """현재 단계에서 사용자 입력을 파싱합니다. (값, 오류) 반환."""
    t = text.strip()
    if step == "company":
        return (t or None, "회사명을 입력해주세요." if not t else None)
    if step == "industry":
        return (t or None, "업종을 입력해주세요." if not t else None)
    if step == "audience":
        return _parse_single(t, AUDIENCE_OPTIONS)
    if step == "level":
        return _parse_single(t, LEVEL_OPTIONS)
    if step == "topics":
        return _parse_multi(t, AX_TOPICS)
    if step == "extra":
        return (("" if t.lower() in SKIP_WORDS else t), None)
    if step == "duration":
        return _parse_single(t, DURATION_OPTIONS)
    if step == "format":
        return _parse_single(t, FORMAT_OPTIONS)
    return None, "알 수 없는 단계입니다."


# ── LLM ──────────────────────────────────────────────────────
def get_client() -> OpenAI:
    if "client" not in st.session_state:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            st.stop()
        st.session_state.client = OpenAI(api_key=api_key)
    return st.session_state.client


def build_curriculum_message(info: dict) -> str:
    topics_str = ", ".join(info["topics"])
    if info.get("extra"):
        topics_str += f", {info['extra']}"
    return f"""다음 정보를 바탕으로 AX 교육 커리큘럼을 설계해주세요.

- **회사명**: {info["company"]}
- **업종/도메인**: {info["industry"]}
- **교육 대상**: {info["audience"]}
- **교육 수준**: {info["level"]}
- **교육 주제**: {topics_str}
- **교육 기간**: {info["duration"]}
- **교육 방식**: {info["format"]}
"""


def stream_llm(messages: list[dict]):
    client = get_client()
    api_msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    return client.chat.completions.create(
        model="gpt-4o", messages=api_msgs,
        stream=True, temperature=0.7, max_tokens=4000,
    )


# ── 세션 초기화 ──────────────────────────────────────────────
for _k, _v in {
    "step": "company",     # 현재 수집 단계
    "info": {},            # 수집된 정보
    "messages": [],        # 화면에 표시할 대화 (role + content)
    "llm_messages": [],    # LLM에 보낼 메시지
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# 최초 진입 시 웰컴 메시지
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": _bot_question("company"),
    })


# ── 진행 상황 계산 ───────────────────────────────────────────
def _step_index() -> int:
    step = st.session_state.step
    if step in STEPS:
        return STEPS.index(step)
    return len(STEPS)  # generating / chat


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 0.5rem;">
      <div style="font-size:0.7rem;letter-spacing:0.18em;color:#999;text-transform:uppercase;">AI Transformation</div>
      <div style="font-size:1.2rem;font-weight:800;color:#111;margin-top:0.3rem;">AX 커리큘럼 설계</div>
    </div>
    """, unsafe_allow_html=True)

    # 진행 단계 도트 표시
    cur_idx = _step_index()
    dots_html = ""
    for i in range(len(STEPS)):
        cls = "step-done" if i < cur_idx else ("step-cur" if i == cur_idx else "step-todo")
        dots_html += f'<span class="step-dot {cls}"></span>'
    progress_label = (
        f"{cur_idx}/{len(STEPS)} 단계 완료"
        if st.session_state.step in STEPS
        else "정보 수집 완료"
    )
    st.markdown(
        f'<div style="margin:0.3rem 0 0.8rem;">{dots_html}'
        f'<span style="font-size:0.75rem;color:#999;margin-left:0.5rem;">{progress_label}</span></div>',
        unsafe_allow_html=True,
    )

    # 수집된 정보 요약
    info = st.session_state.info
    if info:
        st.markdown('<div class="section-header">수집된 정보</div>', unsafe_allow_html=True)
        rows = ""
        field_map = [
            ("company", "회사명"), ("industry", "업종"),
            ("audience", "대상"), ("level", "수준"),
            ("duration", "기간"), ("format", "방식"),
        ]
        for key, label in field_map:
            if key in info:
                rows += (
                    f'<div class="info-row">'
                    f'<span class="info-label">{label}</span>'
                    f'<span class="info-value">{info[key]}</span>'
                    f'</div>'
                )
        if "topics" in info:
            tags = "".join(f'<span class="tag">{t}</span>' for t in info["topics"])
            if info.get("extra"):
                tags += f'<span class="tag">{info["extra"]}</span>'
            rows += (
                f'<div class="info-row">'
                f'<span class="info-label">주제</span>'
                f'<span class="info-value">{tags}</span>'
                f'</div>'
            )
        st.markdown(f'<div class="info-box">{rows}</div>', unsafe_allow_html=True)

    # 다시 시작 버튼
    if st.session_state.step not in STEPS or cur_idx > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("처음부터 다시", use_container_width=True):
            for k in ["step", "info", "messages", "llm_messages"]:
                del st.session_state[k]
            st.rerun()


# ── 메인 헤더 ────────────────────────────────────────────────
st.markdown("""
<div style="padding:1.5rem 0 0.8rem;">
  <h1 style="font-size:1.7rem;font-weight:800;margin:0;color:#111;">AX 커리큘럼 설계 챗봇</h1>
  <p style="color:#777;margin:0.3rem 0 0;font-size:0.88rem;">질문에 답하시면 맞춤형 커리큘럼을 설계해 드립니다</p>
</div><hr>
""", unsafe_allow_html=True)

# ── 메시지 렌더링 ────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🎓" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── 커리큘럼 생성 단계 ───────────────────────────────────────
if st.session_state.step == "generating":
    curriculum_msg = build_curriculum_message(st.session_state.info)
    st.session_state.llm_messages.append({"role": "user", "content": curriculum_msg})

    with st.chat_message("assistant", avatar="🎓"):
        stream = stream_llm(st.session_state.llm_messages)
        response = st.write_stream(
            chunk.choices[0].delta.content or ""
            for chunk in stream
            if chunk.choices[0].delta.content
        )

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.llm_messages.append({"role": "assistant", "content": response})
    st.session_state.step = "chat"

# ── 후속 채팅 단계 ───────────────────────────────────────────
if st.session_state.step == "chat":
    st.markdown(
        '<div style="color:#999;font-size:0.82rem;text-align:center;padding:0.5rem 0;">'
        '수정·보완 요청이나 추가 질문을 입력하세요</div>',
        unsafe_allow_html=True,
    )
    if prompt := st.chat_input("메시지를 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.llm_messages.append({"role": "user", "content": prompt})

        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🎓"):
            stream = stream_llm(st.session_state.llm_messages)
            response = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream
                if chunk.choices[0].delta.content
            )

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.llm_messages.append({"role": "assistant", "content": response})
        st.rerun()

# ── 정보 수집 단계 (대화형) ──────────────────────────────────
elif st.session_state.step in STEPS:
    step = st.session_state.step

    # 현재 단계에 맞는 플레이스홀더
    placeholders = {
        "company": "회사명을 입력하세요",
        "industry": "업종을 입력하세요 (예: 금융, 제조, 의료)",
        "audience": "번호를 입력하세요 (예: 3)",
        "level": "번호를 입력하세요 (예: 2)",
        "topics": "번호를 입력하세요 (예: 1,3,5 또는 0)",
        "extra": "추가 요청사항 또는 '없음'",
        "duration": "번호를 입력하세요 (예: 2)",
        "format": "번호를 입력하세요 (예: 1)",
    }

    if user_input := st.chat_input(placeholders.get(step, "입력하세요...")):
        # 사용자 입력 저장 및 표시
        st.session_state.messages.append({"role": "user", "content": user_input})

        # 파싱
        value, error = process_user_input(step, user_input)

        if error:
            # 오류 → 재질문
            bot_reply = f"⚠️ {error}\n\n다시 입력해주세요."
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
        else:
            # 값 저장
            st.session_state.info[step] = value

            # 다음 단계로
            next_idx = STEPS.index(step) + 1

            if next_idx < len(STEPS):
                next_step = STEPS[next_idx]
                st.session_state.step = next_step
                bot_reply = _bot_question(next_step)
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            else:
                # 모든 정보 수집 완료
                company = st.session_state.info.get("company", "")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        f"완벽합니다! 🎉 **{company}** 의 맞춤형 커리큘럼을 설계하겠습니다.\n\n"
                        "잠시만 기다려주세요..."
                    ),
                })
                st.session_state.step = "generating"

        st.rerun()
