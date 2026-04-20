"""
RAG 검색 및 사용자 메시지 빌더
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


def retrieve_type_info(
    collection: chromadb.Collection,
    types: list[str],
    n_results: int = 6,
) -> str:
    """관련 유형 정보를 벡터 DB에서 검색합니다."""
    query = "AX Compass 유형별 특성과 교육 접근법: " + ", ".join(types)
    n = min(n_results, len(schemas.AX_COMPASS_DOCS))
    results = collection.query(
        query_texts=[query],
        n_results=n,
        where={"source": "ax_compass_structured"},
    )
    if not results["documents"] or not results["documents"][0]:
        return ""
    return "\n\n---\n\n".join(results["documents"][0])


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
) -> str:
    """후속 질문에 RAG 컨텍스트를 보강합니다."""
    keywords = ["그룹", "유형", "실습", "프로젝트", "맞춤", "균형형", "이해형",
                "과신형", "실행형", "판단형", "조심형"]
    if not any(kw in user_input for kw in keywords):
        return user_input

    ctx = retrieve_type_info(collection, active_types, n_results=n_results)
    if ctx:
        return f"[참고: {ctx[:500]}...]\n\n{user_input}"
    return user_input
