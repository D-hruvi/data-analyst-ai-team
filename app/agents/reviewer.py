"""Reviewer agent: checks the Coder's work and recommends approval or a fix.
It never writes or executes code."""

import json

from app import config, llm, prompts


def review_work(question, summary, plan, code, outcome, tracker=None):
    """Returns a verdict and feedback.

    Verdict is one of: ok, fix, cannot_answer.
    If the AI reply cannot be parsed, fail safely with a fix verdict.
    """

    prompt = prompts.REVIEWER.format(
        summary=summary,
        question=question,
        plan=plan,
        code=code,
        outcome=outcome,
    )

    reply = llm.chat(
        [{"role": "user", "content": prompt}],
        tracker,
        max_tokens=1000,
        reasoning_effort=config.AGENT_EFFORT["reviewer"],
    ).strip()

    # Accept JSON even if the model wraps it in a code fence.
    reply = llm.extract_code(reply)

    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return {
            "verdict": "fix",
            "feedback": "Reviewer returned invalid JSON. Check the work again.",
        }

    verdict = data.get("verdict")
    feedback = data.get("feedback", "")

    if verdict not in ("ok", "fix", "cannot_answer"):
        return {
            "verdict": "fix",
            "feedback": "Reviewer returned an invalid verdict. Check the work again.",
        }

    if not isinstance(feedback, str):
        return {
            "verdict": "fix",
            "feedback": "Reviewer feedback was not valid text. Check the work again.",
        }

    return {"verdict": verdict, "feedback": feedback}