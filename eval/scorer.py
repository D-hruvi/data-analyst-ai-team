"""Scorer: decides if an answer is right. No AI is used here.

score(question, record) returns {"verdict": pass|review|fail, "category": ..., "reason": ...}

Charts: the saved code is re-run in the Docker sandbox with a few extra lines
(CHART_PROBE) that read the figure and write a small summary into `result`.
Only the sandbox runs code, as the design rules say.
"""
import datetime
import json
import os
import re

import pandas as pd

from app import config, sandbox

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_DISTINCT_NUMBERS = 3  # more than this + a match = "review"
RESULT_MISSING = "did not set 'result'"
_CATEGORY_CACHE = {}


def _res(verdict, category, reason=""):
    return {"verdict": verdict, "category": category, "reason": reason}


# ---------------------------------------------------------------- numbers
def _numbers(text):
    """All numbers in the text as (value, decimals_shown)."""
    t = str(text).replace("\u2212", "-")
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", t)  # 1,234 -> 1234
    out = []
    for m in NUM_RE.finditer(t):
        s = m.group(0)
        decimals = len(s.split(".")[1]) if "." in s else 0
        out.append((float(s), decimals))
    return out


def _close(value, decimals, exp):
    target, rel = exp["value"], exp["rel_tol"]
    if rel == 0:
        return value == target  # counts must be exactly right
    tol = rel * abs(target)
    if decimals >= 1:  # allow normal rounding, e.g. 19.8 for 19.7859
        tol = max(tol, 0.5 * 10 ** -decimals + 1e-9)
    return abs(value - target) <= max(tol, 1e-9)


def score_number(exp, answer):
    nums = _numbers(answer)
    if exp["value"] == 0 and not nums:
        if re.search(r"\b(no|none|zero|nothing)\b", str(answer).lower()):
            return _res("pass", "correct", "says none/zero")
    if not nums:
        return _res("fail", "wrong_answer", f"no number in the answer (expected {exp['value']})")
    if not any(_close(v, d, exp) for v, d in nums):
        shown = [v for v, _ in nums][:5]
        return _res("fail", "wrong_answer", f"expected {exp['value']}, answer has {shown}")
    distinct = len({v for v, _ in nums})
    if distinct > MAX_DISTINCT_NUMBERS:
        return _res("review", "correct", f"matches, but the answer has {distinct} different numbers")
    return _res("pass", "correct")


# ---------------------------------------------------------------- text
def _word_re(s):
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])", re.I)


def _variants(target):
    """The expected text, plus other ways to write a date."""
    out = [target]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", target):
        d = datetime.date.fromisoformat(target)
        out += [f"{d:%B} {d.day}, {d.year}", f"{d.day} {d:%B} {d.year}",
                f"{d:%b} {d.day}, {d.year}", f"{d.day} {d:%b} {d.year}"]
    return out


def _distractors(csv_rel, target):
    """Other values from the same column as the expected value."""
    if csv_rel not in _CATEGORY_CACHE:
        df = pd.read_csv(os.path.join(config.ROOT, csv_rel))
        cols = {}
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                continue
            vals = [str(v) for v in df[c].dropna().unique()]
            if len(vals) <= 400:
                cols[c] = vals
        _CATEGORY_CACHE[csv_rel] = cols
    out = []
    for vals in _CATEGORY_CACHE[csv_rel].values():
        if target in vals:
            out += [v for v in vals if v != target and v.lower() not in target.lower()]
    return out


def score_text(exp, answer, csv_rel):
    target = exp["value"]
    answer = str(answer)
    if not any(_word_re(v).search(answer) for v in _variants(target)):
        return _res("fail", "wrong_answer", f"expected '{target}' not found in the answer")
    others = [o for o in _distractors(csv_rel, target) if _word_re(o).search(answer)]
    extra_dates = set(ISO_DATE_RE.findall(answer)) - {target} if ISO_DATE_RE.fullmatch(target) else set()
    if others or extra_dates:
        names = (others + sorted(extra_dates))[:4]
        return _res("review", "correct", f"contains '{target}' but also {names}")
    return _res("pass", "correct")


