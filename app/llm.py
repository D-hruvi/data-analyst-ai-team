"""The ONLY file that talks to the AI provider. To switch provider, edit only this file."""
import re
import time

from groq import Groq, RateLimitError

from app import config

_client = None  # created on first use, then reused


def _get_client():
    global _client
    if _client is None:
        config.require_key()
        # max_retries=0: we do our own waiting below, so we can count it
        _client = Groq(api_key=config.GROQ_API_KEY, max_retries=0)
    return _client


def _wait_seconds(error, attempt):
    """How long to wait after a 429 error. Use the server's hint if it sent one."""
    hint = error.response.headers.get("retry-after")
    try:
        return min(float(hint), 60)
    except (TypeError, ValueError):
        return min(5 * 2 ** attempt, 60)  # 5, 10, 20, 40 ... seconds


def chat(messages, tracker=None, max_tokens=3000):
    """Send messages, return the reply text. Reports token use to the tracker."""
    client = _get_client()
    for attempt in range(config.LLM_MAX_WAITS + 1):
        try:
            response = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                temperature=0,  # 0 = least random, better for code
                max_completion_tokens=max_tokens,
                reasoning_effort=config.REASONING_EFFORT,
            )
            break
        except RateLimitError as error:
            if attempt == config.LLM_MAX_WAITS:
                raise  # waited enough, give up
            if tracker:
                tracker.rate_limit_waits += 1
            time.sleep(_wait_seconds(error, attempt))

    if tracker:
        tracker.add_call(response.usage.prompt_tokens, response.usage.completion_tokens)

    text = response.choices[0].message.content or ""
    if not text.strip():
        raise RuntimeError("Model returned empty text (it may have used all its tokens thinking).")
    return text


def extract_code(reply):
    """Pull code out of a ```python ... ``` block. If there is no block, use the whole reply."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.DOTALL)
    return (match.group(1) if match else reply).strip()
