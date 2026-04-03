"""
Generate Difference Analysis Report (.MD) for UGB and/or IFRS reconciliation.

Reads the reconciliation output and produces a structured Markdown report with:
  1. Overview
  2. Difference waterfall (offsetting pairs, unmatched, remaining)
  3. Confirmed offsetting pairs detail
  4. GEBOS-only rows
  5. SAP-only rows
  6. Remaining unexplained rows
  7. Dimension breakdowns (AccProd, Counterparty, ResiCurr, Partnerges)
  8. Placeholders for analyst commentary

Usage:
  python src/generate_report.py          # generates both UGB and IFRS
  python src/generate_report.py ugb      # generates UGB only
  python src/generate_report.py ifrs     # generates IFRS only
  python src/generate_report.py both     # generates both (default)

The script outputs DATA-DRIVEN sections only. Narrative interpretation
(what is confirmed related, what is unknown) should be added by the analyst
or by the AI prompt that calls this script.
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = SCRIPT_DIR / "Output"
DIFF_THRESHOLD = 0.01
CANCEL_PCT = 90  # % cancellation to qualify as offsetting pair

REPORT_CONFIGS = {
    "ugb": {
        "recon_file": OUTPUT_DIR / "UGB_Reconciliation_Result.xlsx",
        "report_file": OUTPUT_DIR / "UGB_Difference_Analysis.md",
        "title": "UGB Reconciliation — Difference Analysis",
    },
    "ifrs": {
        "recon_file": OUTPUT_DIR / "IFRS_Reconciliation_Result.xlsx",
        "report_file": OUTPUT_DIR / "IFRS_Difference_Analysis.md",
        "title": "IFRS Reconciliation — Difference Analysis",
    },
}


def load_recon(recon_file):
    """Load Reconciliation sheet from output file."""
    df = pd.read_excel(recon_file, sheet_name="Reconciliation", engine="openpyxl")
    return df


def get_diffs(df):
    """Filter to rows with a material difference."""
    return df[df["Difference"].abs() > DIFF_THRESHOLD].copy()


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------
def find_offsetting_customers(diffs):
    """Find customers where diffs cancel each other >CANCEL_PCT%."""
    by_kund = diffs.groupby("Kundennr").agg(
        Count=("Difference", "size"),
        Net=("Difference", "sum"),
        Gross=("Difference", lambda x: x.abs().sum()),
    ).query("Count >= 2")
    by_kund["Cancel_pct"] = (1 - by_kund["Net"].abs() / by_kund["Gross"]) * 100
    return by_kund[by_kund["Cancel_pct"] > CANCEL_PCT].sort_values("Gross", ascending=False)


def find_unmatched(diffs):
    """Split into GEBOS-only and SAP-only rows."""
    gebos_only = diffs[diffs["SAP_Amount"] == 0].copy()
    sap_only = diffs[diffs["GEBOS_Amount"] == 0].copy()
    return gebos_only, sap_only


# ---------------------------------------------------------------------------
# Markdown formatting helpers
# ---------------------------------------------------------------------------
def fmt(val):
    """Format number with comma separator, 2 decimals, with sign for positive."""
    if pd.isna(val):
        return "—"
    v = float(val)
    if v > 0:
        return f"+{v:,.2f}"
    return f"{v:,.2f}"


def fmt_plain(val):
    """Format number with comma separator, 2 decimals, no forced sign."""
    if pd.isna(val):
        return "—"
    return f"{float(val):,.2f}"


def fmt_pct(val):
    """Format percentage."""
    return f"{float(val):.1f}%"


def md_table(headers, rows):
    """Build a Markdown table string."""
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------
def section_overview(recon, diffs):
    """§1 Overview."""
    total = len(recon)
    n_diff = len(diffs)
    pct = n_diff / total * 100 if total > 0 else 0
    net = diffs["Difference"].sum()
    lines = [
        "## 1. Overview\n",
        md_table(
            ["Metric", "Value"],
            [
                ["Total reconciliation rows", f"{total:,}"],
                ["Rows with differences", f"{n_diff:,} ({pct:.1f}%)"],
                ["Total net difference", f"**{fmt_plain(net)} EUR**"],
            ],
        ),
    ]
    return "\n".join(lines)


def section_waterfall(diffs, cancel_kundenrs, gebos_only, sap_only):
    """§2 Difference waterfall."""
    cancel_rows = diffs[diffs["Kundennr"].isin(cancel_kundenrs)]
    cancel_net = cancel_rows["Difference"].sum()
    cancel_count = len(cancel_rows)

    gebos_net = gebos_only["Difference"].sum()
    gebos_count = len(gebos_only)

    sap_net = sap_only["Difference"].sum()
    sap_count = len(sap_only)

    explained_idx = set(cancel_rows.index) | set(gebos_only.index) | set(sap_only.index)
    remaining = diffs[~diffs.index.isin(explained_idx)]
    remain_net = remaining["Difference"].sum()
    remain_count = len(remaining)

    total_net = diffs["Difference"].sum()

    lines = [
        "## 2. Difference Waterfall\n",
        "The table below breaks the total difference into groups by how confident we can be about their cause.\n",
        md_table(
            ["Category", "Rows", "Net Diff", "Explanation"],
            [
                [f"**A. Confirmed offsetting pairs**", cancel_count, fmt(cancel_net), "Customers where diffs cancel >90% — see §3"],
                [f"**B. GEBOS-only (no SAP key)**", gebos_count, fmt(gebos_net), "Key exists in GEBOS but not in SAP — see §4"],
                [f"**C. SAP-only (no GEBOS key)**", sap_count, fmt(sap_net), "Key exists in SAP but not in GEBOS — see §5"],
                [f"**D. Remaining unexplained**", remain_count, fmt(remain_net), "Amount mismatches — cause unknown from data alone — see §6"],
                [f"**Total**", f"**{len(diffs)}**", f"**{fmt(total_net)}**", ""],
            ],
        ),
    ]
    return "\n".join(lines), remaining


def section_offsetting_pairs(diffs, cancel_df):
    """§3 Confirmed offsetting pairs."""
    lines = [
        "## 3. Confirmed Offsetting Pairs (Category A)\n",
        "These are customers where the differences across rows cancel each other out by >90%. "
        "This means the same amount appears to be booked against different accounts in SAP vs. GEBOS "
        "for the same customer — the total per customer is correct (or nearly so), but it is split "
        "differently between the two systems.\n",
    ]
    cols = ["SAP-Konto", "AccProd", "Counterparty", "ResiCurr", "GEBOS_Amount", "SAP_Amount", "Difference"]
    for i, (kund, row) in enumerate(cancel_df.iterrows(), 1):
        detail = diffs[diffs["Kundennr"] == kund].sort_values("Difference", key=abs, ascending=False)
        lines.append(f"### 3.{i} Kundennr {kund} — net {fmt(row['Net'])} ({fmt_pct(row['Cancel_pct'])} cancellation)\n")
        table_rows = []
        for _, r in detail.iterrows():
            table_rows.append([
                r["SAP-Konto"], r["AccProd"], r.get("Counterparty", ""), r["ResiCurr"],
                fmt_plain(r["GEBOS_Amount"]), fmt_plain(r["SAP_Amount"]), fmt(r["Difference"]),
            ])
        lines.append(md_table(
            ["SAP-Konto", "AccProd", "Counterparty", "ResiCurr", "GEBOS Amount", "SAP Amount", "Difference"],
            table_rows,
        ))
        # Add insight about which accounts are involved
        accounts = detail["SAP-Konto"].unique().tolist()
        largest_abs = detail["Difference"].abs().max()
        if len(accounts) > 1:
            acct_list = " and ".join(f"`{a}`" for a in accounts[:2])
            lines.append(f"\n> The ±{fmt_plain(largest_abs)} difference is split between accounts {acct_list} differently in each system. The customer total is consistent (net {fmt(row['Net'])}).\n")
        elif len(detail) > 1:
            lines.append(f"\n> Multiple rows in account `{accounts[0]}` offset each other. Net residual: {fmt(row['Net'])}.\n")
        lines.append("")
    return "\n".join(lines)


def section_unmatched(title, section_num, description, rows):
    """§4 or §5 — GEBOS-only or SAP-only."""
    total = rows["Difference"].sum()
    lines = [
        f"## {section_num}. {title}\n",
        f"{description} Total: **{fmt(total)} EUR**.\n",
    ]
    cols_display = ["SAP-Konto", "AccProd", "Counterparty", "Kundennr", "ResiCurr"]
    amt_col = "GEBOS_Amount" if "GEBOS" in title else "SAP_Amount"
    sorted_rows = rows.sort_values("Difference", key=abs, ascending=False)
    table_rows = []
    for _, r in sorted_rows.iterrows():
        table_rows.append([
            r["SAP-Konto"], r["AccProd"], r["Counterparty"], r["Kundennr"],
            r["ResiCurr"], fmt_plain(r[amt_col]), fmt(r["Difference"]),
        ])
    lines.append(md_table(
        ["SAP-Konto", "AccProd", "Counterparty", "Kundennr", "ResiCurr", f"{amt_col.replace('_', ' ')}", "Difference"],
        table_rows,
    ))
    # Add insights
    if len(rows) > 0:
        largest = sorted_rows.iloc[0]
        largest_diff = abs(largest["Difference"])
        total_abs = rows["Difference"].abs().sum()
        largest_pct = largest_diff / total_abs * 100 if total_abs > 0 else 0
        lines.append(f"\n> The largest entry is `{largest['SAP-Konto']}` / `{largest['AccProd']}` / Kundennr `{largest['Kundennr']}` at {fmt(largest['Difference'])}, accounting for {largest_pct:.0f}% of this category's absolute total.")
        # Note dominant account if one account has many rows
        acct_counts = rows["SAP-Konto"].value_counts()
        top_acct = acct_counts.index[0]
        top_acct_count = acct_counts.iloc[0]
        if top_acct_count > 1 and top_acct_count >= len(rows) * 0.4:
            lines.append(f"\n> Account `{top_acct}` appears in {top_acct_count} of {len(rows)} rows in this category.")
        # Note how many rows are immaterial (<100 EUR)
        small_rows = rows[rows["Difference"].abs() < 100]
        if len(small_rows) > 0:
            lines.append(f"\n> {len(small_rows)} of {len(rows)} rows have differences below 100 EUR.")
    return "\n".join(lines)


def section_remaining(remaining):
    """§6 Remaining unexplained."""
    net = remaining["Difference"].sum()
    lines = [
        "## 6. Remaining Unexplained Rows (Category D)\n",
        f"**{len(remaining)} rows with a net difference of {fmt(net)} EUR.** "
        "In these rows, the key exists in both SAP and GEBOS, but the amounts differ. "
        "The script cannot identify offsetting patterns or determine the root cause from "
        "the reconciliation data alone.\n",
    ]
    # Insight: detect rows with identical absolute differences (potential related pairs)
    remaining = remaining.copy()
    remaining["_abs"] = remaining["Difference"].abs()
    abs_counts = remaining.groupby("_abs").size()
    identical_pairs = abs_counts[abs_counts >= 2].index.tolist()
    identical_pairs = [v for v in identical_pairs if v > 1000]  # only material
    if identical_pairs:
        lines.append("### Notable patterns\n")
        for abs_val in sorted(identical_pairs, reverse=True):
            pair_rows = remaining[remaining["_abs"].between(abs_val - 0.01, abs_val + 0.01)]
            pair_net = pair_rows["Difference"].sum()
            kundenrs = pair_rows["Kundennr"].unique()
            accts = pair_rows["SAP-Konto"].unique()
            lines.append(f"- **{len(pair_rows)} rows share an identical absolute difference of {fmt_plain(abs_val)}** "
                         f"(net: {fmt(pair_net)}). "
                         f"Accounts: {', '.join(f'`{a}`' for a in accts)}. "
                         f"Customer(s): {', '.join(str(k) for k in kundenrs)}.")
        lines.append("")
    # Insight: dominant account
    acct_counts = remaining["SAP-Konto"].value_counts()
    top_acct = acct_counts.index[0]
    top_acct_count = acct_counts.iloc[0]
    top_acct_net = remaining[remaining["SAP-Konto"] == top_acct]["Difference"].sum()
    if top_acct_count >= 5:
        lines.append(f"> Account `{top_acct}` appears in {top_acct_count} of {len(remaining)} remaining rows (net: {fmt(top_acct_net)}).\n")
    # Insight: top customer
    kund_abs = remaining.groupby("Kundennr")["Difference"].agg(["sum", lambda x: x.abs().sum()])
    kund_abs.columns = ["net", "gross"]
    top_kund = kund_abs["gross"].idxmax()
    top_kund_gross = kund_abs.loc[top_kund, "gross"]
    top_kund_net = kund_abs.loc[top_kund, "net"]
    total_gross = remaining["_abs"].sum()
    top_kund_pct = top_kund_gross / total_gross * 100 if total_gross > 0 else 0
    if top_kund_pct > 10:
        lines.append(f"> Customer `{top_kund}` is the largest contributor: {fmt_plain(top_kund_gross)} absolute ({top_kund_pct:.0f}% of category), net {fmt(top_kund_net)}.\n")
    lines.append("### Top 30 by absolute difference\n")
    top = remaining.sort_values("_abs", ascending=False).head(30)
    table_rows = []
    for _, r in top.iterrows():
        table_rows.append([
            r["SAP-Konto"], r["AccProd"], r["Counterparty"], r["Kundennr"],
            r["ResiCurr"], fmt_plain(r["GEBOS_Amount"]), fmt_plain(r["SAP_Amount"]), fmt(r["Difference"]),
        ])
    lines.append(md_table(
        ["SAP-Konto", "AccProd", "Counterparty", "Kundennr", "ResiCurr", "GEBOS Amount", "SAP Amount", "Difference"],
        table_rows,
    ))
    return "\n".join(lines)


def section_dimension(diffs, col_name, section_num, title, top_n=None):
    """Generic dimension breakdown."""
    by_dim = diffs.groupby(col_name).agg(
        Count=("Difference", "size"),
        Sum_Diff=("Difference", "sum"),
    ).sort_values("Sum_Diff", key=abs, ascending=False)
    if top_n:
        by_dim = by_dim.head(top_n)
    lines = [
        f"### {section_num} By {title}\n",
    ]
    table_rows = []
    for idx, r in by_dim.iterrows():
        table_rows.append([idx, int(r["Count"]), fmt(r["Sum_Diff"])])
    lines.append(md_table([title, "Count", "Sum Diff"], table_rows))
    # Add insight: highlight the top entry and concentration
    if len(by_dim) > 1:
        top_entry = by_dim.iloc[0]
        top_name = by_dim.index[0]
        total_abs = by_dim["Sum_Diff"].abs().sum()
        top_pct = abs(top_entry["Sum_Diff"]) / total_abs * 100 if total_abs > 0 else 0
        lines.append(f"\n> `{top_name}` accounts for {top_pct:.0f}% of the absolute difference across {title} ({int(top_entry['Count'])} rows, {fmt(top_entry['Sum_Diff'])}).")
    return "\n".join(lines)


def section_dimensions(diffs):
    """§7 All dimension breakdowns."""
    lines = [
        "## 7. Dimension Breakdowns\n",
        "For reference, the following tables show how the diff rows distribute across each dimension. "
        "These are descriptive only — they do not explain the cause of the differences.\n",
        section_dimension(diffs, "AccProd", "7.1", "AccProd"),
        "",
        section_dimension(diffs, "Counterparty", "7.2", "Counterparty"),
        "",
        section_dimension(diffs, "ResiCurr", "7.3", "ResiCurr"),
        "",
        section_dimension(diffs, "SAP-Konto", "7.4", "SAP-Konto", top_n=20),
        "",
        section_dimension(diffs, "Kundennr", "7.5", "Kundennr", top_n=20),
    ]

    # Partnerges — only if any non-empty
    non_empty = diffs[diffs["Partnerges"].astype(str).str.strip().ne("") & diffs["Partnerges"].notna()]
    if len(non_empty) > 0:
        lines.append("")
        lines.append(section_dimension(diffs, "Partnerges", "7.6", "Partnerges"))
    else:
        lines.append(f"\n### 7.6 By Partnerges\n")
        lines.append("No diff rows have a non-empty Partnerges. This dimension does not help explain the differences.")
    return "\n".join(lines)


def section_placeholders():
    """§8 & §9 — placeholders for analyst interpretation and next steps."""
    return "\n".join([
        "## 8. What Cannot Be Determined From Data Alone\n",
        "_This section should be filled in by the analyst or AI after reviewing the data above._\n",
        "## 9. Suggested Next Steps\n",
        "_This section should be filled in by the analyst or AI after reviewing the data above._\n",
    ])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def generate_report(report_type):
    """Generate a difference analysis report for the given type (ugb or ifrs)."""
    config = REPORT_CONFIGS[report_type]
    recon_file = config["recon_file"]
    report_file = config["report_file"]
    title = config["title"]

    if not recon_file.exists():
        print(f"SKIP: {recon_file.name} not found — run reconcile_{report_type}.py first.", flush=True)
        return

    print(f"\nReading {recon_file.name}...", flush=True)
    recon = load_recon(recon_file)
    diffs = get_diffs(recon)
    print(f"  Total rows: {len(recon)}, diff rows: {len(diffs)}", flush=True)

    # Analysis
    cancel_df = find_offsetting_customers(diffs)
    cancel_kundenrs = cancel_df.index.tolist()
    gebos_only, sap_only = find_unmatched(diffs)

    # Build report
    report_date = datetime.now().strftime("%B %Y")
    sections = []
    sections.append(f"# {title}\n")
    sections.append(f"**Date:** {report_date}  ")
    sections.append(f"**Source:** `{recon_file.name}`  ")
    sections.append(f"**Threshold:** Differences > {DIFF_THRESHOLD} EUR\n")
    sections.append("---\n")

    sections.append(section_overview(recon, diffs))
    sections.append("\n---\n")

    waterfall_text, remaining = section_waterfall(diffs, cancel_kundenrs, gebos_only, sap_only)
    sections.append(waterfall_text)
    sections.append("\n---\n")

    sections.append(section_offsetting_pairs(diffs, cancel_df))
    sections.append("\n---\n")

    sections.append(section_unmatched(
        "GEBOS-Only Rows — No SAP Match (Category B)", 4,
        f"These {len(gebos_only)} rows have a GEBOS balance but no corresponding key in SAP.",
        gebos_only,
    ))
    sections.append("\n---\n")

    sections.append(section_unmatched(
        "SAP-Only Rows — No GEBOS Match (Category C)", 5,
        f"These {len(sap_only)} rows have a SAP balance but no corresponding key in GEBOS.",
        sap_only,
    ))
    sections.append("\n---\n")

    sections.append(section_remaining(remaining))
    sections.append("\n---\n")

    sections.append(section_dimensions(diffs))
    sections.append("\n---\n")

    sections.append(section_placeholders())

    # Write
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_text = "\n".join(sections)
    report_file.write_text(report_text, encoding="utf-8")
    print(f"Report written to {report_file.name}", flush=True)
    print(f"  Sections 8 & 9 are placeholders for analyst/AI commentary.", flush=True)


def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "both"
    valid = list(REPORT_CONFIGS.keys()) + ["both"]
    if target not in valid:
        print(f"Usage: python src/generate_report.py [{' | '.join(valid)}]")
        sys.exit(1)

    types = list(REPORT_CONFIGS.keys()) if target == "both" else [target]
    for t in types:
        generate_report(t)


if __name__ == "__main__":
    main()
