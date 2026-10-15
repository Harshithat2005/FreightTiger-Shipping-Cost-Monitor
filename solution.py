
import re
import pandas as pd

ANOMALY_THRESHOLD_PCT = 20.0
HISTORY_WEEKS = 8

# ==========================================
# STEP 1: LOAD AND VALIDATE INPUTS
# ==========================================

shipments = pd.read_csv("shipment_records.csv")
notes = pd.read_csv("context_notes.csv")

required_columns = [
    "origin", "destination", "route_type", "quantity_tonnes",
    "distance_km", "freight_cost_inr", "shipment_date", "shipment_id"
]

missing = [c for c in required_columns if c not in shipments.columns]
if missing:
    raise ValueError(f"Missing shipment columns: {missing}")

note_columns = ["note_id", "date", "applies_to", "note"]
missing_notes = [c for c in note_columns if c not in notes.columns]
if missing_notes:
    raise ValueError(f"Missing context-note columns: {missing_notes}")

shipments["shipment_date"] = pd.to_datetime(
    shipments["shipment_date"], errors="raise"
)
notes["date"] = pd.to_datetime(notes["date"], errors="raise")

if shipments[required_columns].isna().any().any():
    raise ValueError("Required shipment fields contain missing values.")

if notes[note_columns].isna().any().any():
    raise ValueError("Required context-note fields contain missing values.")

for col in ["quantity_tonnes", "distance_km", "freight_cost_inr"]:
    shipments[col] = pd.to_numeric(shipments[col], errors="raise")

if (
    (shipments["quantity_tonnes"] <= 0).any()
    or (shipments["distance_km"] <= 0).any()
    or (shipments["freight_cost_inr"] < 0).any()
):
    raise ValueError("Invalid quantity, distance, or freight cost.")

# ==========================================
# STEP 2: WEEKLY ROUTE COSTS
# ==========================================

# Monday is the start of each week.
shipments["week_of"] = (
    shipments["shipment_date"]
    - pd.to_timedelta(shipments["shipment_date"].dt.weekday, unit="D")
).dt.normalize()

shipments["route"] = (
    shipments["origin"].astype(str).str.strip()
    + "-"
    + shipments["destination"].astype(str).str.strip()
)

shipments["tonne_km"] = (
    shipments["quantity_tonnes"] * shipments["distance_km"]
)

weekly = (
    shipments.groupby(
        ["route", "route_type", "week_of"], as_index=False
    )
    .agg(
        total_cost=("freight_cost_inr", "sum"),
        total_tonne_km=("tonne_km", "sum"),
        shipment_count=("shipment_id", "count"),
    )
)

weekly["cost_per_tonne_km"] = (
    weekly["total_cost"] / weekly["total_tonne_km"]
)

weekly = weekly.sort_values(
    ["route", "week_of"]
).reset_index(drop=True)

# ==========================================
# STEP 3: TRAILING 8-CALENDAR-WEEK BASELINE
# ==========================================

weekly["own_history_avg"] = float("nan")

for _, indices in weekly.groupby("route").groups.items():
    indices = list(indices)

    for idx in indices:
        current_week = weekly.at[idx, "week_of"]
        window_start = current_week - pd.Timedelta(weeks=HISTORY_WEEKS)

        # Strictly prior weeks within the previous 8 calendar weeks.
        prior = weekly.loc[
            (weekly["route"] == weekly.at[idx, "route"])
            & (weekly["week_of"] < current_week)
            & (weekly["week_of"] >= window_start),
            "cost_per_tonne_km",
        ]

        if not prior.empty:
            weekly.at[idx, "own_history_avg"] = prior.mean()

weekly["vs_own_history_pct"] = (
    (weekly["cost_per_tonne_km"] / weekly["own_history_avg"] - 1) * 100
)

# ==========================================
# STEP 4: SIMILAR-ROUTE BASELINE
# ==========================================

peer_stats = (
    weekly.groupby(["week_of", "route_type"])["cost_per_tonne_km"]
    .agg(peer_total="sum", peer_count="count")
    .reset_index()
)

weekly = weekly.merge(
    peer_stats, on=["week_of", "route_type"], how="left"
)

weekly["peer_avg"] = (
    (weekly["peer_total"] - weekly["cost_per_tonne_km"])
    / (weekly["peer_count"] - 1)
)

weekly.loc[weekly["peer_count"] <= 1, "peer_avg"] = float("nan")

weekly["vs_similar_routes_pct"] = (
    (weekly["cost_per_tonne_km"] / weekly["peer_avg"] - 1) * 100
)

# ==========================================
# STEP 5: ANOMALY DETECTION
# ==========================================

weekly["anomaly_candidate"] = (
    (weekly["vs_own_history_pct"] >= ANOMALY_THRESHOLD_PCT)
    | (weekly["vs_similar_routes_pct"] >= ANOMALY_THRESHOLD_PCT)
)

# ==========================================
# STEP 6: CONTEXT NOTE EVIDENCE
# ==========================================

