# Data Analyst AI Team

Upload a CSV and ask a question in plain English. A small team of AI helpers answers it: a **Planner** decides how to answer, a **Coder** writes pandas code, a **Reviewer** checks the work (up to 3 attempts), and an **Explainer** writes the answer in plain English. The code runs in a locked-down Docker sandbox. The response includes the answer, the code used, a chart when useful, and tokens, cost and time.

The project also measures whether the team beats a single AI. See `eval/results/RESULTS.md`.

## Design rules

- Agents never run code. Only `app/sandbox.py` runs generated code.
- Only `app/llm.py` talks to the AI provider (Groq). The API key lives in `.env`, never in code.
- The AI never sees the full CSV, only a short summary.
- Maximum 3 attempts, then the answer is "I am not sure." The system does not guess.
- Every question logs tokens, cost, time and retries (`app/tracker.py`).
- Use only public or made-up data.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Then put your GROQ_API_KEY in .env
docker build -t data-analyst-sandbox:1 sandbox/
```

Docker Desktop must be running.

## Run

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

In another terminal, submit a request:

```bash
curl -F "file=@eval/datasets/tips.csv" \
     -F "question=What is the average tip?" \
     -F "mode=team" \
     http://127.0.0.1:8000/ask
```

`mode` is `team` or `baseline`. `GET /health` shows the model. The plain HTML/JavaScript client is in `frontend/`.

## Test

```bash
.venv/bin/python -m tests.test_sandbox_gate
.venv/bin/python -m tests.test_sandbox_security
.venv/bin/python -m tests.test_scorer
```

The sandbox tests require Docker. The scorer tests do not make AI calls.

## The sandbox

Each run starts a fresh container with:

- No network access.
- An empty environment, so no API key is available inside the container.
- A read-only filesystem.
- A non-root user.
- All Linux capabilities dropped.
- Limits on memory, CPU, processes, file size and execution time.

Only the CSV and generated code are mounted, read-only. The container is removed even after a timeout.

**Security limitations:** Docker shares a kernel with its host, so this setup is not sufficient for hostile users on a public server. Generated code can read the CSV it is given and can forge its own result file. The Reviewer is the defence against wrong answers, not the sandbox.

## Evaluation

The evaluation contains 50 questions across three public datasets: `tips`, `penguins`, and `taxis` from the seaborn-data repository. The questions cover four kinds of tasks: lookup, calculation, chart, and unanswerable.

Expected answers are computed with plain pandas in `eval/make_truth.py`. The questions were frozen with a SHA-256 fingerprint in `eval/questions.sha256` before the evaluation run; the tag `eval-questions-frozen` records that version. The evaluation runner checks that the questions have not changed.

Three configurations are compared:

- `baseline1`: single AI, one attempt.
- `baseline3`: single AI, up to three attempts.
- `team`: multi-agent workflow.

`baseline3` helps separate the benefit of additional attempts from the benefit of assigning different roles to multiple agents.

Run the evaluation and regenerate its report:

```bash
.venv/bin/python -m eval.run_eval --run-name full
.venv/bin/python -m eval.report --run-name full --rescore
```

The evaluation saves results as it runs so it can resume after interruption.

Dataset licences could not be established (checked 2026-10-27). See `eval/datasets/SOURCES.md` for sources, status and file fingerprints.

## Evaluation results

The corrected primary scores are:

| Arm | Correct answers | Accuracy |
|---|---:|---:|
| baseline1 | 47/50 | 94% |
| baseline3 | 50/50 | 100% |
| team | 48/50 | 96% |

The scorer correction fixed a number-word parsing bug that incorrectly marked the team's answer "Four rows have a size of 6" as wrong when the expected answer was 4. The correction changed `team tips-08` from fail to pass.

The team did not outperform baseline3 in this evaluation. The team also cost substantially more. The results do not establish a statistically distinguishable winner.

See `eval/results/RESULTS.md` for the failure analysis, limitations, and interview questions. See `eval/results/full_report.md` for the corrected primary report, `eval/results/full_report_as_built.md` for the original as-built report, and `eval/results/full_sensitivity_report.md` for the separate post-hoc chart-scoring sensitivity analysis.

## Limits of the evaluation

This was one run of 50 questions across three small datasets using one model. Small score differences should be interpreted cautiously. Baseline3 achieved 100%, creating a ceiling effect that limits what this test can reveal about the potential benefits of a multi-agent system.

The automatic scorer is not perfect. The number-word issue was found while examining failed answers, demonstrating why failures need manual inspection. Chart scoring checks plotted data, not visual presentation. The cause of the run metadata's dirty-tree flag has not been proven.

Future evaluation should use more questions, harder tasks, more diverse datasets, and repeated runs.

## Further work

Potential improvements include investigating the team's `tips-05` failure to report the requested average, understanding why `tips-15` ended in `not_sure`, and testing any proposed changes in a new evaluation version. Do not treat post-hoc sensitivity results as changes to the primary run.