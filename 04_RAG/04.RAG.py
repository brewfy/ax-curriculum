import os
import sys
import json
import hashlib
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.rule import Rule
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import pypdf

load_dotenv()

console = Console()

# ── 경로 설정 ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
PDF_PATH = DATA_DIR / "AXCompass.pdf"

# ── OpenAI 클라이언트 ────────────────────────────────────────
def get_client():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[bold red]오류:[/] OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        sys.exit(1)
    return OpenAI(api_key=api_key)

# ── AXCompass 유형 설명 (RAG 지식 베이스) ───────────────────
AX_COMPASS_DOCS = [
    {
        "id": "type_balanced",
        "type": "균형형",
        "code": "BALANCED",
        "group": "A",
        "content": """
균형형 (BALANCED)

균형형은 판단과 행동력이 균형 있게 발달한 타입으로, AX에 대비하는 최선의 활동 역량을 보유한 인재형 이라고 볼 수 있는 타입이다.

강점:
- 이미 필요한 순간에 AI를 활용하고 활용 필요성을 인식하고 할 수 있는 역량이 있다.
- 다양한 업무에 능통하고 다양한 역할에 있어 임무 수행이 가능하며 자동화하거나 최적화하며 Ȱ용한다.
- 현 수준을 넘어서 성장하기 위해 반복 학습과 도전적인 시도를 통해 Ȱ용 역량을 높일 수 있다.
- 이 역량 수준이면 프로젝트 팀 커뮤니티에서 실무로 Ȯ용 역량의 구체적 Ȱ용 효과에 큰 역할을 할 수 있다.

교육 접근법:
- 이미 AI 활용 기반이 있으므로 심화 프로젝트 리더 역할 부여
- 다양한 업무 시나리오에서의 AI 통합 전략 수립 실습
- 다른 유형 구성원 멘토링 역할 수행 가능
- AX 전략 수립 및 팀 내 AI 활용 문화 확산 프로젝트

대표 태그: #자기인식_균형있게, #상황판단_보통, #행동역량_보통
"""
    },
    {
        "id": "type_learner",
        "type": "이해형",
        "code": "LEARNER",
        "group": "A",
        "content": """
이해형 (LEARNER)

이해형은 학습 의욕은 높지만 실제 업무에서 AI 활용 경험이 부족한 유형으로, 이론적 이해도는 높으나 실행 역량이 아직 충분히 발달하지 않은 타입이다.

강점:
- AI에 대한 관심이 높고, 새로운 기술과 트렌드를 빠르게 이해하고 습득할 수 있다.
- 새로운 가이드라인이나 가이드를 받아들이는 속도가 빠른 학습 유연성이 뛰어나다.
- 기본 원리를 이해하는 데 집중함으로써, 응용 업무에서의 활용 가능성이 있다.

도전 과제 (개선 필요 영역):
- 반복적으로 발생하는 루틴을 자동화하는 방향의 실무 해결로 Ȱ용 능력이 아직 이어지지 않고 있다.
- 반복 학습보다 새로운 루틴에 집중하는 학습 패턴에서 노력과 시간을 낭비하며 자리 잡는 데 더디게 되는 경향이 있다.
- 변화를 수용하는 최소 기준치를 설정하며 Ȱ용 자신감과 신뢰를 위해 함께 성장하는 데 필요하다.

교육 접근법:
- 이론 학습 후 즉각적인 실습 연계로 경험 쌓기
- 단계별 가이드가 있는 실습 워크플로우 제공
- 소규모 성공 경험(Quick Win) 프로젝트로 자신감 구축
- 실무 적용 사례 중심의 학습 설계

대표 태그: #자기인식_보통, #상황판단_보통, #행동역량_낮음, #학습중심성향
"""
    },
    {
        "id": "type_doer",
        "type": "실행형",
        "code": "DOER",
        "group": "B",
        "content": """
실행형 (DOER)

실행형은 빠른 환경 변화에 맞서 새로운 것들을 적극적으로 Ȱ용하려는 강한 실행력을 보유하고 있으나, 충분한 이해 없이 Ȱ용 역량을 바로 업무에 활용하는 경향이 있는 타입이다.

강점:
- 새로운 것에 대한 높은 관심으로 적극적으로 시도해볼 수 있는 역량이 있다.
- AI 관련 프로젝트나 아이디어 흐름을 자유롭게 활용하는 데 익숙하다.
- 새로운 것을 시도해 보려는 의욕이 있어서, 업무 내에서 활용 가능성을 확인하고 찾아나간다.

도전 과제 (개선 필요 영역):
- 검증 확인이나 테스트 없이 아이디어를 함께 실행하면서 품질이 낮아질 수 있다.
- 저작권/개인정보/윤리 등 확인 없이 활용 역량을 무분별하게 사용하여 문제가 생길 수 있다.
- 최초 요청의 결과를 표준화하며 매번 반복하고 일관성을 잃는 경향이 있다.

교육 접근법:
- 빠른 실행을 장점으로 살리되 검증 프로세스를 추가하는 실습 설계
- AI 윤리, 저작권, 프롬프트 품질 관리 실습
- 팀 협업 프로젝트에서 아이디어 구현 후 검증하는 워크플로우
- 재현 가능한 표준 프로세스 구축 실습

대표 태그: #행동역량_매우높음, #상황판단_보통, #확인켠행동, #행동Ȱ용환경
"""
    },
    {
        "id": "type_overconfident",
        "type": "과신형",
        "code": "OVERCONFIDENT",
        "group": "B",
        "content": """
과신형 (OVERCONFIDENT)

과신형은 자신감을 바탕으로 새로운 것들을 쉽게 시도하는 편이나, 판단과 준비 없이 확인하지 않아 실패하는 경우가 많으며 빠르게 나타나는 경향이 있는 타입이다.

강점:
- 새로운 기술이나 도구를 두려워하지 않고 빠르게 시도해보려는 도전정신이 있다.
- 가이드나 설명이 없어도 빠른 단계에서 빠르게 먼저 해보려는 추진력이 있다.
- 변화된 환경과 반환 없이 새로운 Ȱ용 방향의 가능성을 받아들이고 적응하게 된다.

도전 과제 (개선 필요 영역):
- 다른 확인과 검증 없이, 활용과 역할에 함께 실무 결과에서 신뢰성이 낮아지는 문제가 생길 수 있다.
- 저작권/개인정보/윤리 확인 없이 이미 활용하며 Ȱ용 역량에 신뢰도와 오류가 높아질 수 있다.
- 더 경우와 품질에서 낮아질 수 있는 가능성을 설정하며 Ȯ용하는 경우 효율적이지 않을 수 있다.

교육 접근법:
- 과감한 실행력은 유지하되 검증과 품질 체크 습관 구축
- 구조화된 프롬프트 엔지니어링과 결과 검증 방법론 실습
- AI 윤리, 저작권, 정보 보안 의식 강화 교육
- 페어 프로그래밍 방식으로 다른 유형과 협업하여 상호 보완

대표 태그: #자기인식_매우높음, #상황판단_낮음, #확인보다실행, #검토보조필요
"""
    },
    {
        "id": "type_analyst",
        "type": "판단형",
        "code": "ANALYST",
        "group": "C",
        "content": """
판단형 (ANALYST)

판단형은 근거와 Ȱ용 아이디어를 꼼꼼히 분석하고 판단하는 편이며, 활용의 정확한 가능성과 역할을 충분히 검토한 뒤 활용 역량을 발휘하는 타입이다.

강점:
- 활용의 가능성이나 위험 가능성을 많이 발견하고 분석할 수 있다.
- 저작권/개인정보/윤리가 중요하고 활용의 판단으로 활용 역량을 위한 근거를 찾을 수 있다.
- 의사결정과 판단을 도울 수 있는 커뮤니케이션을 정확하게 활용하게 될 수 있다.

도전 과제 (개선 필요 영역):
- 막상 결과를 분석하기보다 판단으로 행동이 느려지거나 판단에 의존하는 경향이 생길 수 있다.
- 확실히 확인이 되어 분석하기보다 규칙으로만 판단하여 반복 학습에서 Ȱ용 역량이 낮아질 수 있다.
- 분석에 의한 많은 역할을 함께 할수록 역할에 의존하는 업무 Ȱ용이 어떻게 자유롭게 되는지 놓칠 수 있다.

교육 접근법:
- 분석적 사고를 살린 AI 도구 평가/검증 프로젝트
- 데이터 기반 의사결정 실습에 AI 도구 통합
- 프로토타입 빠른 실행 → 분석 → 개선의 반복 사이클 학습
- AI 윤리와 거버넌스 프레임워크 설계 실습

대표 태그: #상황판단_매우높음, #행동역량_낮음, #판단우선, #분석신중한환경
"""
    },
    {
        "id": "type_cautious",
        "type": "조심형",
        "code": "CAUTIOUS",
        "group": "C",
        "content": """
조심형 (CAUTIOUS)

조심형은 충분한 준비와 검증이 완료된 뒤에야 새로운 Ȱ용에 천천히 접근하는 편이며, 익숙한 것들에서 벗어나려는 Ȱ용 역량을 아직 발휘하지 않는 타입이다.

강점:
- 기술 리스크에 대한 충분한 인식이 있어 안전하게 진행할 수 있는 가능성이 있다.
- 기존의 변화 환경에서 변화에 소극적이고 안정적인 속도에 활동에 이어나갈 수 있다.
- 불확실한 상황이나 근거 소거를 바탕으로 Ȱ용 역량이 발휘될 수 있도록 기반이 되어야 한다.

도전 과제 (개선 필요 영역):
- 변화의 비용에서 익숙함에서 단계적인 첫 진입으로 Ȱ용 역량 장벽을 낮출 수 있다.
- 체크리스트나 검증 기준을 정해 Ȱ용 자신감이 아직 낮아 가능성을 시도하는 방향의 역량이 필요하다.
- 최소한의 역할로 넘어가는 역량에 의한 Ȱ용 시작의 첫 번째 작은 단계부터 도전이 필요하다.

교육 접근법:
- 안전한 샌드박스 환경에서 단계별 실습 (낮은 위험 → 점진적 확장)
- 체크리스트 기반의 구조화된 AI 도구 사용 가이드 제공
- 성공 사례 중심의 학습으로 심리적 장벽 낮추기
- 소규모 Quick Win 프로젝트로 첫 경험의 성취감 제공

대표 태그: #자기인식_낮음, #행동역량_낮음, #분석신중, #안전우선Ȱ용
"""
    },
]

