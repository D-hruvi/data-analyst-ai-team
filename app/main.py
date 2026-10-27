

"""Web server for the Data Analyst AI Team."""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from app import config
from app.orchestrator import analyze
from baseline.single_agent import answer_question

log = logging.getLogger("data-analyst")

FRONTEND_DIR = os.path.join(config.ROOT, "frontend")

os.makedirs(config.CHART_DIR, exist_ok=True)
os.makedirs(config.UPLOAD_DIR, exist_ok=True)


def delete_old_charts(directory, max_age_hours):
    """Delete .png files older than max_age_hours. Returns how many were deleted."""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0

    for name in os.listdir(directory):
        path = os.path.join(directory, name)

        if (
            name.endswith(".png")
            and os.path.isfile(path)
            and os.path.getmtime(path) < cutoff
        ):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass

    return removed


@asynccontextmanager
async def lifespan(app):
    delete_old_charts(config.CHART_DIR, config.CHART_MAX_AGE_HOURS)
    yield


app = FastAPI(title="Data Analyst AI Team", lifespan=lifespan)

app.mount("/charts", StaticFiles(directory=config.CHART_DIR), name="charts")


def save_upload(file, path):
    """Copy the upload in 1 MB pieces and stop as soon as it exceeds the limit."""
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size = 0

    with open(path, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)

            if not chunk:
                break

            size += len(chunk)

            if size > limit:
                raise HTTPException(
                    413,
                    f"File is larger than {config.MAX_UPLOAD_MB} MB.",
                )

            out.write(chunk)

    if size == 0:
        raise HTTPException(400, "The file is empty.")


def public_result(result, mode):
    """Return a consistent response with a chart URL, never a server file path."""
    result = dict(result)
    result["mode"] = mode

    chart_path = result.pop("chart_path", None)

    if chart_path and not result.get("chart_url"):
        result["chart_url"] = "/charts/" + os.path.basename(chart_path)

    result.setdefault("chart_url", None)

    return result


@app.get("/health")
def health():
    return {"status": "ok", "model": config.MODEL}


@app.post("/ask")
def ask(
    file: UploadFile = File(...),
    question: str = Form(...),
    mode: str = Form("team"),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")

    question = question.strip()

    if not question or len(question) > config.MAX_QUESTION_CHARS:
        raise HTTPException(
            400,
            f"Question must be 1-{config.MAX_QUESTION_CHARS} characters.",
        )

    if mode not in ("baseline", "team"):
        raise HTTPException(400, "Choose mode 'baseline' or 'team'.")

    if not config.GROQ_API_KEY:
        raise HTTPException(
            503,
            "GROQ_API_KEY is missing. Copy .env.example to .env and add your key.",
        )

    path = os.path.join(config.UPLOAD_DIR, uuid.uuid4().hex + ".csv")

    try:
        save_upload(file, path)

        try:
            if mode == "baseline":
                result = answer_question(path, question)
            else:
                result = analyze(question, path)
        except Exception:
            log.exception("analysis failed")
            raise HTTPException(
                500,
                "The analysis failed on the server. See the server log.",
            )

        return public_result(result, mode)

    finally:
        if os.path.exists(path):
            os.remove(path)


# Keep this LAST so /ask, /health and /charts are matched first.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
