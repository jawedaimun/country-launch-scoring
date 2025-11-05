
import json
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Country Launch Scoring", layout="wide")

with open("thresholds.json") as f:
    RUBRIC = json.load(f)["categories"]
    
DEFAULT_SELECT = ["Very weak","Weak","Moderate","Strong","Excellent"]

@st.cache_data
def load_thresholds():
    with open("thresholds.json", "r") as f:
        return json.load(f)

def score_numeric(value, breaks, scores, direction):
    if value is None:
        return 3, "N/A → neutral 3"
    if direction == "higher_better":
        # Iterate from highest break downward
        for b, s in zip(reversed(breaks), reversed(scores)):
            if value >= b:
                return s, f"{value} ≥ {b} → {s}"
        return scores[0], f"{value} < {breaks[0]} → {scores[0]}"
    else:
        for b, s in zip(reversed(breaks), reversed(scores)):
            if value <= b:
                return s, f"{value} ≤ {b} → {s}"
        return scores[0], f"{value} > {breaks[0]} → {scores[0]}"

def score_select(val, custom_options, reverse=False):
    options = custom_options or DEFAULT_SELECT
    try:
        idx = options.index(val)
    except ValueError:
        idx = 2  # Moderate
    score = (5 - idx) if reverse else (idx + 1)
    return score, f"{val} → {score}"

def readiness_label(score):
    if score >= 4.5: return "Launch-ready (Excellent)", "green"
    elif score >= 3.8: return "Strong candidate (Good)", "blue"
    elif score >= 3.0: return "Conditional (Needs fixes)", "orange"
    else: return "High risk (Major issues)", "red"

def narrative(country, category_scores, overall):
    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    top3, bot3 = sorted_cats[:3], sorted_cats[-3:]
    label, _ = readiness_label(overall)
    lines = [f"**Market Assessment: {country}**", "", f"Launch Readiness: {overall:.2f}/5 → **{label}**", ""]
    lines.append("Top-scoring categories:")
    lines += [f"- {c}: {v:.2f}" for c, v in top3]
    lines.append("")
    lines.append("Lowest-scoring categories:")
    lines += [f"- {c}: {v:.2f}" for c, v in bot3]
    return "\n".join(lines)


def score_custom(metric_type, value, field_name):
    if value is None:
        return 3, "N/A → neutral 3"

    if metric_type == "custom_islamic_robo_count":
        try:
            n = int(value)
        except:
            return 3, "Invalid → neutral 3"
        if n == 0: return 5, "No competitors → 5"
        if n == 1: return 4, "1 competitor (assume weak) → 4"
        if n <= 2: return 3, "Moderate competition → 3"
        if n >= 3: return 2, "Crowded → 2"
        return 3, "Default → 3"

    if metric_type == "custom_binary_high_good":
        # True/Yes = 5, False/No = 2, else neutral
        if isinstance(value, bool):
            return (5, "Yes/Present → 5") if value else (2, "No/Absent → 2")
        return 3, "Unknown → 3"

    if metric_type == "custom_shariah_board":
        if isinstance(value, bool):
            return (5, "National Shariah board present → 5") if value else (3, "Absent; private boards acceptable → 3")
        return 3, "Unknown → 3"

    if metric_type == "custom_ternary_acceptance":
        # expected values: "low","neutral","high"
        if isinstance(value, str):
            v = value.lower()
            if v.startswith("high"): return 5, "High acceptance → 5"
            if v.startswith("neutral"): return 3, "Neutral/mixed → 3"
            if v.startswith("low"): return 2, "Low acceptance → 2"
        return 3, "Unknown → 3"

    return 3, "Unhandled custom type → 3"

def score_metric(metric_cfg, value):
    t = metric_cfg["type"]
    if t == "numeric":
        return score_numeric(value, metric_cfg["breaks"], metric_cfg["scores"], metric_cfg["direction"])
    else:
        return score_custom(t, value, metric_cfg["field"])

def safe_float(x):
    try:
        return float(x)
    except:
        return None

# Styling (single-quoted to avoid breaking outer triple-string)
st.markdown('''
<style>
body { background: white; color: #333; }
div[data-baseweb="input"] input, .stNumberInput input { max-width: 280px; border-radius: 10px; }
div[role="combobox"] { max-width: 320px; }
.stButton>button { border-radius: 10px; }
</style>
''', unsafe_allow_html=True)


thresholds = load_thresholds()
st.title("Shariah/Ethical Robo Advisory Country Launch Scoring")
country = st.text_input("Jurisdiction", "Singapore")

