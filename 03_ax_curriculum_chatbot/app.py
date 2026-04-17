import os
import sys
from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from rich.markdown import Markdown
from rich.rule import Rule
from rich import print as rprint

load_dotenv()

console = Console()

# ── OpenAI 클라이언트 ────────────────────────────────────────
def get_client():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[bold red]오류:[/] OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        sys.exit(1)
    return OpenAI(api_key=api_key)

# ── 시스템 프롬프트 ──────────────────────────────────────────
SYSTEM_PROMPT = """
당신은 20년 경력의 IT·AI 교육 전문가이자 교육 스타트업 대표입니다.

[강의 철학]
- 1시간이든 6개월이든, 수강생에게 실질적인 만족감과 업무 역량 향상을 제공합니다.
- 이론에 그치지 않고 현장에서 즉시 활용 가능한 실무 중심 커리큘럼을 설계합니다.
- 교육 대상자의 수준과 업무 맥락을 최우선으로 고려합니다.

[역할]
기업의 AX(AI Transformation) 교육을 위한 커리큘럼을 설계하는 챗봇입니다.
사용자가 제공한 정보를 바탕으로 맞춤형 커리큘럼을 생성합니다.

[커리큘럼 출력 형식]
커리큘럼 요청이 들어오면 반드시 아래 구조로 작성합니다:

## 📋 교육 개요
- 교육명 / 교육 대상 / 총 교육 시간 / 교육 방식

## 🎯 교육 목표
3~5개의 명확한 학습 성과 기술

## 🗂️ 모듈별 커리큘럼
각 모듈마다:
  - 모듈 제목
  - 학습 목표
  - 세부 주제 목록
  - 실습/실무 적용 내용
  - 소요 시간

## 📝 평가 방법
평가 방식 및 기준

## 💼 기대 효과
수료 후 업무에서 기대되는 변화

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
        console.print(f"[red]올바른 형식으로 입력해주세요 (예: 1,3,5)[/]")

# ── 정보 수집 ────────────────────────────────────────────────
def collect_info() -> dict:
    console.print(Panel(
        "[bold white]AX 커리큘럼 설계 챗봇[/]\n"
        "[dim]기업 맞춤형 AI Transformation 교육 커리큘럼을 설계합니다.[/]",
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

    return {
        "company": company,
        "industry": industry,
        "audience": audience,
        "level": level,
        "topics": topics,
        "extra": extra,
        "duration": duration,
        "format": fmt,
    }

# ── 요약 출력 ────────────────────────────────────────────────
def print_summary(info: dict):
    table = Table(title="입력 정보 요약", show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=16)
    table.add_column(style="white")

    topics_str = "\n".join(f"• {t}" for t in info["topics"])
    if info["extra"]:
        topics_str += f"\n• {info['extra']} (추가)"

    table.add_row("회사명", info["company"])
    table.add_row("업종", info["industry"])
    table.add_row("교육 대상", info["audience"])
    table.add_row("교육 수준", info["level"])
    table.add_row("주제", topics_str)
    table.add_row("교육 기간", info["duration"])
    table.add_row("교육 방식", info["format"])

    console.print()
    console.print(Panel(table, style="blue", padding=(1, 2)))

# ── 커리큘럼 생성 ────────────────────────────────────────────
def build_user_message(info: dict) -> str:
    topics_str = ", ".join(info["topics"])
    if info["extra"]:
        topics_str += f", {info['extra']}"

    return f"""다음 정보를 바탕으로 AX 교육 커리큘럼을 설계해주세요.

- **회사명**: {info["company"]}
- **업종/도메인**: {info["industry"]}
- **교육 대상**: {info["audience"]}
- **교육 수준**: {info["level"]}
- **교육 주제**: {topics_str}
- **교육 기간**: {info["duration"]}
- **교육 방식**: {info["format"]}
"""

def stream_response(client: OpenAI, messages: list[dict]) -> str:
    console.print(Rule("[bold green]커리큘럼[/]", style="green"))
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    full_response = ""
    # 1. 스트림 생성
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=api_messages,
        stream=True,
        temperature=0.7,
        max_tokens=4000,
    )

    # 2. 첫 응답이 올 때까지 상태 표시줄 노출
    with console.status("[bold green]커리큘럼 설계 중...[/]", spinner="dots"):
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_response += delta
                console.print()  # 상태 표시줄 아래로 한 칸 띄움
                console.print(delta, end="", markup=False, highlight=False)
                break  # 상태 표시줄(status) 블록을 빠져나감

    # 3. 나머지는 상태 표시줄 없이 스트리밍 출력
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
    messages: list[dict] = []

    info = collect_info()
    print_summary(info)

    confirm = Prompt.ask("\n[bold]위 정보로 커리큘럼을 생성할까요?[/]", choices=["y", "n"], default="y")
    if confirm == "n":
        console.print("[yellow]처음부터 다시 시작합니다.[/]")
        main()
        return

    user_msg = build_user_message(info)
    messages.append({"role": "user", "content": user_msg})

    response = stream_response(client, messages)
    messages.append({"role": "assistant", "content": response})

    # ── 후속 대화 루프 ─────────────────────────────────────
    console.print("[dim]커리큘럼 수정·보완 요청이나 추가 질문을 입력하세요. 종료하려면 'q' 또는 'quit'[/]\n")
    while True:
        user_input = Prompt.ask("[bold blue]>[/]").strip()
        if user_input.lower() in ("q", "quit", "exit", "종료"):
            console.print(Panel("[bold green]감사합니다! 성공적인 AX 교육이 되길 바랍니다.[/]", padding=(1, 4)))
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        response = stream_response(client, messages)
        messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]프로그램을 종료합니다.[/]")
