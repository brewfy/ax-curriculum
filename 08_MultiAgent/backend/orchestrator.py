"""
멀티에이전트 오케스트레이터.

실행 흐름:
  RagAgent → WebAgent → (GeneratorAgent → ValidatorAgent) × MAX_RETRIES
  검증 실패 시 code_checks + llm_checks 피드백을 구성해 재생성.
  모든 상태를 명시적으로 추적하고 SSE 이벤트로 스트리밍.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from .agents import GeneratorAgent, RagAgent, ValidatorAgent, WebAgent
from .schemas import ValidationResult

MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent / "prompts")))


def _load_orchestrator_prompt() -> str:
    path = PROMPTS_DIR / "orchestrator_system.txt"
    return path.read_text(encoding="utf-8") if path.exists() else "AX 교육 커리큘럼 멀티에이전트 오케스트레이터입니다."


# ── 결과 컨테이너 ─────────────────────────────────────────────────

@dataclass
class OrchestratorState:
    """오케스트레이터 내부 상태 — 명시적 추적."""
    rag_context: str = ""
    rag_success: bool = False
    web_context: str = ""
    web_success: bool = False
    curriculum: str | None = None
    validation: ValidationResult | None = None
    attempt: int = 0               # 현재 생성 시도 횟수
    complete: bool = False
    steps: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)  # UI 경고용


@dataclass
class OrchestratorResult:
    reply: str
    complete: bool
    curriculum: str | None
    validation_result: dict | None
    agent_steps: list[str]
    curriculum_id: str | None = None


# ── 피드백 구성 ────────────────────────────────────────────────────

def _build_feedback(validation: ValidationResult) -> str:
    lines: list[str] = ["[검증 실패 — 다음 항목을 반드시 수정하세요]"]

    code = validation.code_checks
    if not code.hours_ok:
        lines.append(f"• [구조] 총 교육 시간({code.expected_hours}시간)을 커리큘럼 개요표에 명시하세요.")
    if not code.groups_ok:
        missing = [g for g in ["A", "B", "C"] if g not in code.groups_found]
        lines.append(f"• [구조] 누락된 그룹({', '.join(missing)}그룹)의 실습 섹션을 추가하세요.")
    if not code.modules_ok:
        lines.append("• [구조] '세션 N:' 또는 '모듈 N:' 형식의 세션 헤더를 추가하세요.")
    if not code.topics_ok and code.missing_topics:
        lines.append(f"• [내용] 누락된 주제({', '.join(code.missing_topics[:3])})를 세션 내용에 포함하세요.")

    llm = validation.llm_checks
    if not llm.group_customization:
        lines.append("• [품질] A/B/C그룹 실습을 실질적으로 차별화하세요 — 접근법·과제·방식이 달라야 합니다.")
    if not llm.time_balance:
        lines.append("• [품질] 이론(50~60%) / 실습(40~50%) 시간 비율과 각 세션 시간을 명시하세요.")
    if not llm.goal_alignment:
        lines.append("• [품질] 교육 목표의 핵심 역량을 세션 학습 목표에 명시적으로 연결하세요.")
    if llm.feedback:
        lines.append(f"• [LLM 피드백] {llm.feedback}")

    return "\n".join(lines)


# ── 오케스트레이터 ─────────────────────────────────────────────────

class MultiAgentOrchestrator:
    def __init__(self, llm: OpenAI, education_info: dict, api_key: str):
        self.llm = llm
        self.education_info = education_info
        self.api_key = api_key
        self._orchestrator_prompt = _load_orchestrator_prompt()

        self.rag_agent = RagAgent(llm, api_key)
        self.web_agent = WebAgent(llm)
        self.gen_agent = GeneratorAgent(llm)
        self.val_agent = ValidatorAgent(llm)

    # ── 동기 실행 ─────────────────────────────────────────────────

    def run(self, user_messages: list[dict]) -> OrchestratorResult:
        events = list(self.run_stream(user_messages))
        result_event = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if result_event:
            return OrchestratorResult(
                reply=result_event["reply"],
                complete=result_event["complete"],
                curriculum=result_event.get("curriculum"),
                validation_result=result_event.get("validation_result"),
                agent_steps=result_event.get("agent_steps", []),
            )
        return OrchestratorResult(
            reply="오류: 결과 이벤트 없음",
            complete=False,
            curriculum=None,
            validation_result=None,
            agent_steps=[],
        )

    # ── 스트리밍 실행 ─────────────────────────────────────────────

    def run_stream(
        self, user_messages: list[dict]
    ) -> Generator[dict[str, Any], None, None]:
        state = OrchestratorState()

        yield _progress("🤖 멀티에이전트 오케스트레이터 시작")

        # ── Step 1: RAG 에이전트 ──────────────────────────────────
        yield _progress("🔍 RAG 에이전트 — AX Compass 유형별 특성 검색 중")
        state.rag_context, state.rag_success = self.rag_agent.run(self.education_info)
        if state.rag_success:
            state.steps.append("✅ RAG 에이전트 완료")
            yield _tool_done("rag_agent", "🔍 RAG 에이전트 완료 — 유형별 특성 수집")
        else:
            state.steps.append(f"⚠️ RAG 에이전트 실패: {state.rag_context[:80]}")
            state.validation_warnings.append(f"RAG 검색 실패: {state.rag_context[:80]}")
            yield _tool_warn("rag_agent", "⚠️ RAG 검색 실패 — 기본 컨텍스트로 진행")

        # ── Step 2: 웹 검색 에이전트 ────────────────────────────
        yield _progress("🌐 웹 검색 에이전트 — 최신 AI 교육 트렌드 수집 중")
        state.web_context, state.web_success = self.web_agent.run(self.education_info)
        if state.web_success:
            state.steps.append("✅ 웹 검색 에이전트 완료")
            yield _tool_done("web_agent", "🌐 웹 검색 에이전트 완료 — 트렌드 수집")
        else:
            state.steps.append("⚠️ 웹 검색 에이전트 실패 (Tavily 미설정 또는 오류)")
            state.validation_warnings.append("웹 검색 실패 — Tavily API 키를 확인하세요")
            yield _tool_warn("web_agent", "⚠️ 웹 검색 실패 — Tavily API 키 필요")

        # ── Step 3~5: 생성 → 검증 루프 ───────────────────────────
        feedback = ""
        for attempt in range(1, MAX_RETRIES + 1):
            state.attempt = attempt

            # 생성
            label = f"✏️  커리큘럼 생성 에이전트 — #{attempt}회 시도"
            yield _progress(label)
            curriculum, gen_ok = self.gen_agent.run(
                self.education_info,
                rag_context=state.rag_context,
                web_context=state.web_context,
                feedback=feedback,
                previous_curriculum=state.curriculum or "",
            )
            if not gen_ok:
                state.steps.append(f"❌ 커리큘럼 생성 실패 (#{attempt}): {curriculum[:80]}")
                state.validation_warnings.append(f"생성 실패 #{attempt}: {curriculum[:80]}")
                yield _progress(f"❌ 커리큘럼 생성 실패 — {curriculum[:80]}")
                if attempt == MAX_RETRIES:
                    break
                continue

            state.curriculum = curriculum
            state.steps.append(f"✅ 커리큘럼 생성 완료 (#{attempt})")
            yield _tool_done("generator_agent", f"✏️  커리큘럼 생성 완료 (#{attempt}회)")

            # 검증
            yield _progress("✅ 검증 에이전트 — 코드 검증 + LLM 판단 실행 중")
            validation = self.val_agent.run(curriculum, self.education_info)
            state.validation = validation

            code_ok = validation.code_checks.passed
            llm_ok = validation.llm_checks.passed
            issues_count = len(validation.all_issues)

            if validation.passed:
                state.complete = True
                state.steps.append(f"✅ 검증 통과 (#{attempt}) — 점수: {validation.score:.0%}")
                yield _tool_done(
                    "validator_agent",
                    f"✅ 검증 통과 — 점수 {validation.score:.0%} (코드: {'✓' if code_ok else '✗'} / LLM: {'✓' if llm_ok else '✗'})",
                )
                break
            else:
                # 검증 실패 — 상태 명시적 기록
                code_issues = validation.code_checks.issues()
                llm_issues = validation.llm_checks.issues()
                fail_summary = f"검증 실패 (#{attempt}) — 코드: {len(code_issues)}건, LLM: {len(llm_issues)}건"
                state.steps.append(f"⚠️ {fail_summary}")
                state.validation_warnings.extend(validation.all_issues)
                yield _tool_done(
                    "validator_agent",
                    f"⚠️ {fail_summary} — 재생성 중",
                )

                if attempt < MAX_RETRIES:
                    feedback = _build_feedback(validation)
                    yield _progress(f"🔄 피드백 적용 후 재생성 (#{attempt + 1}회 예정)")

        # ── 최종 결과 ─────────────────────────────────────────────
        reply = self._build_reply(state)
        yield {
            "type": "result",
            "reply": reply,
            "complete": state.complete,
            "curriculum": state.curriculum,
            "validation_result": state.validation.model_dump() if state.validation else None,
            "agent_steps": state.steps,
            "validation_warnings": state.validation_warnings,
        }

    # ── 최종 답변 구성 ────────────────────────────────────────────

    def _build_reply(self, state: OrchestratorState) -> str:
        if state.complete and state.validation:
            vr = state.validation
            code = vr.code_checks
            llm = vr.llm_checks
            return (
                f"✅ **커리큘럼 설계 완료** (점수: {vr.score:.0%}, {state.attempt}회 시도)\n\n"
                f"**검증 결과:**\n"
                f"- 코드 검증: 시간 {'✓' if code.hours_ok else '✗'} / 그룹 {'✓' if code.groups_ok else '✗'} / 세션 {'✓' if code.modules_ok else '✗'} / 주제 {'✓' if code.topics_ok else '✗'}\n"
                f"- LLM 판단: 그룹차별화 {'✓' if llm.group_customization else '✗'} / 시간균형 {'✓' if llm.time_balance else '✗'} / 목표정합 {'✓' if llm.goal_alignment else '✗'}\n\n"
                "우측 패널에서 커리큘럼을 확인하고 다운로드할 수 있습니다."
            )
        elif state.curriculum and state.validation:
            issues = "\n".join(f"- {i}" for i in state.validation.all_issues[:5])
            return (
                f"⚠️ **커리큘럼 생성 완료 (검증 미통과)** — 점수: {state.validation.score:.0%}\n\n"
                f"**미충족 항목:**\n{issues}\n\n"
                f"생성된 커리큘럼을 확인 후 수동으로 수정하거나, 다시 요청해 재생성할 수 있습니다."
            )
        elif state.curriculum:
            return (
                "⚠️ **커리큘럼 생성됨 (검증 실행 안 됨)**\n\n"
                "커리큘럼이 생성되었지만 검증 단계에서 오류가 발생했습니다. "
                "우측에서 커리큘럼을 확인해주세요."
            )
        else:
            return (
                "❌ **커리큘럼 생성 실패**\n\n"
                "에이전트 실행 중 오류가 발생했습니다. "
                "RAG/웹 검색 오류나 API 키 설정을 확인 후 다시 시도해주세요."
            )


# ── 이벤트 헬퍼 ──────────────────────────────────────────────────

def _progress(step: str) -> dict:
    return {"type": "progress", "step": step}


def _tool_done(tool: str, label: str) -> dict:
    return {"type": "tool_done", "tool": tool, "label": label}


def _tool_warn(tool: str, label: str) -> dict:
    return {"type": "tool_warn", "tool": tool, "label": label}
