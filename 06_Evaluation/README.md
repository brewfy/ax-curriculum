# 06_Evaluation — RAG 평가 파이프라인

AX Compass 교육 커리큘럼 RAG 시스템의 품질을 4가지 지표로 측정한다.

---

## 평가 지표

| 지표 | 파일 | 설명 |
|------|------|------|
| **Precision@k** | `06_1.Metrics.py` | 상위 k개 검색 결과 중 정답 문서 비율 |
| **Faithfulness** | `06_1.Metrics.py` | 생성 답변이 검색 컨텍스트에 근거하는 정도 (LLM judge) |
| **Requirement Coverage** | `06_1.Metrics.py` | 필수 주제가 커리큘럼에 반영된 정도 (LLM judge) |
| **Rule-based** | `06_1.Metrics.py` | 세션 수 / 총 시간 / 그룹 구성 규칙 준수 여부 |

---

## 파일 구조

```
06_Evaluation/
├── 06_1.Metrics.py          # 지표 함수 모음 (순수 함수)
├── 06_2.Evaluator.py        # 평가 오케스트레이터 (ChromaDB + HybridRetriever)
├── 06_3.Run.py              # CLI 실행 스크립트
├── testset_template.json    # 테스트셋 작성 가이드
├── testset_sample.json      # 샘플 테스트셋 (3케이스)
└── reports/                 # 평가 결과 출력 디렉토리 (자동 생성)
```

---

## 설치

```bash
pip install -r ../05_Advanced_RAG/requirements.txt
```

`.env` 파일에 `OPENAI_API_KEY` 필요 (상위 디렉토리 `.env` 자동 로드).

---

## 실행

```bash
# 기본 실행 (샘플 테스트셋)
python 06_3.Run.py --testset testset_sample.json

# 출력 디렉토리 지정
python 06_3.Run.py --testset testset_sample.json --output ./reports

# ChromaDB 경로 직접 지정
python 06_3.Run.py --testset testset_sample.json --chroma-path ../05_Advanced_RAG/chroma_db
```

결과는 `reports/report_YYYYMMDD_HHMMSS.json` 과 `.md` 두 파일로 저장된다.

---

## 테스트셋 작성

`testset_template.json`을 복사해서 작성.

### 필드 설명

```json
{
  "id": "tc_001",
  "input": {
    "company": "회사명",
    "goal": "교육 목표",
    "audience": "교육 대상",
    "level": "초급 | 중급 | 고급",
    "topics": ["주제1", "주제2"],
    "extra": "",
    "duration": "1일 (8시간)",
    "type_counts": {
      "균형형": 3, "이해형": 4, "과신형": 5,
      "실행형": 6, "판단형": 2, "조심형": 2
    }
  },
  "expected": {
    "retrieval_ground_truth": ["균형형/강점", "과신형/도전"],
    "required_topics": ["ChatGPT", "프롬프트"],
    "session_count_range": [3, 6],
    "total_hours": 8,
    "groups_required": ["A", "B", "C"]
  },
  "generated_answer": null
}
```

### retrieval_ground_truth 형식

`HybridRetriever._label()` 출력과 동일한 형식:
- 섹션 청크: `"유형명/섹션명"` — 예: `"균형형/강점"`, `"과신형/도전"`, `"이해형/교육접근법"`
- 전체 청크: `"유형명"` — 예: `"균형형"`, `"판단형"`

### expected 항목 생략

각 `expected` 항목은 독립적이며 생략 가능. 생략된 항목은 해당 지표를 종합 점수 계산에서 제외한다.

### generated_answer

`null`이면 파이프라인이 OpenAI API를 호출해 커리큘럼을 직접 생성한다.
미리 생성된 답변 문자열을 넣으면 생성 단계를 건너뛰어 Faithfulness / Coverage / Rule만 측정한다.

---

## 출력 리포트 예시

### 콘솔
```
[1/3] 평가 중: tc_001
[2/3] 평가 중: tc_002
[3/3] 평가 중: tc_003

==================================================
평가 완료
==================================================
  종합 점수    : 0.7812
  Precision@k  : 0.5000
  Faithfulness : 0.8750
  Coverage     : 0.9200
  Rule Pass    : 0.6667
  소요 시간    : 42.3s

  JSON  → reports/report_20260423_143021.json
  MD    → reports/report_20260423_143021.md
```

### Markdown 리포트

| ID | 요약 | 종합 | P@k | Faith | Coverage | Rule |
|----|------|------|-----|-------|----------|------|
| tc_001 | 스타트업A / 1일 | 0.82 | 0.50 | 0.90 | 0.95 | ✅ |
| tc_002 | 중견기업B / 2일 | 0.74 | 0.25 | 0.85 | 0.88 | ✅ |
| tc_003 | 대기업C / 3일 | 0.79 | 0.50 | 0.87 | 0.92 | ❌ |
