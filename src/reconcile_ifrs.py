"""
IFRS Reconciliation Report: SAP vs GEBOS
Compares balances from SAP (Balances sheet, Ledger='0L') and GEBOS (GEB_gesamt sheet)
by matching on 6 dimension columns via a concatenated key.

Input files (in /Input folder):
  - File with "SAP" + "IFRS" in name → Sheet "Balances", headers in row 9
  - File with "GEBOS" + "IFRS" in name → Sheet "GEB_gesamt", headers in row 1

Output:
  - IFRS_Reconciliation_Result.xlsx
"""

import os
import sys
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = SCRIPT_DIR / "Input"
OUTPUT_FILE = SCRIPT_DIR / "Output" / "IFRS_Reconciliation_Result.xlsx"

SAP_KEYWORDS = ["SAP", "IFRS"]
GEBOS_KEYWORDS = ["GEBOS", "IFRS"]


def find_input_file(keywords):
    """Find a single file in INPUT_DIR whose name contains ALL keywords (case-insensitive)."""
    if isinstance(keywords, str):
        keywords = [keywords]
    matches = [
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and all(kw.lower() in f.name.lower() for kw in keywords)
    ]
    label = " + ".join(keywords)
    if len(matches) == 0:
        print(f"ERROR: No file with [{label}] in name found in {INPUT_DIR}")
        sys.exit(1)
    if len(matches) > 1:
        names = [f.name for f in matches]
        print(f"ERROR: Multiple files with [{label}] in name found in {INPUT_DIR}: {names}")
        sys.exit(1)
    print(f"  Found [{label}] file: {matches[0].name}", flush=True)
    return matches[0]


# SAP dimension columns (raw names from Balances sheet)
SAP_DIMS = [
    "Account Number",
    "Account.Product",
    "Counterparty",
    "KMS number",
    "Residence/Curr",
    "Trading Partner No.",
]
SAP_AMOUNT = "Ending Balance LC"

# GEBOS dimension columns (raw names from GEB_gesamt sheet)
GEBOS_DIMS = [
    "SAP-Konto",
    "AccProd",
    "Counterparty",
    "Kundennr",
    "ResiCurr",
    "Partnerges",
]
GEBOS_AMOUNT = "GEBOS_saldo_eur_ifrs"

