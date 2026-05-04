---
applyTo: "**/GEBOS_SAP_Recon/**"
---
# Reconciliation Difference Analysis (UGB & IFRS)

## Objective
Read the auto-generated difference analysis reports in `Output/` and fill in all **AI Analysis** placeholders in sections 3–6, plus sections 8 and 9. The reports already contain auto-embedded **Source-Data Findings** subsections (generated from the raw Input files by `generate_report.py`). Use these findings as the primary evidence for your analysis. Everything outside the **AI Analysis** placeholders must not be modified.

## Steps

### Step 1 — Read the generated report(s)
Read `Output/UGB_Difference_Analysis.md` and/or `Output/IFRS_Difference_Analysis.md`. Process each report independently — do not cross-reference between UGB and IFRS.

Each of sections 3–6 includes a **Source-Data Findings** subsection with blockquoted findings. These contain:
- **Customer-level total comparisons** — whether the total per Kundennr matches across systems.
- **Key mismatch results** — whether GEBOS-only/SAP-only keys exist in the other system under different AccProd or accounts.
- **Raw-total checks** — whether pre-aggregation sums match (indicating sub-dimension allocation) or differ (indicating genuine amount discrepancy).
- **Cross-customer offset verification** — whether combined totals of suspected cross-customer offsets match.

### Step 2 — Fill in "AI Analysis" placeholders in sections 3–6
Each of sections 3 (Offsetting Pairs), 4 (GEBOS-only), 5 (SAP-only), and 6 (Remaining Unexplained) contains a placeholder line:
`**AI Analysis:** _To be filled in by the AI..._`

Replace each placeholder with a concise interpretation based on the **Source-Data Findings** already embedded in the same section. Follow the analysis rules below. Keep each AI Analysis to 2–7 bullet points covering:
- What the source-data findings confirm (prefix with **ROOT CAUSE IDENTIFIED** or **Source-data finding**).
- What remains uncertain and why.
- Which specific rows or customers warrant investigation.

### Step 3 — Fill in section 8: "What Cannot Be Determined From Data Alone"
- Mark previously open questions as ~~resolved~~ → **RESOLVED** when source-data findings provide the answer.
- State explicitly what questions remain unanswered even after source-data analysis.
- If you cannot tell whether two differences are related, say so.
- Do NOT invent causal explanations that are not directly supported by the numbers.

### Step 4 — Fill in section 9: "Suggested Next Steps"
- List only concrete, actionable steps ordered by expected impact (largest difference first).
- Each step must reference specific rows, accounts, or customers from the report.
- Distinguish between mapping-alignment fixes (where source data confirmed the root cause) and genuine amount discrepancies (where transaction-level investigation is still needed).
- Do NOT suggest generic process improvements unless the user asks for them.

## Analysis Rules (CRITICAL)

### What you CAN state as confirmed
- Rows with **identical absolute differences** that cancel each other (net ≈ 0) for the same customer — these are confirmed offsetting pairs. The script detects these automatically (>90% cancellation).
- Rows where one side is exactly zero — these are confirmed unmatched (GEBOS-only or SAP-only).
- **AccProd or account mapping mismatches** — when the targeted analysis finds the same Kundennr+account in the other system under a different AccProd, state this as **ROOT CAUSE IDENTIFIED** (e.g., "GEBOS uses `RISKP`, SAP uses `RRAHM`").
- **Zero-balance GEBOS entries** — when the targeted analysis finds a SAP-only key exists in GEBOS with amt=0.00, state "key exists in GEBOS with zero balance, not genuinely missing."
- **Dimension-allocation differences** — when per-account raw totals match (diff ≈ 0) but the reconciliation shows a difference, state "per-account totals match; differences are sub-dimension allocation, not genuine amount discrepancies."
- **Genuine amount differences** — when per-account raw totals differ and source row counts are different, state "confirmed genuine amount difference" with the row counts and sums.

### What you CANNOT state without further investigation
- WHY matched rows have different amounts, even if the difference is confirmed genuine. Do not guess.
- Whether unmatched rows are genuinely missing or caused by key formatting differences — UNLESS the targeted analysis resolved this (then state the finding).
- Whether two large differences that are CLOSE but not IDENTICAL in absolute value are related. Say "I cannot confirm" and state the gap.
- Root causes involving feeders, komponente, or transaction-level detail — the targeted analysis does not drill into these.

### Tone
- Be direct and factual.
- When you don't know something, say "I cannot determine this from the data alone."
- Do not soften uncertainty with words like "likely", "probably", "suggests". Use "I cannot confirm" or "this requires investigation."
- Do not add creative analysis beyond what the numbers directly show.

## Output format
- Replace each `**AI Analysis:** _To be filled in...` placeholder in sections 3–6 with source-data-backed analysis.
- Replace the placeholder text in sections 8 and 9 of each generated .MD file.
- Prefix confirmed root causes with **ROOT CAUSE IDENTIFIED** or **Source-data finding**.
- Mark resolved questions in section 8 with ~~strikethrough~~ → **RESOLVED**.
- Keep all other content unchanged (tables, insights, and section headers are auto-generated and correct).
- Do not add or remove sections.
- Process each report (UGB / IFRS) independently — do not cross-reference between them.
