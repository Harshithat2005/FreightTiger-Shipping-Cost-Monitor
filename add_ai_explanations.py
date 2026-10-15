
import os
import time
import pandas as pd
from google import genai

INPUT_FILE = "final_output.csv"
OUTPUT_FILE = "final_output_with_ai.csv"
LOG_FILE = "ai_usage_log.csv"
MODEL = "gemini-3.8-flash"

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    df = pd.read_csv(INPUT_FILE)
    client = genai.Client(api_key=api_key)

    # Add a separate column; do not modify the original flags or reasons.
    df["ai_explanation"] = ""

    logs = []
    candidates = df.index[df["flagged"] == "Yes"].tolist()

    print(f"Flagged anomalies to explain: {len(candidates)}")

    for count, idx in enumerate(candidates, start=1):
        row = df.loc[idx]

        prompt = f"""
You are a freight-cost analyst.

Explain this already-detected anomaly in 2-3 concise sentences.
Use only the facts below. Do not invent causes.
Do not change the anomaly flag.
Clearly distinguish evidence from uncertainty.

Route: {row['route']}
Week starting: {row['week_of']}
Cost per tonne-km: {row['cost_per_tonne_km']}
Comparison with own history: {row['vs_own_history']}
Comparison with similar routes: {row['vs_similar_routes']}
Matched note ID: {row['matched_note_id']}
Existing analysis: {row['reason']}

Return only the explanation.
"""

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )

            explanation = response.text or "No explanation returned."
            df.at[idx, "ai_explanation"] = explanation

            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0
            total_tokens = getattr(usage, "total_token_count", 0) or 0

            logs.append({
                "route": row["route"],
                "week_of": row["week_of"],
                "model": MODEL,
                "status": "success",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_inr": 0.0
            })

            print(f"[{count}/{len(candidates)}] Explained: {row['route']}")

        except Exception as exc:
            df.at[idx, "ai_explanation"] = (
                "AI explanation unavailable; use the existing analysis."
            )

            logs.append({
                "route": row["route"],
                "week_of": row["week_of"],
                "model": MODEL,
                "status": f"error: {str(exc)[:200]}",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_inr": 0.0
            })

            print(f"[{count}/{len(candidates)}] Gemini failed for {row['route']}")

        # Small pause between API requests.
        if count < len(candidates):
            time.sleep(1)

        # Save progress so completed explanations are not lost.
        df.to_csv(OUTPUT_FILE, index=False)
        pd.DataFrame(logs).to_csv(LOG_FILE, index=False)

    print("\nAI explanation step completed.")
    print(f"Enhanced output: {OUTPUT_FILE}")
    print(f"Usage log: {LOG_FILE}")
    print(f"Successful calls: {sum(x['status'] == 'success' for x in logs)}")
    print(f"Failed calls: {sum(x['status'] != 'success' for x in logs)}")
    print("Original final_output.csv remains unchanged.")

if __name__ == "__main__":
    main()

