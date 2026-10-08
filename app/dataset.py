"""Loads a CSV and builds a SHORT summary. The full CSV is never sent to the AI."""
import pandas as pd

from app import config


def load_csv(path):
    """Read a CSV. If it is not UTF-8, try latin-1 (common in older files)."""
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def _short(value, limit=40):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def build_summary(df):
    """One line per column + a few sample rows. Type 'str' (or 'object') means text."""
    columns = list(df.columns)[: config.MAX_SUMMARY_COLUMNS]
    lines = [f"Rows: {len(df)} | Columns: {len(df.columns)}", "Columns:"]

    for name in columns:
        col = df[name]
        info = f"- {name!r} | type: {col.dtype} | missing: {int(col.isna().sum())}"
        if pd.api.types.is_numeric_dtype(col) and col.notna().any():
            info += f" | min: {col.min()} | max: {col.max()} | mean: {round(float(col.mean()), 2)}"
        else:
            examples = [_short(v) for v in col.dropna().unique()[:5]]
            info += f" | unique values: {col.nunique()} | examples: {examples}"
        lines.append(info)

    hidden = len(df.columns) - len(columns)
    if hidden > 0:
        lines.append(f"(+{hidden} more columns not shown)")

    lines.append(f"First {config.SAMPLE_ROWS} rows:")
    sample = df.head(config.SAMPLE_ROWS)[columns]
    lines.append(sample.to_string(max_colwidth=30))
    return "\n".join(lines)
