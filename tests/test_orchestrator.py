from pprint import pprint

from app.orchestrator import analyze

CSV = "eval/datasets/sample_sales.csv"

questions = [
    "Which region has the highest revenue?",
    "Show total units per region as a bar chart",
    "What is the average salary?",
]

for question in questions:
    print("\n" + "=" * 60)
    print("QUESTION:", question)

    try:
        result = analyze(question, CSV)
        pprint(result)
    except Exception as error:
        print("ERROR:", type(error).__name__, str(error))
        raise