from app import llm
from app.agents import explainer

sent = {}


def fake(reply):
    def chat(messages, tracker=None, max_tokens=0, reasoning_effort=None):
        sent["prompt"] = messages[0]["content"]
        sent["effort"] = reasoning_effort
        sent["max_tokens"] = max_tokens
        return reply
    return chat


# Test 1: Simple explanation
llm.chat = fake("East has the highest total revenue in the dataset.")
answer = explainer.explain_result(
    question="Which region has the highest revenue?",
    result="East",
    plan="Revenue = units * unit_price",
    code="result = 'East'",
)
print("1. Explanation:", answer)

# Test 2: Whitespace is removed
llm.chat = fake("  East has the highest revenue.  \n")
answer = explainer.explain_result("q", "East", "plan", "code")
print("2. Strips whitespace:", answer == "East has the highest revenue.")

# Test 3: Prompt includes the question, result, plan and code
llm.chat = fake("East has the highest revenue.")
explainer.explain_result(
    question="Which region has the highest revenue?",
    result="East",
    plan="Revenue = units * unit_price",
    code="result = 'East'",
)
prompt = sent["prompt"]
print("3. Question included:", "Which region has the highest revenue?" in prompt)
print("4. Result included:", "East" in prompt)
print("5. Plan included:", "Revenue = units * unit_price" in prompt)
print("6. Code included:", "result = 'East'" in prompt)
print("7. Model settings:", sent["effort"], sent["max_tokens"])