# Mapping: GEBOS dim name → display alignment
DIM_DISPLAY = [
    "SAP-Konto",
    "AccProd",
    "Counterparty",
    "Kundennr",
    "ResiCurr",
    "Partnerges",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clean_dim_value(val):
    """Convert a dimension value to a clean string for concatenation."""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s == "#":
        return ""
    return s


def build_concat_key(row, dim_cols):
    """Build concatenation key from dimension columns."""
    return "".join(clean_dim_value(row[c]) for c in dim_cols)


def format_account_number(val):
    """Convert Account Number from float to integer string."""
    if pd.isna(val):
        return ""
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


def format_kundennr(val):
    """Convert Kundennr from float to integer."""
    if pd.isna(val):
        return ""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return val


# ---------------------------------------------------------------------------
# Step 1: Load and prepare SAP data
# ---------------------------------------------------------------------------
def load_sap_data(sap_file):
    print("Loading SAP data...", flush=True)
    df = pd.read_excel(sap_file, sheet_name="Balances", header=8, engine="openpyxl")
    print(f"  Raw rows: {len(df)}", flush=True)

    # Exclude summary row
    df = df[df["Ledger"] != "Result"].copy()
    print(f"  After excluding Result row: {len(df)}", flush=True)

    # Format Account Number as integer string
    df["Account Number"] = df["Account Number"].apply(format_account_number)

    # Filter: remove rows where Account Number starts with '6'
    df = df[~df["Account Number"].str.startswith("6")].copy()
    print(f"  After removing Account Number starting with 6: {len(df)}", flush=True)

    # Replace '#' with '' across all dimension columns
    for col in SAP_DIMS:
        df[col] = df[col].apply(clean_dim_value)

    # Ensure amount is numeric
    df[SAP_AMOUNT] = pd.to_numeric(df[SAP_AMOUNT], errors="coerce").fillna(0)

    # Group by dimensions, SUM amount
    grouped = df.groupby(SAP_DIMS, as_index=False)[SAP_AMOUNT].sum()
    print(f"  Grouped rows (pivot): {len(grouped)}", flush=True)

    # Build concat key
    grouped["Concat"] = grouped.apply(lambda r: build_concat_key(r, SAP_DIMS), axis=1)

    return grouped


# ---------------------------------------------------------------------------
# Step 2: Load and prepare GEBOS data
# ---------------------------------------------------------------------------
def load_gebos_data(gebos_file):
    print("Loading GEBOS data...", flush=True)
    df = pd.read_excel(gebos_file, sheet_name="GEB_gesamt", header=0, engine="openpyxl")
    print(f"  Raw rows: {len(df)}", flush=True)

    # Filter: remove rows where SAP-Konto is empty (including whitespace-only)
    df = df[df["SAP-Konto"].notna()].copy()
    df = df[df["SAP-Konto"].astype(str).str.strip() != ""].copy()
    print(f"  After removing empty SAP-Konto: {len(df)}", flush=True)

    # Filter: remove rows where SAP-Konto starts with '6'
    df = df[~df["SAP-Konto"].astype(str).str.strip().str.startswith("6")].copy()
    print(f"  After removing SAP-Konto starting with 6: {len(df)}", flush=True)

    # Filter: remove rows where komponente is empty
    df = df[df["komponente"].notna() & (df["komponente"] != "")].copy()
    print(f"  After removing empty komponente: {len(df)}", flush=True)

    # Convert Kundennr to integer
    df["Kundennr"] = df["Kundennr"].apply(format_kundennr)

    # Clean dimension values (NaN → '')
    for col in GEBOS_DIMS:
        df[col] = df[col].apply(clean_dim_value)

    # Ensure amount is numeric
    df[GEBOS_AMOUNT] = pd.to_numeric(df[GEBOS_AMOUNT], errors="coerce").fillna(0)

    # Group by dimensions, SUM amount
    grouped = df.groupby(GEBOS_DIMS, as_index=False)[GEBOS_AMOUNT].sum()
    print(f"  Grouped rows (pivot): {len(grouped)}", flush=True)

    # Build concat key
    grouped["Concat"] = grouped.apply(lambda r: build_concat_key(r, GEBOS_DIMS), axis=1)

    return grouped


# ---------------------------------------------------------------------------
# Step 3: Reconcile
# ---------------------------------------------------------------------------
def reconcile(sap_df, gebos_df):
    print("Reconciling...", flush=True)

    # Create lookup dict: SAP concat → SAP amount
    sap_lookup = dict(zip(sap_df["Concat"], sap_df[SAP_AMOUNT]))

    # --- GEBOS-based reconciliation (all GEBOS rows, lookup SAP) ---
    gebos_result = gebos_df.copy()
    gebos_result["SAP_Amount"] = gebos_result["Concat"].map(sap_lookup).fillna(0)
    gebos_result["Difference"] = gebos_result[GEBOS_AMOUNT] - gebos_result["SAP_Amount"]

    # Rename GEBOS amount for clarity
    gebos_result = gebos_result.rename(columns={GEBOS_AMOUNT: "GEBOS_Amount"})

    # Ensure amount columns are numeric and round to 2 decimal places
    for col in ["GEBOS_Amount", "SAP_Amount", "Difference"]:
        gebos_result[col] = pd.to_numeric(gebos_result[col], errors="coerce").fillna(0).round(2)

    # Reorder columns (no Concat in output)
    gebos_result = gebos_result[
        DIM_DISPLAY + ["GEBOS_Amount", "SAP_Amount", "Difference"]
    ]

    matched_gebos = len(gebos_result[gebos_result["SAP_Amount"] != 0])
    unmatched_gebos = len(gebos_result[gebos_result["SAP_Amount"] == 0])
    print(f"  GEBOS rows matched in SAP: {matched_gebos}", flush=True)
    print(f"  GEBOS rows NOT matched in SAP: {unmatched_gebos}", flush=True)

    return gebos_result


# ---------------------------------------------------------------------------
# Step 4: Build summary
# ---------------------------------------------------------------------------
def build_summary(gebos_result):
    summary_data = {
        "Metric": [
            "Total GEBOS rows (after filters & grouping)",
            "GEBOS rows matched in SAP",
            "GEBOS rows NOT matched in SAP",
            "",
            "Sum GEBOS_Amount",
            "Sum SAP_Amount",
            "Sum Difference",
            "",
            "Rows with non-zero difference",
        ],
        "Value": [
            len(gebos_result),
            len(gebos_result[gebos_result["SAP_Amount"] != 0]),
            len(gebos_result[gebos_result["SAP_Amount"] == 0]),
            "",
            round(gebos_result["GEBOS_Amount"].sum(), 2),
            round(gebos_result["SAP_Amount"].sum(), 2),
            round(gebos_result["Difference"].sum(), 2),
            "",
            len(gebos_result[gebos_result["Difference"].abs() > 0.001]),
        ],
    }
    return pd.DataFrame(summary_data)


# ---------------------------------------------------------------------------
# Step 5: Write output
# ---------------------------------------------------------------------------
def write_output(gebos_result, summary):
    print(f"Writing output to {OUTPUT_FILE.name}...", flush=True)

    # Force amount columns to float64 so openpyxl writes them as numbers
    amount_cols = ["GEBOS_Amount", "SAP_Amount", "Difference"]
    for col in amount_cols:
        gebos_result[col] = gebos_result[col].astype(float)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        gebos_result.to_excel(writer, sheet_name="Reconciliation", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)

        # Apply number format to amount columns
        ws = writer.sheets["Reconciliation"]
        for col_idx, col_name in enumerate(gebos_result.columns, start=1):
            if col_name in amount_cols:
                for row_idx in range(2, len(gebos_result) + 2):
                    ws.cell(row=row_idx, column=col_idx).number_format = '#,##0.00'

    print("Done.", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Find input files by keywords (all must match)
    sap_file = find_input_file(SAP_KEYWORDS)
    gebos_file = find_input_file(GEBOS_KEYWORDS)

    sap_df = load_sap_data(sap_file)
    gebos_df = load_gebos_data(gebos_file)
    gebos_result = reconcile(sap_df, gebos_df)
    summary = build_summary(gebos_result)
    write_output(gebos_result, summary)

    # Print quick stats
    diff_rows = gebos_result[gebos_result["Difference"].abs() > 0.001]
    print(f"\n=== Quick Summary ===")
    print(f"  Reconciliation rows: {len(gebos_result)}")
    print(f"  Rows with difference: {len(diff_rows)}")
    print(f"  Total difference: {round(gebos_result['Difference'].sum(), 2)}")


if __name__ == "__main__":
    main()
