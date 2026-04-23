"""
RAG 평가 지표 모듈

- Precision@k     : 검색 품질
- Faithfulness    : 생성 결과가 검색 근거에 기반하는지
- Req. Coverage   : 요구사항(주제) 반영도
- Rule-based      : 세션 수 / 총 시간 / 그룹 구성 규칙 준수
"""
import re
from openai import OpenAI


# ── Precision@k ──────────────────────────────────────────────
def precision_at_k(retrieved: list[str], ground_truth: list[str], k: int) -> float:
    """상위 k개 검색 결과 중 정답 문서 비율."""
    if not ground_truth or k == 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc in top_k if doc in ground_truth)
    return round(hits / k, 4)


# ── LLM Judge (공통) ─────────────────────────────────────────
def _llm_judge(prompt: str, client: OpenAI, model: str = "gpt-4o-mini") -> float:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        m = re.search(r"[\d.]+", raw)
        return max(0.0, min(1.0, float(m.group()))) if m else 0.0


# ── Faithfulness ─────────────────────────────────────────────
def faithfulness_score(answer: str, context: str, client: OpenAI) -> float:
    """생성 답변이 검색 컨텍스트에 근거하는 정도 (0.0~1.0)."""
    prompt = f"""다음 [컨텍스트]와 [답변]을 비교하세요.
답변의 내용이 컨텍스트에 근거하는 정도를 0.0~1.0 사이 숫자 하나만 출력하세요.
(1.0=완전히 근거, 0.5=일부 근거, 0.0=전혀 근거 없음)

[컨텍스트]
{context[:3000]}

[답변]
{answer[:2000]}

점수(숫자만):"""
    return _llm_judge(prompt, client)


# ── Requirement Coverage ──────────────────────────────────────
def requirement_coverage(answer: str, required_topics: list[str], client: OpenAI) -> float:
    """필수 주제가 답변에 반영된 정도 (0.0~1.0)."""
    topics_str = "\n".join(f"- {t}" for t in required_topics)
    prompt = f"""다음 [필수 주제] 목록이 [답변]에 충분히 포함되어 있는지 평가하세요.
0.0~1.0 사이 숫자 하나만 출력하세요.
(1.0=모든 주제 충분히 반영, 0.5=절반 반영, 0.0=전혀 반영 안됨)

[필수 주제]
{topics_str}

[답변]
{answer[:2000]}

점수(숫자만):"""
    return _llm_judge(prompt, client)


# ── Rule-based ───────────────────────────────────────────────
def rule_check(answer: str, rules: dict) -> dict:
    """규칙 기반 평가.

    rules 구조:
        session_count_range : [min, max]   세션 수 범위
        total_hours         : int          총 교육 시간 (±2h 허용)
        groups_required     : list[str]    필수 그룹 ["A","B","C"]

    반환: {"passed": bool, "score": float, "details": {...}}
    """
    details: dict = {}
    results: list[bool] = []

    if "session_count_range" in rules:
        count = _count_sessions(answer)
        lo, hi = rules["session_count_range"]
        ok = lo <= count <= hi
        details["session_count"] = {"value": count, "expected": f"{lo}~{hi}", "pass": ok}
        results.append(ok)

    if "total_hours" in rules:
        hours = _extract_total_hours(answer)
        expected = rules["total_hours"]
        ok = hours is not None and abs(hours - expected) <= 2
        details["total_hours"] = {"value": hours, "expected": expected, "pass": ok}
        results.append(ok)

    if "groups_required" in rules:
        group_keywords = {
            "A": ["A그룹", "균형형", "이해형"],
            "B": ["B그룹", "과신형", "실행형"],
            "C": ["C그룹", "판단형", "조심형"],
        }
        found = {
            g: any(kw in answer for kw in group_keywords.get(g, [g]))
            for g in rules["groups_required"]
        }
        ok = all(found.values())
        details["groups_present"] = {"value": found, "pass": ok}
        results.append(ok)

    passed = all(results)
    score = round(sum(results) / len(results), 4) if results else 0.0
    return {"passed": passed, "score": score, "details": details}


# ── 내부 파서 ────────────────────────────────────────────────
def _count_sessions(text: str) -> int:
    # 명시적 번호 패턴
    numbered_patterns = [
        r"세션\s*\d+",
        r"Session\s*\d+",
        r"\d+\s*차시",
        r"모듈\s*\d+",
        r"Module\s*\d+",
        r"Day\s*\d+",
        r"\d+일\s*차",
    ]
    found: set[str] = set()
    for p in numbered_patterns:
        found.update(re.findall(p, text, re.IGNORECASE))

    # fallback: 스케줄 키워드가 포함된 마크다운 헤더 (## / ###)
    if not found:
        found = set(re.findall(
            r"^#{2,3}\s+.*(세션|Session|차시|실습|이론|오전|오후|모듈)",
            text, re.MULTILINE | re.IGNORECASE,
        ))

    # 2차 fallback: 오전/오후 블록 개수 (Day × 2)
    if not found:
        am_pm = re.findall(r"(오전|오후)\s*(세션|실습|이론|강의)", text)
        if am_pm:
            return len(am_pm)

    return len(found)


def _extract_total_hours(text: str) -> float | None:
    # "총 N시간" 우선
    m = re.search(r"총\s*(\d+(?:\.\d+)?)\s*시간", text)
    if m:
        return float(m.group(1))
    # "N일 (M시간)" → M이 총 시간
    m = re.search(r"\d+\s*일\s*[(\s]\s*(\d+(?:\.\d+)?)\s*시간", text)
    if m:
        return float(m.group(1))
    # 단독 "N시간"
    m = re.search(r"(\d+)\s*시간", text)
    if m:
        return float(m.group(1))
    return None
