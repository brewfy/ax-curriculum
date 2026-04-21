"""
ChromaDB 벡터 DB 초기화 및 인덱싱 파이프라인

개선 사항:
  - 문서 종류별 전략 분리 (StructuredDocIndexer / PDFDocIndexer)
  - 청킹 전 구조 보존 전처리 (섹션 파싱 / 헤더 감지)
  - 검색 친화적 메타데이터 확장 (doc_type, section, page, keywords 등)
  - content_hash 기반 증분 인덱싱 (변경된 청크만 재임베딩)
  - Contextual Embedding: LLM이 청크별 컨텍스트를 생성하여 임베딩 품질 향상
"""
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import pypdf


# ── 형제 모듈 로드 헬퍼 ──────────────────────────────────────────
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


# ── Contextual Embedding ─────────────────────────────────────────
class ContextualEmbedder:
    """Anthropic Contextual Retrieval: LLM으로 청크별 컨텍스트를 생성하여 임베딩 품질을 향상시킨다.

    각 청크에 대해 전체 문서 맥락을 참고한 1-2문장 설명을 prepend하므로,
    벡터 검색 시 청크 단독으로는 잡기 어렵던 상위 개념 쿼리도 히트된다.
    """

    MODEL = "gpt-4o-mini"
    CACHE_FILE = "contextual_cache.json"

    def __init__(self, api_key: str, cache_dir: Path | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._cache_path = (cache_dir or Path(".")) / self.CACHE_FILE
        self._cache: dict[str, str] = self._load_cache()

    def _load_cache(self) -> dict:
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cache(self):
        try:
            self._cache_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _call_llm(self, doc_summary: str, chunk_text: str) -> str:
        prompt = (
            "다음은 AX Compass 교육 관련 문서와 그 일부 청크입니다.\n"
            "전체 문서 맥락에서 이 청크가 어떤 내용을 담고 있는지 한국어로 1-2문장으로 설명해주세요. "
            "설명만 출력하세요.\n\n"
            f"<document>\n{doc_summary[:1500]}\n</document>\n\n"
            f"<chunk>\n{chunk_text[:600]}\n</chunk>"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return ""

    def enrich(self, doc_summary: str, chunk_text: str) -> str:
        """청크에 LLM 생성 컨텍스트를 prepend한 enriched text를 반환한다."""
        cache_key = hashlib.sha256((doc_summary[:200] + chunk_text).encode()).hexdigest()[:20]
        if cache_key not in self._cache:
            self._cache[cache_key] = self._call_llm(doc_summary, chunk_text)
            self._save_cache()
        ctx = self._cache[cache_key]
        return f"{ctx}\n\n{chunk_text}" if ctx else chunk_text


# ── 인덱스 아이템 ────────────────────────────────────────────────
@dataclass
class IndexItem:
    id: str
    content: str
    metadata: dict

    @classmethod
    def make(cls, uid: str, content: str, metadata: dict) -> "IndexItem":
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return cls(
            id=uid,
            content=content,
            metadata={
                **metadata,
                "content_hash": content_hash,
                "char_count": len(content),
            },
        )


# ── 전략 1: 구조화 문서 인덱서 ───────────────────────────────────
class StructuredDocIndexer:
    """AX_COMPASS_DOCS 구조화 문서 인덱싱 전략.

    문서를 전체(full)와 섹션 단위(강점 / 도전 과제 / 교육 접근법 / 대표 태그)로
    분리하여 인덱싱하므로, 세부 질의에서도 정확한 청크를 검색할 수 있다.
    """

    DOC_TYPE = "structured"

    _SECTION_MAP = {
        "강점": "strengths",
        "도전 과제": "challenges",
        "교육 접근법": "education_approach",
        "대표 태그": "tags",
    }

    def __init__(self, docs: list[dict], embedder: "ContextualEmbedder | None" = None):
        self.docs = docs
        self.embedder = embedder

    def build_items(self) -> list[IndexItem]:
        items = []
        for doc in self.docs:
            items.extend(self._index_doc(doc))
        return items

    # ── 단일 문서 처리 ──────────────────────────────────────────
    def _index_doc(self, doc: dict) -> list[IndexItem]:
        base_meta = {
            "doc_type": self.DOC_TYPE,
            "source": "ax_compass_structured",
            "type": doc["type"],
            "type_code": doc["code"],
            "group": doc["group"],
            "keywords": f"{doc['type']} {doc['code']} {doc['group']}그룹 AX Compass",
        }

        full_content = doc["content"].strip()
        items = []

        # 전체 문서 (primary chunk — 기존 retrieval 호환 유지, 컨텍스트 불필요)
        items.append(IndexItem.make(
            doc["id"],
            full_content,
            {**base_meta, "section": "full", "is_primary": 1},
        ))

        # 섹션별 세부 청크 (Contextual Embedding 적용)
        for section_name, section_text in self._parse_sections(doc["content"]).items():
            if len(section_text.strip()) < 30:
                continue
            section_key = self._SECTION_MAP.get(section_name, section_name)
            chunk_text = f"[{doc['type']} / {doc['code']}] {section_name}:\n{section_text.strip()}"
            if self.embedder:
                chunk_text = self.embedder.enrich(full_content, chunk_text)
            items.append(IndexItem.make(
                f"{doc['id']}_{section_key}",
                chunk_text,
                {
                    **base_meta,
                    "section": section_key,
                    "section_title": section_name,
                    "is_primary": 0,
                },
            ))

        return items

    def _parse_sections(self, content: str) -> dict[str, str]:
        """문서 본문에서 섹션 헤더를 감지하고 섹션별 텍스트를 추출한다."""
        sections: dict[str, list[str]] = {}
        current: str | None = None

        for line in content.split("\n"):
            stripped = line.strip()
            # 헤더: 알려진 섹션명 (콜론 포함/불포함 모두 허용)
            matched = next(
                (s for s in self._SECTION_MAP if stripped.rstrip(":") == s),
                None,
            )
            if matched:
                current = matched
                sections.setdefault(current, [])
            elif current and stripped:
                sections[current].append(stripped)

        return {k: "\n".join(v) for k, v in sections.items() if v}


# ── 전략 2: PDF 문서 인덱서 ──────────────────────────────────────
class PDFDocIndexer:
    """PDF 파일 인덱싱 전략.

    페이지 경계와 헤더를 인식하여 구조를 보존하며 청킹하고,
    page_start / page_end / section_title 메타데이터를 기록한다.
    """

    DOC_TYPE = "pdf"
    CHUNK_SIZE = 800
    OVERLAP = 150
    MIN_LEN = 100

    def __init__(self, pdf_path: Path, embedder: "ContextualEmbedder | None" = None):
        self.pdf_path = pdf_path
        self._stem = pdf_path.stem
        self.embedder = embedder

    def build_items(self) -> list[IndexItem]:
        if not self.pdf_path.exists():
            return []
        try:
            reader = pypdf.PdfReader(str(self.pdf_path))
        except Exception:
            return []

        raw_pages = self._extract_pages(reader)
        chunks = self._chunk(raw_pages)

        # PDF 전체 요약 (첫 2페이지) — 컨텍스트 생성 시 참고용
        doc_summary = " ".join(
            line
            for page in raw_pages[:2]
            for line in page["lines"]
        )[:1200]

        items = []
        for i, chunk in enumerate(chunks):
            text = chunk["text"].strip()
            if len(text) < self.MIN_LEN:
                continue
            if self.embedder:
                text = self.embedder.enrich(doc_summary, text)
            meta = {
                "doc_type": self.DOC_TYPE,
                "source": "ax_compass_pdf",
                "source_file": self.pdf_path.name,
                "chunk_index": i,
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "section_title": chunk.get("section_title", ""),
            }
            items.append(IndexItem.make(f"pdf_{self._stem}_{i}", text, meta))

        return items

    # ── 페이지 추출 ─────────────────────────────────────────────
    def _extract_pages(self, reader: pypdf.PdfReader) -> list[dict]:
        pages = []
        for pnum, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            pages.append({"page_num": pnum, "lines": lines})
        return pages

    # ── 헤더 판별 ──────────────────────────────────────────────
    @staticmethod
    def _is_header(line: str) -> bool:
        s = line.strip()
        if not s or len(s) > 60:
            return False
        if s[0] in "-•*·①②③":
            return False
        return bool(
            s.isupper()
            or s.endswith(":")
            or re.match(r"^\d+[\.\)]\s+\S", s)
            or re.match(r"^[가-힣\s]{2,20}$", s)
        )

    # ── 구조 보존 청킹 ─────────────────────────────────────────
    def _chunk(self, pages: list[dict]) -> list[dict]:
        chunks: list[dict] = []
        buf = ""
        page_start = 1
        cur_section = ""

        def flush(page_end: int):
            nonlocal buf, page_start
            if buf.strip():
                chunks.append({
                    "text": buf.strip(),
                    "page_start": page_start,
                    "page_end": page_end,
                    "section_title": cur_section,
                })
            buf = ""

        for page in pages:
            pnum = page["page_num"]
            for line in page["lines"]:
                is_hdr = self._is_header(line)

                # 헤더 도달 시 현재 버퍼가 충분히 차 있으면 분리
                if is_hdr and len(buf) > self.CHUNK_SIZE // 3:
                    flush(pnum)
                    page_start = pnum

                if is_hdr:
                    cur_section = line

                buf += line + "\n"

                # 크기 초과 시 오버랩 포함하여 분리
                if len(buf) >= self.CHUNK_SIZE:
                    overlap = buf[-self.OVERLAP:]
                    flush(pnum)
                    page_start = pnum
                    buf = overlap

        last_page = pages[-1]["page_num"] if pages else 1
        flush(last_page)
        return chunks


# ── 증분 인덱서 ──────────────────────────────────────────────────
class IncrementalIndexer:
    """content_hash를 비교하여 변경된 청크만 재임베딩하는 증분 인덱서.

    신규 소스를 추가하려면 새 전략 클래스를 만들고 build_items()를 구현한 뒤
    init_vector_db()에서 sync()를 한 번 더 호출하면 된다.
    """

    def __init__(self, collection: chromadb.Collection):
        self.col = collection

    def get_existing(self, doc_type: str) -> dict[str, str]:
        """DB에서 {id: content_hash} 맵을 반환한다."""
        try:
            result = self.col.get(
                where={"doc_type": doc_type},
                include=["metadatas"],
            )
            return {
                rid: (meta.get("content_hash") or "")
                for rid, meta in zip(result["ids"], result["metadatas"])
            }
        except Exception:
            return {}

    def sync(
        self,
        items: list[IndexItem],
        doc_type: str,
        log=None,
    ) -> dict:
        """items와 현재 DB를 비교하여 추가 / 업데이트 / 삭제를 수행한다."""
        existing = self.get_existing(doc_type)
        new_map = {item.id: item for item in items}

        # 사라진 ID 삭제
        to_delete = [k for k in existing if k not in new_map]

        # 신규 또는 해시가 달라진 것만 upsert (임베딩 API 호출 최소화)
        to_upsert = [
            item for item in items
            if item.id not in existing
            or existing[item.id] != item.metadata.get("content_hash")
        ]

        if to_delete:
            self.col.delete(ids=to_delete)
        if to_upsert:
            self.col.upsert(
                ids=[i.id for i in to_upsert],
                documents=[i.content for i in to_upsert],
                metadatas=[i.metadata for i in to_upsert],
            )

        stats = {
            "added": sum(1 for i in to_upsert if i.id not in existing),
            "updated": sum(1 for i in to_upsert if i.id in existing),
            "deleted": len(to_delete),
        }
        if log:
            log(f"  +{stats['added']} 추가  ~{stats['updated']} 업데이트  -{stats['deleted']} 삭제")
        return stats

    def _cleanup_old_schema(self) -> None:
        """doc_type 필드가 없는 구버전 문서를 제거한다 (마이그레이션)."""
        try:
            all_docs = self.col.get(include=["metadatas"])
            old_ids = [
                rid for rid, meta in zip(all_docs["ids"], all_docs["metadatas"])
                if not meta.get("doc_type") and not rid.startswith("_")
            ]
            if old_ids:
                self.col.delete(ids=old_ids)
        except Exception:
            pass


# ── 유틸 ────────────────────────────────────────────────────────
def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ── 공개 API ─────────────────────────────────────────────────────
def init_vector_db(
    api_key: str,
    chroma_dir: Path,
    pdf_path: Path,
    status_callback=None,
) -> chromadb.Collection:
    """ChromaDB 컬렉션을 초기화하고 반환한다.

    증분 인덱싱을 사용하므로 변경된 청크만 재임베딩된다.
    새 문서 소스를 추가하려면 이 함수 내에 전략 인스턴스를 추가하면 된다.
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

    existing_names = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing_names:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    else:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    inc = IncrementalIndexer(collection)
    inc._cleanup_old_schema()

    # ── Contextual Embedder (섹션·PDF 청크에 LLM 컨텍스트 prepend) ─
    embedder = ContextualEmbedder(api_key, cache_dir=chroma_dir)

    # ── 전략 1: 구조화 문서 ─────────────────────────────────────
    _log("벡터 DB: 구조화 문서 동기화 중...")
    structured_items = StructuredDocIndexer(schemas.AX_COMPASS_DOCS, embedder).build_items()
    inc.sync(structured_items, StructuredDocIndexer.DOC_TYPE, _log)

    # ── 전략 2: PDF 문서 (파일 해시 비교 후 필요 시만 재인덱싱) ──
    pdf_hash = _file_hash(pdf_path)
    meta_id = f"_meta_pdf_{pdf_path.stem}"
    try:
        stored = collection.get(ids=[meta_id])
        stored_hash = stored["documents"][0] if stored["documents"] else ""
    except Exception:
        stored_hash = ""

    if pdf_hash != stored_hash:
        if pdf_path.exists():
            _log(f"벡터 DB: PDF 변경 감지 — 인덱싱 중 ({pdf_path.name})...")
            pdf_items = PDFDocIndexer(pdf_path, embedder).build_items()
            inc.sync(pdf_items, PDFDocIndexer.DOC_TYPE, _log)
        else:
            _log(f"PDF 없음: {pdf_path} — PDF 인덱스 초기화")
            inc.sync([], PDFDocIndexer.DOC_TYPE, _log)

        # 파일 해시 갱신
        try:
            collection.delete(ids=[meta_id])
        except Exception:
            pass
        if pdf_hash:
            collection.add(
                ids=[meta_id],
                documents=[pdf_hash],
                metadatas=[{"source": "meta", "doc_type": "meta"}],
            )
    else:
        _log("벡터 DB: PDF 변경 없음 — 기존 인덱스 재사용")

    total = max(0, collection.count() - 1)  # meta 문서 제외
    _log(f"벡터 DB: 총 {total}개 청크 준비 완료")
    return collection
