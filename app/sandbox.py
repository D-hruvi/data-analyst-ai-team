"""Safe sandbox: runs generated code inside a locked-down Docker container.

Generated code runs inside Docker, not directly on your Mac.
The public interface remains run_code(code, csv_path).
"""
import json
import os
import shutil
import subprocess
import tempfile
import uuid

from app import config

CONTAINER_PREFIX = "sandbox_run_"
MAX_CHART_BYTES = 5_000_000


def _fail(message):
    return {"ok": False, "result": "", "chart_path": None, "error": message}


def _regular_file(path):
    """Accept only normal files, never symlinks."""
    if os.path.islink(path) or not os.path.isfile(path):
        return None
    return path


def _remove_container(docker, name):
    """Force-remove the container, including after a timeout."""
    try:
        subprocess.run(
            [docker, "rm", "-f", name],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass


def run_code(code, csv_path):
    """Run generated code in Docker. Return {ok, result, chart_path, error}."""
    docker = shutil.which("docker")
    if docker is None:
        return _fail("Docker was not found. Install Docker Desktop and start it.")

    name = CONTAINER_PREFIX + uuid.uuid4().hex[:12]
    work = os.path.realpath(tempfile.mkdtemp(prefix="sandbox_"))

    try:
        in_dir = os.path.join(work, "in")
        out_dir = os.path.join(work, "out")
        os.mkdir(in_dir)
        os.mkdir(out_dir)

        os.chmod(work, 0o755)
        os.chmod(in_dir, 0o755)
        os.chmod(out_dir, 0o777)

        try:
            shutil.copyfile(csv_path, os.path.join(in_dir, "input.csv"))
        except OSError as exc:
            return _fail(f"Could not copy the CSV into the sandbox: {exc}")

        with open(
            os.path.join(in_dir, "generated_code.py"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(code)

        cmd = [
            docker, "run",
            "--name", name,
            "--pull", "never",
            "--network", "none",
            "--memory", config.SANDBOX_MEMORY,
            "--memory-swap", config.SANDBOX_MEMORY,
            "--cpus", config.SANDBOX_CPUS,
            "--pids-limit", str(config.SANDBOX_MAX_PROCESSES),
            "--ulimit",
            f"fsize={config.SANDBOX_MAX_FILE_BYTES}:{config.SANDBOX_MAX_FILE_BYTES}",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "10001:10001",
            "-w", "/out",
            "-v", f"{in_dir}:/in:ro",
            "-v", f"{out_dir}:/out",
            config.SANDBOX_IMAGE,
            "/in/input.csv", "/in/generated_code.py",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.SANDBOX_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return _fail(
                f"The code ran longer than {config.SANDBOX_TIMEOUT_SEC} "
                "seconds and was stopped."
            )

        stderr = (proc.stderr or "").strip()

        if proc.returncode in (125, 126, 127):
            return _fail(
                "The sandbox could not start. Is Docker running and is the "
                "image built? Details: " + stderr[-500:]
            )

        if proc.returncode == 137 and not stderr:
            return _fail(
                f"The code was killed, most likely because it exceeded "
                f"{config.SANDBOX_MEMORY} of memory."
            )

        if proc.returncode != 0:
            return _fail(
                stderr[-1500:] or "The code failed without an error message."
            )

        result_file = _regular_file(os.path.join(out_dir, "result.json"))
        if result_file is None:
            return _fail("The code finished but did not produce a valid result file.")

        try:
            with open(result_file, encoding="utf-8") as f:
                result = json.load(f)["result"]
        except (OSError, ValueError, KeyError, TypeError):
            return _fail("The result file could not be read.")

        if not isinstance(result, str):
            result = str(result)[:3000]

        chart_path = None
        temp_chart = _regular_file(os.path.join(out_dir, "chart.png"))

        if temp_chart and os.path.getsize(temp_chart) <= MAX_CHART_BYTES:
            os.makedirs(config.CHART_DIR, exist_ok=True)
            chart_path = os.path.join(config.CHART_DIR, uuid.uuid4().hex + ".png")
            shutil.copyfile(temp_chart, chart_path)

        return {
            "ok": True,
            "result": result,
            "chart_path": chart_path,
            "error": "",
        }

    finally:
        _remove_container(docker, name)
        shutil.rmtree(work, ignore_errors=True)