# ── 시스템 프롬프트 ──────────────────────────────────────────
SYSTEM_PROMPT = """
당신은 20년 경력의 IT·AI 교육 전문가이자 교육 스타트업 대표입니다.

[강의 철학]
- 1시간이든 6개월이든, 수강생에게 실질적인 만족감과 업무 역량 향상을 제공합니다.
- 이론에 그치지 않고 현장에서 즉시 활용 가능한 실무 중심 커리큘럼을 설계합니다.
- 교육 대상자의 수준과 업무 맥락을 최우선으로 고려합니다.
- AX Compass 진단 결과를 바탕으로 유형별 맞춤형 실습/프로젝트를 설계합니다.

[역할]
기업의 AX(AI Transformation) 교육을 위한 커리큘럼을 설계하는 챗봇입니다.
사용자가 제공한 정보와 AX Compass 진단 결과를 바탕으로 맞춤형 커리큘럼을 생성합니다.

[그룹 구성]
- A그룹 (균형형 + 이해형): 이미 AI에 친숙하거나 학습 의욕이 높은 그룹. 심화 프로젝트 중심.
- B그룹 (과신형 + 실행형): 실행력은 높지만 검증/품질 관리가 필요한 그룹. 실행+검증 중심.
- C그룹 (판단형 + 조심형): 신중하고 분석적이지만 실행에 장벽이 있는 그룹. 체계적 단계 실습 중심.

[커리큘럼 출력 형식]
커리큘럼 요청이 들어오면 반드시 아래 구조로 작성합니다:

## 📋 교육 개요
- 교육명 / 교육 대상 / 총 교육 시간 / 교육 방식
- 그룹 구성 현황 (A그룹 N명, B그룹 N명, C그룹 N명)

## 🎯 교육 목표
3~5개의 명확한 학습 성과 기술 (공통 + 그룹별 추가 목표)

## 🗂️ 공통 이론 모듈
모든 그룹이 함께 수강하는 이론 수업:
  - 모듈 제목
  - 학습 목표
  - 세부 주제 목록
  - 소요 시간

## 🔬 그룹별 맞춤 실습/프로젝트

### 🅐 A그룹 실습 (균형형 + 이해형) - N명
  각 실습/프로젝트마다:
  - 실습명
  - 목적 및 방향
  - 세부 활동
  - 기대 성과
  - 소요 시간

### 🅑 B그룹 실습 (과신형 + 실행형) - N명
  (동일 구조)

### 🅒 C그룹 실습 (판단형 + 조심형) - N명
  (동일 구조)

## 📝 평가 방법
공통 평가 + 그룹별 맞춤 평가 기준

## 💼 기대 효과
수료 후 업무에서 기대되는 변화 (공통 + 그룹별)

정보가 부족하면 추가 질문을 통해 파악하고, 커리큘럼 생성 후에는
수정·보완 요청을 적극 반영합니다.
"""

