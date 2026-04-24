"""
AgentTools — 4개 도구 구현
  rag_search, web_search, generate_curriculum, validate_curriculum
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# ── RAG 모듈 경로 (env 우선, 없으면 상대 경로) ────────────────────
_RAG_DIR = Path(os.getenv("RAG_DIR", str(Path(__file__).parent.parent.parent / "05_Advanced_RAG")))
CHROMA_DIR = str(Path(os.getenv("CHROMA_DIR", str(_RAG_DIR / "chroma_db"))))
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", str(Path(__file__).parent.parent / "prompts")))
COLLECTION_NAME = "ax_compass_types"
EMBED_MODEL = "text-embedding-3-small"
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")


def _load_rag_module(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = _RAG_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── OpenAI 도구 정의 ─────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "AX Compass 유형별 특성과 교육 접근법을 ChromaDB에서 검색합니다. 커리큘럼 생성 전 반드시 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 쿼리 (유형명과 교육 주제 포함 권장)",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "검색 결과 수 (기본값 6)",
                        "default": 6,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Tavily 검색 API를 사용하여 최신 AI 교육 트렌드나 특정 기술 정보를 웹에서 검색합니다. 커리큘럼 생성 전 반드시 1회 이상 호출하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 쿼리",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_curriculum",
            "description": "RAG 및 웹 검색 컨텍스트를 기반으로 맞춤형 AX 교육 커리큘럼을 생성합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rag_context": {
                        "type": "string",
                        "description": "rag_search로 가져온 AX Compass 유형별 특성 정보",
                    },
                    "web_context": {
                        "type": "string",
                        "description": "web_search로 가져온 최신 트렌드 정보 (없으면 빈 문자열)",
                        "default": "",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "이전 검증 실패 시 개선 피드백 (재생성 시 사용)",
                        "default": "",
                    },
                },
                "required": ["rag_context"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_curriculum",
            "description": "생성된 커리큘럼이 교육 요구사항(시간, 그룹 구성, 세션 수 등)을 충족하는지 검증합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "curriculum": {
                        "type": "string",
                        "description": "검증할 커리큘럼 텍스트",
                    }
                },
                "required": ["curriculum"],
            },
        },
    },
]


# ── AgentTools ────────────────────────────────────────────────────
class AgentTools:
    """에이전트 도구 구현체. education_info를 클로저로 보유."""

    def __init__(self, llm: OpenAI, education_info: dict, api_key: str):
        self.llm = llm
        self.education_info = education_info
        self._api_key = api_key

        # 상태 축적
        self.rag_context: str = ""
        self.web_context: str = ""
        self.curriculum: str | None = None
        self.validation_result: dict | None = None

        # 지연 초기화
        self._retriever = None
        self._schemas = None
        self._tavily = None

    # ── 내부 초기화 ────────────────────────────────────────────
    def _init_retriever(self):
        if self._retriever is not None:
            return
        retrieval = _load_rag_module("retrieval", "05_5.Retrieval.py")
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self._api_key, model_name=EMBED_MODEL
        )
        chroma = chromadb.PersistentClient(path=CHROMA_DIR)
        col = chroma.get_collection(name=COLLECTION_NAME, embedding_function=ef)
        reranker = retrieval.Reranker()
        self._retriever = retrieval.HybridRetriever(col, reranker=reranker, bm25_weight=1.0)

    def _init_schemas(self):
        if self._schemas is None:
            self._schemas = _load_rag_module("schemas", "05_2.Schemas.py")

    def _init_tavily(self):
        if self._tavily is not None:
            return
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if not tavily_key:
            print("[Tavily] ⚠️ TAVILY_API_KEY 환경변수가 비어있습니다.")
            return
        print(f"[Tavily] API 키 감지됨: {tavily_key[:10]}...")
        try:
            from tavily import TavilyClient
            self._tavily = TavilyClient(api_key=tavily_key)
            print("[Tavily] ✅ TavilyClient 초기화 성공")
        except ImportError:
            print("[Tavily] ❌ tavily-python 패키지가 설치되지 않았습니다. pip install tavily-python")
        except Exception as e:
            print(f"[Tavily] ❌ 초기화 실패: {e}")

    # ── 도구 1: RAG 검색 ────────────────────────────────────────
    def rag_search(self, query: str, n_results: int = 6) -> str:
        try:
            self._init_retriever()
            if not self._retriever or not self._retriever._ids:
                return json.dumps({"error": "ChromaDB 컬렉션이 비어 있습니다."}, ensure_ascii=False)
            docs, _ = self._retriever.query_debug(query, n_results=n_results)
            self.rag_context = docs
            preview = docs[:200] + "..." if len(docs) > 200 else docs
            return json.dumps(
                {"status": "ok", "docs_preview": preview, "length": len(docs)},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 도구 2: 웹 검색 ─────────────────────────────────────────
    def web_search(self, query: str) -> str:
        try:
            self._init_tavily()
            if not self._tavily:
                return json.dumps(
                    {"status": "unavailable", "message": "TAVILY_API_KEY 미설정"},
                    ensure_ascii=False,
                )
            results = self._tavily.search(query, max_results=5)
            snippets = [r.get("content", "")[:300] for r in results.get("results", [])]
            self.web_context = "\n\n".join(snippets)
            return json.dumps(
                {"status": "ok", "snippets": snippets[:3]}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 도구 3: 커리큘럼 생성 ───────────────────────────────────
    def generate_curriculum(
        self,
        rag_context: str,
        web_context: str = "",
        feedback: str = "",
    ) -> str:
        try:
            self._init_schemas()
            # LLM이 web_context를 빈 문자열로 넘겨도 자동 수집된 컨텍스트 사용
            if not web_context and self.web_context:
                web_context = self.web_context
            info = self.education_info
            topics = ", ".join(info.get("topics", []))
            if info.get("extra"):
                topics += f", {info['extra']}"

            counts = info.get("type_counts", {})
            from .schemas import ALL_TYPES, GROUPS
            _all_types = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
            _groups = {"A": ["균형형", "이해형"], "B": ["과신형", "실행형"], "C": ["판단형", "조심형"]}
            type_detail = "\n".join(f"  - {t}: {counts.get(t, 0)}명" for t in _all_types)
            group_counts = {g: sum(counts.get(t, 0) for t in ts) for g, ts in _groups.items()}
            total = sum(counts.values())

            rag_section = (
                "[AX Compass 유형별 특성 참고 자료]\n"
                f"{rag_context}\n\n---\n"
            ) if rag_context else ""

            web_section = (
                "\n[최신 AI 교육 트렌드 참고]\n"
                f"{web_context}\n\n---\n"
            ) if web_context else ""

            feedback_section = (
                f"\n[이전 검증 실패 피드백 — 반드시 반영할 것]\n{feedback}\n\n---\n"
            ) if feedback else ""

            user_msg = (
                f"{rag_section}{web_section}{feedback_section}"
                f"다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.\n\n"
                f"- **회사명**: {info.get('company', '')}\n"
                f"- **교육 목표**: {info.get('goal', '')}\n"
                f"- **교육 대상**: {info.get('audience', '')}\n"
                f"- **교육 수준**: {info.get('level', '')}\n"
                f"- **교육 주제**: {topics}\n"
                f"- **교육 기간**: {info.get('duration', '')}\n\n"
                f"**AX Compass 진단 결과 유형별 인원:**\n{type_detail}\n\n"
                f"**그룹 구성:**\n"
                f"  - A그룹 (균형형+이해형): {group_counts['A']}명\n"
                f"  - B그룹 (과신형+실행형): {group_counts['B']}명\n"
                f"  - C그룹 (판단형+조심형): {group_counts['C']}명\n"
                f"  - 총 인원: {total}명\n\n"
                "이론 수업은 전체 동일하게 진행하되, 각 그룹별 특성에 맞는 맞춤형 실습/프로젝트를 설계해주세요.\n"
                "- A그룹 (균형형+이해형): AI 활용 이해도가 높거나 학습 의욕이 강한 그룹. 심화 프로젝트 중심.\n"
                "- B그룹 (과신형+실행형): 행동력과 실행력이 높지만 검증과 품질 관리가 필요한 그룹. 실행+검증 프로세스 중심.\n"
                "- C그룹 (판단형+조심형): 신중하고 분석적이지만 실행에 심리적 장벽이 있는 그룹. 체계적 단계별 실습 중심."
            )

            system_prompt = self._schemas.SYSTEM_PROMPT if self._schemas else "맞춤형 AX 교육 커리큘럼을 설계합니다."

            resp = self.llm.chat.completions.create(
                model=GEN_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            self.curriculum = resp.choices[0].message.content
            return json.dumps(
                {"status": "ok", "curriculum_length": len(self.curriculum)},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 도구 4: 커리큘럼 검증 ───────────────────────────────────
    def validate_curriculum(self, curriculum: str) -> str:
        info = self.education_info
        duration_str = info.get("duration", "")

        # 총 교육 시간 파싱: "3일 (24시간)" → 24
        hours_match = re.search(r"(\d+)\s*시간", duration_str)
        expected_hours = int(hours_match.group(1)) if hours_match else None

        # 교육 일수 파싱: "3일 (24시간)" → 3
        days_match = re.search(r"(\d+)\s*일", duration_str)
        expected_days = int(days_match.group(1)) if days_match else None

        issues = []
        details: dict = {}

        # ① 총 시간 검증 (유연하게: 총 시간 언급 OR 일수 언급 OR 일별 시간 합산)
        if expected_hours:
            hour_mentions = re.findall(r"(\d+)\s*시간", curriculum)
            found_hours = [int(h) for h in hour_mentions]
            day_mentions = re.findall(r"(\d+)\s*일", curriculum)
            found_days = [int(d) for d in day_mentions]
            details["expected_hours"] = expected_hours
            details["found_hour_mentions"] = found_hours

            # 총 시간이 직접 언급되었거나, 일수가 언급되었거나, 일별 시간 합산이 맞으면 통과
            hours_ok = (
                any(h == expected_hours for h in found_hours)  # "24시간" 직접 언급
                or (expected_days and any(d == expected_days for d in found_days))  # "3일" 언급
                or (sum(found_hours) >= expected_hours * 0.8)  # 일별 시간 합산이 80% 이상
            )
            if not hours_ok:
                issues.append(f"총 교육 시간 {expected_hours}시간 또는 {expected_days}일이 커리큘럼에 명시되지 않음")

        # ② 그룹 검증 (A, B, C) — 다양한 표기 패턴 허용
        groups_found = []
        for g in ["A", "B", "C"]:
            pattern = rf"{g}\s*그룹|그룹\s*{g}|Group\s*{g}|{g}조|{g}\s*팀|{g}\s*반"
            if re.search(pattern, curriculum, re.IGNORECASE):
                groups_found.append(g)
        details["groups_found"] = groups_found
        missing_groups = [g for g in ["A", "B", "C"] if g not in groups_found]
        if missing_groups:
            issues.append(f"누락된 그룹: {', '.join(missing_groups)}그룹")

        # ③ 세션/모듈 수 검증 — 더 다양한 패턴 허용
        module_patterns = r"모듈\s*\d+|세션\s*\d+|Session\s*\d+|Day\s*\d+|\d+일차|\d+일\s*차|Part\s*\d+"
        module_count = len(re.findall(module_patterns, curriculum, re.IGNORECASE))
        details["module_count"] = module_count
        if module_count == 0:
            issues.append("모듈/세션 구분이 없음")

        # ④ 핵심 주제 검증 — 키워드 기반 부분 매칭 (정확한 문자열 대신 핵심 단어 포함 여부)
        topics = info.get("topics", [])
        missing_topics = []
        for topic in topics:
            # 주제에서 핵심 키워드 추출 (2글자 이상 단어)
            keywords = [w for w in re.split(r'[,\s·및과를의에서]+', topic) if len(w) >= 2]
            if not keywords:
                continue
            # 핵심 키워드 중 절반 이상이 커리큘럼에 포함되면 통과
            matched = sum(1 for kw in keywords if kw in curriculum)
            if matched < max(1, len(keywords) * 0.4):
                missing_topics.append(topic)
        if missing_topics:
            issues.append(f"누락된 주제: {', '.join(missing_topics[:3])}")
        details["missing_topics"] = missing_topics

        passed = len(issues) == 0
        score = max(0.0, 1.0 - len(issues) * 0.2)

        self.validation_result = {
            "passed": passed,
            "score": round(score, 2),
            "issues": issues,
            "details": details,
        }

        return json.dumps(self.validation_result, ensure_ascii=False)

    # ── 도구 디스패처 ───────────────────────────────────────────
    def call(self, name: str, arguments: dict) -> str:
        dispatch = {
            "rag_search": self.rag_search,
            "web_search": self.web_search,
            "generate_curriculum": self.generate_curriculum,
            "validate_curriculum": self.validate_curriculum,
        }
        fn = dispatch.get(name)
        if fn is None:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        return fn(**arguments)
