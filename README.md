# AX Curriculum Chatbot

학습자 수준과 목표에 따라 맞춤형 커리큘럼을 설계해주는AI 서비스를 개발하고자 한다.
기업의 **AX(AI Transformation) 교육 커리큘럼**을 자동으로 설계해주는 챗봇 프로젝트입니다.  
회사 정보, 교육 대상, 주제, 일정 등을 입력하면 GPT-4o 기반으로 맞춤형 커리큘럼을 생성합니다.

# 프로젝트 목표
**학습자 수준과 목표에 따라 맞춤형 커리큘럼을 설계해주는 AI 서비스를 개발하고자 한다.**
---

## 프로젝트 구조

```
ax-workspace/
├── 03_ax_curriculum_chatbot/   # 기본 커리큘럼 챗봇
│   ├── app.py
│   └── requirements.txt
├── 04.RAG/                     # RAG 강화 버전 (AX Compass 진단 연동)
│   └── 04.RAG.py
├── Data/
│   └── AXCompass.pdf           # AX Compass 역량 진단 유형 설명 자료
├── .env.example                # 환경변수 템플릿
└── README.md
```

---

## 프로젝트 소개

### 03. AX Curriculum Chatbot (기본)

터미널 UI(Rich)를 통해 다음 정보를 입력받아 커리큘럼을 생성합니다.

| 항목 | 설명 |
|---|---|
| 회사명 / 업종 | 교육 대상 기업 정보 |
| 교육 대상 | 임원 / 팀장 / 실무자 / 개발자 등 |
| 교육 수준 | 입문 / 기초 / 중급 / 고급 |
| 교육 주제 | AI 기초, 프롬프트 엔지니어링, RAG, AI 자동화 등 12개 주제 |
| 교육 기간 | 반일(4h) ~ 6개월 |
| 교육 방식 | 집합 / 온라인 / 혼합 / 자기주도 |

**출력 형식**
- 교육 개요 / 교육 목표 / 모듈별 커리큘럼 / 평가 방법 / 기대 효과

---

### 04. RAG 강화 버전 (AX Compass 진단 연동)

기본 버전에 **AX Compass 역량 진단 결과**를 연동하여, 수강생 유형별 맞춤 실습/프로젝트를 설계합니다.

#### AX Compass 6가지 유형

| 유형 | 특성 |
|---|---|
| 균형형 (BALANCED) | 판단력과 실행력이 균형 있게 발달. AI 활용 준비도 최상 |
| 이해형 (LEARNER) | 학습 의욕은 높지만 실무 경험 부족. 단계적 실습 필요 |
| 과신형 (OVERCONFIDENT) | 자신감 높고 빠르게 시도하나 검증 절차 미흡 |
| 실행형 (DOER) | 행동력이 강하고 적극적이나 품질·윤리 체크 필요 |
| 판단형 (ANALYST) | 분석·판단 우선, 실행에는 신중. 데이터 기반 접근 선호 |
| 조심형 (CAUTIOUS) | 준비와 검증 후 진입. 심리적 장벽 낮추는 교육 필요 |

#### 그룹 구성

```
A그룹 (균형형 + 이해형)  →  심화 프로젝트 중심 실습
B그룹 (과신형 + 실행형)  →  실행 + 검증 프로세스 실습
C그룹 (판단형 + 조심형)  →  체계적 단계별 실습
```

- **이론 수업**: 전체 동일 진행
- **실습/프로젝트**: 그룹별 맞춤 설계
- **벡터 DB**: ChromaDB + OpenAI Embeddings로 유형 정보 RAG 검색

---

## 설치 및 실행

### 1. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 OpenAI API 키 입력
```

### 2. 의존성 설치

```bash
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Mac/Linux

pip install openai python-dotenv rich pypdf chromadb
```

### 3. 실행

```bash
# 기본 버전
python 03_ax_curriculum_chatbot/app.py

# RAG 강화 버전
python 04.RAG/04.RAG.py
```

---

## 기술 스택

| 항목 | 내용 |
|---|---|
| LLM | GPT-4o (OpenAI) |
| Embedding | text-embedding-3-small (OpenAI) |
| Vector DB | ChromaDB (로컬 Persistent) |
| PDF 파싱 | pypdf |
| Terminal UI | Rich |
| 환경변수 | python-dotenv |

---

## 라이선스

MIT