AX_TOPICS = [
    "AI 기초 개념 및 트렌드",
    "ChatGPT / LLM 업무 활용",
    "프롬프트 엔지니어링",
    "AI 기반 데이터 분석",
    "RAG / 사내 지식 검색 AI",
    "AI 코딩 보조 (GitHub Copilot 등)",
    "이미지·영상 생성 AI",
    "AI 자동화 (RPA + AI)",
    "LLM API 활용 및 앱 개발",
    "AI 윤리 및 보안",
    "AI 전략 수립 / AX 로드맵",
    "업종별 AI 활용 사례",
]

AUDIENCE_OPTIONS = [
    "임원 / 경영진 (C-Level)",
    "팀장 / 중간관리자",
    "실무자 (비개발직군)",
    "개발자 / 엔지니어",
    "데이터 분석가",
    "혼합 (다양한 직군)",
]

LEVEL_OPTIONS = [
    "입문 (AI 완전 초보)",
    "기초 (기본 개념 이해)",
    "중급 (실무 활용)",
    "고급 (심화 / 개발)",
]

DURATION_OPTIONS = [
    "반일 (4시간)",
    "1일 (8시간)",
    "2일 (16시간)",
    "3일 (24시간)",
    "1주 (5일)",
    "1개월",
    "3개월",
    "6개월",
]