# ---------------------------------------------------------------- charts
CHART_PROBE = r'''
def __probe():
    import json
    import numpy as np
    from matplotlib.collections import PathCollection
    from matplotlib.patches import Rectangle

    def isnum(s):
        try:
            float(str(s).replace("\u2212", "-").replace(",", ""))
            return True
        except ValueError:
            return False

    def nearest(ticks, pos):
        if not ticks:
            return ""
        return min(ticks, key=lambda t: abs(t[0] - pos))[1]

    def stats(a):
        return {"min": round(float(np.min(a)), 6), "max": round(float(np.max(a)), 6),
                "sum": round(float(np.sum(a)), 6)}

    out = {"n_figures": len(plt.get_fignums()), "rects": 0, "bars": [], "sum": 0.0,
           "left": None, "right": None, "scatter": None}
    if not plt.get_fignums():
        return json.dumps(out)
    fig = plt.gcf()
    fig.canvas.draw()
    for ax in fig.axes:
        rects = [p for p in ax.patches if isinstance(p, Rectangle)]
        if len(rects) > out["rects"]:
            xt = [(float(t), l.get_text()) for t, l in zip(ax.get_xticks(), ax.get_xticklabels())]
            yt = [(float(t), l.get_text()) for t, l in zip(ax.get_yticks(), ax.get_yticklabels())]
            horizontal = all(isnum(l) for _, l in xt if l) and any(not isnum(l) for _, l in yt if l)
            vals, lefts, rights, items = [], [], [], []
            for r in rects:
                if horizontal:
                    v, lo, hi = r.get_width(), r.get_y(), r.get_y() + r.get_height()
                    label = nearest(yt, (lo + hi) / 2)
                else:
                    v, lo, hi = r.get_height(), r.get_x(), r.get_x() + r.get_width()
                    label = nearest(xt, (lo + hi) / 2)
                vals.append(float(v))
                lefts.append(float(lo))
                rights.append(float(hi))
                items.append([label, round(float(v), 6)])
            out["rects"] = len(rects)
            out["sum"] = round(sum(vals), 6)
            out["left"] = min(lefts)
            out["right"] = max(rights)
            out["bars"] = items if len(items) <= 40 else []
        pts = []
        for c in ax.collections:
            if isinstance(c, PathCollection):
                off = np.ma.filled(np.ma.asarray(c.get_offsets()).astype(float), np.nan)
                pts.append(np.asarray(off, dtype=float))
        for ln in ax.lines:
            if ln.get_marker() not in (None, "None", "", " ") and ln.get_linestyle() in ("None", "none", " ", ""):
                pts.append(np.column_stack([np.asarray(ln.get_xdata(), dtype=float),
                                            np.asarray(ln.get_ydata(), dtype=float)]))
        if pts:
            arr = np.vstack(pts)
            arr = arr[np.isfinite(arr).all(axis=1)]
            if len(arr) and (out["scatter"] is None or len(arr) > out["scatter"]["n"]):
                out["scatter"] = {"n": int(len(arr)), "x": stats(arr[:, 0]), "y": stats(arr[:, 1])}
    return json.dumps(out)


result = __probe()
'''


def _probe(code, csv_abs):
    """Re-run the saved code in the sandbox and read the figure. Returns (summary, error)."""
    out = sandbox.run_code(code.rstrip() + "\n\n" + CHART_PROBE, csv_abs)
    if out.get("chart_path") and os.path.exists(out["chart_path"]):
        os.remove(out["chart_path"])  # the probe's own picture is not needed
    if not out["ok"]:
        return None, out["error"][-300:]
    try:
        return json.loads(out["result"]), ""
    except ValueError:
        return None, "probe output could not be read"


def _near(a, b, rel):
    return abs(a - b) <= rel * abs(b) + 1e-9


