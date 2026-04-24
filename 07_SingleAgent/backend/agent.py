"""
SingleAgent — OpenAI tool-calling ReAct 루프
"""
import json
import os
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from .tools import AgentTools, TOOL_DEFINITIONS

# 도구별 진행 메시지
_TOOL_LABELS: dict[str, str] = {
    "rag_search":           "🔍 RAG 검색 — ChromaDB에서 AX Compass 유형 정보 검색 중",
    "web_search":           "🌐 웹 검색 — 최신 AI 교육 트렌드 검색 중",
    "generate_curriculum":  "✏️  커리큘럼 생성 — LLM 호출 중",
    "validate_curriculum":  "✅ 커리큘럼 검증 — 요구사항 충족 여부 확인 중",
}

MAX_ITER = int(os.getenv("AGENT_MAX_ITER", "20"))
MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "3"))
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent / "prompts")))


def _load_system_prompt() -> str:
    path = PROMPTS_DIR / "agent_system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "당신은 AX 교육 커리큘럼 설계 전문 AI 에이전트입니다."


@dataclass
class AgentResult:
    reply: str
    complete: bool = False
    curriculum: str | None = None
    validation_result: dict | None = None
    agent_steps: list[str] = field(default_factory=list)


class SingleAgent:
    def __init__(self, llm: OpenAI, education_info: dict, api_key: str):
        self.llm = llm
        self.tools = AgentTools(llm, education_info, api_key)
        self.system_prompt = _load_system_prompt()
        self._generate_count = 0
        self._web_searched = False  # generate_curriculum 전 웹 검색 보장용
        self._tavily_forced = False  # Tavily 강제 검색 완료 여부

    def _auto_web_query(self) -> str:
        info = self.tools.education_info
        topics = " ".join(info.get("topics", [])[:2])
        level = info.get("level", "")
        return f"{topics} {level} AI 교육 커리큘럼 설계 트렌드 2025"

    def _force_tavily_search(self) -> dict | None:
        """에이전트 루프 시작 전 Tavily 웹 검색을 반드시 1회 실행합니다."""
        query = self._auto_web_query()
        result_str = self.tools.web_search(query)
        result = json.loads(result_str)
        if result.get("status") == "ok" and self.tools.web_context:
            self._web_searched = True
            self._tavily_forced = True
            return result
        # 첫 시도 실패 시 간단한 쿼리로 재시도
        fallback_query = "AI 교육 커리큘럼 최신 트렌드 2025"
        result_str = self.tools.web_search(fallback_query)
        result = json.loads(result_str)
        if result.get("status") == "ok" and self.tools.web_context:
            self._web_searched = True
            self._tavily_forced = True
            return result
        return result  # 실패해도 결과 반환 (에러 정보 포함)

    def _edu_summary(self) -> str:
        info = self.tools.education_info
        topics = ", ".join(info.get("topics", []))
        counts = info.get("type_counts", {})
        dominant = sorted(counts, key=counts.get, reverse=True)[:3]
        return (
            f"[교육 요청 정보]\n"
            f"- 회사: {info.get('company', '')}\n"
            f"- 목표: {info.get('goal', '')}\n"
            f"- 대상: {info.get('audience', '')} / 수준: {info.get('level', '')}\n"
            f"- 주제: {topics}\n"
            f"- 기간: {info.get('duration', '')}\n"
            f"- 주요 유형: {', '.join(dominant)}"
        )

    def run(self, user_messages: list[dict]) -> AgentResult:
        system_with_edu = self.system_prompt + "\n\n" + self._edu_summary()
        messages: list[dict] = [{"role": "system", "content": system_with_edu}]
        messages.extend(user_messages)

        steps: list[str] = []

        # ── Tavily 강제 검색 (에이전트 루프 시작 전 반드시 1회 실행) ──
        tavily_result = self._force_tavily_search()
        if self._tavily_forced:
            steps.append("🌐 Tavily 웹 검색 강제 실행 완료")
            # 검색 결과를 컨텍스트 메시지로 삽입
            messages.append({
                "role": "user",
                "content": (
                    f"[Tavily 웹 검색 결과 — 커리큘럼 설계 시 반드시 참고할 것]\n"
                    f"{self.tools.web_context[:1500]}"
                ),
            })
        else:
            steps.append("⚠️ Tavily 웹 검색 실패 (API 키 확인 필요)")

        for iteration in range(MAX_ITER):
            response = self.llm.chat.completions.create(
                model=AGENT_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            choice = response.choices[0]

            # 에이전트가 최종 답변으로 종료
            if choice.finish_reason == "stop":
                reply = choice.message.content or ""
                passed = (
                    self.tools.validation_result is not None
                    and self.tools.validation_result.get("passed", False)
                )
                return AgentResult(
                    reply=reply,
                    complete=passed,
                    curriculum=self.tools.curriculum,
                    validation_result=self.tools.validation_result,
                    agent_steps=steps,
                )

            # 도구 호출 처리
            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    # generate_curriculum 전 웹 검색 강제 실행
                    if name == "generate_curriculum" and not self._web_searched:
                        auto_query = self._auto_web_query()
                        self.tools.web_search(auto_query)
                        if self.tools.web_context:
                            self._web_searched = True
                            steps.append("web_search 자동 실행")

                    # generate_curriculum 재시도 상한
                    if name == "generate_curriculum":
                        if self._generate_count >= MAX_RETRIES:
                            result_str = json.dumps(
                                {
                                    "error": f"최대 재생성 횟수({MAX_RETRIES}회) 초과. 현재 커리큘럼을 최종 결과로 사용합니다.",
                                    "curriculum_available": self.tools.curriculum is not None,
                                },
                                ensure_ascii=False,
                            )
                            steps.append(f"generate_curriculum 상한 도달 ({MAX_RETRIES}/{MAX_RETRIES})")
                        else:
                            self._generate_count += 1
                            result_str = self.tools.call(name, args)
                            steps.append(f"generate_curriculum #{self._generate_count}")
                    else:
                        result_str = self.tools.call(name, args)
                        # web_search 성공 여부를 결과(context 채워짐)로 판단
                        if name == "web_search" and self.tools.web_context:
                            self._web_searched = True
                        steps.append(f"{name} 완료")

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_str,
                        }
                    )

        # MAX_ITER 초과
        return AgentResult(
            reply="최대 반복 횟수에 도달했습니다. 지금까지 생성된 결과를 반환합니다.",
            complete=False,
            curriculum=self.tools.curriculum,
            validation_result=self.tools.validation_result,
            agent_steps=steps,
        )

    def run_stream(
        self, user_messages: list[dict]
    ) -> Generator[dict[str, Any], None, None]:
        """SSE용 제너레이터. 각 단계마다 progress 이벤트, 완료 시 result 이벤트를 yield."""
        system_with_edu = self.system_prompt + "\n\n" + self._edu_summary()
        messages: list[dict] = [{"role": "system", "content": system_with_edu}]
        messages.extend(user_messages)
        steps: list[str] = []

        yield {"type": "progress", "step": "🤖 에이전트 시작 — LLM에 첫 번째 요청 전송 중"}

        # ── Tavily 강제 검색 (에이전트 루프 시작 전 반드시 1회 실행) ──
        yield {"type": "progress", "step": "🌐 Tavily 웹 검색 강제 실행 중 (필수 단계)"}
        tavily_result = self._force_tavily_search()
        if self._tavily_forced:
            steps.append("🌐 Tavily 웹 검색 강제 실행 완료")
            yield {"type": "tool_done", "tool": "web_search", "label": "🌐 Tavily 웹 검색 완료 (강제 실행)"}
            # 검색 결과를 컨텍스트 메시지로 삽입
            messages.append({
                "role": "user",
                "content": (
                    f"[Tavily 웹 검색 결과 — 커리큘럼 설계 시 반드시 참고할 것]\n"
                    f"{self.tools.web_context[:1500]}"
                ),
            })
        else:
            steps.append("⚠️ Tavily 웹 검색 실패 (API 키 확인 필요)")
            yield {"type": "progress", "step": "⚠️ Tavily 웹 검색 실패 — API 키를 확인하세요"}

        for _iteration in range(MAX_ITER):
            yield {"type": "progress", "step": "💭 LLM 응답 대기 중..."}

            response = self.llm.chat.completions.create(
                model=AGENT_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            choice = response.choices[0]

            if choice.finish_reason == "stop":
                reply = choice.message.content or ""
                passed = (
                    self.tools.validation_result is not None
                    and self.tools.validation_result.get("passed", False)
                )
                yield {
                    "type": "result",
                    "reply": reply,
                    "complete": passed,
                    "curriculum": self.tools.curriculum,
                    "validation_result": self.tools.validation_result,
                    "agent_steps": steps,
                }
                return

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    label = _TOOL_LABELS.get(name, f"⚙️ {name} 실행 중")

                    # generate_curriculum 전 웹 검색 강제 실행
                    if name == "generate_curriculum" and not self._web_searched:
                        auto_query = self._auto_web_query()
                        yield {"type": "progress", "step": "🌐 웹 검색 자동 실행 중 (커리큘럼 생성 전 필수)"}
                        self.tools.web_search(auto_query)
                        if self.tools.web_context:
                            self._web_searched = True
                            steps.append("web_search 자동 실행")
                            yield {"type": "tool_done", "tool": "web_search", "label": "🌐 웹 검색 완료 (자동 실행)"}

                    # generate_curriculum 재시도 상한
                    if name == "generate_curriculum":
                        if self._generate_count >= MAX_RETRIES:
                            label = f"⛔ 커리큘럼 최대 재생성 횟수({MAX_RETRIES}회) 도달"
                            result_str = json.dumps(
                                {
                                    "error": f"최대 재생성 횟수({MAX_RETRIES}회) 초과.",
                                    "curriculum_available": self.tools.curriculum is not None,
                                },
                                ensure_ascii=False,
                            )
                            steps.append(label)
                        else:
                            self._generate_count += 1
                            label = f"✏️  커리큘럼 생성 — #{self._generate_count}회 시도 중"
                            yield {"type": "progress", "step": label}
                            result_str = self.tools.call(name, args)
                            steps.append(f"generate_curriculum #{self._generate_count}")
                            yield {"type": "tool_done", "tool": name, "label": f"커리큘럼 생성 완료 (#{self._generate_count})"}
                            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})
                            continue
                    else:
                        yield {"type": "progress", "step": label}
                        result_str = self.tools.call(name, args)
                        # web_search 성공 여부를 결과(context 채워짐)로 판단
                        if name == "web_search" and self.tools.web_context:
                            self._web_searched = True
                        steps.append(f"{name} 완료")

                    done_labels = {
                        "rag_search":          "🔍 RAG 검색 완료",
                        "web_search":          "🌐 웹 검색 완료",
                        "validate_curriculum": "✅ 검증 완료",
                    }
                    if name in done_labels:
                        vr = self.tools.validation_result
                        extra = ""
                        if name == "validate_curriculum" and vr:
                            extra = " — 통과 ✓" if vr.get("passed") else f" — 미통과 ({len(vr.get('issues', []))}개 항목)"
                        yield {"type": "tool_done", "tool": name, "label": done_labels[name] + extra}

                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

        yield {
            "type": "result",
            "reply": "최대 반복 횟수에 도달했습니다. 지금까지 생성된 결과를 반환합니다.",
            "complete": False,
            "curriculum": self.tools.curriculum,
            "validation_result": self.tools.validation_result,
            "agent_steps": steps,
        }
