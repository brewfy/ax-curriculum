"""
08_MultiAgent — Pydantic 스키마
평가 스키마: 코드 검증 항목(code_checks)과 LLM 판단 항목(llm_checks) 명확히 분리
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

ALL_TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]
GROUPS = {"A": ["균형형", "이해형"], "B": ["과신형", "실행형"], "C": ["판단형", "조심형"]}


# ── 교육 정보 ────────────────────────────────────────────────────

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


# ── 평가 스키마 (코드 검증 / LLM 판단 분리) ──────────────────────

class CodeCheckResult(BaseModel):
    """규칙 기반(정규식·집계) 항목 — 결정론적"""
    hours_ok: bool = False
    groups_ok: bool = False          # A·B·C 세 그룹 모두 존재
    modules_ok: bool = False         # 1개 이상의 세션/모듈 패턴
    topics_ok: bool = False          # 핵심 주제 40% 이상 커버
    groups_found: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    module_count: int = 0
    expected_hours: Optional[int] = None
    found_hour_mentions: list[int] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.hours_ok and self.groups_ok and self.modules_ok and self.topics_ok

    def issues(self) -> list[str]:
        out: list[str] = []
        if not self.hours_ok:
            out.append(f"총 교육 시간({self.expected_hours}시간)이 커리큘럼에 명시되지 않음")
        if not self.groups_ok:
            missing = [g for g in ["A", "B", "C"] if g not in self.groups_found]
            out.append(f"누락된 그룹: {', '.join(missing)}그룹")
        if not self.modules_ok:
            out.append("모듈/세션 구분이 없음")
        if not self.topics_ok and self.missing_topics:
            out.append(f"누락된 주제: {', '.join(self.missing_topics[:3])}")
        return out


class LLMCheckResult(BaseModel):
    """LLM이 판단하는 정성적 항목"""
    group_customization: bool = False   # 그룹별 실습이 실질적으로 차별화됐는가
    time_balance: bool = False          # 이론 50~60% / 실습 40~50% 비율 적절한가
    goal_alignment: bool = False        # 교육 목표와 내용이 일치하는가
    feedback: str = ""                  # 미통과 시 구체적 개선 사항

    @property
    def passed(self) -> bool:
        return self.group_customization and self.time_balance and self.goal_alignment

    def issues(self) -> list[str]:
        out: list[str] = []
        if not self.group_customization:
            out.append("그룹별 실습이 실질적으로 차별화되지 않음")
        if not self.time_balance:
            out.append("이론/실습 시간 배분이 지침(이론 50~60%)에서 벗어남")
        if not self.goal_alignment:
            out.append("교육 목표와 커리큘럼 내용의 정합성 부족")
        return out


class ValidationResult(BaseModel):
    """통합 검증 결과"""
    code_checks: CodeCheckResult = Field(default_factory=CodeCheckResult)
    llm_checks: LLMCheckResult = Field(default_factory=LLMCheckResult)
    passed: bool = False
    score: float = 0.0
    all_issues: list[str] = Field(default_factory=list)

    @classmethod
    def build(
        cls,
        code: CodeCheckResult,
        llm: LLMCheckResult,
    ) -> "ValidationResult":
        all_issues = code.issues() + llm.issues()
        # 코드 검증 통과가 선행 조건, LLM 검증은 보너스 품질
        passed = code.passed and llm.passed
        # 점수: 코드 검증 70% + LLM 검증 30%
        code_score = sum([code.hours_ok, code.groups_ok, code.modules_ok, code.topics_ok]) / 4
        llm_score = sum([llm.group_customization, llm.time_balance, llm.goal_alignment]) / 3
        score = round(code_score * 0.7 + llm_score * 0.3, 2)
        return cls(
            code_checks=code,
            llm_checks=llm,
            passed=passed,
            score=score,
            all_issues=all_issues,
        )


# ── API 스키마 ────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
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
    curriculum_id: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurriculumRecord(BaseModel):
    id: str
    company: str
    created_at: str
    passed: bool
    score: float
    filename: str
