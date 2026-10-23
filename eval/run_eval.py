import argparse
import json
import re
import time
from pathlib import Path

from app.orchestrator import analyze

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = ROOT / "eval" / "questions.json"
RESULTS_FILE = ROOT / "eval" / "results.json"


def normalize_text(value):
    value = str(value).strip().lower()
    value = re.sub(r"[`*_]", "", value)
    return re.sub(r"\s+", " ", value)


def extract_number(value):
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "")

    # Prefer explicitly stated percentages.
    percentages = list(re.finditer(r"([-+]?\d*\.?\d+)\s*%", text))
    if percentages:
        return float(percentages[-1].group(1))

    # Prefer explicitly stated numerical results.
    patterns = [
        r"(?:the\s+)?(?:count|total|result|answer)\s+is\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
        r"\bthere\s+are\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
        r"\b(?:count|total)\s*[:=]\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            return float(matches[-1].group(1))

    # Prefer the first number in the first sentence, which usually states the answer.
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    matches = list(re.finditer(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", first_sentence))
    if matches:
        return float(matches[0].group())

    # Handle number words at the start of an answer.
    words = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12,
    }
    match = re.match(r"^\s*(" + "|".join(words) + r")\b", text, re.IGNORECASE)
    if match:
        return float(words[match.group(1).lower()])

    matches = list(re.finditer(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text))
    return float(matches[0].group()) if matches else None


def _chart_probe_code(code, plot):
    prefix = r"""
import json as __probe_json
import numpy as __probe_np
import matplotlib.axes as __probe_axes

__chart_probe = {"bar": [], "hist": [], "scatter": []}

__original_bar = __probe_axes.Axes.bar
def __record_bar(self, x, height, *args, **kwargs):
    __chart_probe["bar"].append({
        "ax": self,
        "x": __probe_np.asarray(x, dtype=object).reshape(-1).tolist(),
        "height": __probe_np.asarray(height).reshape(-1).tolist(),
    })
    return __original_bar(self, x, height, *args, **kwargs)
__probe_axes.Axes.bar = __record_bar

__original_hist = __probe_axes.Axes.hist
def __record_hist(self, x, *args, **kwargs):
    values = __probe_np.asarray(x).reshape(-1)
    __chart_probe["hist"].append(values.tolist())
    return __original_hist(self, x, *args, **kwargs)
__probe_axes.Axes.hist = __record_hist

__original_scatter = __probe_axes.Axes.scatter
def __record_scatter(self, x, y, *args, **kwargs):
    __chart_probe["scatter"].append({
        "x": __probe_np.asarray(x).reshape(-1).tolist(),
        "y": __probe_np.asarray(y).reshape(-1).tolist(),
    })
    return __original_scatter(self, x, y, *args, **kwargs)
__probe_axes.Axes.scatter = __record_scatter
"""
    suffix = r"""
import json as __summary_json
import numpy as __summary_np
import matplotlib.pyplot as __summary_plt

def __stats(values):
    a = __summary_np.asarray(values, dtype=float).reshape(-1)
    a = a[__summary_np.isfinite(a)]
    if len(a) == 0:
        raise ValueError("Chart contains no valid numeric values")
    return {
        "min": round(float(a.min()), 6),
        "max": round(float(a.max()), 6),
        "sum": round(float(a.sum()), 6),
    }

__plot = __EXPECTED_PLOT__
if __plot == "bar":
    if not __chart_probe["bar"]:
        raise ValueError("No bar data was captured")
    entry = __chart_probe["bar"][-1]
    ax = entry["ax"]
    labels = entry["x"]
    heights = entry["height"]
    if not all(isinstance(x, str) for x in labels):
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        if len(tick_labels) == len(heights) and all(tick_labels):
            labels = tick_labels
    __summary = {
        "type": "chart", "plot": "bar",
        "labels": [str(x) for x in labels],
        "heights": [round(float(x), 6) for x in heights],
    }
elif __plot == "hist":
    if not __chart_probe["hist"]:
        raise ValueError("No histogram data was captured")
    values = __summary_np.asarray(
        __chart_probe["hist"][-1], dtype=float
    ).reshape(-1)
    values = values[__summary_np.isfinite(values)]
    if len(values) == 0:
        raise ValueError("Histogram contains no valid values")
    __summary = {
        "type": "chart", "plot": "hist", "n": int(len(values)),
        "min": round(float(values.min()), 6),
        "max": round(float(values.max()), 6),
    }
elif __plot == "scatter":
    if not __chart_probe["scatter"]:
        raise ValueError("No scatter data was captured")
    entry = __chart_probe["scatter"][-1]
    x = __summary_np.asarray(entry["x"], dtype=float).reshape(-1)
    y = __summary_np.asarray(entry["y"], dtype=float).reshape(-1)
    if len(x) != len(y):
        raise ValueError("Scatter axes have different lengths")
    valid = __summary_np.isfinite(x) & __summary_np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(x) == 0:
        raise ValueError("Scatter plot contains no valid points")
    __summary = {
        "type": "chart", "plot": "scatter", "n": int(len(x)),
        "x": __stats(x), "y": __stats(y),
    }
else:
    raise ValueError("Unsupported chart type: " + str(__plot))

result = __summary_json.dumps(__summary)
"""
    suffix = suffix.replace("__EXPECTED_PLOT__", repr(plot))
    return prefix + "\n" + code + "\n" + suffix


def _close_enough(actual, expected, tolerance):
    try:
        actual = float(actual)
        expected = float(expected)
        if tolerance == 0:
            return actual == expected
        return abs(actual - expected) <= abs(expected) * tolerance
    except (TypeError, ValueError):
        return False


def _compare_chart(actual, expected):
    plot = expected["plot"]
    if actual.get("plot") != plot:
        return False, {"error": "Chart type mismatch", "actual": actual}

    tolerance = float(expected.get("rel_tol", 0.01))
    problems = []

    if plot == "bar":
        actual_labels = actual.get("labels", [])
        actual_heights = actual.get("heights", [])
        expected_labels = expected.get("labels", [])
        expected_heights = expected.get("heights", [])

        if len(actual_labels) != len(actual_heights):
            problems.append("actual label/height count differs")
        elif len(expected_labels) != len(expected_heights):
            problems.append("expected label/height count differs")
        elif len(actual_labels) != len(expected_labels):
            problems.append("bar category count differs")
        else:
            actual_map = {
                str(label): height
                for label, height in zip(actual_labels, actual_heights)
            }
            expected_map = {
                str(label): height
                for label, height in zip(expected_labels, expected_heights)
            }

            if len(actual_map) != len(actual_labels):
                problems.append("actual chart has duplicate labels")
            elif len(expected_map) != len(expected_labels):
                problems.append("expected chart has duplicate labels")
            elif set(actual_map) != set(expected_map):
                problems.append("bar labels differ")
            elif not all(
                _close_enough(actual_map[label], expected_map[label], tolerance)
                for label in expected_map
            ):
                problems.append("bar heights differ")

    elif plot == "hist":
        if actual.get("n") != expected.get("n"):
            problems.append("histogram count differs")
        for key in ("min", "max"):
            if not _close_enough(actual.get(key), expected.get(key), tolerance):
                problems.append("histogram " + key + " differs")

    elif plot == "scatter":
        if actual.get("n") != expected.get("n"):
            problems.append("scatter point count differs")
        for axis in ("x", "y"):
            for key in ("min", "max", "sum"):
                if not _close_enough(
                    actual.get(axis, {}).get(key),
                    expected.get(axis, {}).get(key),
                    tolerance,
                ):
                    problems.append(f"scatter {axis}.{key} differs")
    else:
        problems.append("unsupported expected chart type")

    return not problems, {
        "actual": actual,
        "expected": expected,
        "problems": problems,
    }


def score_result(result, expected, csv_path=None):
    expected_type = expected["type"]
    status = result.get("status", "")
    answer = result.get("answer", "")

    if expected_type == "cannot_answer":
        passed = status == "cannot_answer"
        return passed, "Correctly refused" if passed else "Expected cannot_answer"

    if expected_type == "chart":
        if status != "ok" or not result.get("chart_path"):
            return False, "Expected a successfully generated chart"
        if not result.get("code") or csv_path is None:
            return False, "Chart code or dataset path unavailable for validation"

        from app import sandbox
        probe = sandbox.run_code(
            _chart_probe_code(result["code"], expected["plot"]),
            str(csv_path),
        )
        if not probe.get("ok"):
            return False, {
                "error": "Chart data probe failed",
                "details": probe.get("error", ""),
            }

        try:
            actual = json.loads(probe["result"])
        except (ValueError, TypeError):
            return False, {
                "error": "Chart data probe returned invalid JSON",
                "details": probe.get("result", ""),
            }

        return _compare_chart(actual, expected)

    if status != "ok":
        return False, f"Pipeline status was {status or 'missing'}"

    if expected_type == "number":
        actual = extract_number(answer)
        if actual is None:
            return False, "Could not extract a number from the answer"
        target = float(expected["value"])
        tolerance = float(expected.get("rel_tol", 0.01))
        allowed_error = abs(target) * tolerance
        passed = actual == target if tolerance == 0 else abs(actual - target) <= allowed_error
        return passed, {
            "actual": actual,
            "expected": target,
            "absolute_error": abs(actual - target),
        }

    if expected_type == "text":
        actual = normalize_text(answer)
        target = normalize_text(expected["value"])
        return target in actual, {"actual": answer, "expected": expected["value"]}

    return False, f"Unsupported expected type: {expected_type}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", help="Question IDs to run, e.g. taxis-04 taxis-05")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed questions in saved results")
    args = parser.parse_args()

    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    old_report = {}
    old_results = {}

    if RESULTS_FILE.exists():
        try:
            old_report = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            old_results = {r["id"]: r for r in old_report.get("results", [])}
        except (json.JSONDecodeError, KeyError, TypeError):
            old_report, old_results = {}, {}

    if args.ids:
        selected_ids = set(args.ids)
        unknown = selected_ids - {q["id"] for q in questions}
        if unknown:
            parser.error("Unknown question IDs: " + ", ".join(sorted(unknown)))
        selected = [q for q in questions if q["id"] in selected_ids]
    elif args.retry_failed:
        selected = [
            q for q in questions
            if q["id"] not in old_results or not old_results[q["id"]].get("passed", False)
        ]
    else:
        selected = questions

    if not selected:
        print("No questions selected.")
        return

    results_by_id = dict(old_results)
    started = time.time()

    for index, item in enumerate(selected, start=1):
        csv_path = ROOT / item["csv"]
        print(f'[{index}/{len(selected)}] {item["id"]}: {item["question"]}', flush=True)

        record = {
            "id": item["id"],
            "dataset": item["dataset"],
            "kind": item["kind"],
            "question": item["question"],
            "expected": item["expected"],
        }

        try:
            pipeline_result = analyze(item["question"], str(csv_path))
            passed, details = score_result(pipeline_result, item["expected"], csv_path)
            record.update({
                "passed": passed,
                "details": details,
                "status": pipeline_result.get("status"),
                "answer": pipeline_result.get("answer"),
                "error": pipeline_result.get("error", ""),
                "chart_path": pipeline_result.get("chart_path"),
                "stats": pipeline_result.get("stats", {}),
            })
        except Exception as error:
            record.update({
                "passed": False,
                "details": "Evaluation raised an exception",
                "status": "exception",
                "error": f"{type(error).__name__}: {error}",
            })

        results_by_id[item["id"]] = record
        print("    " + ("PASS" if record["passed"] else "FAIL"), flush=True)

        # Save progress after every question so interruptions don't lose results.
        ordered_results = [
            results_by_id[q["id"]] for q in questions if q["id"] in results_by_id
        ]
        passed_count = sum(r.get("passed", False) for r in ordered_results)
        total = len(questions)
        report = {
            "total": total,
            "passed": passed_count,
            "failed": len(ordered_results) - passed_count,
            "accuracy_percent": round(passed_count / len(ordered_results) * 100, 2)
                if ordered_results else 0,
            "duration_seconds": round(time.time() - started, 2),
            "results": ordered_results,
            "completed_questions": len(ordered_results),
        }
        RESULTS_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Questions in this run: {len(selected)}")
    print(f"Saved results: {len(results_by_id)}/{len(questions)}")
    print(f"Passed: {sum(r.get('passed', False) for r in results_by_id.values())}")
    print(f"Failed: {sum(not r.get('passed', False) for r in results_by_id.values())}")
    print(f"Report saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
