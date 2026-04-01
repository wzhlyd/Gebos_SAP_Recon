# GEBOS_SAP_Recon — UGB Reconciliation Report

## Overview

Reconciles balances between **SAP** and **GEBOS** for UGB reporting by matching on 6 dimension columns via a concatenated key.

## Folder Structure

```
GEBOS_SAP_Recon/
├── Input/
│   ├── SAP_FILE_UGB.xlsb
│   └── GEBOS_FILE_UGB.xlsx
├── Output/
│   └── UGB_Reconciliation_Result.xlsx
├── src/
│   └── reconcile_ugb.py
└── .venv/
```

## How to Run

**1. Create and activate virtual environment (first time only):**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**2. Install dependencies (first time only):**

```bash
pip install -r requirements.txt
```

**3. Activate venv and run the reconciliation:**

```bash
.venv\Scripts\activate

python src/reconcile_ugb.py
```

## Input Files

Files are auto-detected in the `/Input` folder by keyword in the filename:
- The **SAP** file must contain `"SAP"` in its name (e.g., `SAP_FILE_UGB.xlsb`, `SAP_Jan2026.xlsb`)
- The **GEBOS** file must contain `"GEBOS"` in its name (e.g., `GEBOS_FILE_UGB.xlsx`, `GEBOS_Q1.xlsx`)

The script will error if zero or multiple files match a keyword.

| Keyword | Sheet | Headers | Description |
|---|---|---|---|
| `SAP` | Balances | Row 9 | SAP balances |
| `GEBOS` | GEB_gesamt | Row 1 | GEBOS balances |

## Transformation Steps

### Step 1: Load and Prepare SAP Data

1. Read sheet **Balances** from `SAP_FILE_UGB.xlsb` (headers in row 9).
2. **Exclude** the summary row where `Ledger = 'Result'`.
3. **Format** `Account Number` from float to integer string (e.g., `1128800001.0` → `"1128800001"`).
4. **Filter out** rows where `Account Number` starts with `6`.
5. **Replace** `"#"` with `""` (empty string) across all 6 dimension columns. SAP uses `#` as a placeholder for blank cells.
6. **Cast** `Ending Balance LC` to numeric (coerce errors to 0).
7. **Group by** 6 dimensions, **SUM** `Ending Balance LC` (equivalent to a pivot table).
8. **Build concat key** by joining all 6 dimension values into a single string.

**SAP Dimension Columns:**
| Column | Description |
|---|---|
| Account Number | SAP account number |
| Account.Product | Product type |
| Counterparty | Counterparty classification |
| KMS number | Customer number |
| Residence/Curr | Residence/Currency indicator |
| Trading Partner No. | Trading partner |

### Step 2: Load and Prepare GEBOS Data

1. Read sheet **GEB_gesamt** from `GEBOS_FILE_UGB.xlsx` (headers in row 1).
2. **Filter out** rows where `SAP-Konto` is empty (including whitespace-only values).
3. **Filter out** rows where `SAP-Konto` starts with `6`.
4. **Filter out** rows where `komponente` is empty.
5. **Convert** `Kundennr` from float to integer (e.g., `33084.0` → `33084`).
6. **Clean** all dimension values: NaN → `""`, strip whitespace.
7. **Cast** `GEBOS_saldo_eur_ugb` to numeric (coerce errors to 0).
8. **Group by** 6 dimensions, **SUM** `GEBOS_saldo_eur_ugb` (equivalent to a pivot table).
9. **Build concat key** by joining all 6 dimension values into a single string.

**GEBOS Dimension Columns:**
| Column | Maps to SAP Column |
|---|---|
| SAP-Konto | Account Number |
| AccProd | Account.Product |
| Counterparty | Counterparty |
| Kundennr | KMS number |
| ResiCurr | Residence/Curr |
| Partnerges | Trading Partner No. |

### Step 3: Reconcile

1. **Build SAP lookup** dictionary: concat key → SAP amount.
2. For each GEBOS grouped row, **look up** the matching SAP amount by concat key (0 if no match).
3. **Calculate** `Difference = GEBOS_Amount − SAP_Amount`.
4. **Cast** all amount columns (`GEBOS_Amount`, `SAP_Amount`, `Difference`) to float.

### Step 4: Build Summary

Generate summary metrics:
- Total GEBOS rows (after filters & grouping)
- GEBOS rows matched / not matched in SAP
- Sum of GEBOS_Amount, SAP_Amount, Difference
- Count of rows with non-zero difference (threshold: 0.001)

### Step 5: Write Output

1. Write **Reconciliation** sheet with columns: `SAP-Konto`, `AccProd`, `Counterparty`, `Kundennr`, `ResiCurr`, `Partnerges`, `GEBOS_Amount`, `SAP_Amount`, `Difference`.
2. Write **Summary** sheet with key metrics.
3. **Apply** `#,##0.00` number format to all amount columns.

## Output File

`Output/UGB_Reconciliation_Result.xlsx` with 2 sheets:

| Sheet | Content |
|---|---|
| Reconciliation | One row per unique GEBOS dimension combination with GEBOS amount, SAP amount, and difference |
| Summary | Aggregate metrics (row counts, totals, mismatch count) |

## Key Design Decisions

- **Concat key matching**: Dimensions are concatenated into a single string for lookup — mirrors the original manual XLOOKUP approach.
- **`#` → blank**: SAP's `#` placeholder is stripped before concat so keys align with GEBOS.
- **SAP filters applied before grouping**: `Ledger = 'Result'` summary row and `Account Number` starting with `6` are excluded from the raw data before aggregation.
- **GEBOS filters applied before grouping**: Empty `SAP-Konto`, `SAP-Konto` starting with `6`, and empty `komponente` rows are excluded from the raw data before aggregation.
- **Left join on GEBOS**: The reconciliation is GEBOS-based — every GEBOS row appears in the output; SAP rows with no GEBOS match are not included.
