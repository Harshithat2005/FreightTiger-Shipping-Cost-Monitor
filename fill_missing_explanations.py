
import pandas as pd

file = "final_output_with_ai.csv"
df = pd.read_csv(file)

missing = (
    df["flagged"].eq("Yes")
    & (
        df["ai_explanation"].isna()
        | df["ai_explanation"].astype(str).str.strip().eq("")
        | df["ai_explanation"].astype(str).str.startswith(
            "AI explanation unavailable"
        )
    )
)

df.loc[missing, "ai_explanation"] = (
    "Rule-based fallback: " + df.loc[missing, "reason"].astype(str)
)

df.to_csv(file, index=False)

print("Fallback explanations added:", int(missing.sum()))
print("Saved:", file)
