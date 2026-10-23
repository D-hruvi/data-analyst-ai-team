
"""The ONLY file that talks to the AI provider. To switch provider, edit only this file."""

import re
import time

from groq import Groq, RateLimitError, APIConnectionError, APITimeoutError

from app import config


_client = None


def _get_client():
    global _client

    if _client is None:
        config.require_key()
        _client = Groq(
            api_key=config.GROQ_API_KEY,
            max_retries=0,
        )

    return _client


def _wait_seconds(error, attempt):
    hint = error.response.headers.get("retry-after")

    try:
        return min(float(hint), 60)
    except (TypeError, ValueError):
        return min(5 * 2 ** attempt, 60)


def chat(messages, tracker=None, max_tokens=3000, reasoning_effort=None):
    """Send messages, return the reply text. Reports token use to the tracker.

    reasoning_effort: how long the model thinks:
    "low", "medium" or "high".
    None = config default.
    """

    effort = reasoning_effort or config.REASONING_EFFORT

    if effort not in ("low", "medium", "high"):
        raise ValueError(
            f"reasoning_effort must be low, medium or high, got {effort!r}"
        )

    client = _get_client()

    for attempt in range(config.LLM_MAX_WAITS + 1):
        try:
            response = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=0,
                max_completion_tokens=max_tokens,
                reasoning_effort=effort,
            )
            break

        except RateLimitError as error:
            if attempt == config.LLM_MAX_WAITS:
                raise

            if tracker:
                tracker.rate_limit_waits += 1

            time.sleep(_wait_seconds(error, attempt))

        except (APIConnectionError, APITimeoutError):
            if attempt == config.LLM_MAX_WAITS:
                raise

            if tracker:
                tracker.connection_retries += 1

            time.sleep(min(2 ** (attempt + 1), 30))

    if tracker:
        tracker.add_call(
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )

    text = response.choices[0].message.content or ""

    if not text.strip():
        raise RuntimeError(
            "Model returned empty text "
            "(it may have used all its tokens thinking)."
        )

    return text


def extract_code(reply):
    """Remove Python or JSON Markdown fences when present."""

    match = re.search(
        r"```(?:python|json)?\s*\n(.*?)```",
        reply,
        re.DOTALL,
    )

    return (match.group(1) if match else reply).strip()