def note_window(note):
    """Return a conservative date window from the note text."""
    start = note["date"]
    text = str(note["note"]).lower()

    # Explicit event range, e.g. "from Feb 24 to Mar 8".
    match = re.search(
        r"from\s+([a-z]+\s+\d{1,2})\s+to\s+([a-z]+\s+\d{1,2})",
        text,
    )
    if match:
        year = start.year
        event_start = pd.to_datetime(
            f"{match.group(1)} {year}", errors="coerce"
        )
        event_end = pd.to_datetime(
            f"{match.group(2)} {year}", errors="coerce"
        )

        if pd.isna(event_start) or pd.isna(event_end):
            return start, start

        if event_end < event_start:
            event_end = event_end.replace(year=year + 1)

        return event_start, event_end
    # A week-long effect, where the wording explicitly indicates it.
    if any(term in text for term in [
        "festival week", "about a week", "starting this week"
    ]):
        return start, start + pd.Timedelta(days=6)

    # Quarter wording is broad; use a conservative 90-day window.
    if "this quarter" in text:
        return start, start + pd.Timedelta(days=89)

    # No stated duration: use only the note date.
    return start, start


def note_is_positive_evidence(note):
    """Reject notes that contradict or fail to explain a cost rise."""
    text = str(note["note"]).lower()

    negative_phrases = [
        "not part of this dataset",
        "costs were not significantly affected",
        "no major disruptions",
        "no significant disruptions",
        "remained normal",
        "improved road conditions",
        "returned to normal",
        "without a rate change",
        "costs were absorbed",
        "stable demand",
    ]
    if any(phrase in text for phrase in negative_phrases):
        return False

    positive_phrases = [
        "higher trip costs",
        "surcharge",
        "pushing up transportation costs",
        "increased transportation costs",
        "increased freight costs",
        "higher freight costs",
    ]
    if not any(phrase in text for phrase in positive_phrases):
        return False

    # A 5–7% diesel effect alone cannot explain a >=20% anomaly.
    percentages = [
        float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    ]
    if percentages and max(percentages) < ANOMALY_THRESHOLD_PCT:
        return False

    return True


def match_context_note(route, week_of):
    """Return the first note with matching route, time and evidence."""
    week_start = pd.Timestamp(week_of)
    week_end = week_start + pd.Timedelta(days=6)

    for _, note in notes.iterrows():
        applies = str(note["applies_to"]).strip().casefold()
        if applies != "all routes" and applies != route.casefold():
            continue

        start, end = note_window(note)
        if start > week_end or end < week_start:
            continue

        if note_is_positive_evidence(note):
            return str(note["note_id"]), str(note["note"])

    return "", ""


# ==========================================
# STEP 7: BUILD FINAL OUTPUT
# ==========================================

def format_pct(value):
    return "N/A" if pd.isna(value) else f"{value:+.1f}%"


def build_reason(row, note_id, note_text):
    if not row["anomaly_candidate"]:
        return (
            "No anomaly: neither available baseline shows an increase "
            "of 20% or more."
        )

    if note_id:
        return f"Anomaly detected but supported by {note_id}: {note_text}"

    comparisons = []
    if pd.notna(row["vs_own_history_pct"]):
        comparisons.append(
            f"{format_pct(row['vs_own_history_pct'])} versus own history"
        )
    if pd.notna(row["vs_similar_routes_pct"]):
        comparisons.append(
            f"{format_pct(row['vs_similar_routes_pct'])} versus similar routes"
        )

    evidence = "; ".join(comparisons) or "insufficient baseline data"
    return (
        f"Unexplained anomaly: {evidence}. "
        "No applicable note sufficiently explains the increase."
    )


output_rows = []

for _, row in weekly.iterrows():
    note_id, note_text = "", ""

    if row["anomaly_candidate"]:
        note_id, note_text = match_context_note(
            row["route"], row["week_of"]
        )

    if row["anomaly_candidate"] and note_id:
        flagged = "No (justified)"
    elif row["anomaly_candidate"]:
        flagged = "Yes"
    else:
        flagged = "No"

    output_rows.append({
        "route": row["route"],
        "week_of": row["week_of"].strftime("%Y-%m-%d"),
        "cost_per_tonne_km": round(row["cost_per_tonne_km"], 2),
        "vs_own_history": (
            f"{format_pct(row['vs_own_history_pct'])} vs own history"
        ),
        "vs_similar_routes": (
            f"{format_pct(row['vs_similar_routes_pct'])} "
            "vs similar routes"
        ),
        "flagged": flagged,
        "matched_note_id": note_id,
        "reason": build_reason(row, note_id, note_text),
    })

output_columns = [
    "route", "week_of", "cost_per_tonne_km",
    "vs_own_history", "vs_similar_routes",
    "flagged", "matched_note_id", "reason",
]

final_output = pd.DataFrame(output_rows, columns=output_columns)
final_output.to_csv("final_output.csv", index=False)

# Save the intermediate analysis only once.
weekly.to_csv("weekly_costs.csv", index=False)

print("Shipment records:", len(shipments))
print("Route-week records:", len(weekly))
print("Anomaly candidates:", int(weekly["anomaly_candidate"].sum()))
print("Unexplained anomalies:", int((final_output["flagged"] == "Yes").sum()))
print(
    "Justified anomalies:",
    int((final_output["flagged"] == "No (justified)").sum()),
)
print("Not flagged:", int((final_output["flagged"] == "No").sum()))
print("Created weekly_costs.csv and final_output.csv")

# Validate the output schema.
assert list(final_output.columns) == output_columns
assert len(final_output) == len(weekly)
assert final_output["flagged"].notna().all()

print("Output validation passed.")
