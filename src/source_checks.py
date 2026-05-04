"""
Source-data checks for reconciliation differences.
Loads raw GEBOS + SAP files and returns structured findings
that generate_report.py embeds directly into the .md report.

No komponente/feeder drill-down — works at the 6-dimension key level.
"""

import pandas as pd
from pathlib import Path

INPUT_DIR = Path(__file__).resolve().parent.parent / "Input"


def _cl(v):
    if pd.isna(v) or v is None:
        return ""
    s = str(v).strip()
    return "" if s == "#" else s


def _fi(v):
    if pd.isna(v):
        return ""
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return str(v).strip()


def _find_file(keywords):
    matches = [
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and all(k.lower() in f.name.lower() for k in keywords)
    ]
    return matches[0] if len(matches) == 1 else None


DIMS = ["SAP-Konto", "AccProd", "Counterparty", "Kundennr", "ResiCurr", "Partnerges"]


def load_source(mode):
    """Load and group GEBOS + SAP source data. Returns (gebos_raw, sap_raw, g_grp, s_grp, amt_col_g) or None."""
    g_file = _find_file(["GEBOS", mode.upper()])
    s_file = _find_file(["SAP", mode.upper()])
    if g_file is None or s_file is None:
        return None

    gf = pd.read_excel(g_file, sheet_name="GEB_gesamt", header=0, engine="openpyxl")
    sf = pd.read_excel(s_file, sheet_name="Balances", header=8, engine="openpyxl")

    # GEBOS prep
    gf = gf[gf["SAP-Konto"].notna()].copy()
    gf = gf[gf["SAP-Konto"].astype(str).str.strip() != ""].copy()
    gf = gf[~gf["SAP-Konto"].astype(str).str.strip().str.startswith("6")].copy()
    gf = gf[gf["komponente"].notna() & (gf["komponente"] != "")].copy()
    for c in DIMS:
        gf[c] = gf[c].apply(_cl)
    gf["Kundennr"] = gf["Kundennr"].apply(_fi)
    amt_col_g = "GEBOS_saldo_eur_ugb" if mode == "ugb" else "GEBOS_saldo_eur_ifrs"
    gf[amt_col_g] = pd.to_numeric(gf[amt_col_g], errors="coerce").fillna(0)

    # SAP prep
    sf = sf[sf["Ledger"] != "Result"].copy()
    sf["Account Number"] = sf["Account Number"].apply(_fi)
    sf = sf[~sf["Account Number"].str.startswith("6")].copy()
    sap_dims = ["Account Number", "Account.Product", "Counterparty",
                "KMS number", "Residence/Curr", "Trading Partner No."]
    for c in sap_dims:
        sf[c] = sf[c].apply(_cl)
    sf["Ending Balance LC"] = pd.to_numeric(sf["Ending Balance LC"], errors="coerce").fillna(0)
    sf.rename(columns={
        "Account Number": "SAP-Konto", "Account.Product": "AccProd",
        "KMS number": "Kundennr", "Residence/Curr": "ResiCurr",
        "Trading Partner No.": "Partnerges",
    }, inplace=True)

    # Group
    g_grp = gf.groupby(DIMS, as_index=False)[amt_col_g].sum()
    g_grp.rename(columns={amt_col_g: "Amt"}, inplace=True)
    g_grp["Amt"] = g_grp["Amt"].round(2)

    s_grp = sf.groupby(DIMS, as_index=False)["Ending Balance LC"].sum()
    s_grp.rename(columns={"Ending Balance LC": "Amt"}, inplace=True)
    s_grp["Amt"] = s_grp["Amt"].round(2)

    return gf, sf, g_grp, s_grp, amt_col_g


# ── Check 1: Key mismatch for a single unmatched row ─────────────────────

