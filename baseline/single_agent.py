"""Baseline: ONE AI writes the pandas code. No planner, no reviewer.
This is the control group we compare the team against in Stage 3.
Run:  python -m baseline.single_agent <file.csv> "your question"   (from the project root)"""
import json
import os
import re
import sys

from app import llm, sandbox
from app.dataset import build_summary, load_csv
from app.tracker import Tracker

# The AI writes this when the data cannot answer the question (Stage 2 moves it to prompts.py)
CANNOT_ANSWER = "CANNOT_ANSWER:"

PROMPT = """You are a data analyst. Write Python code that answers the question.

Rules:
- A pandas DataFrame called df is already loaded. Do NOT load any file.
- pandas (pd), numpy (np) and matplotlib (plt) are already imported.
- Save the final answer in a variable called result (a number, text, or small table).
- If a chart helps, draw it with plt. Do NOT call plt.show().
- Use the column names exactly as written in the summary.
- Before using a column, check that it exists in the summary.
- If the data cannot answer the question (for example the needed column does not exist),
  do NOT invent an answer. Do NOT set result to NaN, None, 0 or a guess. Instead write
  exactly one line: raise ValueError("CANNOT_ANSWER: <short reason>")
- Reply with ONE python code block and nothing else.

DATASET SUMMARY:
{summary}

QUESTION: {question}
"""


def _reason(error):
    """If the error is a 'cannot answer' signal, return the reason. Otherwise None."""
    if not error:
        return None
    last_line = error.strip().splitlines()[-1]  # the error message is the last line of a traceback
    match = re.search(CANNOT_ANSWER + r"\s*(.*)", last_line)
    return match.group(1).strip() if match else None


def _pack(tracker, code, outcome, error):
    """Same output shape the team will use later, so the eval treats both the same."""
    ok = bool(outcome and outcome["ok"])
    chart = outcome["chart_path"] if ok else None
    if not error and outcome and not ok:
        error = outcome["error"]

    status = "answered" if ok else "error"
    reason = _reason(error)
    if reason is not None:
        status = "cannot_answer"
        error = f"I cannot answer this: {reason}"

    return {
        "mode": "baseline",
        "ok": ok,
        "status": status,  # answered | cannot_answer | error
        "answer": outcome["result"] if ok else "",
        "code": code,  # rule: always return the code used
        "chart_url": f"/charts/{os.path.basename(chart)}" if chart else None,
        "error": error,
        "stats": tracker.summary(),
    }


def answer_question(csv_path, question, max_attempts=1):
    tracker = Tracker()
    try:
        summary = build_summary(load_csv(csv_path))
    except Exception as exc:
        return _pack(tracker, "", None, f"Could not read the CSV: {exc}")

    messages = [{"role": "user", "content": PROMPT.format(summary=summary, question=question)}]
    code, outcome, error = "", None, ""
    try:
        for attempt in range(max_attempts):
            reply = llm.chat(messages, tracker)
            code = llm.extract_code(reply)
            outcome = sandbox.run_code(code, csv_path)  # UNSAFE until Stage 3
            if outcome["ok"]:
                break
            if _reason(outcome["error"]) is not None:
                break  # the data cannot answer it; retrying will not help
            if attempt < max_attempts - 1:  # feed the error back and try again
                tracker.retries += 1
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": f"That code failed:\n{outcome['error']}\n"
                                                "Fix it. Reply with ONE python code block."},
                ]
    except Exception as exc:  # e.g. rate limit never cleared. Record it, do not crash.
        error = f"AI call failed: {exc}"
    return _pack(tracker, code, outcome, error)


if __name__ == "__main__":
    print(json.dumps(answer_question(sys.argv[1], sys.argv[2]), indent=2))
