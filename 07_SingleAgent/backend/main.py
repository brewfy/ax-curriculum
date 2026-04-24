"""
FastAPI 백엔드 — 07_SingleAgent
"""
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .auth import authenticate, create_token, verify_token
from .schemas import ChatRequest, ChatResponse, LoginRequest, TokenResponse
from .agent import SingleAgent

app = FastAPI(title="AX SingleAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api_key = os.getenv("OPENAI_API_KEY", "")
_llm = OpenAI(api_key=_api_key)


# ── 인증 ──────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if not authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(req.username)
    return TokenResponse(access_token=token)


@app.get("/auth/verify")
def verify(username: str = Depends(verify_token)):
    return {"username": username, "valid": True}


# ── 헬스 ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "ax-single-agent"}


# ── 채팅 ──────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, username: str = Depends(verify_token)):
    edu_info = req.education_info.model_dump()
    # TypeCounts 모델 → dict 평탄화
    edu_info["type_counts"] = req.education_info.type_counts.model_dump()

    agent = SingleAgent(llm=_llm, education_info=edu_info, api_key=_api_key)

    user_messages = [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant")
    ]
    if not user_messages:
        user_messages = [{"role": "user", "content": "교육 커리큘럼을 설계해주세요."}]

    result = agent.run(user_messages)
    return ChatResponse(
        reply=result.reply,
        complete=result.complete,
        curriculum=result.curriculum,
        validation_result=result.validation_result,
        agent_steps=result.agent_steps,
    )
