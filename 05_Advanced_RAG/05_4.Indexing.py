"""
ChromaDB 벡터 DB 초기화 및 PDF 인덱싱
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import pypdf


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

COLLECTION_NAME = "ax_compass_types"


def extract_pdf_chunks(pdf_path: Path) -> list[str]:
    """PDF에서 텍스트를 추출하고 단락 단위로 분할합니다."""
    reader = pypdf.PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages:
        text = page.extract_text() or ""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks.extend(paragraphs)
    return chunks


def _pdf_hash(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    with open(pdf_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def init_vector_db(
    api_key: str,
    chroma_dir: Path,
    pdf_path: Path,
    status_callback=None,
) -> chromadb.Collection:
    """ChromaDB 컬렉션을 초기화하고 반환합니다.

    이미 최신 인덱스가 있으면 재사용하고, 변경이 감지되면 재인덱싱합니다.
    status_callback(msg: str) 으로 진행 상황을 전달할 수 있습니다.
    """
    def _log(msg: str):
        if status_callback:
            status_callback(msg)

    embedding_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )

    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))

    current_hash = _pdf_hash(pdf_path)
    existing_names = [c.name for c in client.list_collections()]
    needs_ingest = True

    if COLLECTION_NAME in existing_names:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
        try:
            meta = collection.get(ids=["_meta_hash"])
            if meta["documents"] and meta["documents"][0] == current_hash:
                needs_ingest = False
                _log("벡터 DB: 기존 인덱스 재사용")
        except Exception:
            pass
    else:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    if needs_ingest:
        _log("벡터 DB: 문서 인덱싱 중...")

        try:
            existing = collection.get()
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

        docs, ids, metas = [], [], []

        for doc in schemas.AX_COMPASS_DOCS:
            docs.append(doc["content"])
            ids.append(doc["id"])
            metas.append({
                "type": doc["type"],
                "code": doc["code"],
                "group": doc["group"],
                "source": "ax_compass_structured",
            })

        if pdf_path.exists():
            try:
                _log(f"벡터 DB: PDF 추출 중 ({pdf_path.name})...")
                chunks = extract_pdf_chunks(pdf_path)
                for i, chunk in enumerate(chunks):
                    if len(chunk.strip()) > 100:
                        docs.append(chunk)
                        ids.append(f"pdf_chunk_{i}")
                        metas.append({"source": "ax_compass_pdf", "chunk_index": i})
            except Exception as e:
                _log(f"PDF 추출 경고: {e}")
        else:
            _log(f"PDF 없음: {pdf_path} — 구조화 문서만 사용")

        docs.append(current_hash)
        ids.append("_meta_hash")
        metas.append({"source": "meta"})

        collection.add(documents=docs, ids=ids, metadatas=metas)
        _log(f"벡터 DB: {len(docs) - 1}개 문서 인덱싱 완료")

    return collection
