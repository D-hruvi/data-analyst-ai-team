from app import llm, prompts, sandbox
from app.agents import coder
from app.dataset import load_csv, build_summary

CSV = "eval/datasets/sample_sales.csv"
summary = build_summary(load_csv(CSV))
sent = {}

def fake(reply):
    def chat(messages, tracker=None, max_tokens=0, reasoning_effort=None):
        sent.update(
            prompt=messages[0]["content"],
            effort=reasoning_effort,
            max_tokens=max_tokens,
        )
        return reply
    return chat

GOOD = """```python
df['revenue'] = df['units'] * df['unit_price']
result = df.groupby('region')['revenue'].sum().idxmax()
```"""

PLAN = """COLUMNS: region, units, unit_price
STEPS: multiply units by unit_price; group by region; sum
WATCH OUT: none
ASSUMPTION: revenue = units * unit_price"""

llm.chat = fake(GOOD)

code = coder.write_code("Which region has the highest revenue?", summary, PLAN)
p = sent["prompt"]
print("1. Code extracted:", code.startswith("df['revenue']"))
print("2. Prompt checks:", "ASSUMPTION: revenue" in p,
      "'unit_price'" in p, prompts.CODE_RULES in p,
      "Which region" in p)
print("3. Uses configured effort:", sent["effort"], "| max tokens:", sent["max_tokens"])

fix = {
    "previous_code": "result = df['sales'].sum()",
    "outcome": "ERROR: KeyError: 'sales'",
    "feedback": "No column 'sales'. Use units * unit_price.",
}
coder.write_code("q", summary, PLAN, fix=fix)
p = sent["prompt"]
print("4. Retry checks:",
      "df['sales'].sum()" in p,
      "KeyError: 'sales'" in p,
      "Use units * unit_price" in p)

llm.chat = fake("result = 5")
print("5. Code without a code fence:",
      coder.write_code("q", summary, PLAN) == "result = 5")

try:
    coder.write_code("q", summary, PLAN, fix={"previous_code": "x"})
except KeyError as e:
    print("6. Incomplete retry rejected:", e)

llm.chat = fake(GOOD)
out = sandbox.run_code(coder.write_code("q", summary, PLAN), CSV)
print("7. Sandbox execution:", out["ok"], "| answer:", out["result"])