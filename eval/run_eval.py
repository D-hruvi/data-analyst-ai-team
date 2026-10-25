
"""Runs the evaluation: 3 arms x 50 questions. Saves after EVERY result.

Arms:
  baseline1 = single AI, 1 attempt
  baseline3 = single AI, up to 3 attempts
  team      = Planner + Coder + Reviewer + Explainer

Run from the project root:
  .venv/bin/python -m eval.run_eval --run-name full

Resume after a stop: run the same command again.
Re-run API failures: add --retry-errors
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

from app import config
from app.orchestrator import analyze
from baseline.single_agent import answer_question
from eval import scorer

ROOT = config.ROOT
Q_PATH = os.path.join(ROOT, "eval", "questions.json")
SHA_PATH = os.path.join(ROOT, "eval", "questions.sha256")
RESULTS_DIR = os.path.join(ROOT, "eval", "results")
ARMS = ("baseline1", "baseline3", "team")


def check_frozen():
    """Stop if questions.json changed after the freeze."""
    with open(SHA_PATH, encoding="utf-8") as f:
        frozen = f.read().split()[0]
    with open(Q_PATH, "rb") as f:
        now = hashlib.sha256(f.read()).hexdigest()
    if now != frozen:
        sys.exit(
            "STOP: eval/questions.json does not match eval/questions.sha256. "
            "The questions changed after the freeze. Do not run the evaluation."
        )
    return now


def git(*args):
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip()
    except Exception:
        return "unknown"


def run_arm(arm, csv_abs, question):
    if arm == "baseline1":
        return answer_question(csv_abs, question)
    if arm == "baseline3":
        return answer_question(csv_abs, question, max_attempts=3)
    return analyze(question, csv_abs)


def team_review_retries(status, llm_calls):
    """Estimate retries because the orchestrator does not count them directly.

    Assumes planner, coder, reviewer and explainer each make one call.
    Success with A attempts = 2A+2 calls. Giving up after 3 attempts = 7 calls.
    """
    calls = llm_calls or 0
    if status == "ok":
        return max(0, (calls - 4) // 2)
    return max(0, (calls - 3) // 2)


def chart_exists(result):
    if result.get("chart_path"):
        return os.path.exists(result["chart_path"])
    if result.get("chart_url"):
        return os.path.exists(
            os.path.join(config.CHART_DIR, os.path.basename(result["chart_url"]))
        )
    return False


def load_records(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", required=True, help="e.g. dry or full")
    ap.add_argument("--ids", default="", help="comma list of question IDs (default: all)")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument(
        "--tpm", type=int, default=8000,
        help="tokens per minute allowed by your plan",
    )
    ap.add_argument(
        "--retry-errors", action="store_true",
        help="run again the records that crashed",
    )
    args = ap.parse_args()

    if args.tpm <= 0:
        ap.error("--tpm must be greater than zero")

    fingerprint = check_frozen()
    config.require_key()
    arms = [a for a in args.arms.split(",") if a]
    for arm in arms:
        if arm not in ARMS:
            sys.exit(f"Unknown arm {arm}. Choose from {ARMS}")

    with open(Q_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    if args.ids:
        wanted = set(args.ids.split(","))
        unknown = wanted - {q["id"] for q in questions}
        if unknown:
            sys.exit(f"Unknown question ids: {sorted(unknown)}")
        questions = [q for q in questions if q["id"] in wanted]

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"{args.run_name}.jsonl")
    meta_path = os.path.join(RESULTS_DIR, f"{args.run_name}.meta.json")

    if not os.path.exists(meta_path):
        meta = {
            "started": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": config.MODEL,
            "reasoning_effort": config.REASONING_EFFORT,
            "agent_effort": config.AGENT_EFFORT,
            "git_commit": git("rev-parse", "--short", "HEAD"),
            "git_tree_dirty": bool(git("status", "--porcelain")),
            "questions_sha256": fingerprint,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    else:
        with open(meta_path, encoding="utf-8") as f:
            old = json.load(f)
        if old.get("model") != config.MODEL:
            sys.exit(
                f"STOP: this run used model {old.get('model')} but config says "
                f"{config.MODEL}. Use a new --run-name, or you will mix two models."
            )
        if old.get("questions_sha256") != fingerprint:
            sys.exit("STOP: this run's metadata has a different questions fingerprint.")
        if old.get("agent_effort") != config.AGENT_EFFORT:
            sys.exit("STOP: agent effort differs from the existing run. Use a new run name.")
        if old.get("reasoning_effort") != config.REASONING_EFFORT:
            sys.exit("STOP: reasoning effort differs from the existing run. Use a new run name.")

    done = set()
    for record in load_records(out_path):
        if args.retry_errors and record.get("status") == "exception":
            continue
        done.add((record["arm"], record["id"]))

    todo = [
        (question, arm)
        for question in questions
        for arm in arms
        if (arm, question["id"]) not in done
    ]
    print(f"{len(done)} already done, {len(todo)} to run. Saving to {out_path}")
    crashes = 0

    for i, (question, arm) in enumerate(todo, 1):
        csv_abs = os.path.join(ROOT, question["csv"])
        start = time.time()
        exc = None

        try:
            result = run_arm(arm, csv_abs, question["question"])
        except Exception as error:
            result = {}
            exc = f"{type(error).__name__}: {error}"

        wall = round(time.time() - start, 2)
        stats = result.get("stats", {}) or {}
        status = "exception" if exc else result.get("status", "unknown")

        record = {
            "arm": arm,
            "id": question["id"],
            "dataset": question["dataset"],
            "kind": question["kind"],
            "question": question["question"],
            "status": status,
            "ok": bool(result.get("ok")),
            "answer": str(result.get("answer", ""))[:3000],
            "code": result.get("code", ""),
            "error": exc or str(result.get("error", ""))[:500],
            "chart_exists": chart_exists(result),
            "wall_seconds": wall,
            "stats": stats,
            "review_retries": (
                team_review_retries(status, stats.get("llm_calls"))
                if arm == "team"
                else stats.get("retries", 0)
            ),
            "time": datetime.datetime.now().isoformat(timespec="seconds"),
        }

        try:
            record["score"] = (
                scorer.score(question, record)
                if not exc
                else {
                    "verdict": "fail",
                    "category": "infra_error",
                    "reason": exc[:200],
                }
            )
        except Exception as error:
            record["score"] = {
                "verdict": "unscored",
                "category": "scorer_error",
                "reason": f"{type(error).__name__}: {error}"[:200],
            }

        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        score = record["score"]
        print(
            f"[{i}/{len(todo)}] {question['id']:<12} {arm:<9} "
            f"{score['verdict']:<7} {score['category']:<14} "
            f"calls={stats.get('llm_calls')} "
            f"tokens={stats.get('total_tokens')} {wall}s",
            flush=True,
        )

        crashes = crashes + 1 if exc else 0
        if crashes >= 5:
            sys.exit(
                "STOP: 5 API failures in a row. Check your network and token limit, "
                "then run the same command again with --retry-errors."
            )

        # Pace calls to stay under the average tokens-per-minute limit.
        needed = (stats.get("total_tokens") or 0) / args.tpm * 60
        if i < len(todo) and needed > wall:
            time.sleep(needed - wall)

    print("Finished. Next: .venv/bin/python -m eval.report --run-name", args.run_name)


if __name__ == "__main__":
    main()
