"""
검증 에이전트 — 코드 검증(규칙 기반) + LLM 판단(정성 평가) 명확히 분리.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import OpenAI

from ..schemas import CodeCheckResult, LLMCheckResult, ValidationResult

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent.parent / "prompts")))
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")


def _load_prompt() -> str:
    path = PROMPTS_DIR / "validator_agent_system.txt"
    return path.read_text(encoding="utf-8") if path.exists() else "커리큘럼 품질을 검증합니다."


# ── 코드 검증 (규칙 기반) ─────────────────────────────────────────

def _parse_total_hours(duration_str: str) -> tuple[int | None, int | None]:
    """
    '3일 8시간씩' → total_hours=24, days=3. 
    '3일 24시간' → total_hours=24, days=3. (하루 12시간 초과는 총 시간으로 간주)
    """
    days_match = re.search(r"(\d+)\s*일", duration_str)
    hours_match = re.search(r"(\d+)\s*시간", duration_str)
    days = int(days_match.group(1)) if days_match else None
    hours_num = int(hours_match.group(1)) if hours_match else None

    if days and hours_num:
        if hours_num > 12:  # 하루 12시간 초과면 총 시간으로 간주
            return hours_num, days
        return days * hours_num, days
    if hours_num:
        return hours_num, days
    return None, days


def _run_code_checks(curriculum: str, education_info: dict) -> CodeCheckResult:
    duration_str = education_info.get("duration", "")
    expected_hours, expected_days = _parse_total_hours(duration_str)

    # ① 총 시간 검증 — 커리큘럼에 총 시간이 명시됐는가
    hours_ok = True
    found_hour_mentions: list[int] = []
    if expected_hours:
        hour_mentions = re.findall(r"(\d+)\s*시간", curriculum)
        found_hour_mentions = [int(h) for h in hour_mentions]
        day_mentions = re.findall(r"(\d+)\s*일", curriculum)
        found_days = [int(d) for d in day_mentions]
        # 총 시간 직접 언급 또는 일수 언급
        hours_ok = (
            any(h == expected_hours for h in found_hour_mentions)
            or (expected_days and any(d == expected_days for d in found_days))
        )

    # ② 그룹 검증
    groups_found = []
    for g in ["A", "B", "C"]:
        pattern = rf"{g}\s*그룹|그룹\s*{g}|Group\s*{g}|{g}조|{g}\s*팀|{g}\s*반"
        if re.search(pattern, curriculum, re.IGNORECASE):
            groups_found.append(g)
    groups_ok = len(groups_found) == 3

    # ③ 세션/모듈 수 검증
    module_patterns = r"모듈\s*\d+|세션\s*\d+|Session\s*\d+|Day\s*\d+|\d+일차|\d+일\s*차|Part\s*\d+"
    module_count = len(re.findall(module_patterns, curriculum, re.IGNORECASE))
    modules_ok = module_count > 0

    # ④ 핵심 주제 검증
    topics = education_info.get("topics", [])
    missing_topics: list[str] = []
    for topic in topics:
        keywords = [w for w in re.split(r"[,\s·및과를의에서]+", topic) if len(w) >= 2]
        if not keywords:
            continue
        matched = sum(1 for kw in keywords if kw in curriculum)
        if matched < max(1, len(keywords) * 0.3):
            missing_topics.append(topic)
    topics_ok = len(missing_topics) == 0

    return CodeCheckResult(
        hours_ok=hours_ok,
        groups_ok=groups_ok,
        modules_ok=modules_ok,
        topics_ok=topics_ok,
        groups_found=groups_found,
        missing_topics=missing_topics,
        module_count=module_count,
        expected_hours=expected_hours,
        found_hour_mentions=found_hour_mentions,
    )


# ── LLM 판단 ─────────────────────────────────────────────────────

def _run_llm_checks(
    llm: OpenAI,
    system_prompt: str,
    curriculum: str,
    education_info: dict,
) -> LLMCheckResult:
    goal = education_info.get("goal", "")
    topics = ", ".join(education_info.get("topics", []))
    user_msg = (
        f"교육 목표: {goal}\n"
        f"교육 주제: {topics}\n\n"
        f"아래 커리큘럼을 평가해주세요:\n\n{curriculum[:15000]}"
    )
    try:
        resp = llm.chat.completions.create(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return LLMCheckResult(
            group_customization=bool(data.get("group_customization", False)),
            time_balance=bool(data.get("time_balance", False)),
            goal_alignment=bool(data.get("goal_alignment", False)),
            feedback=str(data.get("feedback", "")),
        )
    except Exception as e:
        return LLMCheckResult(
            group_customization=False,
            time_balance=False,
            goal_alignment=False,
            feedback=f"LLM 판단 실패: {e}",
        )


class ValidatorAgent:
    """
    단일 책임: 커리큘럼 → 코드 검증 + LLM 판단 → ValidationResult 반환.
    """

    def __init__(self, llm: OpenAI):
        self.llm = llm
        self._system_prompt = _load_prompt()

    def run(self, curriculum: str, education_info: dict) -> ValidationResult:
        code = _run_code_checks(curriculum, education_info)
        llm = _run_llm_checks(self.llm, self._system_prompt, curriculum, education_info)
        return ValidationResult.build(code, llm)
