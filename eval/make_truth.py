"""Builds eval/questions.json.

Every expected answer is computed with plain pandas from the CSV files.
No AI is used here. Run from the project root:
    .venv/bin/python eval/make_truth.py

The script stops with a message if a column, a category value or a tie
would make a question ambiguous. Nothing is written in that case.
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "datasets")
OUT = os.path.join(HERE, "questions.json")

EXPECTED_COLUMNS = {
    "tips": ["total_bill", "tip", "sex", "smoker", "day", "time", "size"],
    "penguins": ["species", "island", "bill_length_mm", "bill_depth_mm",
                 "flipper_length_mm", "body_mass_g", "sex"],
    "taxis": ["pickup", "dropoff", "passengers", "distance", "fare", "tip", "tolls",
              "total", "color", "payment", "pickup_zone", "dropoff_zone",
              "pickup_borough", "dropoff_borough"],
}


def load(name):
    df = pd.read_csv(os.path.join(DATA, name + ".csv"))
    if set(df.columns) != set(EXPECTED_COLUMNS[name]):
        sys.exit(f"STOP: {name}.csv columns are {list(df.columns)}. "
                 f"Expected {EXPECTED_COLUMNS[name]}. Paste this message to me.")
    return df


def need(df, col, value):
    """Stop if a category value is not what the question assumes."""
    if value not in set(df[col].dropna().unique()):
        sys.exit(f"STOP: value {value!r} not found in column {col!r}. "
                 f"Found: {sorted(df[col].dropna().unique())[:10]}")


def top_label(series):
    """Name of the biggest group. Stops if the top two are tied."""
    s = series.sort_values(ascending=False)
    if s.iloc[0] == s.iloc[1]:
        sys.exit(f"STOP: tie at the top: {s.head(3).to_dict()}")
    return str(s.index[0])


# ---- expected-answer shapes (the scorer in Batch 4 reads these) ----
def num(value, exact=False):
    if exact:
        return {"type": "number", "value": int(value), "rel_tol": 0}
    return {"type": "number", "value": round(float(value), 6), "rel_tol": 0.01}


def text(value):
    return {"type": "text", "value": str(value)}


def _stats(s):
    return {"min": round(float(s.min()), 6), "max": round(float(s.max()), 6),
            "sum": round(float(s.sum()), 6)}


def chart_bar(labels, heights):
    """Bar chart: each label must have a bar of about this height."""
    return {"type": "chart", "plot": "bar",
            "labels": [str(x) for x in labels],
            "heights": [round(float(h), 6) for h in heights],
            "rel_tol": 0.01}


def chart_hist(values):
    """Histogram: touching bars, total count = n, bins cover min to max."""
    v = pd.Series(values).dropna()
    return {"type": "chart", "plot": "hist", "n": int(len(v)),
            "min": round(float(v.min()), 6), "max": round(float(v.max()), 6)}


def chart_scatter(x, y):
    """Scatter: one point per complete (x, y) pair. x and y are checked separately."""
    d = pd.DataFrame({"x": x.values, "y": y.values}).dropna()
    return {"type": "chart", "plot": "scatter", "n": int(len(d)),
            "x": _stats(d["x"]), "y": _stats(d["y"]), "rel_tol": 0.001}


CANNOT = {"type": "cannot_answer"}

QUESTIONS = []


def add(dataset, kind, question, expected):
    n = sum(1 for x in QUESTIONS if x["dataset"] == dataset) + 1
    QUESTIONS.append({
        "id": f"{dataset}-{n:02d}",
        "dataset": dataset,
        "csv": f"eval/datasets/{dataset}.csv",
        "kind": kind,  # lookup | calculation | chart | unanswerable
        "question": question,
        "expected": expected,
    })


# ======================= tips (17) =======================
tips = load("tips")
for v in ("Dinner", "Lunch"):
    need(tips, "time", v)
need(tips, "smoker", "Yes")

add("tips", "calculation", "What is the average total_bill?", num(tips["total_bill"].mean()))
add("tips", "calculation", "What is the sum of all tip values?", num(tips["tip"].sum()))
add("tips", "lookup", "Which day has the highest average tip?",
    text(top_label(tips.groupby("day")["tip"].mean())))
add("tips", "calculation", "What percentage of rows have smoker equal to Yes?",
    num((tips["smoker"] == "Yes").mean() * 100))
add("tips", "calculation",
    "What is the average of tip divided by total_bill, times 100, calculated for each row?",
    num((tips["tip"] / tips["total_bill"] * 100).mean()))
add("tips", "lookup", "What is the largest total_bill value?", num(tips["total_bill"].max()))
add("tips", "calculation", "What is the median tip?", num(tips["tip"].median()))
add("tips", "calculation", "How many rows have size equal to 6?", num((tips["size"] == 6).sum(), exact=True))
add("tips", "calculation",
    "What is the average tip for time Dinner minus the average tip for time Lunch?",
    num(tips[tips["time"] == "Dinner"]["tip"].mean() - tips[tips["time"] == "Lunch"]["tip"].mean()))
add("tips", "lookup", "Which sex has the highest sum of total_bill?",
    text(top_label(tips.groupby("sex")["total_bill"].sum())))
add("tips", "calculation", "What is the correlation between total_bill and tip?",
    num(tips["total_bill"].corr(tips["tip"])))
# True answer is 0 (the maximum tip is 10). Zero is a real answer, not "cannot answer".
add("tips", "calculation", "How many rows have a tip greater than 10?", num((tips["tip"] > 10).sum(), exact=True))
add("tips", "chart", "Draw a bar chart of the sum of tip for each day.", chart_bar(tips.groupby("day")["tip"].sum().index, tips.groupby("day")["tip"].sum().values))
add("tips", "chart", "Draw a histogram of total_bill.", chart_hist(tips["total_bill"]))
add("tips", "chart", "Draw a scatter plot with total_bill on the x-axis and tip on the y-axis.", chart_scatter(tips["total_bill"], tips["tip"]))
add("tips", "unanswerable", "What is the average waiter rating?", CANNOT)
add("tips", "unanswerable", "Which waiter received the most tips?", CANNOT)

# ======================= penguins (17) =======================
pen = load("penguins")
for v in ("FEMALE", "MALE"):
    need(pen, "sex", v)
for v in ("Gentoo", "Chinstrap"):
    need(pen, "species", v)

add("penguins", "calculation", "How many rows are in the data?", num(len(pen), exact=True))
add("penguins", "calculation", "What is the average body_mass_g?", num(pen["body_mass_g"].mean()))
add("penguins", "lookup", "Which species has the most rows?", text(top_label(pen["species"].value_counts())))
add("penguins", "calculation", "What is the average flipper_length_mm of the Gentoo species?",
    num(pen[pen["species"] == "Gentoo"]["flipper_length_mm"].mean()))
add("penguins", "calculation", "How many rows have a missing value in the sex column?",
    num(pen["sex"].isna().sum(), exact=True))
add("penguins", "lookup", "Which island has the highest average body_mass_g?",
    text(top_label(pen.groupby("island")["body_mass_g"].mean())))
add("penguins", "lookup", "What is the largest bill_length_mm value?", num(pen["bill_length_mm"].max()))
add("penguins", "calculation",
    "Among the rows where sex is known, what percentage have sex equal to FEMALE?",
    num((pen["sex"].dropna() == "FEMALE").mean() * 100))
add("penguins", "calculation", "What is the average bill_depth_mm of the Chinstrap species?",
    num(pen[pen["species"] == "Chinstrap"]["bill_depth_mm"].mean()))
add("penguins", "lookup", "Which species has the highest average body_mass_g?",
    text(top_label(pen.groupby("species")["body_mass_g"].mean())))
add("penguins", "calculation", "How many rows have at least one missing value in any column?",
    num(pen.isna().any(axis=1).sum(), exact=True))
add("penguins", "calculation", "What is the sample standard deviation of flipper_length_mm?",
    num(pen["flipper_length_mm"].std()))
add("penguins", "calculation",
    "What is the average body_mass_g of MALE penguins minus the average body_mass_g of FEMALE penguins?",
    num(pen[pen["sex"] == "MALE"]["body_mass_g"].mean() - pen[pen["sex"] == "FEMALE"]["body_mass_g"].mean()))
add("penguins", "chart", "Draw a bar chart of the number of rows for each species.",
    chart_bar(pen["species"].value_counts().index, pen["species"].value_counts().values))
add("penguins", "chart", "Draw a scatter plot with bill_length_mm on the x-axis and bill_depth_mm on the y-axis.", chart_scatter(pen["bill_length_mm"], pen["bill_depth_mm"]))
add("penguins", "chart", "Draw a bar chart of the average body_mass_g for each species.",
    chart_bar(pen.groupby("species")["body_mass_g"].mean().index, pen.groupby("species")["body_mass_g"].mean().values))
add("penguins", "unanswerable", "What is the average age of the penguins?", CANNOT)

# ======================= taxis (16) =======================
tx = load("taxis")
need(tx, "payment", "credit card")
need(tx, "color", "yellow")
pickup = pd.to_datetime(tx["pickup"])
dropoff = pd.to_datetime(tx["dropoff"])

add("taxis", "calculation", "How many rows are in the data?", num(len(tx), exact=True))
add("taxis", "calculation", "What is the average fare?", num(tx["fare"].mean()))
add("taxis", "calculation", "What is the sum of all tip values?", num(tx["tip"].sum()))
add("taxis", "lookup", "Which pickup_borough has the most rides?",
    text(top_label(tx["pickup_borough"].value_counts())))
add("taxis", "calculation", "What is the average distance of rides where payment is credit card?",
    num(tx[tx["payment"] == "credit card"]["distance"].mean()))
add("taxis", "calculation", "How many rows have a missing value in the payment column?",
    num(tx["payment"].isna().sum(), exact=True))
add("taxis", "calculation", "How many rides had more than 2 passengers?", num((tx["passengers"] > 2).sum(), exact=True))
add("taxis", "lookup", "What is the highest fare?", num(tx["fare"].max()))
add("taxis", "calculation", "What is the average total for rides where color is yellow?",
    num(tx[tx["color"] == "yellow"]["total"].mean()))
add("taxis", "lookup", "On which calendar date (YYYY-MM-DD) were the most rides picked up?",
    text(top_label(pickup.dt.date.value_counts())))
add("taxis", "calculation",
    "What is the average trip duration in minutes, from pickup to dropoff?",
    num(((dropoff - pickup).dt.total_seconds() / 60).mean()))
add("taxis", "calculation", "What percentage of rides have a tip of exactly 0?", num((tx["tip"] == 0).mean() * 100))
add("taxis", "lookup", "Which pickup_zone has the most rides?", text(top_label(tx["pickup_zone"].value_counts())))
add("taxis", "chart", "Draw a bar chart of the number of rides for each pickup_borough. Ignore rows with a missing pickup_borough.",
    chart_bar(tx["pickup_borough"].value_counts().index, tx["pickup_borough"].value_counts().values))
add("taxis", "chart", "Draw a histogram of fare.", chart_hist(tx["fare"]))
add("taxis", "unanswerable", "What is the average driver rating?", CANNOT)

# ======================= final checks =======================
ids = [q["id"] for q in QUESTIONS]
if len(QUESTIONS) != 50 or len(set(ids)) != 50:
    sys.exit(f"STOP: expected 50 unique questions, got {len(QUESTIONS)} ({len(set(ids))} unique).")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(QUESTIONS, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"{'id':<13}{'kind':<14}expected")
for q in QUESTIONS:
    e = q["expected"]
    shown = e.get("value", e.get("labels", e.get("plot", ""))) if e["type"] != "cannot_answer" else "CANNOT ANSWER"
    print(f"{q['id']:<13}{q['kind']:<14}{shown}")

kinds = {}
for q in QUESTIONS:
    kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
print(f"\nWrote {len(QUESTIONS)} questions to {OUT}")
print("By kind:", kinds)