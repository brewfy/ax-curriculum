"""
Streamlit 프론트엔드 — AX SingleAgent (대화형 입력)
"""
import json
import os
import requests
import streamlit as st


def _backend_url() -> str:
    if url := os.getenv("BACKEND_URL"):
        return url
    try:
        return st.secrets["BACKEND_URL"]
    except Exception:
        return "http://localhost:8000"


BACKEND_URL = _backend_url()

st.set_page_config(
    page_title="AX 교육 커리큘럼 AI 에이전트",
    page_icon="🤖",
    layout="wide",
)

LEVEL_OPTIONS = ["초급", "중급", "고급"]
AX_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]


# ── 검증 함수 ──────────────────────────────────────────────────
def _validate_nonempty(v: str):
    s = v.strip()
    return bool(s), s or None, None if s else "입력값이 비어 있습니다. 다시 입력해주세요."


def _validate_level(v: str):
    s = v.strip()
    ok = s in LEVEL_OPTIONS
    return ok, s if ok else None, None if ok else "`초급`, `중급`, `고급` 중 하나를 정확히 입력해주세요."


def _validate_topics(v: str):
    ts = [t.strip() for t in v.split(",") if t.strip()]
    return bool(ts), ts, None


def _validate_days(v: str):
    s = v.strip()
    if s.isdigit() and int(s) >= 1:
        return True, int(s), None
    return False, None, "1 이상의 숫자를 입력해주세요. (예: `2`)"


def _validate_hours_per_day(v: str):
    s = v.strip()
    if s.isdigit() and 1 <= int(s) <= 24:
        return True, int(s), None
    return False, None, "1~24 사이의 숫자를 입력해주세요. (예: `6`)"


def _validate_count(v: str):
    s = v.strip()
    if s.isdigit():
        return True, int(s), None
    return False, None, "0 이상의 숫자를 입력해주세요. (예: `5`)"


def _validate_extra(v: str):
    s = v.strip()
    return True, ("" if s in ("없음", "-", "") else s), None


COLLECT_STEPS = [
    {
        "key": "company",
        "question": (
            "안녕하세요! AX 교육 커리큘럼 설계 에이전트입니다. 🤖\n\n"
            "맞춤형 커리큘럼 설계를 위해 몇 가지 정보를 입력해주세요.\n\n"
            "**[1/14] 회사명**을 입력해주세요."
        ),
        "validate": _validate_nonempty,
    },
    {
        "key": "goal",
        "question": (
            "**[2/14] 교육 목표**를 입력해주세요.\n"
            "> 예: ChatGPT 등 AI 도구를 실무에 활용할 수 있는 역량 강화"
        ),
        "validate": _validate_nonempty,
    },
    {
        "key": "audience",
        "question": (
            "**[3/14] 교육 대상**을 입력해주세요.\n"
            "> 예: 전 직원 (비개발자 포함)"
        ),
        "validate": _validate_nonempty,
    },
    {
        "key": "level",
        "question": "**[4/14] 교육 수준**을 선택해주세요.\n`초급` / `중급` / `고급`",
        "validate": _validate_level,
    },
    {
        "key": "topics",
        "question": (
            "**[5/14] 교육 주제**를 쉼표로 구분하여 입력해주세요.\n"
            "> 예: ChatGPT 활용, 프롬프트 작성, 업무 자동화"
        ),
        "validate": _validate_topics,
    },
    {
        "key": "_days",
        "question": (
            "**[6/14] 교육 일수**를 입력해주세요.\n"
            "> 숫자만 입력  (예: `3`)"
        ),
        "validate": _validate_days,
    },
    {
        "key": "_hours_per_day",
        "question": (
            "**[7/14] 하루 사용 가능한 교육 시간**을 입력해주세요.\n"
            "> 숫자만 입력  (예: `6`)"
        ),
        "validate": _validate_hours_per_day,
    },
    {
        "key": "_tc_균형형",
        "question": (
            "**[8/14] AX Compass 유형별 인원수**를 순서대로 입력해주세요.\n\n"
            "**균형형** 인원수는 몇 명인가요?\n"
            "> 숫자만 입력 (없으면 `0`)"
        ),
        "validate": _validate_count,
    },
    {
        "key": "_tc_이해형",
        "question": "**[9/14] 이해형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)",
        "validate": _validate_count,
    },
    {
        "key": "_tc_과신형",
        "question": "**[10/14] 과신형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)",
        "validate": _validate_count,
    },
    {
        "key": "_tc_실행형",
        "question": "**[11/14] 실행형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)",
        "validate": _validate_count,
    },
    {
        "key": "_tc_판단형",
        "question": "**[12/14] 판단형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)",
        "validate": _validate_count,
    },
    {
        "key": "_tc_조심형",
        "question": "**[13/14] 조심형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)",
        "validate": _validate_count,
    },
    {
        "key": "extra",
        "question": (
            "**[14/14] 추가 요구사항**이 있으면 입력해주세요.\n"
            "없으면 `없음`을 입력하세요."
        ),
        "validate": _validate_extra,
    },
]


