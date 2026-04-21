"""
RAG 검색 및 사용자 메시지 빌더

Contextual BM25 + 벡터 검색을 RRF로 결합하는 HybridRetriever 포함.
"""
import importlib.util
import sys
from pathlib import Path

import chromadb


# ── 형제 모듈 로드 헬퍼 ──────────────────────────────────────
def _load_sibling(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parent / filename
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


schemas = _load_sibling("schemas", "05_2.Schemas.py")


# ── Reciprocal Rank Fusion ───────────────────────────────────
def _rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """여러 랭킹 리스트를 RRF 점수로 합산하여 단일 순위 리스트로 반환한다."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


# ── Hybrid Retriever (BM25 + Vector + RRF) ───────────────────
class HybridRetriever:
    """벡터 검색과 BM25 키워드 검색을 RRF로 결합하는 하이브리드 검색기.

    컬렉션 초기화 시 is_primary=1인 구조화 문서 청크로 BM25 인덱스를 구축한다.
    query() 호출 시 벡터 검색과 BM25 검색을 병렬 수행 후 RRF로 병합한다.
    """

    def __init__(self, collection: chromadb.Collection):
        self.collection = collection
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._metas: list[dict] = []
        self._bm25 = None
        self._build_bm25_index()

    def _build_bm25_index(self):
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return

        try:
            result = self.collection.get(
                where={"$and": [
                    {"source": {"$eq": "ax_compass_structured"}},
                    {"is_primary": {"$eq": 1}},
                ]},
                include=["documents", "metadatas"],
            )
            self._ids = result["ids"]
            self._docs = result["documents"]
            self._metas = result["metadatas"]
            if self._ids:
                tokenized = [doc.split() for doc in self._docs]
                from rank_bm25 import BM25Okapi
                self._bm25 = BM25Okapi(tokenized)
        except Exception:
            pass

    def _label(self, doc_id: str) -> str:
        try:
            idx = self._ids.index(doc_id)
            return self._metas[idx].get("type", doc_id)
        except (ValueError, IndexError):
            return doc_id

    def _query_internal(self, query_text: str, n_results: int) -> tuple[str, dict]:
        n = min(n_results, len(self._ids))
        where = {"$and": [
            {"source": {"$eq": "ax_compass_structured"}},
            {"is_primary": {"$eq": 1}},
        ]}

        vec_ids: list[str] = []
        try:
            vec_res = self.collection.query(
                query_texts=[query_text], n_results=n, where=where,
            )
            vec_ids = vec_res["ids"][0] if vec_res["ids"] else []
        except Exception:
            pass

        bm25_ids: list[str] = []
        if self._bm25:
            scores = self._bm25.get_scores(query_text.split())
            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
            bm25_ids = [self._ids[i] for i in ranked]

        merged = _rrf([vec_ids, bm25_ids]) if bm25_ids else vec_ids
        id_to_doc = dict(zip(self._ids, self._docs))
        docs = [id_to_doc[i] for i in merged[:n] if i in id_to_doc]

        debug = {
            "vec":    [self._label(i) for i in vec_ids],
            "bm25":   [self._label(i) for i in bm25_ids],
            "merged": [self._label(i) for i in merged[:n]],
        }
        return "\n\n---\n\n".join(docs), debug

    def query(self, query_text: str, n_results: int = 6) -> str:
        """하이브리드 검색을 수행하고 상위 문서를 개행 구분 문자열로 반환한다."""
        if not self._ids:
            return ""
        docs, _ = self._query_internal(query_text, n_results)
        return docs

    def query_debug(self, query_text: str, n_results: int = 6) -> tuple[str, dict]:
        """query()와 동일하나 (docs_str, debug_dict)를 반환한다."""
        if not self._ids:
            return "", {"vec": [], "bm25": [], "merged": []}
        return self._query_internal(query_text, n_results)


# ── 기본 벡터 검색 ───────────────────────────────────────────
def retrieve_type_info(
    collection: chromadb.Collection,
    types: list[str],
    n_results: int = 6,
    section: str | None = None,
    hybrid_retriever: "HybridRetriever | None" = None,
) -> str:
    """관련 유형 정보를 검색한다.

    hybrid_retriever가 제공되고 section 지정이 없으면 BM25+벡터 하이브리드 검색을 사용한다.
    section 파라미터가 있으면 특정 섹션 청크만 벡터 검색한다.
    """
    query = "AX Compass 유형별 특성과 교육 접근법: " + ", ".join(types)
    n = min(n_results, len(schemas.AX_COMPASS_DOCS))

    # 하이브리드 검색 우선 (section 미지정 시)
    if hybrid_retriever and not section:
        return hybrid_retriever.query(query, n)

    # 벡터 전용 검색
    if section:
        where = {"$and": [{"source": {"$eq": "ax_compass_structured"}}, {"section": {"$eq": section}}]}
    else:
        where = {"$and": [{"source": {"$eq": "ax_compass_structured"}}, {"is_primary": {"$eq": 1}}]}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
        )
    except Exception:
        results = collection.query(query_texts=[query], n_results=n)

    if not results["documents"] or not results["documents"][0]:
        return ""
    return "\n\n---\n\n".join(results["documents"][0])


def retrieve_type_info_debug(
    collection: chromadb.Collection,
    types: list[str],
    n_results: int = 6,
    hybrid_retriever: "HybridRetriever | None" = None,
) -> tuple[str, dict | None]:
    """retrieve_type_info의 debug 버전. (docs_str, debug_info) 튜플을 반환한다."""
    if hybrid_retriever:
        query = "AX Compass 유형별 특성과 교육 접근법: " + ", ".join(types)
        n = min(n_results, len(schemas.AX_COMPASS_DOCS))
        return hybrid_retriever.query_debug(query, n)
    return retrieve_type_info(collection, types, n_results), None


def build_user_message(info, rag_context: str) -> str:
    """EducationInfo와 RAG 컨텍스트를 결합하여 LLM 메시지를 생성합니다."""
    topics_str = ", ".join(info.topics)
    if info.extra:
        topics_str += f", {info.extra}"

    counts = info.type_counts
    group_a = info.group_count("A")
    group_b = info.group_count("B")
    group_c = info.group_count("C")
    total = info.total_count()

    type_detail = "\n".join(
        f"  - {t}: {counts.get(t, 0)}명" for t in schemas.TYPES
    )
    group_summary = (
        f"  - A그룹 (균형형+이해형): {group_a}명\n"
        f"  - B그룹 (과신형+실행형): {group_b}명\n"
        f"  - C그룹 (판단형+조심형): {group_c}명\n"
        f"  - 총 인원: {total}명"
    )

    rag_section = ""
    if rag_context:
        rag_section = (
            "[AX Compass 유형별 특성 참고 자료]\n"
            "다음은 RAG로 검색된 유형별 특성 및 교육 접근법입니다. "
            "이를 참고하여 그룹별 맞춤 실습을 설계해주세요:\n\n"
            f"{rag_context}\n\n---\n"
        )

    return f"""{rag_section}다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.

- **회사명**: {info.company}
- **교육 목표**: {info.goal}
- **교육 대상**: {info.audience}
- **교육 수준**: {info.level}
- **교육 주제**: {topics_str}
- **교육 기간**: {info.duration}

**AX Compass 진단 결과 유형별 인원:**
{type_detail}

**그룹 구성:**
{group_summary}

이론 수업은 전체 동일하게 진행하되, 각 그룹별 특성에 맞는 맞춤형 실습/프로젝트를 설계해주세요.
- A그룹 (균형형+이해형): AI 활용 이해도가 높거나 학습 의욕이 강한 그룹. 심화 프로젝트 중심.
- B그룹 (과신형+실행형): 행동력과 실행력이 높지만 검증과 품질 관리가 필요한 그룹. 실행+검증 프로세스 중심.
- C그룹 (판단형+조심형): 신중하고 분석적이지만 실행에 심리적 장벽이 있는 그룹. 체계적 단계별 실습 중심.
"""


def enrich_followup(
    user_input: str,
    collection: chromadb.Collection,
    active_types: list[str],
    n_results: int = 3,
    hybrid_retriever: "HybridRetriever | None" = None,
) -> str:
    """후속 질문에 RAG 컨텍스트를 보강합니다."""
    keywords = ["그룹", "유형", "실습", "프로젝트", "맞춤", "균형형", "이해형",
                "과신형", "실행형", "판단형", "조심형"]
    if not any(kw in user_input for kw in keywords):
        return user_input

    ctx = retrieve_type_info(
        collection, active_types, n_results=n_results, hybrid_retriever=hybrid_retriever
    )
    if ctx:
        return f"[참고: {ctx[:500]}...]\n\n{user_input}"
    return user_input