FORMAT_OPTIONS = [
    "집합 교육 (오프라인)",
    "온라인 라이브",
    "온·오프라인 혼합",
    "자기주도 학습 (비동기)",
]

TYPES = ["균형형", "이해형", "과신형", "실행형", "판단형", "조심형"]

GROUPS = {
    "A": ("균형형", "이해형"),
    "B": ("과신형", "실행형"),
    "C": ("판단형", "조심형"),
}

# ── RAG: ChromaDB 초기화 ─────────────────────────────────────
def init_vector_db(api_key: str) -> chromadb.Collection:
    """AXCompass PDF를 벡터 DB에 로드하고 컬렉션을 반환합니다."""
    embedding_fn = OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # PDF 파일 해시 계산 (변경 감지)
    pdf_hash = ""
    if PDF_PATH.exists():
        with open(PDF_PATH, "rb") as f:
            pdf_hash = hashlib.md5(f.read()).hexdigest()

    collection_name = "ax_compass_types"

    # 기존 컬렉션 확인
    existing_collections = [c.name for c in client.list_collections()]
    needs_ingest = True

    if collection_name in existing_collections:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_fn
        )
        # 메타데이터로 PDF 해시 확인
        try:
            meta = collection.get(ids=["_meta_hash"])
            if meta["documents"] and meta["documents"][0] == pdf_hash:
                needs_ingest = False
                console.print("[dim]벡터 DB: 기존 인덱스 재사용[/]")
        except Exception:
            pass
    else:
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    if needs_ingest:
        console.print("[dim]벡터 DB: AXCompass PDF 인덱싱 중...[/]")

        # 기존 문서 삭제
        try:
            existing = collection.get()
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # 1. 구조화된 유형 설명 문서 추가
        docs, ids, metas = [], [], []
        for doc in AX_COMPASS_DOCS:
            docs.append(doc["content"])
            ids.append(doc["id"])
            metas.append({
                "type": doc["type"],
                "code": doc["code"],
                "group": doc["group"],
                "source": "ax_compass_structured",
            })

        # 2. PDF 원문에서 추가 청크 추출
        if PDF_PATH.exists():
            try:
                pdf_chunks = extract_pdf_chunks(PDF_PATH)
                for i, chunk in enumerate(pdf_chunks):
                    if len(chunk.strip()) > 100:
                        docs.append(chunk)
                        ids.append(f"pdf_chunk_{i}")
                        metas.append({"source": "ax_compass_pdf", "chunk_index": i})
            except Exception as e:
                console.print(f"[yellow]PDF 추출 경고: {e}[/]")

        # 메타 해시 문서 추가
        docs.append(pdf_hash)
        ids.append("_meta_hash")
        metas.append({"source": "meta"})

        collection.add(documents=docs, ids=ids, metadatas=metas)
        console.print(f"[dim]벡터 DB: {len(docs)-1}개 문서 인덱싱 완료[/]")

    return collection


