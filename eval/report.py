"""Builds the results report from eval/results/<run>.jsonl.

  .venv/bin/python -m eval.report --run-name full
  Add --rescore to score the saved answers again (use this after fixing the scorer).
"""
import argparse
import json
import math
import os
import statistics

from eval import scorer
from eval.run_eval import ARMS, Q_PATH, RESULTS_DIR, load_records


def wilson(k, n):
    """95% range for a rate. With 50 questions it is wide - that is the honest picture."""
    if n == 0:
        return 0.0, 0.0
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def sign_test(b, c):
    """Two-sided exact test on the questions where exactly one of the two systems was right."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def pct(k, n):
    return f"{100 * k / n:.0f}%" if n else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", required=True)
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args()

    path = os.path.join(RESULTS_DIR, f"{args.run_name}.jsonl")
    latest = {}
    for r in load_records(path):  # the last record for each (arm, id) wins
        latest[(r["arm"], r["id"])] = r
    if not latest:
        raise SystemExit(f"No results in {path}")

    with open(Q_PATH, encoding="utf-8") as f:
        questions = {q["id"]: q for q in json.load(f)}
    if args.rescore:
        for key, r in latest.items():
            if r["status"] != "exception":
                r["score"] = scorer.score(questions[r["id"]], r)

    arms = [a for a in ARMS if any(k[0] == a for k in latest)]
    rows = {a: [r for k, r in latest.items() if k[0] == a] for a in arms}
    lines = [f"# Evaluation report: {args.run_name}", ""]

    # ---- accuracy
    lines += ["## Accuracy", "",
              "Strict = `review` counts as wrong. Lenient = `review` counts as right. The truth is in between.", "",
              "| Arm | Questions | Strict | Lenient | Strict 95% range | Review |",
              "|---|---|---|---|---|---|"]
    for a in arms:
        n = len(rows[a])
        p = sum(r["score"]["verdict"] == "pass" for r in rows[a])
        rv = sum(r["score"]["verdict"] == "review" for r in rows[a])
        lo, hi = wilson(p, n)
        lines.append(f"| {a} | {n} | {p} ({pct(p, n)}) | {p + rv} ({pct(p + rv, n)}) | "
                     f"{100 * lo:.0f}% - {100 * hi:.0f}% | {rv} |")

    # ---- by kind
    kinds = ["lookup", "calculation", "chart", "unanswerable"]
    lines += ["", "## Strict score by question kind", "",
              "| Arm | " + " | ".join(kinds) + " |", "|---|" + "---|" * len(kinds)]
    for a in arms:
        cells = []
        for k in kinds:
            sub = [r for r in rows[a] if r["kind"] == k]
            cells.append(f"{sum(r['score']['verdict'] == 'pass' for r in sub)}/{len(sub)}")
        lines.append(f"| {a} | " + " | ".join(cells) + " |")

    # ---- failure types
    cats = ["wrong_answer", "chart_wrong", "chart_missing", "false_refusal", "guessed",
            "not_sure", "error", "infra_error", "scorer_error"]
    lines += ["", "## Failure types (count)", "", "| Arm | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for a in arms:
        lines.append(f"| {a} | " + " | ".join(
            str(sum(r["score"]["category"] == c and r["score"]["verdict"] != "pass" for r in rows[a]))
            for c in cats) + " |")

    # ---- cost and time
    lines += ["", "## Cost, time and retries", "",
              "| Arm | Mean tokens | Total cost (USD) | Mean seconds | Median seconds | Mean AI calls "
              "| Review retries* | Connection retries | Rate-limit waits |", "|---|---|---|---|---|---|---|---|---|"]
    for a in arms:
        rs = rows[a]
        st = lambda key: [(r["stats"].get(key) or 0) for r in rs]
        secs = [r["wall_seconds"] for r in rs]
        lines.append(f"| {a} | {statistics.mean(st('total_tokens')):.0f} | {sum(st('cost_usd')):.4f} | "
                     f"{statistics.mean(secs):.1f} | {statistics.median(secs):.1f} | "
                     f"{statistics.mean(st('llm_calls')):.1f} | {sum(r['review_retries'] for r in rs)} | "
                     f"{sum(st('connection_retries'))} | {sum(st('rate_limit_waits'))} |")
    lines += ["", "*Team review retries are estimated from the number of AI calls. "
              "Seconds include rate-limit waits, but not the pause between questions. "
              "Cost can be slightly low if a request timed out after the server had already done the work.", ""]

    # ---- cost per correct answer
    lines += ["## Cost per correct answer (strict)", ""]
    for a in arms:
        p = sum(r["score"]["verdict"] == "pass" for r in rows[a])
        cost = sum((r["stats"].get("cost_usd") or 0) for r in rows[a])
        lines.append(f"- {a}: {'n/a (no correct answers)' if p == 0 else f'USD {cost / p:.5f} per correct answer'}")

    # ---- team vs baselines
    lines += ["", "## Team compared with each baseline (same questions)", "",
              "| Compared with | Both right | Only team right | Only baseline right | Both wrong | Sign-test p (strict) |",
              "|---|---|---|---|---|---|"]
    verdicts = []
    if "team" in arms:
        for base in ("baseline1", "baseline3"):
            if base not in arms:
                continue
            ids = sorted({r["id"] for r in rows["team"]} & {r["id"] for r in rows[base]})
            t = {i: latest[("team", i)]["score"]["verdict"] == "pass" for i in ids}
            b = {i: latest[(base, i)]["score"]["verdict"] == "pass" for i in ids}
            both = sum(t[i] and b[i] for i in ids)
            only_t = sum(t[i] and not b[i] for i in ids)
            only_b = sum(b[i] and not t[i] for i in ids)
            neither = sum(not t[i] and not b[i] for i in ids)
            p = sign_test(only_t, only_b)
            lines.append(f"| {base} | {both} | {only_t} | {only_b} | {neither} | {p:.3f} |")
            if p >= 0.05:
                verdicts.append(f"- Team vs {base}: NOT distinguishable at this sample size "
                                f"({only_t} vs {only_b} one-sided wins, p={p:.2f}). Do not claim a winner.")
            else:
                who = "team" if only_t > only_b else base
                verdicts.append(f"- Team vs {base}: the difference favours {who} "
                                f"({only_t} vs {only_b}, p={p:.3f}) in this one run.")
    lines += ["", "### Reading", ""] + verdicts + [
        "- This is ONE run of 50 questions on 3 small datasets. A gap of a few questions is noise.",
        "- The answer to 'is the team better?' must also weigh the extra tokens, cost and time above.", ""]

    # ---- failures
    lines += ["## Every question that did not pass", ""]
    for a in arms:
        bad = [r for r in rows[a] if r["score"]["verdict"] != "pass"]
        lines += [f"### {a} ({len(bad)})", ""]
        for r in sorted(bad, key=lambda x: x["id"]):
            ans = r["answer"].replace("\n", " ")[:90]
            lines.append(f"- {r['id']} [{r['score']['verdict']}/{r['score']['category']}] "
                         f"{r['score']['reason'][:140]} | answer: {ans}")
        lines.append("")

    text = "\n".join(lines)
    out = os.path.join(RESULTS_DIR, f"{args.run_name}_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()