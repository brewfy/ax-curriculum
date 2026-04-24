"""
SingleAgent — OpenAI tool-calling ReAct 루프
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from openai import OpenAI

from .tools import AgentTools, TOOL_DEFINITIONS

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