def score_chart(exp, rec, csv_abs):
    if not rec.get("chart_exists"):
        return _res("fail", "chart_missing", "no chart file was produced")
    summ, err = _probe(rec.get("code", ""), csv_abs)
    if summ is None:
        return _res("fail", "chart_wrong", f"could not inspect the chart: {err}")
    if summ["n_figures"] == 0:
        return _res("fail", "chart_wrong", "no figure found when the code was re-run")
    plot = exp["plot"]

    if plot == "bar":
        if not summ["bars"]:
            return _res("fail", "chart_wrong", "not a bar chart (no bars or too many bars)")
        obs = {}
        for label, v in summ["bars"]:
            k = str(label).strip().lower()
            obs[k] = obs.get(k, 0.0) + v
        want = {str(l).strip().lower(): h for l, h in zip(exp["labels"], exp["heights"])}
        if set(obs) != set(want):
            return _res("fail", "chart_wrong",
                        f"bar labels {sorted(obs)} differ from expected {sorted(want)}")
        bad = [k for k in want if not _near(obs[k], want[k], exp["rel_tol"])]
        if bad:
            return _res("fail", "chart_wrong", f"wrong bar heights for {bad}")
        return _res("pass", "correct")

    if plot == "hist":
        if summ["rects"] < 5:
            return _res("fail", "chart_wrong", f"only {summ['rects']} bars, not a histogram")
        if abs(summ["sum"] - exp["n"]) > 0.5:
            return _res("fail", "chart_wrong",
                        f"bars add up to {summ['sum']}, expected {exp['n']} (counts, not density)")
        eps = 1e-6 * (exp["max"] - exp["min"]) + 1e-9
        if summ["left"] > exp["min"] + eps or summ["right"] < exp["max"] - eps:
            return _res("fail", "chart_wrong", "bins do not cover the full data range")
        return _res("pass", "correct")

    if plot == "scatter":
        sc = summ["scatter"]
        if not sc:
            return _res("fail", "chart_wrong", "no scatter points found")
        if sc["n"] != exp["n"]:
            return _res("fail", "chart_wrong", f"{sc['n']} points, expected {exp['n']}")
        for axis in ("x", "y"):
            for key in ("min", "max", "sum"):
                if not _near(sc[axis][key], exp[axis][key], exp["rel_tol"]):
                    return _res("fail", "chart_wrong",
                                f"{axis}-axis {key} is {sc[axis][key]}, expected {exp[axis][key]} "
                                "(wrong column or swapped axes)")
        return _res("pass", "correct")

    return _res("fail", "chart_wrong", f"unknown plot type {plot}")


# ---------------------------------------------------------------- main entry
def score(q, rec, relax_result_contract=False):
    """q = a question from questions.json. rec = what the system returned (see run_eval.py)."""
    exp = q["expected"]
    status = rec.get("status")
    delivered = bool(rec.get("ok")) and status in ("ok", "answered")

    if exp["type"] == "cannot_answer":
        if status == "cannot_answer":
            return _res("pass", "correct", "refused correctly")
        if status == "not_sure":
            return _res("review", "not_sure", "said 'I am not sure' (a safe refusal, but not the planned one)")
        if delivered:
            return _res("fail", "guessed", "gave an answer to an unanswerable question")
        return _res("fail", "error", "crashed instead of refusing")

    # POST-HOC sensitivity only, never the primary result: the chart code ran, but the runner
    # rejected it because `result` was None. Score the chart itself.
    if (relax_result_contract and exp["type"] == "chart" and status == "error"
            and RESULT_MISSING in str(rec.get("error", "")) and rec.get("code")):
        r = score_chart(exp, dict(rec, chart_exists=True), os.path.join(config.ROOT, q["csv"]))
        if r["verdict"] == "pass":
            return _res("pass", "correct_post_hoc", "chart is right, but the run failed because result was None")
        return r

    # the question can be answered
    if status == "cannot_answer":
        return _res("fail", "false_refusal", str(rec.get("error", ""))[:200])
    if status == "not_sure":
        return _res("fail", "not_sure", "gave up after the allowed attempts")
    if not delivered:
        return _res("fail", "error", str(rec.get("error", ""))[:200] or "no answer")

    answer = rec.get("answer", "")
    csv_rel = q["csv"]
    if exp["type"] == "number":
        return score_number(exp, answer)
    if exp["type"] == "text":
        return score_text(exp, answer, csv_rel)
    if exp["type"] == "chart":
        return score_chart(exp, rec, os.path.join(config.ROOT, csv_rel))
    return _res("fail", "error", f"unknown expected type {exp['type']}")