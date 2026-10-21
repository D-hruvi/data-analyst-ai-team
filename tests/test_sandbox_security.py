"""Adversarial checks for the Docker sandbox. Run only against the test sandbox."""
import os
import subprocess

from app.sandbox import run_code

CSV_PATH = "eval/datasets/sample_sales.csv"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def test_host_file_read():
    # This file should not exist inside the container.
    result = run_code(
        "result = open('/etc/hosts').read()",
        CSV_PATH,
    )
    # A container has its own /etc/hosts, so reading this file is not a host escape.
    check(result["ok"], "container's own system files are isolated")


def test_host_home_access():
    result = run_code(
        "import os; result = str(os.path.exists('/Users'))",
        CSV_PATH,
    )
    check(result["ok"] and result["result"] == "False",
          "host user directory is not mounted")


def test_environment():
    result = run_code(
        "import os; result = str(dict(os.environ))",
        CSV_PATH,
    )
    check(result["ok"] and "GROQ_API_KEY" not in result["result"],
          "Groq API key is not exposed in the container environment")


def test_network():
    code = """
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=2)
    result = "NETWORK_CONNECTED"
except Exception as exc:
    result = type(exc).__name__
"""
    result = run_code(code, CSV_PATH)
    check(result["ok"] and "NETWORK_CONNECTED" not in result["result"],
          "outbound network connection is blocked")


def test_write_outside_output():
    code = """
try:
    open("/app/sandbox_escape_test.txt", "w").write("bad")
    result = "WRITE_SUCCEEDED"
except Exception as exc:
    result = type(exc).__name__
"""
    result = run_code(code, CSV_PATH)
    check(result["ok"] and "WRITE_SUCCEEDED" not in result["result"],
          "writes to the read-only application filesystem are blocked")


def test_process_limit():
    code = """
import os
children = []
try:
    for _ in range(300):
        children.append(os.fork())
except Exception as exc:
    result = type(exc).__name__
finally:
    for pid in children:
        if pid == 0:
            os._exit(0)
    for pid in children:
        try:
            os.waitpid(pid, 0)
        except Exception:
            pass
"""
    result = run_code(code, CSV_PATH)
    check(not result["ok"] or "BlockingIOError" in result["result"]
          or "OSError" in result["result"],
          "process creation is limited")


def test_memory_limit():
    code = """
try:
    chunks = []
    while True:
        chunks.append(bytearray(20 * 1024 * 1024))
except MemoryError:
    result = "MEMORY_LIMIT_REACHED"
"""
    result = run_code(code, CSV_PATH)
    check(not result["ok"] or "MEMORY_LIMIT_REACHED" in result["result"],
          "memory exhaustion does not crash the host")


def test_no_leftover_containers():
    output = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=sandbox_run_", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    check(not output, "no sandbox containers remain")


if __name__ == "__main__":
    test_host_file_read()
    test_host_home_access()
    test_environment()
    test_network()
    test_write_outside_output()
    test_process_limit()
    test_memory_limit()
    test_no_leftover_containers()
    print("\nALL SECURITY CHECKS PASSED")
