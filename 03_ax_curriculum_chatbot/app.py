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
특히 'AX Compass' 진단 결과를 분석하여 교육생의 성향에 최적화된 학습 경로를 제안합니다.

[AX Compass 성향별 가이드]
- 균형형: AI의 효용과 한계를 고루 이해함 -> 심화 실무 및 전략 수립에 집중
- 이해형: 원리는 아나 실행력이 부족함 -> 직접적인 API 활용 및 실습 비중 강화
- 과신형: AI를 맹신함 -> 할루시네이션(환각) 확인 및 비판적 사고, 검증 교육 강조
- 실행형: 일단 써보는 스타일 -> 생산성 도구 중심의 빠른 적용 사례 공유
- 판단형: 윤리·보안 중시 -> 책임감 있는 AI 활용 및 거버넌스 교육 포함
- 조심형: 보수적/우려 많음 -> 보안 가이드라인 및 안전한 활용법 안내로 심리적 장벽 제거

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

# (기존 선택 방식 관련 상수 및 함수 제거됨)

# ── 정보 수집 ────────────────────────────────────────────────
def collect_info() -> dict:
    console.print(Panel(
        "[bold white]AX 커리큘럼 설계 챗봇[/]\n"
        "[dim]기업 맞춤형 AI Transformation 교육 커리큘럼을 설계합니다.[/]",
        style="bold blue",
        padding=(1, 4),
    ))

    console.print(Rule("[bold]1단계: 교육 기본 정보[/]", style="blue"))
    company = Prompt.ask("1. 회사명 또는 팀 이름")
    goal = Prompt.ask("2. 교육 목표")
    audience = Prompt.ask("3. 교육 대상자")
    level = Prompt.ask("4. 현재 AI 활용 수준 (예: 입문, 초급, 중급)")
    duration = Prompt.ask("5. 교육 기간 또는 총 시간")
    themes = Prompt.ask("6. 원하는 핵심 주제")
    constraints = Prompt.ask("7. 꼭 반영해야 할 조건 또는 제한사항", default="없음")

    console.print(Rule("[bold]2단계: AX Compass 진단 결과[/]", style="blue"))
    console.print("[dim]결과 유형별 인원수를 입력해주세요.[/]")
    
    balanced = IntPrompt.ask("1. 균형형 인원수", default=0)
    understanding = IntPrompt.ask("2. 이해형 인원수", default=0)
    overconfident = IntPrompt.ask("3. 과신형 인원수", default=0)
    execution = IntPrompt.ask("4. 실행형 인원수", default=0)
    judgment = IntPrompt.ask("5. 판단형 인원수", default=0)
    cautious = IntPrompt.ask("6. 조심형 인원수", default=0)

    return {
        "company": company,
        "goal": goal,
        "audience": audience,
        "level": level,
        "duration": duration,
        "themes": themes,
        "constraints": constraints,
        "ax_compass": {
            "균형형": balanced,
            "이해형": understanding,
            "과신형": overconfident,
            "실행형": execution,
            "판단형": judgment,
            "조심형": cautious
        }
    }

# ── 요약 출력 ────────────────────────────────────────────────
def print_summary(info: dict):
    table = Table(title="입력 정보 요약", show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=25)
    table.add_column(style="white")

    table.add_row("1. 회사/팀명", info["company"])
    table.add_row("2. 교육 목표", info["goal"])
    table.add_row("3. 교육 대상자", info["audience"])
    table.add_row("4. AI 활용 수준", info["level"])
    table.add_row("5. 교육 기간", info["duration"])
    table.add_row("6. 핵심 주제", info["themes"])
    table.add_row("7. 조건/제한사항", info["constraints"])
    
    ax_str = ", ".join([f"{k}: {v}명" for k, v in info["ax_compass"].items() if v > 0])
    table.add_row("AX Compass 결과", ax_str if ax_str else "입력 없음")

    console.print()
    console.print(Panel(table, style="blue", padding=(1, 2)))

# ── 커리큘럼 생성 ────────────────────────────────────────────
def build_user_message(info: dict) -> str:
    ax_results = "\n".join([f"- {k}: {v}명" for k, v in info["ax_compass"].items()])
    
    return f"""다음 정보를 바탕으로 맞춤형 AX 교육 커리큘럼을 설계해주세요.

### 📋 기본 정보
1. **회사명 또는 팀 이름**: {info["company"]}
2. **교육 목표**: {info["goal"]}
3. **교육 대상자**: {info["audience"]}
4. **현재 AI 활용 수준**: {info["level"]}
5. **교육 기간 또는 총 시간**: {info["duration"]}
6. **원하는 핵심 주제**: {info["themes"]}
7. **꼭 반영해야 할 조건 또는 제한사항**: {info["constraints"]}

### 📊 [AX Compass 진단 결과]
{ax_results}

위의 진단 결과(유형별 인원수)를 고려하여, 각 유형의 특성에 맞는 교육 방식이나 강조점을 커리큘럼에 반영해 주세요.
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