def check_key_mismatch(row, source_side, g_grp, s_grp):
    """
    For a GEBOS-only or SAP-only row, check if the key exists in the other system
    under a different AccProd or account.

    Returns a string finding or None.
    """
    acct = str(row["SAP-Konto"])
    aprod = str(row["AccProd"])
    kn = str(row["Kundennr"])

    if source_side == "gebos_only":
        other = s_grp
        self_label, other_label = "GEBOS", "SAP"
    else:
        other = g_grp
        self_label, other_label = "SAP", "GEBOS"

    # Exact match on acct+kn — mismatch on another dim?
    exact = other[(other["Kundennr"] == kn) & (other["SAP-Konto"] == acct) & (other["AccProd"] == aprod)]
    if len(exact) > 0:
        amt = exact["Amt"].values[0]
        return f"Key exists in {other_label} (amt={amt:.2f}) — dimension mismatch on Counterparty/ResiCurr/Partnerges."

    # Same acct+kn, different AccProd?
    acct_kn = other[(other["SAP-Konto"] == acct) & (other["Kundennr"] == kn)]
    if len(acct_kn) > 0:
        prods = acct_kn["AccProd"].unique().tolist()
        return f"AccProd mismatch: {self_label} uses `{aprod}`, {other_label} has `{'`, `'.join(prods)}` for same account+customer."

    # Same kn, different accounts?
    kn_any = other[other["Kundennr"] == kn]
    if len(kn_any) > 0:
        n = len(kn_any["SAP-Konto"].unique())
        return f"Kundennr exists in {other_label} under {n} other account(s), but not under `{acct}`/`{aprod}`."

    return f"Kundennr `{kn}` does not exist in {other_label} at all."


# ── Check 2: Per-account raw total comparison ─────────────────────────────

def check_raw_totals(row, gebos_raw, sap_raw, amt_col_g):
    """
    For a matched row with a difference, compare pre-aggregation sums.
    Returns dict with g_rows, s_rows, g_sum, s_sum, raw_diff, finding.
    """
    acct = str(row["SAP-Konto"])
    kn = str(row["Kundennr"])

    gr = gebos_raw[(gebos_raw["Kundennr"] == kn) & (gebos_raw["SAP-Konto"] == acct)]
    sr = sap_raw[(sap_raw["Kundennr"] == kn) & (sap_raw["SAP-Konto"] == acct)]
    g_sum = gr[amt_col_g].sum().round(2)
    s_sum = sr["Ending Balance LC"].sum().round(2)
    raw_diff = round(g_sum - s_sum, 2)

    result = {
        "g_rows": len(gr), "s_rows": len(sr),
        "g_sum": g_sum, "s_sum": s_sum, "raw_diff": raw_diff,
    }

    if abs(raw_diff) <= 0.01:
        result["finding"] = (
            f"Per-account raw totals match (GEBOS {len(gr)} rows = {g_sum:,.2f}, "
            f"SAP {len(sr)} rows = {s_sum:,.2f}). "
            f"Difference is sub-dimension allocation, not a genuine amount discrepancy."
        )
    else:
        result["finding"] = (
            f"Genuine amount difference at source level: "
            f"GEBOS {len(gr)} rows sum to {g_sum:,.2f}, SAP {len(sr)} rows sum to {s_sum:,.2f} "
            f"(gap: {raw_diff:+,.2f})."
        )
    return result


# ── Check 3: Customer-level total ─────────────────────────────────────────

def check_customer_total(kn, g_grp, s_grp):
    """Compare total GEBOS vs SAP for a single Kundennr across all keys."""
    kn = str(kn)
    gt = g_grp[g_grp["Kundennr"] == kn]["Amt"].sum().round(2)
    st = s_grp[s_grp["Kundennr"] == kn]["Amt"].sum().round(2)
    d = round(gt - st, 2)
    return {"gebos_total": gt, "sap_total": st, "diff": d, "matches": abs(d) <= 0.01}


# ── Check 4: Cross-customer offset ───────────────────────────────────────

def check_cross_customer(kn_a, kn_b, g_grp, s_grp):
    """Check if combined totals of two customers match across systems."""
    ta = check_customer_total(kn_a, g_grp, s_grp)
    tb = check_customer_total(kn_b, g_grp, s_grp)
    combined_g = round(ta["gebos_total"] + tb["gebos_total"], 2)
    combined_s = round(ta["sap_total"] + tb["sap_total"], 2)
    combined_diff = round(combined_g - combined_s, 2)
    return {
        "kn_a": ta, "kn_b": tb,
        "combined_g": combined_g, "combined_s": combined_s,
        "combined_diff": combined_diff,
        "matches": abs(combined_diff) <= 0.01,
    }
