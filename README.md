# FreightTiger Case Study — Freight Cost Anomaly Detection

## 1. Project Overview

This project analyses shipment records to identify potentially unusual freight costs across routes and weeks. It calculates weekly freight cost per tonne-kilometre and compares each route's cost against its historical performance and similar routes.

The system also evaluates available context notes to determine whether a potential cost increase has supporting evidence. An optional Google Gemini API integration generates human-readable explanations for flagged anomalies, while keeping the core cost calculations and anomaly flags independent of the AI layer.

## 2. Technologies Used

- **Programming Language:** Python 3.12
- **Data Processing:** Pandas
- **Input and Output:** CSV files
- **AI Integration:** Google Gemini API using `google-genai`
- **Context Analysis:** Rule-based context-note matching
- **Testing:** Python evaluation script and repeated-run reproducibility checks

## 3. Input Files

- `shipment_records.csv` — shipment dates, routes, quantities, distances, freight costs and route types.
- `context_notes.csv` — contextual information about route disruptions, market conditions and other factors that may affect freight costs.
- `sample_output_format_v2.csv` — reference for the expected output schema.

## 4. Processing Pipeline

### Step 1: Data Validation

The program validates the required input columns, dates, missing values and numeric shipment fields before processing the data.

### Step 2: Weekly Cost Calculation

Shipments are grouped by route, route type and week. Each week runs from Monday to Sunday, and `week_of` records the Monday date.

The cost per tonne-kilometre is calculated as:

**Cost per tonne-km = Total freight cost / Total tonne-kilometres**

Where:

**Total tonne-kilometres = Quantity in tonnes × Distance in kilometres**, summed across the shipments in the group.

### Step 3: Historical Cost Comparison

Each route's weekly cost is compared with its historical baseline, calculated using the average cost from the preceding eight calendar weeks.

Only data from strictly earlier weeks is used, preventing future observations from influencing the historical baseline. If fewer than eight prior weeks are available, the available prior weeks are used. If no suitable historical observations exist, the baseline is unavailable.

### Step 4: Similar-Route Comparison

The weekly cost is compared with the average cost of other routes belonging to the same route type during the same week. The route being evaluated is excluded from its own peer group.

This comparison helps identify increases that are unusual relative to comparable routes.

### Step 5: Anomaly Detection

A route-week becomes an anomaly candidate when its cost is at least 20% above either available baseline: its historical route baseline or its same-week peer baseline.

The 20% threshold is a project-selected heuristic, not a threshold specified by the case study. It should be calibrated and validated against business requirements and labelled historical data.

### Step 6: Context-Note Matching

For anomaly candidates, the system checks whether available context notes apply to the route and relevant time period and whether their wording supports a possible explanation for the increase.

The output uses three flag values:

- **`Yes`** — a potential anomaly without sufficient supporting context.
- **`No (justified)`** — an anomaly candidate with a matching context note that supports a possible explanation.
- **`No`** — the route-week does not meet the anomaly-candidate threshold.

The context-note matcher uses deterministic text rules, including route, date and wording checks. It is not a full semantic retrieval system and may miss relevant context or misinterpret ambiguous notes.

### Step 7: AI-Generated Explanations

The optional script `add_ai_explanations.py` sends flagged rows to Google Gemini to generate concise, human-readable explanations based on the existing metrics, rule-based reason and available context.

The AI layer does not recalculate costs or modify the original anomaly flags and reasons. If an API request fails, `fill_missing_explanations.py` provides a rule-based fallback using the existing reason.

AI-generated explanations are supplementary and should not be treated as independent proof of an anomaly's cause.

## 5. Output Files

- **`final_output.csv`** — the primary output containing exactly eight columns:

  `route, week_of, cost_per_tonne_km, vs_own_history, vs_similar_routes, flagged, matched_note_id, reason`

- **`weekly_costs.csv`** — intermediate weekly cost calculations and baseline information.
- **`final_output_with_ai.csv`** — the eight original output fields plus an `ai_explanation` column.
- **`ai_usage_log.csv`** — recorded AI request statuses and token-usage information.
- **`evaluate_results.py`** — a small evaluation harness for five selected route-week scenarios.
- **`reproducibility/`** — directory containing three saved output snapshots.
- **`README.md`** — project documentation and execution instructions.

## 6. Setup and Execution

### Prerequisites

- Python 3.12
- Internet access and a valid Gemini API key for AI-generated explanations
- The input CSV files in the project directory

### Install Dependencies

Run the following command in PowerShell:

```powershell
python -m pip install pandas google-genai
```

### Configure the Gemini API Key

Set the key as an environment variable:

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

Replace the placeholder with your own key. Keep the key private and never commit it to source control or include it in the submission.

### Run the Deterministic Pipeline

```powershell
python solution.py
```

