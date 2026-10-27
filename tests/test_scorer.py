"""Batch 4 gate 1: does the scorer judge made-up answers correctly?
Run from the project root:  .venv/bin/python -m tests.test_scorer"""
import os
import sys

import pandas as pd

from app import config
from eval import scorer

CSV = "eval/datasets/tips.csv"
failures = []


def check(label, got, want):
    ok = got == want
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        failures.append(label)


def q(expected, kind="calculation"):
    return {"id": "t", "csv": CSV, "kind": kind, "question": "?", "expected": expected}


def rec(answer="", status="ok", code="", chart=False):
    return {"status": status, "ok": status in ("ok", "answered"), "answer": answer,
            "code": code, "chart_exists": chart, "error": ""}


def verdict(question, record):
    return scorer.score(question, record)["verdict"]


num = q({"type": "number", "value": 19.785943, "rel_tol": 0.01})
cnt = q({"type": "number", "value": 244, "rel_tol": 0}, "calculation")
zero = q({"type": "number", "value": 0, "rel_tol": 0})
check("number: rounded answer passes", verdict(num, rec("The average total_bill is $19.79.")), "pass")
check("number: raw answer passes", verdict(num, rec("19.78594262295082")), "pass")
check("number: wrong answer fails", verdict(num, rec("The average is $25.00.")), "fail")
check("count: exact passes", verdict(cnt, rec("There are 1,244 rows... no, 244 rows.")), "pass")
check("count: off by one fails", verdict(cnt, rec("There are 245 rows.")), "fail")
check("zero: 'no rows' passes", verdict(zero, rec("No rows match.")), "pass")
check("number: many numbers = review", verdict(num, rec("19.79 and 1 and 2 and 3 and 4")), "review")

text = q({"type": "text", "value": "Sun"}, "lookup")
check("text: right answer passes", verdict(text, rec("Sun")), "pass")
check("text: wrong answer fails", verdict(text, rec("Sat")), "fail")
check("text: also lists others = review", verdict(text, rec("Sun has the highest, Sat is lower")), "review")

cant = q({"type": "cannot_answer"}, "unanswerable")
check("cannot: refusal passes", verdict(cant, rec(status="cannot_answer")), "pass")
check("cannot: a guess fails", verdict(cant, rec("4.5")), "fail")
check("cannot: not_sure = review", verdict(cant, rec(status="not_sure")), "review")
check("answerable but refused fails", verdict(num, rec(status="cannot_answer")), "fail")
check("answerable but not_sure fails", verdict(num, rec(status="not_sure")), "fail")

# ---- charts (needs Docker)
tips = pd.read_csv(os.path.join(config.ROOT, CSV))
g = tips.groupby("day")["tip"].sum()
bar = q({"type": "chart", "plot": "bar", "labels": list(g.index),
         "heights": [float(x) for x in g.values], "rel_tol": 0.01}, "chart")
hist = q({"type": "chart", "plot": "hist", "n": int(tips["total_bill"].count()),
          "min": float(tips["total_bill"].min()), "max": float(tips["total_bill"].max())}, "chart")


def st(s):
    return {"min": float(s.min()), "max": float(s.max()), "sum": float(s.sum())}


sc = q({"type": "chart", "plot": "scatter", "n": len(tips), "x": st(tips["total_bill"]),
        "y": st(tips["tip"]), "rel_tol": 0.001}, "chart")

good_bar = "s = df.groupby('day')['tip'].sum()\nplt.bar(s.index, s.values)\nresult = 'ok'"
mean_bar = "s = df.groupby('day')['tip'].mean()\nplt.bar(s.index, s.values)\nresult = 'ok'"
check("chart bar: right data passes", verdict(bar, rec("ok", code=good_bar, chart=True)), "pass")
check("chart bar: wrong data (mean) fails", verdict(bar, rec("ok", code=mean_bar, chart=True)), "fail")
check("chart: no file fails", verdict(bar, rec("ok", code=good_bar, chart=False)), "fail")
check("chart hist: 10 bins passes",
      verdict(hist, rec("ok", code="plt.hist(df['total_bill'], bins=10)\nresult = 'ok'", chart=True)), "pass")
check("chart hist: 20 bins passes",
      verdict(hist, rec("ok", code="plt.hist(df['total_bill'], bins=20)\nresult = 'ok'", chart=True)), "pass")
check("chart scatter: right axes passes",
      verdict(sc, rec("ok", code="plt.scatter(df['total_bill'], df['tip'])\nresult = 'ok'", chart=True)), "pass")
check("chart scatter: swapped axes fails",
      verdict(sc, rec("ok", code="plt.scatter(df['tip'], df['total_bill'])\nresult = 'ok'", chart=True)), "fail")

print()
# ---- regression: chart code that ended with result = None (runner rejects it)
no_result = {
    "status": "error", "ok": False, "answer": "", "chart_exists": False,
    "error": "The code did not set 'result' (or set it to None).",
    "code": "plt.hist(df['total_bill'], bins=20)\nresult = None",
}
wrong_chart = dict(
    no_result,
    code="plt.hist(df['tip'], bins=20)\nresult = None",
)
other_error = dict(no_result, error="KeyError: 'x'")

check("contract: default scoring still fails it",
      scorer.score(hist, no_result)["verdict"], "fail")
check("contract: relaxed scoring rescues a correct chart",
      scorer.score(hist, no_result, relax_result_contract=True)["verdict"], "pass")
check("contract: relaxed scoring still fails a wrong chart",
      scorer.score(hist, wrong_chart, relax_result_contract=True)["verdict"], "fail")
check("contract: relaxed scoring ignores other errors",
      scorer.score(hist, other_error, relax_result_contract=True)["verdict"], "fail")

if failures:
    print(f"{len(failures)} CHECK(S) FAILED. Paste this output. Do not run the evaluation.")
    sys.exit(1)
print("ALL SCORER CHECKS PASSED")