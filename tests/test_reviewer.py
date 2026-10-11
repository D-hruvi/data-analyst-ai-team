from app import llm
from app.agents import reviewer

sent = {}


def fake(reply):
    def chat(messages, tracker=None, max_tokens=0, reasoning_effort=None):
        sent["prompt"] = messages[0]["content"]
        sent["effort"] = reasoning_effort
        sent["max_tokens"] = max_tokens
        return reply

    return chat


def run_case(label, reply):
    llm.chat = fake(reply)

    result = reviewer.review_work(
        question="Which region has the highest revenue?",
        summary="Columns: region, units, unit_price",
        plan="Revenue = units * unit_price",
        code="result = df.groupby('region')['revenue'].sum().idxmax()",
        outcome="SUCCESS: East",
    )

    print(label, ":", result)


# Test 1: Approve valid work
run_case(
    "1. Approve valid work",
    '{"verdict": "ok", "feedback": ""}',
)

# Test 2: Request a fix
run_case(
    "2. Request a fix",
    '{"verdict": "fix", "feedback": "Use the correct columns."}',
)

# Test 3: Data cannot answer the question
run_case(
    "3. Cannot answer",
    '{"verdict": "cannot_answer", "feedback": "Missing salary column."}',
)

# Test 4: Invalid JSON
run_case("4. Invalid JSON", "this is not JSON")

# Test 5: Invalid verdict
run_case(
    "5. Invalid verdict",
    '{"verdict": "maybe", "feedback": "Unsure"}',
)

# Test 6: Feedback must be text
run_case(
    "6. Invalid feedback type",
    '{"verdict": "ok", "feedback": 123}',
)

# Test 7-9: Verify the prompt and model settings
llm.chat = fake('{"verdict": "ok", "feedback": ""}')

reviewer.review_work(
    question="Which region has the highest revenue?",
    summary="Columns: region, units, unit_price",
    plan="Revenue = units * unit_price",
    code="result = df.groupby('region')['revenue'].sum().idxmax()",
    outcome="SUCCESS: East",
)

print(
    "7. Prompt includes question:",
    "Which region has the highest revenue?" in sent["prompt"],
)

print(
    "8. Prompt includes code:",
    "df.groupby('region')" in sent["prompt"],
)

print(
    "9. Model settings:",
    sent["effort"],
    sent["max_tokens"],
)