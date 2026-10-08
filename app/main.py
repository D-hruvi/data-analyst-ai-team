"""Web server. Run from the project root:  uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs to try it."""
import os
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from app import config
from baseline.single_agent import answer_question

os.makedirs(config.CHART_DIR, exist_ok=True)
os.makedirs(config.UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Data Analyst AI Team")
app.mount("/charts", StaticFiles(directory=config.CHART_DIR), name="charts")  # serves chart images


@app.get("/health")
def health():
    return {"status": "ok", "model": config.MODEL}


# Plain "def" (not async): FastAPI runs it in a worker thread, so a slow AI call
# does not freeze the whole server.
@app.post("/ask")
def ask(file: UploadFile = File(...), question: str = Form(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")
    if not question.strip() or len(question) > config.MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Question must be 1-{config.MAX_QUESTION_CHARS} characters.")

    path = os.path.join(config.UPLOAD_DIR, uuid.uuid4().hex + ".csv")  # random name, never trust user names
    try:
        with open(path, "wb") as out:
            shutil.copyfileobj(file.file, out)
        if os.path.getsize(path) > config.MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB.")
        return answer_question(path, question.strip())
    finally:
        if os.path.exists(path):
            os.remove(path)  # do not keep user files