st.sidebar.header("Weights overview")
total_cat_weight = 0.0
for cat_name, cat_cfg in thresholds["categories"].items():
    total_cat_weight += cat_cfg["weight"]
st.sidebar.write(f"Total category weights = {total_cat_weight:.2f} (should be 1.00)")

cat_scores, cat_breakdown = {}, {}

for cat, cdef in RUBRIC.items():
    st.subheader(cat)
    total, metrics = 0.0, {}
    for mkey, mdef in cdef["metrics"].items():
        label = mdef.get("label", mkey)
        weight = mdef["weight"]
        if mdef.get("custom"):
            options = mdef.get("options", DEFAULT_SELECT)
            reverse = mdef.get("reverse_options", False)
            val = st.selectbox(label, options, key=f"sel_{cat}_{mkey}")
            score, why = score_select(val, options, reverse)
            raw = val
        else:
            val = st.number_input(label, value=0.0, key=f"num_{cat}_{mkey}")
            score, why = score_numeric(val, mdef["breaks"], mdef["scores"], mdef["direction"])
            raw = val
        st.caption(f"{mdef['reason']} → Score {score} ({why}); weight {weight:.2f}")
        total += score * weight
        metrics[mkey] = {"label": label, "input": raw, "score": score, "weight": weight, "reason": mdef["reason"]}
    cat_scores[cat] = round(total, 3)
    cat_breakdown[cat] = {"weight": cdef["weight"], "score": round(total, 3), "metrics": metrics}

if st.button("Compute Launch Readiness"):
    overall = sum([cat_scores[c] * RUBRIC[c]["weight"] for c in RUBRIC.keys()])
    label, color = readiness_label(overall)
    st.markdown(f"<p style='color:{color};font-size:20px'><b>Launch Readiness: {overall:.2f}/5 → {label}</b></p>", unsafe_allow_html=True)

    md = narrative(country, cat_scores, overall)
    st.markdown(md)



st.markdown("---")
if st.button("Compute score"):
    rows = []
    category_rows = []
    overall = 0.0

    for cat_name, cat_cfg in thresholds["categories"].items():
        cat_weight = cat_cfg["weight"]
        cat_score_weighted_sum = 0.0
        cat_weight_sum = 0.0
        
        for mkey, mdef in cat_cfg["metrics"].items():
            label = mdef.get("label", mkey)
            weight = mdef["weight"]
            
            # Get the value from session state using the same keys as your inputs
            if mdef.get("custom"):
                val = st.session_state.get(f"sel_{cat_name}_{mkey}")
                options = mdef.get("options", DEFAULT_SELECT)
                reverse = mdef.get("reverse_options", False)
                score, rationale = score_select(val, options, reverse)
            else:
                val = st.session_state.get(f"num_{cat_name}_{mkey}")
                score, rationale = score_numeric(val, mdef["breaks"], mdef["scores"], mdef["direction"])
            
            rows.append({
                "Category": cat_name,
                "Metric": label,
                "Input": val if val is not None else "N/A",
                "Score": score,
                "Sub-weight": weight,
                "Weighted (metric)": round(score * weight, 3),
                "Rationale": rationale
            })
            cat_score_weighted_sum += score * weight
            cat_weight_sum += weight

        cat_avg_weighted = cat_score_weighted_sum / cat_weight_sum if cat_weight_sum > 0 else 0
        category_rows.append({
            "Category": cat_name,
            "Category weight": cat_weight,
            "Category score (weighted sub-metrics)": round(cat_avg_weighted, 3),
            "Contribution to overall": round(cat_avg_weighted * cat_weight, 3)
        })
        overall += cat_avg_weighted * cat_weight

    st.subheader("Metric-level results")
    st.dataframe(pd.DataFrame(rows))

    st.subheader("Category-level results")
    st.dataframe(pd.DataFrame(category_rows))

    st.subheader("Overall score")
    st.write(f"**{overall:.3f} / 5**  (equivalently **{overall/5*100:.1f}%**)")

    
    safe_country_name = country.replace(" ", "_").replace("/", "_")
    
    st.download_button(
        "Download metric results (CSV)",
        pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
        file_name=f"{safe_country_name}_metrics.csv",
        mime="text/csv"
    )
    st.download_button(
        "Download category results (CSV)",
        pd.DataFrame(category_rows).to_csv(index=False).encode("utf-8"),
        file_name=f"{safe_country_name}_categories.csv",
        mime="text/csv"
    )
    

