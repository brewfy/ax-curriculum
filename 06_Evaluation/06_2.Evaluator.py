"""
RAG 평가 오케스트레이터

ChromaDB + HybridRetriever(Reranker 포함)를 초기화하고
테스트 케이스별로 4개 지표를 측정한다.
"""
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

# ── 모듈 경로 ─────────────────────────────────────────────────
_EVAL_DIR = Path(__file__).parent
_RAG_DIR = _EVAL_DIR.parent / "05_Advanced_RAG"

CHROMA_DIR = str(_RAG_DIR / "chroma_db")
COLLECTION_NAME = "ax_compass_types"
EMBED_MODEL = "text-embedding-3-small"

ALL_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
GROUPS = {"A": ["균형형", "이해형"], "B": ["과신형", "실행형"], "C": ["판단형", "조심형"]}


# ── 형제 모듈 로더 ────────────────────────────────────────────
def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


metrics = _load("eval_metrics", _EVAL_DIR / "06_1.Metrics.py")
retrieval = _load("retrieval", _RAG_DIR / "05_5.Retrieval.py")


# ── 결과 데이터클래스 ─────────────────────────────────────────
@dataclass
class CaseResult:
    id: str
    summary: str
    precision_at_k: float | None = None
    faithfulness: float | None = None
    requirement_coverage: float | None = None
    rule_check: dict = field(default_factory=dict)
    aggregate_score: float = 0.0
    error: str | None = None

    def compute_aggregate(self) -> None:
        scores: list[float] = []
        if self.precision_at_k is not None:
            scores.append(self.precision_at_k)
        if self.faithfulness is not None:
            scores.append(self.faithfulness)
        if self.requirement_coverage is not None:
            scores.append(self.requirement_coverage)
        if self.rule_check:
            scores.append(self.rule_check.get("score", 0.0))
        self.aggregate_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ── 유저 메시지 빌더 (평가용 간소화 버전) ───────────────────────
def _build_user_message(inp: dict, context: str) -> str:
    topics = ", ".join(inp.get("topics", []))
    if inp.get("extra"):
        topics += f", {inp['extra']}"
    counts = inp.get("type_counts", {})
    type_detail = "\n".join(f"  - {t}: {counts.get(t, 0)}명" for t in ALL_TYPES)
    group_counts = {g: sum(counts.get(t, 0) for t in ts) for g, ts in GROUPS.items()}
    total = sum(counts.values())

    rag_section = (
        "[AX Compass 유형별 특성 참고 자료]\n"
        f"{context}\n\n---\n"
    ) if context else ""

    return f"""{rag_section}다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.

- **회사명**: {inp.get('company', '')}
- **교육 목표**: {inp.get('goal', '')}
- **교육 대상**: {inp.get('audience', '')}
- **교육 수준**: {inp.get('level', '')}
- **교육 주제**: {topics}
- **교육 기간**: {inp.get('duration', '')}

**AX Compass 진단 결과 유형별 인원:**
{type_detail}

**그룹 구성:**
  - A그룹 (균형형+이해형): {group_counts['A']}명
  - B그룹 (과신형+실행형): {group_counts['B']}명
  - C그룹 (판단형+조심형): {group_counts['C']}명
  - 총 인원: {total}명

이론 수업은 전체 동일하게 진행하되, 각 그룹별 맞춤 실습을 설계해주세요."""


# ── Evaluator ─────────────────────────────────────────────────
class Evaluator:
    def __init__(
        self,
        chroma_path: str = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        openai_api_key: str | None = None,
    ):
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.llm = OpenAI(api_key=api_key)

        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key, model_name=EMBED_MODEL
        )
        chroma = chromadb.PersistentClient(path=chroma_path)
        col = chroma.get_collection(name=collection_name, embedding_function=ef)

        reranker = retrieval.Reranker()
        self.retriever = retrieval.HybridRetriever(col, reranker=reranker)

    # ── 검색 ─────────────────────────────────────────────────
    def _retrieve(self, query: str, n: int = 6) -> tuple[list[str], str]:
        """(retrieved_labels, docs_str) 반환."""
        if not self.retriever._ids:
            return [], ""
        docs_str, debug = self.retriever.query_debug(query, n_results=n)
        labels = debug.get("reranked") or debug.get("merged", [])
        return labels, docs_str

    # ── 생성 ─────────────────────────────────────────────────
    def _generate(self, user_message: str) -> str:
        resp = self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 AX 교육 전문가입니다. 맞춤형 교육 커리큘럼을 설계해주세요."},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return resp.choices[0].message.content

    # ── 단일 케이스 평가 ──────────────────────────────────────
    def evaluate_case(self, case: dict) -> CaseResult:
        tc_id = case.get("id", "unknown")
        inp = case.get("input", {})
        expected = case.get("expected", {})
        result = CaseResult(
            id=tc_id,
            summary=f"{inp.get('company', '?')} / {inp.get('duration', '?')}",
        )

        try:
            query = "AX Compass 유형별 특성과 교육 접근법: " + ", ".join(inp.get("topics", []))
            retrieved_labels, context = self._retrieve(query, n=6)

            # ① Precision@k
            ground_truth = expected.get("retrieval_ground_truth", [])
            if ground_truth:
                k = min(6, len(retrieved_labels))
                result.precision_at_k = metrics.precision_at_k(retrieved_labels, ground_truth, k)

            # ② 답변 생성 (또는 사전 제공)
            answer = case.get("generated_answer") or self._generate(
                _build_user_message(inp, context)
            )

            # ③ Faithfulness
            if context:
                result.faithfulness = metrics.faithfulness_score(answer, context, self.llm)

            # ④ Requirement Coverage
            req_topics = expected.get("required_topics", [])
            if req_topics:
                result.requirement_coverage = metrics.requirement_coverage(
                    answer, req_topics, self.llm
                )

            # ⑤ Rule check
            rule_keys = ("session_count_range", "total_hours", "groups_required")
            rules = {k: expected[k] for k in rule_keys if k in expected}
            if rules:
                result.rule_check = metrics.rule_check(answer, rules)

        except Exception as e:
            result.error = str(e)

        result.compute_aggregate()
        return result

    # ── 전체 평가 ─────────────────────────────────────────────
    def evaluate_all(self, testset: dict) -> list[CaseResult]:
        cases = testset.get("test_cases", [])
        results = []
        for i, case in enumerate(cases, 1):
            tc_id = case.get("id", f"tc_{i:03d}")
            print(f"[{i}/{len(cases)}] 평가 중: {tc_id}", flush=True)
            results.append(self.evaluate_case(case))
        return results
