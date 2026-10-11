from app import sandbox

CSV = "eval/datasets/sample_sales.csv"

code = """
# Check that the required columns exist
required_cols = {'region', 'units'}

if not required_cols.issubset(df.columns):
    missing = required_cols - set(df.columns)
    raise ValueError(f"CANNOT_ANSWER: missing columns {missing}")

# Check that units is numeric
if not pd.api.types.is_numeric_dtype(df['units']):
    raise ValueError("CANNOT_ANSWER: 'units' column is not numeric")

# Group units by region
grouped = df.groupby('region', as_index=False)['units'].sum()

# Create the bar chart
plt.bar(grouped['region'].astype(str), grouped['units'])
plt.xlabel('Region')
plt.ylabel('Total Units')
plt.title('Total Units per Region')

# Store the result
result = grouped
"""

out = sandbox.run_code(code, CSV)

print("FULL SANDBOX OUTPUT:")
print(out)