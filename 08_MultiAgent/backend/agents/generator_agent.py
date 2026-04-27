"""
커리큘럼 생성 에이전트 — RAG·웹 컨텍스트 + 교육 정보로 커리큘럼 초안 생성.
재생성 시 이전 커리큘럼 + 피드백을 함께 전달해 "수정" 방식으로 동작.
"""
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI
from ..retrieval import get_gen_system_prompt

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent.parent / "prompts")))
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o")
ALL_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
GROUPS = {"A": ["균형형", "이해형"], "B": ["과신형", "실행형"], "C": ["판단형", "조심형"]}


def _load_prompt() -> str:
    path = PROMPTS_DIR / "generator_agent_system.txt"
    return path.read_text(encoding="utf-8") if path.exists() else get_gen_system_prompt()


def _calc_total_hours(duration_str: str) -> str:
    """'3일 8시간씩' → '3일, 총 24시간 (1일 8시간)' 형태로 변환."""
    import re
    days_m = re.search(r"(\d+)\s*일", duration_str)
    hours_m = re.search(r"(\d+)\s*시간", duration_str)
    days = int(days_m.group(1)) if days_m else None
    hpd = int(hours_m.group(1)) if hours_m else None
    if days and hpd:
        return f"{days}일, 총 {days * hpd}시간 (1일 {hpd}시간)"
    return duration_str


def _build_context_header(rag_context: str, web_context: str) -> str:
    """RAG·웹 컨텍스트 섹션 구성 — 초안/재생성 공통."""
    rag_section = f"[AX Compass 유형별 특성 참고 자료]\n{rag_context}\n\n---\n" if rag_context else ""
    web_section = f"\n[최신 AI 교육 트렌드 참고]\n{web_context}\n\n---\n" if web_context else ""
    return rag_section + web_section


def _build_edu_block(education_info: dict) -> str:
    """교육 정보 블록 구성 — 초안/재생성 공통."""
    info = education_info
    topics = ", ".join(info.get("topics", []))
    if info.get("extra"):
        topics += f", {info['extra']}"

    duration_raw = info.get("duration", "")
    duration_display = _calc_total_hours(duration_raw)

    counts = info.get("type_counts", {})
    type_detail = "\n".join(f"  - {t}: {counts.get(t, 0)}명" for t in ALL_TYPES)
    group_counts = {g: sum(counts.get(t, 0) for t in ts) for g, ts in GROUPS.items()}
    total = sum(counts.get(t, 0) for t in ALL_TYPES)

    return (
        f"- **회사명**: {info.get('company', '')}\n"
        f"- **교육 목표**: {info.get('goal', '')}\n"
        f"- **교육 대상**: {info.get('audience', '')}\n"
        f"- **교육 수준**: {info.get('level', '')}\n"
        f"- **교육 주제**: {topics}\n"
        f"- **교육 기간**: {duration_display}\n\n"
        f"**AX Compass 진단 결과 유형별 인원:**\n{type_detail}\n\n"
        f"**그룹 구성:**\n"
        f"  - A그룹 (균형형+이해형): {group_counts['A']}명\n"
        f"  - B그룹 (과신형+실행형): {group_counts['B']}명\n"
        f"  - C그룹 (판단형+조심형): {group_counts['C']}명\n"
        f"  - 총 인원: {total}명"
    )


