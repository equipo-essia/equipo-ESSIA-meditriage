"""Evalúa el motor rules-v0 contra el golden set.

Uso (desde la raíz del repo):
    python docs/ia/evaluate.py

Salida:
    docs/ia/evaluation-report.json  (resultado legible por máquina)
    resumen por pantalla
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from main import classify_esi  # noqa: E402

GOLDEN = HERE / "golden-set.json"
REPORT = HERE / "evaluation-report.json"


def run() -> dict:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    results = []
    for case in data["cases"]:
        category, justification = classify_esi(case["symptoms"], case["vitals"])
        if case["kind"] == "category":
            ok = category == case["expected_esi"]
            detail = {"expected": case["expected_esi"], "got": category}
        elif case["kind"] == "justification":
            missing = [f for f in case["expected_fragments"] if f not in justification]
            ok = not missing
            detail = {"expected_fragments": case["expected_fragments"], "missing": missing}
        else:
            raise ValueError(f"kind desconocido en {case['id']}: {case['kind']}")
        results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "ok": ok,
                "detail": detail,
                "justification": justification,
            }
        )

    total = len(results)
    passed = sum(r["ok"] for r in results)
    by_level = Counter()
    for case, result in zip(data["cases"], results, strict=True):
        if case["kind"] == "category" and result["ok"]:
            by_level[case["expected_esi"]] += 1

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "target": data["metadata"]["target"],
        "golden_set_version": data["metadata"]["version"],
        "total": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0,
        "category_cases": sum(r["kind"] == "category" for r in results),
        "justification_cases": sum(r["kind"] == "justification" for r in results),
        "correct_by_category": dict(sorted(by_level.items())),
        "failures": [r for r in results if not r["ok"]],
    }


def main() -> int:
    report = run()
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Motor: {report['target']}")
    print(f"Golden set: v{report['golden_set_version']}")
    print(f"Casos: {report['total']}  |  OK: {report['passed']}  |  accuracy: {report['accuracy']:.0%}")
    print(f"  categoria: {report['category_cases']}  justificacion: {report['justification_cases']}")
    print(f"  aciertos por categoria: {report['correct_by_category']}")
    if report["failures"]:
        print("FALLOS:")
        for r in report["failures"]:
            print(f"  {r['id']}: {r['detail']}")
        return 1
    print(f"Informe: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
