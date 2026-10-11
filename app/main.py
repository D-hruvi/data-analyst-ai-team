
"""Web server for the Data Analyst AI project."""

import os
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from app import config
from app.orchestrator import analyze
from baseline.single_agent import answer_question

os.makedirs(config.CHART_DIR, exist_ok=True)
os.makedirs(config.UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Data Analyst AI Team")
app.mount("/charts", StaticFiles(directory=config.CHART_DIR), name="charts")


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

    path = os.path.join(config.UPLOAD_DIR, uuid.uuid4().hex + ".csv")

    try:
        with open(path, "wb") as out:
            shutil.copyfileobj(file.file, out)

        if os.path.getsize(path) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(
                413,
                f"File is larger than {config.MAX_UPLOAD_MB} MB.",
            )

        if mode == "baseline":
            result = answer_question(path, question)
            result["mode"] = "baseline"
            return result

        result = analyze(question, path)
        result["mode"] = "team"
        return result

    finally:
        if os.path.exists(path):
            os.remove(path)