def _build_initial_message(education_info: dict, rag_context: str, web_context: str) -> str:
    """최초 생성 메시지."""
    header = _build_context_header(rag_context, web_context)
    edu_block = _build_edu_block(education_info)
    return (
        f"{header}"
        f"다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.\n\n"
        f"{edu_block}\n\n"
        "**설계 요구사항:**\n"
        "1. 교육 기간(일수)에 맞게 1일차/2일차/... 로 나누고, 각 일차마다 이론+실습 세션을 구성하세요.\n"
        "2. 각 세션에 시간(시간수)을 명시하고, 합산이 총 교육 시간과 일치해야 합니다.\n"
        "3. 교육 개요 표에 `| 시간 배분 | 이론: X시간 (Y%) / 실습: X시간 (Y%) |` 행을 반드시 추가하세요.\n"
        "4. A/B/C그룹 실습은 위 AX Compass 특성 자료를 직접 반영해 과제명·방식·도구를 구체적으로 작성하세요.\n"
        "5. B그룹 검증 체크리스트는 매 일차 다른 항목으로 구성하세요 — 복붙 금지.\n"
        "6. 마지막 일차 이론 세션(세션 5)의 소주제에 반드시 구체적 기술명·도구명을 포함하세요 — '심화 프로젝트의 필요성' 같은 추상적 표현 금지.\n"
        "7. 위 트렌드 자료에서 최소 1개 교수법/도구를 세션에 포함하고 어디에 반영했는지 명시하세요."
    )


def _build_revision_messages(
    education_info: dict,
    rag_context: str,
    web_context: str,
    previous_curriculum: str,
    feedback: str,
) -> list[dict]:
    """
    재생성 시 멀티턴 메시지 구성.
    assistant 역할로 이전 커리큘럼을 전달 → user가 피드백 기반 수정 요청.
    이렇게 하면 LLM이 "완전 새로 쓰기"가 아닌 "기존 수정"으로 인식.
    """
    header = _build_context_header(rag_context, web_context)
    edu_block = _build_edu_block(education_info)

    initial_request = (
        f"{header}"
        f"다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.\n\n"
        f"{edu_block}"
    )

    revision_request = (
        f"[검증 실패 — 아래 피드백을 반영해 커리큘럼을 수정해주세요]\n\n"
        f"{feedback}\n\n"
        "**수정 규칙:**\n"
        "1. 피드백에서 지적된 항목만 수정하고, 나머지는 그대로 유지하세요.\n"
        "2. 수정한 항목을 커리큘럼 상단 **[수정 사항]** 섹션에 bullet로 나열하세요.\n"
        "3. 세션 구조(일차 구분, Step 구성, 그룹별 실습)는 반드시 유지하세요.\n"
        "4. 시간 합산이 총 교육 시간과 일치하는지 다시 확인하세요.\n"
        "5. 교육 개요 표에 `| 시간 배분 |` 행이 있는지 확인하세요.\n"
        "6. B그룹 체크리스트가 매 일차 다른 항목인지 확인하세요.\n"
        "7. 마지막 일차 이론 세션 소주제가 구체적 기술명을 포함하는지 확인하세요."
    )

    return [
        {"role": "user", "content": initial_request},
        {"role": "assistant", "content": previous_curriculum},
        {"role": "user", "content": revision_request},
    ]


class GeneratorAgent:
    """
    단일 책임: RAG+웹 컨텍스트 + 교육 정보 → 커리큘럼 마크다운 텍스트 반환.
    - 최초 생성: 단일 user 메시지
    - 재생성: 이전 커리큘럼을 assistant 메시지로 전달 → 수정 방식
    """

    def __init__(self, llm: OpenAI):
        self.llm = llm
        self._system_prompt = _load_prompt()

    def run(
        self,
        education_info: dict,
        rag_context: str,
        web_context: str = "",
        feedback: str = "",
        previous_curriculum: str = "",
    ) -> tuple[str, bool]:
        """
        Returns (curriculum_text, success).
        feedback + previous_curriculum 둘 다 있으면 수정 모드.
        """
        if feedback and previous_curriculum:
            messages = [
                {"role": "system", "content": self._system_prompt},
                *_build_revision_messages(
                    education_info, rag_context, web_context, previous_curriculum, feedback
                ),
            ]
        else:
            messages = [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": _build_initial_message(education_info, rag_context, web_context)},
            ]

        try:
            resp = self.llm.chat.completions.create(
                model=GEN_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=8000,
            )
            curriculum = resp.choices[0].message.content or ""
            return curriculum, bool(curriculum.strip())
        except Exception as e:
            return f"커리큘럼 생성 실패: {e}", False
