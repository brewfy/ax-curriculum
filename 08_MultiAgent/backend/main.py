"""
FastAPI 백엔드 — 08_MultiAgent
추가 기능: 커리큘럼 결과 JSON 저장 / 목록 조회 / 다운로드
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent.parent / ".env")           # 워크스페이스 루트
load_dotenv(Path(__file__).parent.parent / ".env", override=True)   # 08_MultiAgent/.env

from .auth import authenticate, create_token, verify_token
from .schemas import (
    ChatRequest,
    ChatResponse,
    CurriculumRecord,
    LoginRequest,
    TokenResponse,
)
from .orchestrator import MultiAgentOrchestrator

app = FastAPI(title="AX MultiAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api_key = os.getenv("OPENAI_API_KEY", "")
_llm = OpenAI(api_key=_api_key)

# 커리큘럼 저장 디렉터리
_OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(Path(__file__).parent.parent / "outputs")))
_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ── 커리큘럼 저장 헬퍼 ───────────────────────────────────────────

def _save_curriculum(
    company: str,
    curriculum: str,
    validation: dict | None,
) -> CurriculumRecord:
    cid = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_company = "".join(c if c.isalnum() or c in "-_" else "_" for c in company)
    filename = f"{now}_{safe_company}_{cid}.md"
    md_path = _OUTPUTS_DIR / filename

    # 마크다운 파일 저장
    md_path.write_text(curriculum, encoding="utf-8")

    # 메타 JSON 저장
    passed = validation.get("passed", False) if validation else False
    score = validation.get("score", 0.0) if validation else 0.0
    meta = {
        "id": cid,
        "company": company,
        "created_at": now,
        "passed": passed,
        "score": score,
        "filename": filename,
        "validation": validation,
    }
    (_OUTPUTS_DIR / f"{filename}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return CurriculumRecord(
        id=cid,
        company=company,
        created_at=now,
        passed=passed,
        score=score,
        filename=filename,
    )


def _list_records() -> list[CurriculumRecord]:
    records: list[CurriculumRecord] = []
    for meta_file in sorted(_OUTPUTS_DIR.glob("*.json"), reverse=True):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            records.append(CurriculumRecord(**{k: meta[k] for k in CurriculumRecord.model_fields}))
        except Exception:
            continue
    return records


# ── 인증 ──────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if not authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(req.username))


@app.get("/auth/verify")
def verify(username: str = Depends(verify_token)):
    return {"username": username, "valid": True}


# ── 헬스 ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ax-multi-agent"}


# ── 채팅 (블로킹) ─────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, _username: str = Depends(verify_token)):
    edu_info = _flatten_edu_info(req)
    orchestrator = MultiAgentOrchestrator(llm=_llm, education_info=edu_info, api_key=_api_key)
    user_messages = _extract_user_messages(req)
    result = orchestrator.run(user_messages)

    record = None
    if result.curriculum:
        record = _save_curriculum(
            edu_info.get("company", "unknown"),
            result.curriculum,
            result.validation_result,
        )

    return ChatResponse(
        reply=result.reply,
        complete=result.complete,
        curriculum=result.curriculum,
        validation_result=result.validation_result,
        agent_steps=result.agent_steps,
        curriculum_id=record.id if record else None,
    )


# ── 채팅 스트리밍 (SSE) ───────────────────────────────────────────

@app.post("/chat/stream")
def chat_stream(req: ChatRequest, _username: str = Depends(verify_token)):
    edu_info = _flatten_edu_info(req)
    orchestrator = MultiAgentOrchestrator(llm=_llm, education_info=edu_info, api_key=_api_key)
    user_messages = _extract_user_messages(req)

    def event_stream():
        curriculum_buf: str | None = None
        validation_buf: dict | None = None
        try:
            for event in orchestrator.run_stream(user_messages):
                if event.get("type") == "result":
                    curriculum_buf = event.get("curriculum")
                    validation_buf = event.get("validation_result")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        # 커리큘럼 자동 저장
        if curriculum_buf:
            try:
                record = _save_curriculum(
                    edu_info.get("company", "unknown"),
                    curriculum_buf,
                    validation_buf,
                )
                yield f"data: {json.dumps({'type': 'saved', 'curriculum_id': record.id, 'filename': record.filename}, ensure_ascii=False)}\n\n"
            except Exception:
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── 커리큘럼 목록 ─────────────────────────────────────────────────

@app.get("/curricula", response_model=list[CurriculumRecord])
def list_curricula(_username: str = Depends(verify_token)):
    return _list_records()


# ── 커리큘럼 다운로드 ─────────────────────────────────────────────

@app.get("/curricula/{curriculum_id}/download")
def download_curriculum(curriculum_id: str, _username: str = Depends(verify_token)):
    matches = list(_OUTPUTS_DIR.glob(f"*_{curriculum_id}.md"))
    if not matches:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    path = matches[0]
    return FileResponse(
        path=str(path),
        media_type="text/markdown",
        filename=path.name,
    )


# ── 커리큘럼 상세 (JSON) ──────────────────────────────────────────

@app.get("/curricula/{curriculum_id}")
def get_curriculum(curriculum_id: str, _username: str = Depends(verify_token)):
    matches = list(_OUTPUTS_DIR.glob(f"*_{curriculum_id}.md.json"))
    if not matches:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return json.loads(matches[0].read_text(encoding="utf-8"))


# ── 내부 헬퍼 ────────────────────────────────────────────────────

def _flatten_edu_info(req: ChatRequest) -> dict:
    info = req.education_info.model_dump()
    info["type_counts"] = req.education_info.type_counts.model_dump()
    return info


def _extract_user_messages(req: ChatRequest) -> list[dict]:
    msgs = [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant")
    ]
    return msgs or [{"role": "user", "content": "교육 커리큘럼을 설계해주세요."}]
