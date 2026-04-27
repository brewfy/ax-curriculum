import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.abspath("c:\\dev\\ax-workspace\\08_MultiAgent\\.env"))

# Add project root to path
sys.path.append(os.path.abspath("c:\\dev\\ax-workspace\\08_MultiAgent"))

from backend.agents.validator_agent import ValidatorAgent
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()
agent = ValidatorAgent(client)

# Load curriculum
curr_path = r"c:\dev\ax-workspace\curriculum-data\curriculum_헬로월드랩스.md"
with open(curr_path, "r", encoding="utf-8") as f:
    curriculum = f.read()

education_info = {
    "company": "헬로월드랩스",
    "goal": "AI Agent 업무 자동화 개념을 이해하고 팀별 실습과 프로젝트를 통해 실제 업무에 적용 가능한 자동화 워크플로우를 설계하고 구현할 수 있도록 한다.",
    "audience": "재직자",
    "level": "초급",
    "topics": ["n8n을 활용한 AI Agent 및 업무 자동화 기초", "생성형 AI 연동", "반복 업무 자동화 실습", "팀별 프로젝트 기반 자동화 시나리오 설계", "심화 및 통합 프로젝트"],
    "duration": "3일 24시간",
    "type_counts": {
        "균형형": 9,
        "이해형": 9,
        "과신형": 8,
        "실행형": 8,
        "판단형": 9,
        "조심형": 9
    }
}

result = agent.run(curriculum, education_info)

print("CODE CHECKS:")
print(f"Hours OK: {result.code_checks.hours_ok}")
print(f"Groups OK: {result.code_checks.groups_ok}")
print(f"Modules OK: {result.code_checks.modules_ok}")
print(f"Topics OK: {result.code_checks.topics_ok}")
print(f"Missing Topics: {result.code_checks.missing_topics}")

print("\nLLM CHECKS:")
print(f"Group Customization: {result.llm_checks.group_customization}")
print(f"Time Balance: {result.llm_checks.time_balance}")
print(f"Goal Alignment: {result.llm_checks.goal_alignment}")
print(f"Feedback: {result.llm_checks.feedback}")

print(f"\nPASSED: {result.passed}")
print(f"SCORE: {result.score}")
