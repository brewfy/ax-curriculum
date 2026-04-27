"""
Retrieval 헬퍼 — ChromaDB + HybridRetriever 초기화를 한 곳에서 관리.
에이전트들이 직접 importlib 분기 없이 이 모듈만 import해서 사용.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_RAG_DIR = Path(os.getenv("RAG_DIR", str(Path(__file__).parent.parent.parent / "05_Advanced_RAG")))
CHROMA_DIR = str(Path(os.getenv("CHROMA_DIR", str(_RAG_DIR / "chroma_db"))))
COLLECTION_NAME = "ax_compass_types"
EMBED_MODEL = "text-embedding-3-small"


def _load_module(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = _RAG_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def get_retriever(api_key: str):
    """HybridRetriever 싱글턴 — api_key 단위로 캐시."""
    retrieval = _load_module("retrieval_mod", "05_5.Retrieval.py")
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key, model_name=EMBED_MODEL
    )
    chroma = chromadb.PersistentClient(path=CHROMA_DIR)
    col = chroma.get_collection(name=COLLECTION_NAME, embedding_function=ef)
    reranker = retrieval.Reranker()
    return retrieval.HybridRetriever(col, reranker=reranker, bm25_weight=1.0)


def search(query: str, api_key: str, n_results: int = 6) -> tuple[str, bool]:
    """
    Returns (docs_text, success).
    success=False이면 docs_text는 오류 메시지.
    """
    try:
        retriever = get_retriever(api_key)
        if not retriever._ids:
            return "ChromaDB 컬렉션이 비어 있습니다.", False
        docs, _ = retriever.query_debug(query, n_results=n_results)
        return docs, True
    except Exception as e:
        return str(e), False


def get_gen_system_prompt() -> str:
    """05_Advanced_RAG Schemas 모듈의 SYSTEM_PROMPT 반환 (없으면 기본값)."""
    try:
        schemas = _load_module("rag_schemas", "05_2.Schemas.py")
        return schemas.SYSTEM_PROMPT
    except Exception:
        return "맞춤형 AX 교육 커리큘럼을 설계합니다."
