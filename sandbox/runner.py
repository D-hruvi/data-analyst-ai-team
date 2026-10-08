"""Runs ONE piece of generated code and saves the result + chart.
It runs as a separate process. In Stage 3 this same file runs inside Docker.
Usage: python runner.py <csv_path> <code_path>   (writes result.json, chart.png in the current folder)"""
import json
import sys

import matplotlib
matplotlib.use("Agg")  # draw charts into files, no screen needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

csv_path, code_path = sys.argv[1], sys.argv[2]

try:  # same loading rule as dataset.py
    df = pd.read_csv(csv_path)
except UnicodeDecodeError:
    df = pd.read_csv(csv_path, encoding="latin-1")

with open(code_path, encoding="utf-8") as f:
    source = f.read()

# These names are ready to use inside the generated code
namespace = {"df": df, "pd": pd, "np": np, "plt": plt}
exec(compile(source, "generated_code.py", "exec"), namespace)  # run it

result = namespace.get("result")
if result is None:
    sys.exit("The code did not set 'result' (or set it to None).")

# Safety net: a single value that is NaN (not a number) or infinite is not a real answer.
# This runs even if the AI ignores the prompt. (Empty tables are fine: 'no rows match' is valid.)
is_table = isinstance(result, (pd.DataFrame, pd.Series))
if not is_table and pd.api.types.is_scalar(result):
    if pd.isna(result) or (isinstance(result, (float, np.floating)) and np.isinf(result)):
        sys.exit(f"The result is {result}, which is not a real answer. "
                 "The data may not contain what the question needs.")

if is_table:
    text = result.head(50).to_string()  # tables: first 50 rows only
else:
    text = str(result)

if plt.get_fignums():  # a chart was drawn
    plt.savefig("chart.png", dpi=100, bbox_inches="tight")

with open("result.json", "w", encoding="utf-8") as f:
    json.dump({"result": text[:3000]}, f)
