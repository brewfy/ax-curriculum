"""BM25 weight sweep — Precision@k 변화 확인."""
import importlib.util
import json
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).parent


def _load(name, path):
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


testset = json.loads((_EVAL_DIR / "testset_sample.json").read_text(encoding="utf-8"))

weights = [0.5, 1.0, 2.0, 3.0]
print(f"{'BM25w':>6} | {'P@k':>6} | {'Faith':>6} | {'Cover':>6} | {'Rule':>6} | {'Agg':>6}")
print("-" * 52)

for w in weights:
    evaluator_mod = _load("evaluator_mod", _EVAL_DIR / "06_2.Evaluator.py")
    ev = evaluator_mod.Evaluator(bm25_weight=w)
    results = ev.evaluate_all(testset)

    pk   = sum(r.precision_at_k or 0 for r in results) / len(results)
    fa   = sum(r.faithfulness or 0 for r in results) / len(results)
    co   = sum(r.requirement_coverage or 0 for r in results) / len(results)
    ru   = sum(r.rule_check.get("score", 0) for r in results) / len(results)
    agg  = sum(r.aggregate_score for r in results) / len(results)

    print(f"{w:>6.1f} | {pk:>6.4f} | {fa:>6.4f} | {co:>6.4f} | {ru:>6.4f} | {agg:>6.4f}")