def extract_pdf_chunks(pdf_path: Path) -> list[str]:
    """PDF에서 텍스트를 추출하고 청크로 분할합니다."""
    reader = pypdf.PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages:
        text = page.extract_text() or ""
        # 페이지를 단락 단위로 분할
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks.extend(paragraphs)
    return chunks


def retrieve_type_info(collection: chromadb.Collection, types: list[str], n_results: int = 3) -> str:
    """관련 유형 정보를 벡터 DB에서 검색합니다."""
    query = "AX Compass 유형별 특성과 교육 접근법: " + ", ".join(types)
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, len(AX_COMPASS_DOCS)),
        where={"source": "ax_compass_structured"},
    )
    if not results["documents"] or not results["documents"][0]:
        return ""
    return "\n\n---\n\n".join(results["documents"][0])


# ── 선택 메뉴 헬퍼 ───────────────────────────────────────────
def choose(title: str, options: list[str], allow_custom: bool = False) -> str:
    console.print(f"\n[bold cyan]{title}[/]")
    for i, opt in enumerate(options, 1):
        console.print(f"  [yellow]{i}[/]. {opt}")
    if allow_custom:
        console.print(f"  [yellow]{len(options)+1}[/]. 직접 입력")

    max_n = len(options) + (1 if allow_custom else 0)
    while True:
        choice = IntPrompt.ask("번호 선택", default=1)
        if 1 <= choice <= len(options):
            return options[choice - 1]
        if allow_custom and choice == len(options) + 1:
            return Prompt.ask("직접 입력")
        console.print(f"[red]1~{max_n} 사이의 번호를 입력해주세요.[/]")


def choose_multi(title: str, options: list[str]) -> list[str]:
    console.print(f"\n[bold cyan]{title}[/]")
    console.print("[dim]번호를 쉼표로 구분해 입력하세요 (예: 1,3,5) / 전체: 0[/]")
    for i, opt in enumerate(options, 1):
        console.print(f"  [yellow]{i}[/]. {opt}")

    while True:
        raw = Prompt.ask("번호 선택").strip()
        if raw == "0":
            return options[:]
        try:
            indices = [int(x.strip()) for x in raw.split(",")]
            if all(1 <= idx <= len(options) for idx in indices):
                return [options[i - 1] for i in indices]
        except ValueError:
            pass
        console.print("[red]올바른 형식으로 입력해주세요 (예: 1,3,5)[/]")


def collect_type_counts() -> dict[str, int]:
    """AX Compass 진단 결과 유형별 인원수를 입력받습니다."""
    console.print(Rule("[bold]AX Compass 진단 결과 입력[/]", style="magenta"))
    console.print(
        "\n[bold magenta]AX Compass 진단 결과 유형별 인원수를 입력해주세요.[/]\n"
        "[dim]  • A그룹: 균형형 + 이해형  (심화 프로젝트 그룹)\n"
        "  • B그룹: 과신형 + 실행형  (실행+검증 그룹)\n"
        "  • C그룹: 판단형 + 조심형  (체계적 단계 실습 그룹)[/]\n"
    )

    counts = {}
    group_info = [
        ("균형형", "A그룹", "green"),
        ("이해형", "A그룹", "green"),
        ("과신형", "B그룹", "yellow"),
        ("실행형", "B그룹", "yellow"),
        ("판단형", "C그룹", "blue"),
        ("조심형", "C그룹", "blue"),
    ]

    for type_name, group, color in group_info:
        count = IntPrompt.ask(
            f"  [{color}]{type_name}[/] ({group}) 인원수",
            default=0,
        )
        counts[type_name] = max(0, count)

    return counts


