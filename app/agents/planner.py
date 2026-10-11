"""Planner agent: reads the question + dataset summary and returns a short plan.
It writes NO code and runs NO code. It may also say the data cannot answer the question."""

from app import config, llm, prompts


def make_plan(question, summary, tracker=None):
    """Returns {"plan": text, "cannot_answer": reason or None}."""
    prompt = prompts.PLANNER.format(summary=summary, question=question)

    reply = llm.chat(
        [{"role": "user", "content": prompt}],
        tracker,
        max_tokens=1500,
        reasoning_effort=config.AGENT_EFFORT["planner"],
    ).strip()

    # The prompt says: if the data cannot answer, reply with ONE line starting with CANNOT_ANSWER:
    first_line = reply.splitlines()[0].strip()

    if first_line.startswith(prompts.CANNOT_ANSWER):
        reason = (
            first_line[len(prompts.CANNOT_ANSWER):].strip()
            or "no reason given"
        )
        return {"plan": "", "cannot_answer": reason}

    return {"plan": reply, "cannot_answer": None}