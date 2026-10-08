"""!!! UNSAFE - STAGE 1 ONLY !!!
This is NOT a real sandbox. A list of blocked words is easy to bypass, and the code can
still read files on this computer. Never run it with private data or on a public server.
Stage 3 replaces the inside of run_code() with Docker. The function signature stays the same.

This is the ONLY file that runs generated code."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from app import config

# Weak protection: refuse code that contains these words
BLOCKED = ["import os", "from os", "import sys", "from sys", "import subprocess", "import shutil",
           "import socket", "import requests", "__import__", "open(", "eval(", "exec(",
           "compile(", "input("]

RUNNER = os.path.join(config.ROOT, "sandbox", "runner.py")


def _fail(message):
    return {"ok": False, "result": "", "chart_path": None, "error": message}


def run_code(code, csv_path):
    """Run code on the CSV. Returns {ok, result, chart_path, error}."""
    for word in BLOCKED:
        if word in code:
            return _fail(f"Blocked: the code contains '{word}', which is not allowed.")

    work = tempfile.mkdtemp(prefix="sandbox_")  # fresh empty folder for this run
    try:
        code_path = os.path.join(work, "generated_code.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Do not pass the API key to the child process
        env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        try:
            proc = subprocess.run(
                [sys.executable, RUNNER, os.path.abspath(csv_path), code_path],
                cwd=work, capture_output=True, text=True,
                timeout=config.SANDBOX_TIMEOUT_SEC, env=env,
            )
        except subprocess.TimeoutExpired:
            return _fail(f"The code ran longer than {config.SANDBOX_TIMEOUT_SEC} seconds and was stopped.")

        if proc.returncode != 0:
            return _fail(proc.stderr[-1500:])  # the END of a traceback has the real error

        with open(os.path.join(work, "result.json"), encoding="utf-8") as f:
            result = json.load(f)["result"]

        chart_path = None
        temp_chart = os.path.join(work, "chart.png")
        if os.path.exists(temp_chart):
            os.makedirs(config.CHART_DIR, exist_ok=True)
            chart_path = os.path.join(config.CHART_DIR, uuid.uuid4().hex + ".png")
            shutil.copy(temp_chart, chart_path)

        return {"ok": True, "result": result, "chart_path": chart_path, "error": ""}
    finally:
        shutil.rmtree(work, ignore_errors=True)  # always clean up