# ── 정보 수집 ────────────────────────────────────────────────
def collect_info() -> dict:
    console.print(Panel(
        "[bold white]AX 커리큘럼 설계 챗봇 (RAG 강화)[/]\n"
        "[dim]AX Compass 진단 결과 기반 맞춤형 AI Transformation 교육 커리큘럼을 설계합니다.[/]",
        style="bold blue",
        padding=(1, 4),
    ))

    console.print(Rule("[bold]기본 정보 입력[/]", style="blue"))

    company = Prompt.ask("\n[bold cyan]회사명 / 기관명[/]")
    industry = Prompt.ask("[bold cyan]업종 / 도메인[/] [dim](예: 제조, 금융, 의료)[/]")
    audience = choose("교육 대상", AUDIENCE_OPTIONS, allow_custom=True)
    level = choose("교육 수준", LEVEL_OPTIONS)

    console.print(Rule("[bold]AX 주요 주제[/]", style="blue"))
    topics = choose_multi("다루고 싶은 주제 선택 (복수 선택)", AX_TOPICS)

    extra = Prompt.ask(
        "\n[bold cyan]추가 주제 또는 요청사항[/] [dim](없으면 Enter)[/]",
        default=""
    )

    console.print(Rule("[bold]교육 일정[/]", style="blue"))
    duration = choose("교육 기간", DURATION_OPTIONS, allow_custom=True)
    fmt = choose("교육 방식", FORMAT_OPTIONS)

    type_counts = collect_type_counts()

    return {
        "company": company,
        "industry": industry,
        "audience": audience,
        "level": level,
        "topics": topics,
        "extra": extra,
        "duration": duration,
        "format": fmt,
        "type_counts": type_counts,
    }


# ── 요약 출력 ────────────────────────────────────────────────
def print_summary(info: dict):
    table = Table(title="입력 정보 요약", show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=16)
    table.add_column(style="white")

    topics_str = "\n".join(f"• {t}" for t in info["topics"])
    if info["extra"]:
        topics_str += f"\n• {info['extra']} (추가)"

    # 유형별 인원수 및 그룹 요약
    counts = info["type_counts"]
    group_a = counts.get("균형형", 0) + counts.get("이해형", 0)
    group_b = counts.get("과신형", 0) + counts.get("실행형", 0)
    group_c = counts.get("판단형", 0) + counts.get("조심형", 0)
    total = group_a + group_b + group_c

    type_str = (
        f"[green]A그룹[/]: 균형형 {counts.get('균형형',0)}명 + 이해형 {counts.get('이해형',0)}명 = {group_a}명\n"
        f"[yellow]B그룹[/]: 과신형 {counts.get('과신형',0)}명 + 실행형 {counts.get('실행형',0)}명 = {group_b}명\n"
        f"[blue]C그룹[/]: 판단형 {counts.get('판단형',0)}명 + 조심형 {counts.get('조심형',0)}명 = {group_c}명\n"
        f"[bold]총 인원: {total}명[/]"
    )

    table.add_row("회사명", info["company"])
    table.add_row("업종", info["industry"])
    table.add_row("교육 대상", info["audience"])
    table.add_row("교육 수준", info["level"])
    table.add_row("주제", topics_str)
    table.add_row("교육 기간", info["duration"])
    table.add_row("교육 방식", info["format"])
    table.add_row("그룹별 인원", type_str)

    console.print()
    console.print(Panel(table, style="blue", padding=(1, 2)))


