"""
RAG 에이전트 — ChromaDB HybridRetriever로 AX Compass 유형별 특성 검색.
그룹별 3개 쿼리로 A/B/C 각 그룹 특성을 고르게 수집.
"""
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

from ..retrieval import search as rag_search

PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent.parent / "prompts")))
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")

# RAG 실패 시 사용할 기본 AX Compass 특성 텍스트
_FALLBACK_CONTEXT = """
A그룹 (균형형·이해형):
- 핵심 특성: 개념을 충분히 이해한 후 적용하려는 성향. 체계적 탐구와 논리적 구조 선호.
- 적합한 교수법: PBL(문제 기반 학습), 가설→실험→발표 구조, 자율 탐구 과제.
- 주의사항: 너무 단순한 과제엔 흥미를 잃음. 충분한 도전 수준 필요.

B그룹 (과신형·실행형):
- 핵심 특성: 빠른 실행 선호, 결과에 집중, 검증 과정 소홀히 하는 경향.
- 적합한 교수법: 실행→검증→개선 반복 사이클, 체크리스트 기반 품질 확인, 페어리뷰.
- 주의사항: 검증 없이 진행하면 오류 반복. 체크포인트 의무화 필요.

C그룹 (판단형·조심형):
- 핵심 특성: 실패에 대한 두려움, 신중한 의사결정 선호, 심리적 안전감 중요.
- 적합한 교수법: 단계별 가이드 제공, 강사 시연 따라하기, 즉각 피드백, 성공 경험 누적.
- 주의사항: 처음부터 너무 어려운 과제 부여 시 참여 거부. 작은 성공 경험으로 시작.
""".strip()


def _load_prompt() -> str:
    path = PROMPTS_DIR / "rag_agent_system.txt"
    return path.read_text(encoding="utf-8") if path.exists() else "AX Compass 유형별 특성을 검색합니다."


def _build_queries(education_info: dict) -> list[str]:
    """그룹별 특성을 고르게 수집하기 위한 3개 쿼리 생성."""
    topics = " ".join(education_info.get("topics", [])[:3])
    level = education_info.get("level", "")
    counts = education_info.get("type_counts", {})

    # 각 그룹에서 인원 많은 유형 추출
    group_dominant = {
        "A": max(["균형형", "이해형"], key=lambda t: counts.get(t, 0)),
        "B": max(["과신형", "실행형"], key=lambda t: counts.get(t, 0)),
        "C": max(["판단형", "조심형"], key=lambda t: counts.get(t, 0)),
    }

    return [
        f"AX Compass A그룹 {group_dominant['A']} 이해형 교육 특성 학습 스타일 {topics} {level}",
        f"AX Compass B그룹 {group_dominant['B']} 실행형 교육 특성 검증 프로세스 실습 설계",
        f"AX Compass C그룹 {group_dominant['C']} 조심형 심리적 안전감 단계별 교수법",
    ]


class RagAgent:
    """
    단일 책임: 교육 정보를 받아 ChromaDB 검색 → 정리된 컨텍스트 반환.
    그룹별 3개 쿼리로 A/B/C 특성을 고르게 수집.
    RAG 실패 시 fallback 컨텍스트 사용.
    """

    def __init__(self, llm: OpenAI, api_key: str, n_results: int = 4):
        self.llm = llm
        self.api_key = api_key
        self.n_results = n_results
        self._system_prompt = _load_prompt()

    def run(self, education_info: dict) -> tuple[str, bool]:
        """
        Returns (rag_context, success).
        success=False이면 fallback 컨텍스트 반환 (빈 문자열 아님).
        """
        queries = _build_queries(education_info)

        # 그룹별로 검색 — 중복 제거하며 누적
        seen: set[str] = set()
        all_snippets: list[str] = []

        for query in queries:
            docs, ok = rag_search(query, self.api_key, self.n_results)
            if ok and docs:
                for chunk in docs.split("\n\n"):
                    chunk = chunk.strip()
                    if chunk and chunk not in seen:
                        seen.add(chunk)
                        all_snippets.append(chunk)

        if not all_snippets:
            return _FALLBACK_CONTEXT, False

        raw_docs = "\n\n".join(all_snippets)

        # LLM으로 그룹별 구조화
        try:
            resp = self.llm.chat.completions.create(
                model=AGENT_MODEL,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "다음 검색 결과를 A그룹(균형형·이해형), "
                            "B그룹(과신형·실행형), C그룹(판단형·조심형) 별로 정리해주세요.\n"
                            "각 그룹마다 반드시: 핵심 특성 / 적합한 교수법 / 주의사항 을 포함하세요.\n\n"
                            f"{raw_docs[:4000]}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=1500,
            )
            context = resp.choices[0].message.content or raw_docs
        except Exception:
            context = raw_docs

        return context, True
