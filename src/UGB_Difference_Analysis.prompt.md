---
applyTo: "**/GEBOS_SAP_Recon/**"
---
# UGB Reconciliation Difference Analysis

## When to use
Use this prompt after running `reconcile_ugb.py` to produce a structured difference analysis report.

## Workflow

### Step 1 — Generate the data-driven report
Run the report generator script from the GEBOS_SAP_Recon directory:
```
python src/generate_report.py
```
This produces `Output/UGB_Difference_Analysis.md` with sections 1–7 filled in (overview, waterfall, offsetting pairs, unmatched rows, remaining, dimension breakdowns) and sections 8–9 as placeholders.

### Step 2 — Fill in sections 8 and 9 with analyst interpretation
Read the generated report. Then fill in the two placeholder sections using the rules below.

#### Section 8: "What Cannot Be Determined From Data Alone"
- State explicitly what questions remain unanswered from the data.
- If you cannot tell whether two differences are related, say so.
- Do NOT invent causal explanations that are not directly supported by the numbers.

#### Section 9: "Suggested Next Steps"
- List only concrete, actionable steps ordered by expected impact (largest difference first).
- Each step must reference specific rows, accounts, or customers from the report.
- Do NOT suggest generic process improvements unless the user asks for them.

## Analysis Rules (CRITICAL)

### What you CAN state as confirmed
- Rows with **identical absolute differences** that cancel each other (net ≈ 0) for the same customer — these are confirmed offsetting pairs. The script detects these automatically (>90% cancellation).
- Rows where one side is exactly zero — these are confirmed unmatched (GEBOS-only or SAP-only).

### What you CANNOT state without further investigation
- WHY matched rows have different amounts. Do not guess.
- Whether unmatched rows are genuinely missing or caused by key formatting differences. State both possibilities.
- Whether two large differences that are CLOSE but not IDENTICAL in absolute value are related. Say "I cannot confirm" and state the gap.
- Root causes involving feeders, komponente, or transaction-level detail — unless the user provides that data.

### Tone
- Be direct and factual.
- When you don't know something, say "I cannot determine this from the data alone."
- Do not soften uncertainty with words like "likely", "probably", "suggests". Use "I cannot confirm" or "this requires investigation."
- Do not add creative analysis beyond what the numbers directly show.

## Output format
- Replace the placeholder text in sections 8 and 9 of the generated .MD file.
- Keep all other sections unchanged (they are auto-generated and correct).
- Do not add or remove other sections.