# ── 커리큘럼 생성 ────────────────────────────────────────────
def build_user_message(info: dict, rag_context: str) -> str:
    topics_str = ", ".join(info["topics"])
    if info["extra"]:
        topics_str += f", {info['extra']}"

    counts = info["type_counts"]
    group_a = counts.get("균형형", 0) + counts.get("이해형", 0)
    group_b = counts.get("과신형", 0) + counts.get("실행형", 0)
    group_c = counts.get("판단형", 0) + counts.get("조심형", 0)
    total = group_a + group_b + group_c

    type_detail = "\n".join([
        f"  - 균형형: {counts.get('균형형', 0)}명",
        f"  - 이해형: {counts.get('이해형', 0)}명",
        f"  - 과신형: {counts.get('과신형', 0)}명",
        f"  - 실행형: {counts.get('실행형', 0)}명",
        f"  - 판단형: {counts.get('판단형', 0)}명",
        f"  - 조심형: {counts.get('조심형', 0)}명",
    ])

    group_summary = (
        f"  - A그룹 (균형형+이해형): {group_a}명\n"
        f"  - B그룹 (과신형+실행형): {group_b}명\n"
        f"  - C그룹 (판단형+조심형): {group_c}명\n"
        f"  - 총 인원: {total}명"
    )

    rag_section = ""
    if rag_context:
        rag_section = f"""
[AX Compass 유형별 특성 참고 자료]
다음은 RAG로 검색된 유형별 특성 및 교육 접근법입니다. 이를 참고하여 그룹별 맞춤 실습을 설계해주세요:

{rag_context}

---
"""

    return f"""{rag_section}다음 정보를 바탕으로 AX 교육 커리큘럼을 설계해주세요.

- **회사명**: {info["company"]}
- **업종/도메인**: {info["industry"]}
- **교육 대상**: {info["audience"]}
- **교육 수준**: {info["level"]}
- **교육 주제**: {topics_str}
- **교육 기간**: {info["duration"]}
- **교육 방식**: {info["format"]}

**AX Compass 진단 결과 유형별 인원:**
{type_detail}

**그룹 구성:**
{group_summary}

이론 수업은 전체 동일하게 진행하되, 각 그룹별 특성에 맞는 맞춤형 실습/프로젝트를 설계해주세요.
각 그룹의 특성:
- A그룹 (균형형+이해형): AI 활용 이해도가 높거나 학습 의욕이 강한 그룹. 심화 프로젝트 중심으로 설계.
- B그룹 (과신형+실행형): 행동력과 실행력이 높지만 검증과 품질 관리가 필요한 그룹. 실행+검증 프로세스 중심.
- C그룹 (판단형+조심형): 신중하고 분석적이지만 실행에 심리적 장벽이 있는 그룹. 체계적 단계별 실습 중심.
"""


def stream_response(client: OpenAI, messages: list[dict]) -> str:
    console.print(Rule("[bold green]커리큘럼[/]", style="green"))
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    full_response = ""
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=api_messages,
        stream=True,
        temperature=0.7,
        max_tokens=6000,
    )

    with console.status("[bold green]커리큘럼 설계 중...[/]", spinner="dots"):
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response += delta
                console.print()
                console.print(delta, end="", markup=False, highlight=False)
                break

    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            console.print(delta, end="", markup=False, highlight=False)
            full_response += delta

    console.print("\n")
    console.print(Rule(style="green"))
    return full_response


# ── 메인 루프 ────────────────────────────────────────────────
def main():
    client = get_client()

    # 벡터 DB 초기화
    with console.status("[bold blue]벡터 DB 초기화 중...[/]", spinner="dots"):
        collection = init_vector_db(os.getenv("OPENAI_API_KEY", ""))

    messages: list[dict] = []

    info = collect_info()
    print_summary(info)

    confirm = Prompt.ask(
        "\n[bold]위 정보로 커리큘럼을 생성할까요?[/]",
        choices=["y", "n"],
        default="y"
    )
    if confirm == "n":
        console.print("[yellow]처음부터 다시 시작합니다.[/]")
        main()
        return

    # RAG: 유형 정보 검색
    all_types = list(info["type_counts"].keys())
    active_types = [t for t in all_types if info["type_counts"].get(t, 0) > 0]
    if not active_types:
        active_types = all_types

    with console.status("[bold blue]유형별 특성 검색 중 (RAG)...[/]", spinner="dots"):
        rag_context = retrieve_type_info(collection, active_types, n_results=6)

    user_msg = build_user_message(info, rag_context)
    messages.append({"role": "user", "content": user_msg})

    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})

    # ── 후속 대화 루프 ─────────────────────────────────────
    console.print("[dim]커리큘럼 수정·보완 요청이나 추가 질문을 입력하세요. 종료하려면 'q' 또는 'quit'[/]\n")
    while True:
        user_input = Prompt.ask("[bold blue]>[/]").strip()
        if user_input.lower() in ("q", "quit", "exit", "종료"):
            console.print(Panel(
                "[bold green]감사합니다! 성공적인 AX 교육이 되길 바랍니다.[/]",
                padding=(1, 4)
            ))
            break
        if not user_input:
            continue

        # 후속 질문에도 RAG 보강
        with console.status("[bold blue]관련 정보 검색 중...[/]", spinner="dots"):
            followup_context = retrieve_type_info(collection, active_types, n_results=3)

        enriched_input = user_input
        if followup_context and any(kw in user_input for kw in ["그룹", "유형", "실습", "프로젝트", "맞춤"]):
            enriched_input = f"[참고: {followup_context[:500]}...]\n\n{user_input}"

        messages.append({"role": "user", "content": enriched_input})
        response = stream_response(client, messages)
        messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]프로그램을 종료합니다.[/]")
