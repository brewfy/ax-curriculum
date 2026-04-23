"""
RAG 평가 실행 스크립트

사용법:
    python 06_3.Run.py --testset testset_sample.json
    python 06_3.Run.py --testset testset_sample.json --output ./reports
    python 06_3.Run.py --testset testset_sample.json --chroma-path ../05_Advanced_RAG/chroma_db
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAG 평가 파이프라인 실행")
    p.add_argument("--testset", required=True, help="테스트셋 JSON 경로")
    p.add_argument("--output", default="./reports", help="리포트 출력 디렉토리 (기본: ./reports)")
    p.add_argument("--chroma-path", default=None, help="ChromaDB 경로 (기본: ../05_Advanced_RAG/chroma_db)")
    p.add_argument("--collection", default="ax_compass_types", help="ChromaDB 컬렉션명")
    return p.parse_args()


def _load_testset(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_json_report(results, elapsed: float) -> dict:
    cases = [r.to_dict() for r in results]
    scores = [r.aggregate_score for r in results if r.error is None]
    return {
        "generated_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "summary": {
            "total_cases": len(results),
            "passed_cases": sum(1 for r in results if r.error is None),
            "avg_aggregate_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_precision_at_k": _avg([r.precision_at_k for r in results]),
            "avg_faithfulness": _avg([r.faithfulness for r in results]),
            "avg_requirement_coverage": _avg([r.requirement_coverage for r in results]),
            "rule_pass_rate": _rule_pass_rate(results),
        },
        "cases": cases,
    }


def _avg(values: list) -> float | None:
    filtered = [v for v in values if v is not None]
    return round(sum(filtered) / len(filtered), 4) if filtered else None


def _rule_pass_rate(results) -> float | None:
    rule_results = [r.rule_check.get("passed") for r in results if r.rule_check]
    if not rule_results:
        return None
    return round(sum(rule_results) / len(rule_results), 4)


def _build_markdown_report(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# RAG 평가 리포트",
        f"> 생성: {report['generated_at']}  |  소요: {report['elapsed_seconds']}s",
        "",
        "## 요약",
        "| 지표 | 값 |",
        "|------|----|",
        f"| 전체 케이스 | {s['total_cases']} |",
        f"| 성공 케이스 | {s['passed_cases']} |",
        f"| **종합 점수** | **{s['avg_aggregate_score']}** |",
        f"| Precision@k | {_fmt(s['avg_precision_at_k'])} |",
        f"| Faithfulness | {_fmt(s['avg_faithfulness'])} |",
        f"| Requirement Coverage | {_fmt(s['avg_requirement_coverage'])} |",
        f"| Rule Pass Rate | {_fmt(s['rule_pass_rate'])} |",
        "",
        "## 케이스별 결과",
        "| ID | 요약 | 종합 | P@k | Faith | Coverage | Rule | 오류 |",
        "|----|------|------|-----|-------|----------|------|------|",
    ]
    for c in report["cases"]:
        rc = c.get("rule_check", {})
        rule_str = "✅" if rc.get("passed") else ("❌" if rc else "-")
        lines.append(
            f"| {c['id']} | {c['summary']} "
            f"| {c['aggregate_score']} "
            f"| {_fmt(c['precision_at_k'])} "
            f"| {_fmt(c['faithfulness'])} "
            f"| {_fmt(c['requirement_coverage'])} "
            f"| {rule_str} "
            f"| {c['error'] or ''} |"
        )

    lines += ["", "## 규칙 검사 상세"]
    for c in report["cases"]:
        rc = c.get("rule_check", {})
        if not rc:
            continue
        lines.append(f"\n### {c['id']}")
        for key, detail in rc.get("details", {}).items():
            icon = "✅" if detail.get("pass") else "❌"
            lines.append(f"- {icon} `{key}`: 값={detail.get('value')}  기대={detail.get('expected', '-')}")

    return "\n".join(lines)


def _fmt(v) -> str:
    return f"{v:.4f}" if isinstance(v, float) else "-"


def main():
    args = _parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "evaluator_mod", Path(__file__).parent / "06_2.Evaluator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    Evaluator = mod.Evaluator

    testset = _load_testset(args.testset)
    total_cases = len(testset.get("test_cases", []))
    print(f"테스트셋 로드: {total_cases}개 케이스")

    kwargs = {"collection_name": args.collection}
    if args.chroma_path:
        kwargs["chroma_path"] = args.chroma_path

    evaluator = Evaluator(**kwargs)

    import time
    t0 = time.time()
    results = evaluator.evaluate_all(testset)
    elapsed = time.time() - t0

    report = _build_json_report(results, elapsed)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = out_dir / f"report_{ts}.json"
    md_path = out_dir / f"report_{ts}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_build_markdown_report(report))

    # 콘솔 요약 출력
    s = report["summary"]
    print("\n" + "=" * 50)
    print("평가 완료")
    print("=" * 50)
    print(f"  종합 점수    : {s['avg_aggregate_score']}")
    print(f"  Precision@k  : {_fmt(s['avg_precision_at_k'])}")
    print(f"  Faithfulness : {_fmt(s['avg_faithfulness'])}")
    print(f"  Coverage     : {_fmt(s['avg_requirement_coverage'])}")
    print(f"  Rule Pass    : {_fmt(s['rule_pass_rate'])}")
    print(f"  소요 시간    : {elapsed:.1f}s")
    print(f"\n  JSON  → {json_path}")
    print(f"  MD    → {md_path}")


if __name__ == "__main__":
    main()
