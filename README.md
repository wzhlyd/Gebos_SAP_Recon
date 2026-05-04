# GEBOS_SAP_Recon — UGB & IFRS Reconciliation

## Overview

Reconciles balances between **SAP** and **GEBOS** for **UGB** and **IFRS** reporting by matching on 6 dimension columns via a concatenated key.

## Folder Structure

```
GEBOS_SAP_Recon/
├── Input/
│   ├── SAP_UGB_<date>.xlsm
│   ├── SAP_IFRS_<date>.xlsm
│   ├── GEBOS_..._UGB_..._<date>.xlsx
│   └── GEBOS_..._IFRS_..._<date>.xlsx
├── Output/
│   ├── UGB_Reconciliation_Result.xlsx
│   ├── IFRS_Reconciliation_Result.xlsx
│   ├── UGB_Difference_Analysis.md
│   └── IFRS_Difference_Analysis.md
├── src/
│   ├── reconcile.py
│   ├── reconcile_ugb.py
│   ├── reconcile_ifrs.py
│   ├── generate_report.py
│   ├── source_checks.py
│   └── Difference_Analysis.prompt.md
└── .venv/
```

## How to Install

**1. Create and activate virtual environment (first time only):**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**2. Install dependencies (first time only):**

```bash
python -m pip install -r requirements.txt
```

## How to Run

```bash
.venv\Scripts\activate

# Unified (reconciliation + report in one step)
python src/reconcile.py              # runs both UGB and IFRS
python src/reconcile.py ugb           # UGB only
python src/reconcile.py ifrs          # IFRS only

# Individual scripts
python src/reconcile_ugb.py            # UGB reconciliation only
python src/reconcile_ifrs.py           # IFRS reconciliation only

# Difference Analysis Reports (standalone)
python src/generate_report.py          # generates both UGB and IFRS reports
python src/generate_report.py ugb      # UGB report only
python src/generate_report.py ifrs     # IFRS report only
```

## Input Files

Files are auto-detected in the `/Input` folder by keyword in the filename:

| Script | SAP Keywords | GEBOS Keywords | Description |
|---|---|---|---|
| `reconcile_ugb.py` | `SAP` + `UGB` | `GEBOS` + `UGB` | UGB reconciliation |
| `reconcile_ifrs.py` | `SAP` + `IFRS` | `GEBOS` + `IFRS` | IFRS reconciliation |

All keywords must be present in the filename (case-insensitive). This allows both UGB and IFRS files to coexist in the Input folder without conflicts.

| Source | Sheet | Headers | Description |
|---|---|---|---|
| SAP (`.xlsm`) | Balances | Row 9 | SAP balances |
| GEBOS (`.xlsx`) | GEB_gesamt | Row 1 | GEBOS balances |

## Transformation Steps

Both scripts follow the same 5-step process. The only differences are noted below.

### Step 1: Load and Prepare SAP Data

1. Read sheet **Balances** from the SAP `.xlsm` file (headers in row 9).
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

1. Read sheet **GEB_gesamt** from the GEBOS `.xlsx` file (headers in row 1).
2. **Filter out** rows where `SAP-Konto` is empty (including whitespace-only values).
3. **Filter out** rows where `SAP-Konto` starts with `6`.
4. **Filter out** rows where `komponente` is empty.
5. **Convert** `Kundennr` from float to integer (e.g., `33084.0` → `33084`).
6. **Clean** all dimension values: NaN → `""`, strip whitespace.
7. **Cast** the amount column to numeric (coerce errors to 0).
8. **Group by** 6 dimensions, **SUM** the amount column (equivalent to a pivot table).
9. **Build concat key** by joining all 6 dimension values into a single string.

**GEBOS Amount Column:**
| Script | Column |
|---|---|
| `reconcile_ugb.py` | `GEBOS_saldo_eur_ugb` |
| `reconcile_ifrs.py` | `GEBOS_saldo_eur_ifrs` |

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

## Output Files

| Script | Output File |
|---|---|
| `reconcile_ugb.py` | `Output/UGB_Reconciliation_Result.xlsx` |
| `reconcile_ifrs.py` | `Output/IFRS_Reconciliation_Result.xlsx` |
| `generate_report.py` | `Output/UGB_Difference_Analysis.md` and/or `Output/IFRS_Difference_Analysis.md` |

Each reconciliation `.xlsx` has 2 sheets:

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
- **UGB vs IFRS**: Both scripts share identical logic; the only differences are the input file keywords (`SAP` + `UGB` / `GEBOS` + `UGB` vs `SAP` + `IFRS` / `GEBOS` + `IFRS`) and the GEBOS amount column (`GEBOS_saldo_eur_ugb` vs `GEBOS_saldo_eur_ifrs`).
