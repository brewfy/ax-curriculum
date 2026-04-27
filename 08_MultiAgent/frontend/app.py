"""
Streamlit 프론트엔드 — AX MultiAgent
개선 사항:
  - 내부 검증 실패 경고 표시 (코드검증/LLM판단 분리)
  - 평가 이력 가독성 개선
  - 카드형 커리큘럼 뷰 + JSON 뷰 + 다운로드
  - 커리큘럼 이력 목록 사이드바
"""
from __future__ import annotations

import json
import os
import requests
import streamlit as st

# ── 설정 ─────────────────────────────────────────────────────────

def _backend_url() -> str:
    if url := os.getenv("BACKEND_URL"):
        return url
    try:
        return st.secrets["BACKEND_URL"]
    except Exception:
        return "http://localhost:8000"


BACKEND_URL = _backend_url()

st.set_page_config(
    page_title="AX 교육 커리큘럼 멀티에이전트",
    page_icon="🤖",
    layout="wide",
)

LEVEL_OPTIONS = ["초급", "중급", "고급"]
AX_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]

# ── 입력 검증 ─────────────────────────────────────────────────────

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
    {"key": "company", "question": "안녕하세요! AX 교육 커리큘럼 멀티에이전트입니다. 🤖\n\n**[1/14] 회사명**을 입력해주세요.", "validate": _validate_nonempty},
    {"key": "goal", "question": "**[2/14] 교육 목표**를 입력해주세요.\n> 예: ChatGPT 등 AI 도구를 실무에 활용할 수 있는 역량 강화", "validate": _validate_nonempty},
    {"key": "audience", "question": "**[3/14] 교육 대상**을 입력해주세요.\n> 예: 전 직원 (비개발자 포함)", "validate": _validate_nonempty},
    {"key": "level", "question": "**[4/14] 교육 수준**을 선택해주세요.\n`초급` / `중급` / `고급`", "validate": _validate_level},
    {"key": "topics", "question": "**[5/14] 교육 주제**를 쉼표로 구분하여 입력해주세요.\n> 예: ChatGPT 활용, 프롬프트 작성, 업무 자동화", "validate": _validate_topics},
    {"key": "_days", "question": "**[6/14] 교육 일수**를 입력해주세요.\n> 숫자만 입력 (예: `3`)", "validate": _validate_days},
    {"key": "_hours_per_day", "question": "**[7/14] 하루 교육 시간**을 입력해주세요.\n> 숫자만 입력 (예: `6`)", "validate": _validate_hours_per_day},
    {"key": "_tc_균형형", "question": "**[8/14] AX Compass 유형별 인원수**\n\n**균형형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "_tc_이해형", "question": "**[9/14] 이해형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "_tc_과신형", "question": "**[10/14] 과신형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "_tc_실행형", "question": "**[11/14] 실행형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "_tc_판단형", "question": "**[12/14] 판단형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "_tc_조심형", "question": "**[13/14] 조심형** 인원수는 몇 명인가요?\n> 숫자만 입력 (없으면 `0`)", "validate": _validate_count},
    {"key": "extra", "question": "**[14/14] 추가 요구사항**이 있으면 입력해주세요.\n없으면 `없음`을 입력하세요.", "validate": _validate_extra},
]


# ── 세션 상태 초기화 ─────────────────────────────────────────────

