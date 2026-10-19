
"""Orchestrator: coordinates Planner, Coder, Reviewer and Explainer."""

import time

from app import sandbox
from app.agents import planner, coder, reviewer, explainer
from app.dataset import load_csv, build_summary
from app.tracker import Tracker
from app.prompts import CANNOT_ANSWER, NOT_SURE


MAX_REVIEW_ATTEMPTS = 3


def analyze(question, csv_path):
    """Run the multi-agent analysis pipeline and return its answer and stats."""

    start = time.time()
    tracker = Tracker()

    df = load_csv(csv_path)
    summary = build_summary(df)

    # 1. Planner: decide how to answer the question.
    plan_result = planner.make_plan(question, summary, tracker)

    if plan_result["cannot_answer"]:
        return {
            "ok": False,
            "status": "cannot_answer",
            "answer": "",
            "code": "",
            "error": plan_result["cannot_answer"],
            "chart_path": None,
            "stats": tracker.summary(),
        }

    plan = plan_result["plan"]

    # 2. Coder + Reviewer loop.
    code = coder.write_code(question, summary, plan, tracker)
    outcome = None

    for attempt in range(MAX_REVIEW_ATTEMPTS):
        outcome = sandbox.run_code(code, csv_path)

        if not outcome["ok"]:
            error = outcome.get("error", "Unknown execution error")

            if CANNOT_ANSWER in error:
                return {
                    "ok": False,
                    "status": "cannot_answer",
                    "answer": "",
                    "code": code,
                    "error": error,
                    "chart_path": None,
                    "stats": tracker.summary(),
                }

        review = reviewer.review_work(
            question=question,
            summary=summary,
            plan=plan,
            code=code,
            outcome=(
                outcome.get("result", "")
                if outcome["ok"]
                else outcome.get("error", "Execution failed")
            ),
            tracker=tracker,
        )

        if review["verdict"] == "cannot_answer":
            return {
                "ok": False,
                "status": "cannot_answer",
                "answer": "",
                "code": code,
                "error": review["feedback"],
                "chart_path": None,
                "stats": tracker.summary(),
            }

        if review["verdict"] == "ok" and outcome["ok"]:
            break

        # Stop after all three review attempts have been used.
        if attempt == MAX_REVIEW_ATTEMPTS - 1:
            return {
                "ok": False,
                "status": "not_sure",
                "answer": NOT_SURE,
                "code": code,
                "error": review["feedback"] or outcome.get("error", ""),
                "chart_path": outcome.get("chart_path"),
                "stats": tracker.summary(),
            }

        # 3. Ask the Coder to repair its previous code.
        fix = {
            "previous_code": code,
            "outcome": (
                outcome.get("result", "")
                if outcome["ok"]
                else outcome.get("error", "Execution failed")
            ),
            "feedback": review["feedback"] or "The code did not run successfully.",
        }

        code = coder.write_code(
            question, summary, plan, tracker, fix=fix
        )

    # 4. Explainer: turn the verified result into plain English.
    answer = explainer.explain_result(
        question=question,
        result=outcome.get("result", ""),
        plan=plan,
        code=code,
        tracker=tracker,
    )

    stats = tracker.summary()
    stats["seconds"] = round(time.time() - start, 2)

    return {
        "ok": True,
        "status": "ok",
        "answer": answer,
        "code": code,
        "chart_path": outcome.get("chart_path"),
        "error": "",
        "stats": stats,
    }
