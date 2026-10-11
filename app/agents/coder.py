"""Coder agent: writes the pandas code, and fixes it when the Reviewer sends it back.
It NEVER runs the code. Only sandbox.py runs code."""

from app import config, llm, prompts


def write_code(question, summary, plan, tracker=None, fix=None):
    """Returns the code as text.
    On a retry, pass fix = {"previous_code": ..., "outcome": ..., "feedback": ...}."""
    prompt = prompts.CODER.format(
        summary=summary,
        plan=plan,
        question=question,
    )

    if fix is not None:
        # .format(**fix) raises KeyError if a key is missing.
        prompt += prompts.CODER_FIX.format(**fix)

    reply = llm.chat(
        [{"role": "user", "content": prompt}],
        tracker,
        max_tokens=3000,
        reasoning_effort=config.AGENT_EFFORT["coder"],
    )

    return llm.extract_code(reply)