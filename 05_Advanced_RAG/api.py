"""
AX Advanced RAG — FastAPI Backend
"""
import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

DATA_DIR   = Path(os.getenv("DATA_DIR",   "/app/data"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", "/app/chroma_db"))
PDF_PATH   = DATA_DIR / "AXCompass.pdf"
_ENV_KEY   = os.getenv("OPENAI_API_KEY", "")


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / filename)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


schemas   = _load("schemas",   "05_2.Schemas.py")
indexing  = _load("indexing",  "05_4.Indexing.py")
retrieval = _load("retrieval", "05_5.Retrieval.py")

_col: dict = {"inst": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _ENV_KEY and PDF_PATH.exists():
        try:
            _col["inst"] = indexing.init_vector_db(
                _ENV_KEY, CHROMA_DIR, PDF_PATH, lambda m: print(m, flush=True)
            )
            print("Vector DB ready", flush=True)
        except Exception as e:
            print(f"Startup DB init failed: {e}", flush=True)
    yield


app = FastAPI(title="AX Advanced RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 헬퍼 ─────────────────────────────────────────────────────
def _resolve_key(api_key: str) -> str:
    k = api_key or _ENV_KEY
    if not k:
        raise HTTPException(status_code=400, detail="API key required")
    return k


def _get_collection(api_key: str):
    if _col["inst"] is None:
        k = _resolve_key(api_key)
        _col["inst"] = indexing.init_vector_db(
            k, CHROMA_DIR, PDF_PATH, lambda m: None
        )
    return _col["inst"]


def _make_sse_generator(stream):
    def generate():
        try:
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {content}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        yield "data: [DONE]\n\n"
    return generate


# ── 요청 스키마 ───────────────────────────────────────────────
class InitReq(BaseModel):
    api_key: str = ""

class RetrieveReq(BaseModel):
    api_key: str = ""
    types: list[str]
    n_results: int = 6

class GenerateReq(BaseModel):
    api_key: str = ""
    edu_info: dict
    rag_ctx: str = ""

class ChatReq(BaseModel):
    api_key: str = ""
    llm_history: list[dict]
    new_message: str
    active_types: list[str] = []


# ── 엔드포인트 ────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "db_ready": _col["inst"] is not None}


@app.get("/api/config")
async def get_config():
    return {"has_env_key": bool(_ENV_KEY)}


@app.post("/api/init")
async def init_db(req: InitReq):
    k = _resolve_key(req.api_key)
    logs: list[str] = []
    _col["inst"] = indexing.init_vector_db(k, CHROMA_DIR, PDF_PATH, lambda m: logs.append(m))
    return {"status": "ok", "logs": logs}


@app.post("/api/retrieve")
async def retrieve_ctx(req: RetrieveReq):
    col = _get_collection(req.api_key)
    ctx = retrieval.retrieve_type_info(col, req.types, n_results=req.n_results)
    return {"context": ctx}


@app.post("/api/generate")
async def generate(req: GenerateReq):
    from openai import OpenAI
    k   = _resolve_key(req.api_key)
    edu = schemas.EducationInfo(**req.edu_info)
    user_msg = retrieval.build_user_message(edu, req.rag_ctx)
    msgs = [
        {"role": "system", "content": schemas.SYSTEM_PROMPT},
        {"role": "user",   "content": user_msg},
    ]
    client = OpenAI(api_key=k)
    stream = client.chat.completions.create(
        model="gpt-4o", messages=msgs, stream=True, temperature=0.7, max_tokens=6000,
    )
    return StreamingResponse(_make_sse_generator(stream)(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat(req: ChatReq):
    from openai import OpenAI
    k = _resolve_key(req.api_key)

    enriched = req.new_message
    col = _col["inst"]
    if col and req.active_types:
        enriched = retrieval.enrich_followup(req.new_message, col, req.active_types)

    msgs = [{"role": "system", "content": schemas.SYSTEM_PROMPT}]
    msgs += req.llm_history
    msgs.append({"role": "user", "content": enriched})

    client = OpenAI(api_key=k)
    stream = client.chat.completions.create(
        model="gpt-4o", messages=msgs, stream=True, temperature=0.7, max_tokens=6000,
    )
    return StreamingResponse(_make_sse_generator(stream)(), media_type="text/event-stream")