# ── 세션 상태 초기화 ────────────────────────────────────────────
for key, default in {
    "token": None,
    "username": None,
    "messages": [],          # 전체 채팅 이력 (UI 표시용)
    "agent_messages": [],    # 커리큘럼 대화만 (백엔드 전송용)
    "curriculum": None,
    "validation_result": None,
    "agent_steps": [],
    "collect_step": 0,       # 수집 중: 0~13, 완료: None
    "education_info": {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── 헬퍼 ───────────────────────────────────────────────────────
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


def _info_summary_md(info: dict) -> str:
    tc = info.get("type_counts", {})
    type_line = " / ".join(f"{t} {tc.get(t, 0)}명" for t in AX_TYPES)
    topics = ", ".join(info.get("topics", []))
    return (
        f"- **회사**: {info.get('company', '')}\n"
        f"- **목표**: {info.get('goal', '')}\n"
        f"- **대상**: {info.get('audience', '')}\n"
        f"- **수준**: {info.get('level', '')}\n"
        f"- **주제**: {topics}\n"
        f"- **기간**: {info.get('duration', '')}\n"
        f"- **유형**: {type_line}\n"
        f"- **추가**: {info.get('extra', '') or '없음'}"
    )


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


# ── 로그인 후 첫 질문 자동 표시 ─────────────────────────────────
if not st.session_state.messages and st.session_state.collect_step == 0:
    st.session_state.messages.append({
        "role": "assistant",
        "content": COLLECT_STEPS[0]["question"],
    })


# ── 메인 레이아웃 ──────────────────────────────────────────────
st.title("🤖 AX 교육 커리큘럼 AI 에이전트")
st.caption(f"로그인: {st.session_state.username}")

col_main, col_side = st.columns([2, 1])


# ── 사이드바: 수집 현황 + 컨트롤 ────────────────────────────────
with st.sidebar:
    st.header("📋 수집된 교육 정보")
    info = st.session_state.education_info
    cur_step = st.session_state.collect_step

    if cur_step is not None:
        st.progress(cur_step / len(COLLECT_STEPS), text=f"{cur_step}/{len(COLLECT_STEPS)} 완료")

    if info:
        st.markdown(_info_summary_md(info))
    else:
        st.caption("대화를 통해 정보를 입력 중입니다...")

    st.markdown("---")
    if st.button("🔄 처음부터 다시", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent_messages = []
        st.session_state.curriculum = None
        st.session_state.validation_result = None
        st.session_state.agent_steps = []
        st.session_state.collect_step = 0
        st.session_state.education_info = {}
        st.rerun()

    if st.button("🚪 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── 메인: 채팅 ─────────────────────────────────────────────────
with col_main:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("메시지를 입력하세요...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        step = st.session_state.collect_step

        # ── 정보 수집 단계 ──────────────────────────────────────
        if step is not None:
            current = COLLECT_STEPS[step]
            ok, value, err = current["validate"](user_input)

            if not ok:
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {err}"})
            else:
                st.session_state.education_info[current["key"]] = value
                if current["key"] == "_hours_per_day":
                    days = st.session_state.education_info.get("_days", 1)
                    st.session_state.education_info["duration"] = f"{days}일 ({days * value}시간)"
                elif current["key"] == "_tc_조심형":
                    type_counts = {t: st.session_state.education_info.get(f"_tc_{t}", 0) for t in AX_TYPES}
                    st.session_state.education_info["type_counts"] = type_counts
                next_step = step + 1

                if next_step < len(COLLECT_STEPS):
                    st.session_state.collect_step = next_step
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": COLLECT_STEPS[next_step]["question"],
                    })
                else:
                    st.session_state.collect_step = None
                    summary = _info_summary_md(st.session_state.education_info)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": (
                            "✅ 모든 정보 입력이 완료되었습니다!\n\n"
                            f"{summary}\n\n"
                            "---\n"
                            "커리큘럼 설계를 시작하려면 요청을 입력해주세요.\n"
                            "> 예: `커리큘럼을 설계해줘` / `AX 교육 커리큘럼을 만들어줘`"
                        ),
                    })

            st.rerun()

        # ── 커리큘럼 대화 단계 ──────────────────────────────────
        else:
            edu = st.session_state.education_info
            st.session_state.agent_messages.append({"role": "user", "content": user_input})

            payload = {
                "messages": st.session_state.agent_messages,
                "education_info": {
                    "company":     edu.get("company", ""),
                    "goal":        edu.get("goal", ""),
                    "audience":    edu.get("audience", ""),
                    "level":       edu.get("level", "초급"),
                    "topics":      edu.get("topics", []),
                    "extra":       edu.get("extra", ""),
                    "duration":    edu.get("duration", "1일 (8시간)"),
                    "type_counts": edu.get("type_counts", {t: 0 for t in AX_TYPES}),
                },
            }

            with st.chat_message("assistant"):
                status_placeholder = st.empty()
                reply_placeholder  = st.empty()
                result_data: dict  = {}

                try:
                    with requests.post(
                        f"{BACKEND_URL}/chat/stream",
                        json=payload,
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        stream=True,
                        timeout=180,
                    ) as resp:
                        if resp.status_code == 401:
                            st.error("인증 만료. 다시 로그인해주세요.")
                            st.session_state.token = None
                            st.rerun()
                        elif resp.status_code != 200:
                            st.error(f"오류: {resp.status_code} — {resp.text[:200]}")
                        else:
                            for raw in resp.iter_lines():
                                if not raw:
                                    continue
                                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                                if not line.startswith("data: "):
                                    continue
                                event = json.loads(line[6:])
                                if event["type"] == "progress":
                                    status_placeholder.info(f"⏳ {event['step']}")
                                elif event["type"] == "tool_done":
                                    status_placeholder.success(event["label"])
                                elif event["type"] == "error":
                                    st.error(f"에이전트 오류: {event['message']}")
                                elif event["type"] == "result":
                                    result_data = event
                                    status_placeholder.empty()

                    if result_data:
                        reply = result_data.get("reply", "")
                        reply_placeholder.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        st.session_state.agent_messages.append({"role": "assistant", "content": reply})
                        st.session_state.curriculum        = result_data.get("curriculum")
                        st.session_state.validation_result = result_data.get("validation_result")
                        st.session_state.agent_steps       = result_data.get("agent_steps", [])
                        if result_data.get("complete"):
                            st.success("✅ 커리큘럼 생성 및 검증 완료")

                except Exception as e:
                    st.error(f"요청 오류: {e}")


# ── 사이드: 결과 패널 ──────────────────────────────────────────
with col_side:
    if st.session_state.agent_steps:
        with st.expander("🔍 에이전트 실행 단계", expanded=False):
            for i, s in enumerate(st.session_state.agent_steps, 1):
                st.write(f"{i}. {s}")

    if st.session_state.validation_result:
        vr = st.session_state.validation_result
        with st.expander("✅ 검증 결과", expanded=True):
            passed = vr.get("passed", False)
            score  = vr.get("score", 0.0)
            st.metric("점수", f"{score:.0%}", delta="통과" if passed else "미통과")
            if vr.get("issues"):
                st.warning("미충족 항목:")
                for issue in vr["issues"]:
                    st.write(f"- {issue}")
            else:
                st.success("모든 요구사항 충족")

    if st.session_state.curriculum:
        edu = st.session_state.education_info
        with st.expander("📚 생성된 커리큘럼", expanded=True):
            st.markdown(st.session_state.curriculum)
            st.download_button(
                "📥 커리큘럼 다운로드",
                data=st.session_state.curriculum,
                file_name=f"curriculum_{edu.get('company', 'ax')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