for key, default in {
    "token": None,
    "username": None,
    "messages": [],
    "agent_messages": [],
    "curriculum": None,
    "validation_result": None,
    "validation_warnings": [],
    "agent_steps": [],
    "curriculum_id": None,
    "collect_step": 0,
    "education_info": {},
    "show_json": False,
    "live_steps": [],       # 스트리밍 중 실시간 단계 누적
    "is_running": False,    # 에이전트 실행 중 여부
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── API 헬퍼 ─────────────────────────────────────────────────────

def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def login(username: str, password: str) -> bool:
    try:
        resp = requests.post(f"{BACKEND_URL}/auth/login", json={"username": username, "password": password}, timeout=10)
        if resp.status_code == 200:
            st.session_state.token = resp.json()["access_token"]
            st.session_state.username = username
            return True
        st.error(resp.json().get("detail", "로그인 실패"))
    except Exception as e:
        st.error(f"서버 연결 오류: {e}")
    return False


def fetch_curricula() -> list[dict]:
    try:
        resp = requests.get(f"{BACKEND_URL}/curricula", headers=_auth_headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


# ── 렌더링 헬퍼 ──────────────────────────────────────────────────

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


def _render_validation(vr: dict):
    """검증 결과 — 코드검증/LLM판단 분리 표시."""
    passed = vr.get("passed", False)
    score = vr.get("score", 0.0)
    all_issues = vr.get("all_issues", [])

    # 전체 상태 배너
    if passed:
        st.success(f"✅ 검증 통과 — 점수 {score:.0%}")
    else:
        st.error(f"❌ 검증 미통과 — 점수 {score:.0%}")

    # 코드 검증 항목
    code = vr.get("code_checks", {})
    with st.expander("🔧 코드 검증 항목 (규칙 기반)", expanded=not passed):
        col1, col2 = st.columns(2)
        with col1:
            st.write("시간 명시:", "✅" if code.get("hours_ok") else "❌")
            st.write("그룹 A·B·C:", "✅" if code.get("groups_ok") else "❌")
        with col2:
            st.write("세션/모듈:", "✅" if code.get("modules_ok") else "❌")
            st.write("핵심 주제:", "✅" if code.get("topics_ok") else "❌")
        if code.get("missing_topics"):
            st.caption(f"누락 주제: {', '.join(code['missing_topics'])}")
        if code.get("groups_found") and code.get("groups_found") != ["A", "B", "C"]:
            st.caption(f"발견된 그룹: {code['groups_found']}")

    # LLM 판단 항목
    llm = vr.get("llm_checks", {})
    with st.expander("🤖 LLM 판단 항목 (정성 평가)", expanded=not passed):
        col1, col2 = st.columns(2)
        with col1:
            st.write("그룹 실습 차별화:", "✅" if llm.get("group_customization") else "❌")
            st.write("이론/실습 균형:", "✅" if llm.get("time_balance") else "❌")
        with col2:
            st.write("목표 정합성:", "✅" if llm.get("goal_alignment") else "❌")
        if llm.get("feedback"):
            st.info(f"💬 {llm['feedback']}")

    # 미충족 항목 요약
    if all_issues:
        st.warning("**미충족 항목:**\n" + "\n".join(f"- {i}" for i in all_issues))


def _render_curriculum_card(curriculum: str, edu_info: dict, curriculum_id: str | None):
    """카드형 커리큘럼 뷰 + JSON 뷰 탭 + 다운로드."""
    company = edu_info.get("company", "ax")
    tab_md, tab_json = st.tabs(["📄 커리큘럼", "📋 JSON 뷰"])

    with tab_md:
        st.markdown(curriculum)

    with tab_json:
        # 커리큘럼을 섹션별로 파싱해 JSON으로 표시
        sections: dict[str, str] = {}
        current_section = "intro"
        buffer_lines: list[str] = []
        for line in curriculum.split("\n"):
            if line.startswith("## "):
                if buffer_lines:
                    sections[current_section] = "\n".join(buffer_lines).strip()
                current_section = line[3:].strip()
                buffer_lines = []
            else:
                buffer_lines.append(line)
        if buffer_lines:
            sections[current_section] = "\n".join(buffer_lines).strip()
        st.json(sections)

    col_dl, col_id = st.columns([3, 1])
    with col_dl:
        st.download_button(
            "📥 마크다운 다운로드",
            data=curriculum,
            file_name=f"curriculum_{company}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_id:
        if curriculum_id:
            st.caption(f"ID: `{curriculum_id}`")


AGENT_PIPELINE = [
    {"key": "rag_agent",       "label": "RAG 에이전트",      "icon": "🔍", "desc": "AX Compass 유형별 특성 검색"},
    {"key": "web_agent",       "label": "웹 검색 에이전트",   "icon": "🌐", "desc": "최신 AI 교육 트렌드 수집"},
    {"key": "generator_agent", "label": "커리큘럼 생성 에이전트", "icon": "✏️", "desc": "맞춤형 커리큘럼 초안 생성"},
    {"key": "validator_agent", "label": "검증 에이전트",      "icon": "✅", "desc": "코드 검증 + LLM 품질 판단"},
]

# 이벤트 → 파이프라인 키 매핑
_TOOL_KEY_MAP = {
    "rag_agent": "rag_agent",
    "web_agent": "web_agent",
    "generator_agent": "generator_agent",
    "validator_agent": "validator_agent",
}


def _render_pipeline(live_steps: list[dict], is_running: bool):
    """에이전트 파이프라인 — 처음부터 끝까지 전체 단계 + 실시간 상태 표시."""
    # 완료된 에이전트 키 목록
    done_tools: set[str] = {s["tool"] for s in live_steps if s["type"] == "tool_done"}
    warn_tools: set[str] = {s["tool"] for s in live_steps if s["type"] == "tool_warn"}
    active_tool: str | None = next(
        (s["tool"] for s in reversed(live_steps) if s["type"] == "active"), None
    )

    for agent in AGENT_PIPELINE:
        key = agent["key"]
        icon = agent["icon"]
        label = agent["label"]
        desc = agent["desc"]

        if key in done_tools:
            # 완료 — 실제 완료 메시지 표시
            msg = next((s["msg"] for s in live_steps if s["type"] == "tool_done" and s["tool"] == key), desc)
            st.markdown(f"**{icon} {label}** ✅")
            st.caption(f"　{msg}")
        elif key in warn_tools:
            msg = next((s["msg"] for s in live_steps if s["type"] == "tool_warn" and s["tool"] == key), desc)
            st.markdown(f"**{icon} {label}** ⚠️")
            st.caption(f"　{msg}")
        elif key == active_tool and is_running:
            # 현재 실행 중
            msg = next((s["msg"] for s in reversed(live_steps) if s["type"] == "active" and s["tool"] == key), desc)
            st.markdown(f"**{icon} {label}** ⏳")
            st.caption(f"　{msg}")
        else:
            # 대기 중
            color = "gray"
            st.markdown(f":{color}[**{icon} {label}**]")
            st.caption(f"　{desc}")

    # 세부 진행 로그 (progress 메시지)
    progress_msgs = [s["msg"] for s in live_steps if s["type"] == "progress"]
    if progress_msgs:
        with st.expander("📋 상세 진행 로그", expanded=False):
            for msg in progress_msgs:
                st.caption(f"• {msg}")


def _render_agent_steps(steps: list[str]):
    """완료 후 에이전트 실행 단계 요약."""
    for i, step in enumerate(steps, 1):
        if "✅" in step or "완료" in step:
            st.markdown(f"`{i}` {step}")
        elif "⚠️" in step or "실패" in step or "❌" in step:
            st.markdown(f"`{i}` :orange[{step}]")
        else:
            st.markdown(f"`{i}` {step}")


# ── 로그인 화면 ─────────────────────────────────────────────────

if not st.session_state.token:
    st.title("🔐 AX 멀티에이전트 로그인")
    with st.form("login_form"):
        user = st.text_input("사용자명", value="admin")
        pwd = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if login(user, pwd):
                st.rerun()
    st.stop()


# ── 로그인 후 초기 메시지 ────────────────────────────────────────

if not st.session_state.messages and st.session_state.collect_step == 0:
    st.session_state.messages.append({
        "role": "assistant",
        "content": COLLECT_STEPS[0]["question"],
    })


# ── 메인 레이아웃 ────────────────────────────────────────────────

st.title("🤖 AX 교육 커리큘럼 멀티에이전트")
st.caption(f"로그인: {st.session_state.username} | 백엔드: {BACKEND_URL}")

col_main, col_side = st.columns([2, 1])


# ── 사이드바 ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("📋 교육 정보")
    info = st.session_state.education_info
    cur_step = st.session_state.collect_step

    if cur_step is not None:
        st.progress(cur_step / len(COLLECT_STEPS), text=f"{cur_step}/{len(COLLECT_STEPS)} 완료")

    if info:
        st.markdown(_info_summary_md(info))
    else:
        st.caption("대화를 통해 정보를 입력 중입니다...")

    # 검증 실패 경고 배너
    if st.session_state.validation_warnings:
        st.markdown("---")
        st.warning("**⚠️ 검증 경고**")
        for w in st.session_state.validation_warnings[:3]:
            st.caption(f"• {w}")

    st.markdown("---")

    # 커리큘럼 이력
    if st.button("📚 이력 새로고침", use_container_width=True):
        records = fetch_curricula()
        if records:
            st.markdown("**저장된 커리큘럼:**")
            for r in records[:5]:
                status = "✅" if r.get("passed") else "⚠️"
                score = r.get("score", 0.0)
                company = r.get("company", "?")
                cid = r.get("id", "?")
                created = r.get("created_at", "?")[:13].replace("_", " ")
                st.markdown(f"{status} `{company}` — {score:.0%} ({created})")
        else:
            st.caption("저장된 커리큘럼 없음")

    st.markdown("---")
    if st.button("🔄 처음부터 다시", use_container_width=True):
        for k in ["messages", "agent_messages", "curriculum", "validation_result",
                  "validation_warnings", "agent_steps", "curriculum_id"]:
            st.session_state[k] = [] if isinstance(st.session_state[k], list) else None
        st.session_state.collect_step = 0
        st.session_state.education_info = {}
        st.rerun()

    if st.button("🚪 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── 메인: 채팅 ──────────────────────────────────────────────────

with col_main:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("메시지를 입력하세요...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        step = st.session_state.collect_step

        # ── 정보 수집 단계 ────────────────────────────────────────
        if step is not None:
            current = COLLECT_STEPS[step]
            ok, value, err = current["validate"](user_input)

            if not ok:
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {err}"})
            else:
                st.session_state.education_info[current["key"]] = value
                if current["key"] == "_hours_per_day":
                    days = st.session_state.education_info.get("_days", 1)
                    st.session_state.education_info["duration"] = f"{days}일 {value}시간씩"
                elif current["key"] == "_tc_조심형":
                    type_counts = {t: st.session_state.education_info.get(f"_tc_{t}", 0) for t in AX_TYPES}
                    st.session_state.education_info["type_counts"] = type_counts
                next_step = step + 1
                if next_step < len(COLLECT_STEPS):
                    st.session_state.collect_step = next_step
                    st.session_state.messages.append({"role": "assistant", "content": COLLECT_STEPS[next_step]["question"]})
                else:
                    st.session_state.collect_step = None
                    summary = _info_summary_md(st.session_state.education_info)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": (
                            "✅ 모든 정보 입력 완료!\n\n"
                            f"{summary}\n\n---\n"
                            "커리큘럼 설계를 시작하려면 요청을 입력해주세요.\n"
                            "> 예: `커리큘럼을 설계해줘`"
                        ),
                    })
            st.rerun()

        # ── 커리큘럼 대화 단계 ────────────────────────────────────
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
                reply_ph = st.empty()

            # 스트리밍 중 실시간 파이프라인을 col_side에 표시
            with col_side:
                pipeline_ph = st.empty()

            def _render_pipeline_snapshot(live_steps: list[dict], is_running: bool):
                done_tools: set[str] = {s["tool"] for s in live_steps if s["type"] == "tool_done"}
                warn_tools: set[str] = {s["tool"] for s in live_steps if s["type"] == "tool_warn"}
                active_tool: str | None = next(
                    (s["tool"] for s in reversed(live_steps) if s["type"] == "active"), None
                )
                lines: list[str] = []
                for agent in AGENT_PIPELINE:
                    key = agent["key"]
                    icon = agent["icon"]
                    label = agent["label"]
                    desc = agent["desc"]
                    if key in done_tools:
                        msg = next((s["msg"] for s in live_steps if s["type"] == "tool_done" and s["tool"] == key), desc)
                        lines.append(f"**{icon} {label}** ✅  \n　*{msg}*")
                    elif key in warn_tools:
                        msg = next((s["msg"] for s in live_steps if s["type"] == "tool_warn" and s["tool"] == key), desc)
                        lines.append(f"**{icon} {label}** ⚠️  \n　*{msg}*")
                    elif key == active_tool and is_running:
                        msg = next((s["msg"] for s in reversed(live_steps) if s["type"] == "active" and s["tool"] == key), desc)
                        lines.append(f"**{icon} {label}** ⏳  \n　*{msg}*")
                    else:
                        lines.append(f":gray[{icon} {label}]  \n　*{desc}*")
                # 최근 progress 메시지 1줄
                progress_msgs = [s["msg"] for s in live_steps if s["type"] == "progress"]
                if progress_msgs and is_running:
                    lines.append(f"\n> ⏳ {progress_msgs[-1]}")
                return "\n\n".join(lines)

            live_steps: list[dict] = []
            result_data: dict = {}

            def _push(entry: dict):
                live_steps.append(entry)

            def _infer_tool(step_text: str) -> str | None:
                if "RAG" in step_text:
                    return "rag_agent"
                if "웹 검색" in step_text or "웹" in step_text:
                    return "web_agent"
                if "생성" in step_text or "커리큘럼 생성" in step_text:
                    return "generator_agent"
                if "검증" in step_text:
                    return "validator_agent"
                return None

            try:
                with requests.post(
                    f"{BACKEND_URL}/chat/stream",
                    json=payload,
                    headers=_auth_headers(),
                    stream=True,
                    timeout=300,
                ) as resp:
                    if resp.status_code == 401:
                        st.error("인증 만료. 다시 로그인해주세요.")
                        st.session_state.token = None
                        st.rerun()
                    elif resp.status_code != 200:
                        st.error(f"오류: {resp.status_code} — {resp.text[:200]}")
                    else:
                        # 초기 파이프라인 (전체 대기 상태)
                        pipeline_ph.markdown(
                            "**🤖 에이전트 파이프라인**\n\n" +
                            _render_pipeline_snapshot(live_steps, True)
                        )
                        for raw in resp.iter_lines():
                            if not raw:
                                continue
                            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                            if not line.startswith("data: "):
                                continue
                            event = json.loads(line[6:])
                            etype = event.get("type")

                            if etype == "progress":
                                step_text = event["step"]
                                tool = _infer_tool(step_text)
                                _push({"type": "progress", "msg": step_text, "tool": tool})
                                if tool:
                                    _push({"type": "active", "tool": tool, "msg": step_text})
                                pipeline_ph.markdown(
                                    "**⏳ 에이전트 실행 중...**\n\n" +
                                    _render_pipeline_snapshot(live_steps, True)
                                )

                            elif etype == "tool_done":
                                tool = _TOOL_KEY_MAP.get(event.get("tool", ""))
                                label = event.get("label", "")
                                if tool:
                                    if "⚠️" in label or "실패" in label:
                                        _push({"type": "tool_warn", "tool": tool, "msg": label})
                                    else:
                                        _push({"type": "tool_done", "tool": tool, "msg": label})
                                pipeline_ph.markdown(
                                    "**⏳ 에이전트 실행 중...**\n\n" +
                                    _render_pipeline_snapshot(live_steps, True)
                                )

                            elif etype == "tool_warn":
                                tool = _TOOL_KEY_MAP.get(event.get("tool", ""))
                                label = event.get("label", "")
                                if tool:
                                    _push({"type": "tool_warn", "tool": tool, "msg": label})
                                pipeline_ph.markdown(
                                    "**⏳ 에이전트 실행 중...**\n\n" +
                                    _render_pipeline_snapshot(live_steps, True)
                                )

                            elif etype == "error":
                                st.error(f"에이전트 오류: {event['message']}")

                            elif etype == "result":
                                result_data = event

                            elif etype == "saved":
                                st.session_state.curriculum_id = event.get("curriculum_id")

                # 완료 — placeholder 제거 (expander가 col_side에서 최종 상태 표시)
                pipeline_ph.empty()
                st.session_state.live_steps = live_steps
                st.session_state.is_running = False

                if result_data:
                    reply = result_data.get("reply", "")
                    reply_ph.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.session_state.agent_messages.append({"role": "assistant", "content": reply})
                    st.session_state.curriculum        = result_data.get("curriculum")
                    st.session_state.validation_result = result_data.get("validation_result")
                    st.session_state.validation_warnings = result_data.get("validation_warnings", [])
                    st.session_state.agent_steps       = result_data.get("agent_steps", [])

                    vr = st.session_state.validation_result
                    if vr and not vr.get("passed"):
                        issues = vr.get("all_issues", [])
                        if issues:
                            with col_main:
                                st.warning(
                                    "**⚠️ 내부 검증 미통과** — 우측에서 상세 내용 확인\n"
                                    + "\n".join(f"- {i}" for i in issues[:3])
                                )

                    if result_data.get("complete"):
                        with col_main:
                            st.success("✅ 커리큘럼 생성 및 검증 완료")

            except Exception as e:
                st.session_state.is_running = False
                pipeline_ph.empty()
                st.error(f"요청 오류: {e}")


# ── 사이드: 에이전트 파이프라인 + 결과 패널 ─────────────────────

with col_side:
    # ① 에이전트 파이프라인 — 항상 표시 (실행 전/중/후 모두)
    is_running = st.session_state.is_running
    live_steps = st.session_state.live_steps
    agent_steps = st.session_state.agent_steps

    pipeline_title = "⏳ 에이전트 실행 중..." if is_running else "🤖 에이전트 파이프라인"
    with st.expander(pipeline_title, expanded=True):
        if live_steps or agent_steps:
            _render_pipeline(live_steps, is_running)
        else:
            # 실행 전 — 전체 파이프라인 대기 상태 미리 표시
            for agent in AGENT_PIPELINE:
                st.markdown(f":gray[**{agent['icon']} {agent['label']}**]")
                st.caption(f"　{agent['desc']}")

    st.markdown("---")

    # ② 검증 결과 (코드/LLM 분리)
    if st.session_state.validation_result:
        with st.expander("📊 검증 결과 상세", expanded=True):
            _render_validation(st.session_state.validation_result)

    # ③ 커리큘럼 (카드형 + 탭)
    if st.session_state.curriculum:
        with st.expander("📚 생성된 커리큘럼", expanded=True):
            _render_curriculum_card(
                st.session_state.curriculum,
                st.session_state.education_info,
                st.session_state.curriculum_id,
            )
