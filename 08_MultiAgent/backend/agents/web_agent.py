"""
웹 검색 에이전트 — Tavily API로 최신 AI 교육 트렌드 수집.
"""
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent.parent / "prompts")))
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")


def _load_prompt() -> str:
    path = PROMPTS_DIR / "web_agent_system.txt"
    return path.read_text(encoding="utf-8") if path.exists() else "최신 AI 교육 트렌드를 검색합니다."


def _build_tavily_client():
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return None
    try:
        from tavily import TavilyClient
        return TavilyClient(api_key=key)
    except Exception:
        return None


class WebAgent:
    """
    단일 책임: 교육 정보를 받아 Tavily 검색 → 정리된 트렌드 컨텍스트 반환.
    Tavily 미설정 시 graceful fallback (빈 컨텍스트 + success=False).
    """

    def __init__(self, llm: OpenAI):
        self.llm = llm
        self._tavily = _build_tavily_client()
        self._system_prompt = _load_prompt()

    @property
    def available(self) -> bool:
        return self._tavily is not None

    def run(self, education_info: dict) -> tuple[str, bool]:
        """
        Returns (web_context, success).
        success=False이면 Tavily 미설정 또는 실패.
        """
        if not self._tavily:
            return "Tavily API 미설정 — 웹 검색 생략", False

        topics = " ".join(education_info.get("topics", [])[:3])
        level = education_info.get("level", "")
        goal = education_info.get("goal", "")
        audience = education_info.get("audience", "")

        # 3개 쿼리로 다각도 검색
        queries = [
            f"{topics} {level} 기업 교육 커리큘럼 설계 2025",
            f"{goal} 직원 교육 사례 베스트 프랙티스 2024 2025",
            f"AI 활용 교육 {audience} 실무 적용 트렌드 2025",
        ]

        all_snippets: list[str] = []
        for q in queries:
            all_snippets.extend(self._tavily_search(q, max_results=3))

        if not all_snippets:
            all_snippets = self._tavily_search("AI 기업 교육 커리큘럼 트렌드 2025", max_results=5)
        if not all_snippets:
            return "웹 검색 결과 없음", False

        raw_text = "\n\n".join(all_snippets)

        # LLM으로 정리 — 교육 맥락 구체적으로 전달
        try:
            resp = self.llm.chat.completions.create(
                model=AGENT_MODEL,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"다음 웹 검색 결과를 커리큘럼 설계에 즉시 활용 가능한 형태로 정리해주세요.\n\n"
                            f"교육 주제: {topics}\n"
                            f"교육 수준: {level}\n"
                            f"교육 목표: {goal}\n"
                            f"교육 대상: {audience}\n\n"
                            f"[웹 검색 결과]\n{raw_text[:3000]}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=1500,
            )
            context = resp.choices[0].message.content or raw_text
        except Exception:
            context = raw_text

        return context, True

    def _tavily_search(self, query: str, max_results: int = 3) -> list[str]:
        try:
            results = self._tavily.search(query, max_results=max_results)
            return [r.get("content", "")[:600] for r in results.get("results", []) if r.get("content")]
        except Exception:
            return []
