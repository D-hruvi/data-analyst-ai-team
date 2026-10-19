
from unittest.mock import patch

from app.orchestrator import analyze


def test_stops_after_three_failed_reviews():
    fake_plan = {
        "plan": "Test plan",
        "cannot_answer": "",
    }

    fake_outcome = {
        "ok": True,
        "result": "123",
        "chart_path": None,
        "error": "",
    }

    fake_review = {
        "verdict": "fix",
        "feedback": "Please fix the code.",
    }

    with (
        patch("app.orchestrator.load_csv"),
        patch("app.orchestrator.build_summary", return_value="test summary"),
        patch("app.orchestrator.planner.make_plan", return_value=fake_plan),
        patch(
            "app.orchestrator.coder.write_code",
            return_value="result = 123",
        ) as coder_mock,
        patch(
            "app.orchestrator.sandbox.run_code",
            return_value=fake_outcome,
        ) as sandbox_mock,
        patch(
            "app.orchestrator.reviewer.review_work",
            return_value=fake_review,
        ) as reviewer_mock,
    ):
        result = analyze("Test question", "unused.csv")

    assert coder_mock.call_count == 3
    assert sandbox_mock.call_count == 3
    assert reviewer_mock.call_count == 3
    assert result["answer"] == "I am not sure."
    assert result["status"] == "not_sure"
    assert result["code"] == "result = 123"
