from typing import Optional
from pydantic import BaseModel

ALL_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
GROUPS = {"A": ["균형형", "이해형"], "B": ["과신형", "실행형"], "C": ["판단형", "조심형"]}


class TypeCounts(BaseModel):
    균형형: int = 0
    이해형: int = 0
    과신형: int = 0
    실행형: int = 0
    판단형: int = 0
    조심형: int = 0

    def dominant(self, n: int = 3) -> list[str]:
        d = self.model_dump()
        return sorted(d, key=lambda k: d[k], reverse=True)[:n]

    def group_count(self, group: str) -> int:
        d = self.model_dump()
        return sum(d.get(t, 0) for t in GROUPS.get(group, []))

    def total(self) -> int:
        return sum(self.model_dump().values())


class EducationInfo(BaseModel):
    company: str
    goal: str
    audience: str
    level: str
    topics: list[str]
    extra: str = ""
    duration: str
    type_counts: TypeCounts


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    education_info: EducationInfo


class ChatResponse(BaseModel):
    reply: str
    complete: bool = False
    curriculum: Optional[str] = None
    validation_result: Optional[dict] = None
    agent_steps: list[str] = []


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
