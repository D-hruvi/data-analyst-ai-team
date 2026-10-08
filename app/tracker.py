"""Counts tokens, cost, time and retries for ONE question."""
import time

from app import config


class Tracker:
    def __init__(self):
        self.started = time.time()
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0     # Groq bills the model's hidden "thinking" as output
        self.retries = 0           # times work was sent back to be fixed
        self.rate_limit_waits = 0  # times we paused because of a 429 error

    def add_call(self, input_tokens, output_tokens):
        self.llm_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def cost_usd(self):
        price = config.PRICES.get(config.MODEL)
        if price is None:
            return None  # unknown model: do not invent a number
        return (self.input_tokens * price[0] + self.output_tokens * price[1]) / 1_000_000

    def summary(self):
        cost = self.cost_usd()
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "cost_usd": None if cost is None else round(cost, 6),
            "seconds": round(time.time() - self.started, 2),
            "retries": self.retries,
            "rate_limit_waits": self.rate_limit_waits,
        }
