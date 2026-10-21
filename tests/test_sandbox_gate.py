"""Basic integration tests for the Docker sandbox."""
import os
import subprocess
import time

from app import config
from app.sandbox import run_code

CSV_PATH = "eval/datasets/sample_sales.csv"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main():
    check(os.path.isfile(CSV_PATH), "sample CSV exists")

    # 1. Normal calculation
    result = run_code("result = int(df.shape[0])", CSV_PATH)
    check(result["ok"] and result["result"].isdigit(),
          "normal code returns a result")

    # 2. Chart generation using actual CSV columns
    chart_code = """
df["revenue"] = df["units"] * df["unit_price"] * (1 - df["discount_pct"].fillna(0) / 100)
df.groupby("region")["revenue"].sum().plot(kind="bar")
result = "chart created"
"""
    result = run_code(chart_code, CSV_PATH)
    check(result["ok"] and result["chart_path"] and
          os.path.isfile(result["chart_path"]),
          "chart is saved and returned")

    # 3. Python error
    result = run_code("raise ValueError('intentional test error')", CSV_PATH)
    check(not result["ok"] and "ValueError" in result["error"],
          "Python errors are returned cleanly")

    # 4. Missing result
    result = run_code("x = 123", CSV_PATH)
    check(not result["ok"] and "did not set 'result'" in result["error"],
          "missing result is rejected")

    # 5. Timeout
    original_timeout = config.SANDBOX_TIMEOUT_SEC
    try:
        config.SANDBOX_TIMEOUT_SEC = 5
        start = time.time()
        result = run_code("while True: pass", CSV_PATH)
        elapsed = time.time() - start
        check(not result["ok"] and "longer than 5 seconds" in result["error"],
              "infinite loop times out")
        check(elapsed < 20, "timeout returns promptly")
    finally:
        config.SANDBOX_TIMEOUT_SEC = original_timeout

    # 6. Container cleanup
    leftovers = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=sandbox_run_", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    check(not leftovers, "sandbox containers are cleaned up")

    print("\nALL GATE CHECKS PASSED")


if __name__ == "__main__":
    main()
