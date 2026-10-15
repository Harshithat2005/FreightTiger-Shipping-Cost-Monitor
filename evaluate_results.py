
import pandas as pd

output = pd.read_csv("final_output.csv")
notes = pd.read_csv("context_notes.csv")

checks = [
    {
        "description": "Ahmedabad-Mumbai festival week",
        "route": "Ahmedabad-Mumbai",
        "week": "2025-01-20",
        "expected_flag": "No (justified)",
        "expected_note": "N002",
    },
    {
        "description": "Chennai-Bangalore flooding",
        "route": "Chennai-Bangalore",
        "week": "2025-02-24",
        "expected_flag": "No (justified)",
        "expected_note": "N001",
    },
    {
        "description": "Chennai-Bangalore flooding continues",
        "route": "Chennai-Bangalore",
        "week": "2025-03-03",
        "expected_flag": "No (justified)",
        "expected_note": "N001",
    },
    {
        "description": "After flooding ended",
        "route": "Chennai-Bangalore",
        "week": "2025-03-10",
        "expected_flag": "Yes",
        "expected_note": "",
    },
    {
        "description": "Route returned to normal",
        "route": "Chennai-Bangalore",
        "week": "2025-03-17",
        "expected_flag": "Yes",
        "expected_note": "",
    },
]

print("\nEVALUATION RESULTS\n")

passed = 0

for check in checks:
    row = output[
        (output["route"] == check["route"])
        & (output["week_of"] == check["week"])
    ]

    if len(row) != 1:
        print(f"FAIL: {check['description']} — row missing or duplicated")
        continue

    row = row.iloc[0]

    ok = (
        row["flagged"] == check["expected_flag"]
        and (
            "" if pd.isna(row["matched_note_id"])
            else str(row["matched_note_id"])
        ) == check["expected_note"]
    )

    print(f"{'PASS' if ok else 'FAIL'}: {check['description']}")
    passed += int(ok)

print(f"\nPassed: {passed}/{len(checks)}")
