"""Stage 4 gate: does the web API behave correctly? No AI calls and no Docker (fakes are used).
Run from the project root:  .venv/bin/python -m tests.test_api"""
import os
import sys
import tempfile
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config, main

client = TestClient(main.app)
failures = []


def check(label, got, want):
    ok = got == want
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        failures.append(label)


def ask(file=("t.csv", b"a,b\n1,2\n3,4\n", "text/csv"), question="What is a?", mode="team"):
    return client.post("/ask", files={"file": file}, data={"question": question, "mode": mode})


def uploads():
    return sorted(os.listdir(config.UPLOAD_DIR))


TEAM_FAKE = {"ok": True, "status": "ok", "answer": "4", "code": "result = 4", "error": "",
             "chart_path": "/Users/someone/project/charts/abc123.png", "stats": {"llm_calls": 4}}
BASE_FAKE = {"mode": "baseline", "ok": True, "status": "answered", "answer": "4", "code": "result = 4",
             "chart_url": "/charts/def456.png", "error": "", "stats": {"llm_calls": 1}}

# ---- basic pages
r = client.get("/health")
check("health: status 200", r.status_code, 200)
check("health: says ok", r.json().get("status"), "ok")
r = client.get("/")
check("page: status 200", r.status_code, 200)
check("page: is our frontend", "Data Analyst AI Team" in r.text, True)

# ---- input checks (these run before the key check)
check("rejects a non-csv file", ask(file=("x.txt", b"hi", "text/plain")).status_code, 400)
check("rejects an empty question", ask(question="   ").status_code, 400)
check("rejects a too-long question", ask(question="x" * (config.MAX_QUESTION_CHARS + 1)).status_code, 400)
check("rejects an unknown mode", ask(mode="magic").status_code, 400)

with patch.object(config, "GROQ_API_KEY", None):
    check("missing API key gives 503", ask().status_code, 503)

with patch.object(config, "GROQ_API_KEY", "test-key"):
    check("rejects an empty file", ask(file=("e.csv", b"", "text/csv")).status_code, 400)

    # ---- team mode
    before = uploads()
    with patch("app.main.analyze", return_value=dict(TEAM_FAKE)) as fake:
        r = ask()
    body = r.json()
    check("team: status 200", r.status_code, 200)
    check("team: chart_url is a URL", body.get("chart_url"), "/charts/abc123.png")
    check("team: no server path in the response", "chart_path" in body, False)
    check("team: mode is set", body.get("mode"), "team")
    check("team: upload file is deleted", uploads(), before)
    check("team: analyze called once", fake.call_count, 1)

    # ---- baseline mode
    with patch("app.main.answer_question", return_value=dict(BASE_FAKE)) as fb, \
         patch("app.main.analyze") as fa:
        r = ask(mode="baseline")
    check("baseline: chart_url kept", r.json().get("chart_url"), "/charts/def456.png")
    check("baseline: baseline function called", fb.call_count, 1)
    check("baseline: team not called", fa.call_count, 0)

    # ---- a crash must not leak details
    before = uploads()
    with patch("app.main.analyze", side_effect=RuntimeError("secret-boom")):
        r = ask()
    check("crash: status 500", r.status_code, 500)
    check("crash: no details leaked", "secret-boom" in r.text, False)
    check("crash: upload file is deleted", uploads(), before)

    # ---- upload too big
    before = uploads()
    with patch.object(config, "MAX_UPLOAD_MB", 1), patch("app.main.analyze") as fake:
        r = ask(file=("big.csv", b"x" * (2 * 1024 * 1024), "text/csv"))
    check("too big: status 413", r.status_code, 413)
    check("too big: analysis never started", fake.call_count, 0)
    check("too big: partial file is deleted", uploads(), before)

# ---- old chart cleanup (uses a temp folder, never your real charts)
with tempfile.TemporaryDirectory() as d:
    old, new, keep = (os.path.join(d, n) for n in ("old.png", "new.png", "note.txt"))
    for p in (old, new, keep):
        open(p, "w").close()
    two_days_ago = time.time() - 48 * 3600
    os.utime(old, (two_days_ago, two_days_ago))
    os.utime(keep, (two_days_ago, two_days_ago))
    removed = main.delete_old_charts(d, 24)
    check("cleanup: old chart removed", os.path.exists(old), False)
    check("cleanup: new chart kept", os.path.exists(new), True)
    check("cleanup: non-png untouched", os.path.exists(keep), True)
    check("cleanup: returns the count", removed, 1)

print()
if failures:
    print(f"{len(failures)} CHECK(S) FAILED. Paste this output.")
    sys.exit(1)
print("ALL API CHECKS PASSED")