This processes the shipment records, calculates weekly costs and baselines, applies anomaly detection and context-note matching, and generates the primary output files.

### Generate AI Explanations

```powershell
python add_ai_explanations.py
```

### Fill Missing Explanations

```powershell
python fill_missing_explanations.py
```

### Run the Evaluation Harness

```powershell
python evaluate_results.py
```

The deterministic pipeline and evaluation harness do not require Gemini API calls. The AI-explanation script requires a valid API key and available API quota; the fallback script can run without making API calls.

## 7. Validation and Evaluation

The deterministic pipeline completed successfully and reported the following results:

- **Input shipment records:** 2,940
- **Aggregated route-week records:** 728
- **Anomaly candidates:** 20
- **Unexplained anomalies flagged as `Yes`:** 17
- **Anomaly candidates classified as `No (justified)`:** 3
- **Records classified as `No`:** 708

The output validation confirmed that `final_output.csv` contains 728 records and exactly eight required columns. The AI-enhanced output contains nine columns, and its anomaly flags match those in the original output.

After fallback processing, every flagged row in the AI-enhanced output has a non-empty explanation.

### Selected Evaluation Cases

The evaluation harness was executed against five selected route-week scenarios:

- Ahmedabad–Mumbai festival week
- Chennai–Bangalore flooding period
- Continued flooding period
- Week after the flooding period ended
- Subsequent route-normalisation period

**Evaluation result: 5/5 selected cases passed.**

These tests verify the expected behaviour for the selected scenarios. They do not establish overall precision, recall or accuracy across the entire dataset because the evaluation set is small and manually selected.

## 8. Reproducibility

The deterministic pipeline was executed three times using the same input CSV files. The SHA256 hashes of `run1.csv`, `run2.csv` and `run3.csv` were identical.

This confirms byte-for-byte reproducibility of the saved output snapshots for those runs. The snapshots are stored in the `reproducibility/` directory.

The reproducibility claim applies to the deterministic pipeline and its saved CSV outputs. Gemini-generated explanations are evaluated separately because API availability, quota behaviour and generated wording may vary.

## 9. API Usage and Cost Report

During the recorded AI-explanation run, 17 Gemini API requests were attempted.

### Request Summary

- **Total requests:** 17
- **Successful requests:** 11
- **Failed requests:** 6
  - HTTP 429 — quota exceeded: 4
  - HTTP 503 — service unavailable: 2

### Token Usage

For the 11 successful requests, the local log records:

- **Input tokens:** 1,789
- **Output tokens:** 956
- **Combined input and output:** 2,745 tokens

**Token-log limitation:** The `total_tokens` column in `ai_usage_log.csv` sums to 9,826 across successful requests. This does not match the 2,745 tokens obtained by adding the recorded input and output token counts. The discrepancy remains unresolved, so the logged total-token figure is not treated as verified.

The six failed requests have zero token counts recorded in the current log. These values do not establish that the failed requests incurred no usage or cost.

### Cost Estimate

The script records an estimated cost of ₹0 based on an assumption of eligible free-tier usage. This is not independently verified billing information. Actual cost depends on the applicable model pricing, account plan, free-tier eligibility and billable usage.

The detailed request statuses and recorded token counts are available in `ai_usage_log.csv`. The cost estimate should be reconciled with the applicable pricing and provider usage information before being treated as an actual cost.

## 10. Limitations and Future Improvements

- **Threshold calibration:** The 20% anomaly threshold is a heuristic and has not been calibrated against a larger labelled dataset.
- **Context understanding:** The deterministic note matcher may miss relevant notes or misinterpret ambiguous wording.
- **Baseline availability:** Historical or peer comparisons may be unavailable for some route-weeks.
- **Evaluation coverage:** Five manually selected test cases are insufficient to estimate overall detection performance.
- **API reliability:** Gemini requests can fail due to quota limits or temporary service unavailability.
- **Explanation quality:** AI-generated explanations require review and should remain grounded in available metrics and context notes.
- **Usage accounting:** Token totals and cost estimates need reconciliation with provider-reported usage and applicable pricing.

Potential future improvements include expanding the labelled evaluation dataset, implementing more robust context retrieval, measuring precision and recall, calibrating the anomaly threshold, and improving API usage and cost accounting.

## 11. Conclusion

This project implements a freight-cost anomaly detection pipeline that combines weekly route-level cost calculations, historical and peer comparisons, context-note matching, and optional AI-generated explanations.

The deterministic pipeline generates the required eight-column output, and the selected evaluation cases passed all five checks. Repeated-run testing also confirmed identical saved output snapshots. The AI layer adds explanatory text and rule-based fallbacks without changing the original anomaly flags.

The solution demonstrates a reproducible approach to identifying potentially unusual freight costs. Larger-scale evaluation and further validation of the threshold, context matching and API usage accounting are needed before production deployment.