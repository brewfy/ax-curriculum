"""
Streamlit 프론트엔드 — AX SingleAgent
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", st.secrets.get("BACKEND_URL", "http://localhost:8000"))

st.set_page_config(
    page_title="AX 교육 커리큘럼 AI 에이전트",
    page_icon="🤖",
    layout="wide",
)

# ── 세션 상태 초기화 ────────────────────────────────────────────
for key, default in {
    "token": None,
    "username": None,
    "messages": [],
    "curriculum": None,
    "validation_result": None,
    "agent_steps": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── 헬퍼 ───────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    return getattr(requests, method)(
        f"{BACKEND_URL}{path}", headers=headers, timeout=120, **kwargs
    )


def login(username: str, password: str) -> bool:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if resp.status_code == 200:
            st.session_state.token = resp.json()["access_token"]
            st.session_state.username = username
            return True
        st.error(resp.json().get("detail", "로그인 실패"))
    except Exception as e:
        st.error(f"서버 연결 오류: {e}")
    return False


# ── 로그인 화면 ─────────────────────────────────────────────────
if not st.session_state.token:
    st.title("🔐 AX 에이전트 로그인")
    with st.form("login_form"):
        user = st.text_input("사용자명", value="admin")
        pwd = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if login(user, pwd):
                st.rerun()
    st.stop()


# ── 메인 UI ────────────────────────────────────────────────────
st.title("🤖 AX 교육 커리큘럼 AI 에이전트")
st.caption(f"로그인: {st.session_state.username}")

col_main, col_side = st.columns([2, 1])

# ── 사이드바: 교육 정보 입력 ────────────────────────────────────
with st.sidebar:
    st.header("📋 교육 정보 입력")
    company = st.text_input("회사명", placeholder="예: 스타트업A")
    goal = st.text_area(
        "교육 목표",
        placeholder="예: ChatGPT 등 AI 도구를 실무에 활용할 수 있는 역량 강화",
        height=80,
    )
    audience = st.text_input("교육 대상", placeholder="예: 전 직원 (비개발자 포함)")
    level = st.selectbox("교육 수준", ["초급", "중급", "고급"])
    topics_raw = st.text_input(
        "교육 주제 (쉼표 구분)",
        placeholder="예: ChatGPT 활용, 프롬프트 작성, 업무 자동화",
    )
    extra = st.text_input("추가 요구사항", placeholder="예: 의사결정 프레임워크 포함")
    duration = st.selectbox(
        "교육 기간",
        ["1일 (8시간)", "2일 (16시간)", "3일 (24시간)", "4일 (32시간)"],
    )

    st.subheader("👥 AX Compass 유형별 인원")
    types = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
    type_counts = {t: st.number_input(t, min_value=0, max_value=100, value=5, key=f"tc_{t}") for t in types}

    st.markdown("---")
    if st.button("🔄 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.curriculum = None
        st.session_state.validation_result = None
        st.session_state.agent_steps = []
        st.rerun()

    if st.button("🚪 로그아웃", use_container_width=True):
        for k in ["token", "username", "messages", "curriculum", "validation_result", "agent_steps"]:
            st.session_state[k] = None if k in ("token", "username") else ([] if k in ("messages", "agent_steps") else None)
        st.rerun()


# ── 메인: 채팅 ─────────────────────────────────────────────────
with col_main:
    # 채팅 이력 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 입력
    user_input = st.chat_input("커리큘럼 요청 또는 추가 질문을 입력하세요...")

    if user_input:
        if not company or not goal:
            st.warning("사이드바에서 회사명과 교육 목표를 입력해주세요.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        topics = [t.strip() for t in topics_raw.split(",") if t.strip()] if topics_raw else []

        payload = {
            "messages": st.session_state.messages,
            "education_info": {
                "company": company,
                "goal": goal,
                "audience": audience,
                "level": level,
                "topics": topics,
                "extra": extra,
                "duration": duration,
                "type_counts": type_counts,
            },
        }

        with st.chat_message("assistant"):
            with st.spinner("에이전트 실행 중..."):
                try:
                    resp = api("post", "/chat", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data["reply"]
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        st.session_state.curriculum = data.get("curriculum")
                        st.session_state.validation_result = data.get("validation_result")
                        st.session_state.agent_steps = data.get("agent_steps", [])

                        if data.get("complete"):
                            st.success("✅ 커리큘럼 생성 및 검증 완료")
                    elif resp.status_code == 401:
                        st.error("인증 만료. 다시 로그인해주세요.")
                        st.session_state.token = None
                        st.rerun()
                    else:
                        st.error(f"오류: {resp.status_code} — {resp.text[:200]}")
                except Exception as e:
                    st.error(f"요청 오류: {e}")


# ── 사이드: 결과 패널 ──────────────────────────────────────────
with col_side:
    if st.session_state.agent_steps:
        with st.expander("🔍 에이전트 실행 단계", expanded=False):
            for i, step in enumerate(st.session_state.agent_steps, 1):
                st.write(f"{i}. {step}")

    if st.session_state.validation_result:
        vr = st.session_state.validation_result
        with st.expander("✅ 검증 결과", expanded=True):
            passed = vr.get("passed", False)
            score = vr.get("score", 0.0)
            st.metric("점수", f"{score:.0%}", delta="통과" if passed else "미통과")
            if vr.get("issues"):
                st.warning("미충족 항목:")
                for issue in vr["issues"]:
                    st.write(f"- {issue}")
            else:
                st.success("모든 요구사항 충족")

    if st.session_state.curriculum:
        with st.expander("📚 생성된 커리큘럼", expanded=True):
            st.markdown(st.session_state.curriculum)
            st.download_button(
                "📥 커리큘럼 다운로드",
                data=st.session_state.curriculum,
                file_name=f"curriculum_{company or 'ax'}.md",
                mime="text/markdown",
                use_container_width=True,
            )
