from app.dataset import load_csv, build_summary
from app.agents import planner, coder
from app import sandbox
from app.tracker import Tracker

CSV = "eval/datasets/sample_sales.csv"
summary = build_summary(load_csv(CSV))
tracker = Tracker()

questions = [
    "Which region has the highest revenue?",
    "Show total units per region as a bar chart",
]

for question in questions:
    plan_result = planner.make_plan(question, summary, tracker)
    if plan_result["cannot_answer"]:
        print("Cannot answer:", plan_result["cannot_answer"])
        continue

    plan = plan_result["plan"]
    code = coder.write_code(question, summary, plan, tracker)
    out = sandbox.run_code(code, CSV)

    print("\nQUESTION:", question)
    print("CODE:\n", code)
    print("SUCCESS:", out["ok"])
    print("RESULT:", out.get("result"))
    print("CHART:", out.get("chart_path"))

question = "Which region has the highest revenue?"
fix = {
    "previous_code": "result = df.groupby('region')['sales'].sum().idxmax()",
    "outcome": "ERROR: KeyError: 'sales'",
    "feedback": "There is no column 'sales'. Revenue should be units * unit_price.",
}

code = coder.write_code(
    question,
    summary,
    "COLUMNS: region, units, unit_price",
    tracker,
    fix=fix,
)
out = sandbox.run_code(code, CSV)

print("\nRETRY CODE:\n", code)
print("RETRY SUCCESS:", out["ok"])
print("RETRY RESULT:", out.get("result"))
print("\nTOKEN AND COST SUMMARY:")
print(tracker.summary())