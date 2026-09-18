import streamlit as st
import json
import os
import glob
import pandas as pd

st.set_page_config(page_title="Overview | DisasterZero", layout="wide")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")

def load_reports():
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports
    for fp in glob.glob(os.path.join(REPORTS_DIR, "*.json")):
        try:
            with open(fp, "r") as f:
                reports.append(json.load(f))
        except Exception:
            continue
    return reports

reports = load_reports()
total = len(reports)
passed = sum(1 for r in reports if r.get("overall_passed", False))
failed = total - passed

rto_vals = [r["rto"]["total_rto_seconds"] for r in reports if "rto" in r]
rpo_vals = [r["rpo"]["records_lost"] for r in reports if "rpo" in r]
avg_rto = sum(rto_vals) / len(rto_vals) if rto_vals else 0
total_loss = sum(rpo_vals)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');
:root { --bg: #0d1117; --bg2: #161b22; --bg3: #21262d; --border: #30363d; --t1: #e6edf3; --t2: #8b949e; --t3: #484f58; --blue: #58a6ff; --green: #3fb950; --red: #f85149; --orange: #d29922; }
* { font-family: 'Inter', sans-serif; }
.stApp { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--bg2); border-right: 1px solid var(--border); }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMetric"] { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
[data-testid="stMetric"] label { color: var(--t2) !important; font-weight: 600; text-transform: uppercase; font-size: 0.7rem !important; letter-spacing: 0.8px; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--t1) !important; font-weight: 800; }
.section-title { font-size: 0.7rem; font-weight: 700; color: var(--t2); text-transform: uppercase; letter-spacing: 1.2px; margin: 40px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.target-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
.target-card:hover { border-color: var(--blue); }
.target-label { font-size: 0.7rem; font-weight: 600; color: var(--t2); text-transform: uppercase; letter-spacing: 0.8px; }
.target-value { font-size: 2rem; font-weight: 800; margin: 8px 0; line-height: 1; }
.target-sub { font-size: 0.8rem; color: var(--t3); }
.target-status { font-size: 0.75rem; font-weight: 700; margin-top: 12px; padding: 4px 10px; border-radius: 4px; display: inline-block; }
.target-pass { background: rgba(63, 185, 80, 0.12); color: var(--green); }
.target-fail { background: rgba(248, 81, 73, 0.12); color: var(--red); }
.bar-bg { height: 4px; background: var(--bg3); border-radius: 2px; margin-top: 12px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 32px 0 8px 0;">
    <h1 style="font-size: 2rem; font-weight: 800; color: #e6edf3; letter-spacing: -1px; margin: 0;">Overview</h1>
    <p style="color: #8b949e; margin: 6px 0 0 0;">System health, RTO/RPO compliance, and scenario history.</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Scenarios", total)
with c2:
    st.metric("Passed", passed)
with c3:
    st.metric("Failed", failed)
with c4:
    st.metric("Avg RTO", f"{avg_rto:.1f}s")
with c5:
    st.metric("Data Loss", f"{total_loss} rec")

# RTO / RPO
st.markdown('<div class="section-title">RTO / RPO Compliance</div>', unsafe_allow_html=True)

tc1, tc2 = st.columns(2)

rto_pct = min((avg_rto / 600) * 100, 100) if avg_rto > 0 else 0
rto_color = "#3fb950" if avg_rto <= 600 else "#f85149"
rto_status_class = "target-pass" if avg_rto <= 600 else "target-fail"
rto_status_text = "ON TARGET" if avg_rto <= 600 else "EXCEEDING"

rpo_color = "#3fb950" if total_loss == 0 else "#f85149"
rpo_status_class = "target-pass" if total_loss == 0 else "target-fail"
rpo_status_text = "ZERO LOSS" if total_loss == 0 else "DATA LOSS"

with tc1:
    st.markdown(f"""
    <div class="target-card">
        <div class="target-label">Recovery Time Objective</div>
        <div class="target-value" style="color: {rto_color};">{avg_rto:.1f}s</div>
        <div class="target-sub">Target: 600s (10 min)</div>
        <div class="bar-bg"><div class="bar-fill" style="width: {rto_pct}%; background: {rto_color};"></div></div>
        <div class="target-status {rto_status_class}">{rto_status_text}</div>
    </div>
    """, unsafe_allow_html=True)

with tc2:
    st.markdown(f"""
    <div class="target-card">
        <div class="target-label">Recovery Point Objective</div>
        <div class="target-value" style="color: {rpo_color};">{total_loss} records</div>
        <div class="target-sub">Target: 0 records lost</div>
        <div class="bar-bg"><div class="bar-fill" style="width: 100%; background: {rpo_color};"></div></div>
        <div class="target-status {rpo_status_class}">{rpo_status_text}</div>
    </div>
    """, unsafe_allow_html=True)

# Scenario History
st.markdown('<div class="section-title">Scenario History</div>', unsafe_allow_html=True)

if reports:
    rows = []
    for r in reports:
        rows.append({
            "Incident": r.get("incident_id", "N/A"),
            "Scenario": r.get("scenario_name", "Unknown"),
            "Status": "PASSED" if r.get("overall_passed", False) else "FAILED",
            "Created": r.get("created_at", "N/A"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No scenarios executed yet. Run a scenario to see data here.")

# Coverage
st.markdown('<div class="section-title">Test Coverage</div>', unsafe_allow_html=True)

cov1, cov2, cov3 = st.columns(3)
with cov1:
    st.metric("Unit Tests", "23")
with cov2:
    st.metric("Integration", "24")
with cov3:
    st.metric("End-to-End", "7")

st.markdown("""
<div style="text-align: center; color: #484f58; padding: 40px 0 20px 0; font-size: 0.8rem; border-top: 1px solid #30363d; margin-top: 48px;">
    DisasterZero v1.0 &middot; Overview
</div>
""", unsafe_allow_html=True)
