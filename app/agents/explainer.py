"""Explainer agent: turns verified results into a simple answer.
It does not write or execute code."""

from app import config, llm, prompts


def explain_result(question, result, plan, code, tracker=None):
    """Return a short, plain-English explanation of the verified result."""

    prompt = prompts.EXPLAINER.format(
        question=question,
        result=result,
        plan=plan,
        code=code,
    )

    reply = llm.chat(
        [{"role": "user", "content": prompt}],
        tracker,
        max_tokens=800,
        reasoning_effort=config.AGENT_EFFORT["explainer"],
    )

    return reply.strip()