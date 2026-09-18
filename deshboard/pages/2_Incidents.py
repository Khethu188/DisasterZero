import streamlit as st
import json
import os
import glob

st.set_page_config(page_title="Incidents | DisasterZero", layout="wide")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")

def load_reports():
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports
    for fp in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json")), reverse=True):
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                data["_file"] = os.path.basename(fp)
                reports.append(data)
        except Exception:
            continue
    return reports

reports = load_reports()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
:root { --bg: #0d1117; --bg2: #161b22; --bg3: #21262d; --border: #30363d; --t1: #e6edf3; --t2: #8b949e; --t3: #484f58; --blue: #58a6ff; --green: #3fb950; --red: #f85149; }
* { font-family: 'Inter', sans-serif; }
.stApp { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--bg2); border-right: 1px solid var(--border); }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMetric"] { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
[data-testid="stMetric"] label { color: var(--t2) !important; font-weight: 600; text-transform: uppercase; font-size: 0.7rem !important; letter-spacing: 0.8px; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--t1) !important; font-weight: 800; }
.section-title { font-size: 0.7rem; font-weight: 700; color: var(--t2); text-transform: uppercase; letter-spacing: 1.2px; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.incident-row { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin: 8px 0; display: flex; justify-content: space-between; align-items: center; transition: border-color 0.15s ease; }
.incident-row:hover { border-color: var(--blue); }
.incident-id { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: var(--t1); }
.incident-scenario { font-size: 0.8rem; color: var(--t2); margin-top: 2px; }
.incident-badge { font-size: 0.7rem; font-weight: 700; padding: 3px 10px; border-radius: 4px; }
.badge-pass { background: rgba(63, 185, 80, 0.12); color: var(--green); }
.badge-fail { background: rgba(248, 81, 73, 0.12); color: var(--red); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 32px 0 8px 0;">
    <h1 style="font-size: 2rem; font-weight: 800; color: #e6edf3; letter-spacing: -1px; margin: 0;">Incidents</h1>
    <p style="color: #8b949e; margin: 6px 0 0 0;">Track disaster recovery incidents and their resolution status.</p>
</div>
""", unsafe_allow_html=True)

s1, s2, s3 = st.columns(3)
with s1:
    st.metric("Total", len(reports))
with s2:
    st.metric("Resolved", sum(1 for r in reports if r.get("overall_passed", False)))
with s3:
    st.metric("Unresolved", sum(1 for r in reports if not r.get("overall_passed", False)))

st.markdown('<div class="section-title">Filters</div>', unsafe_allow_html=True)

fc1, fc2 = st.columns(2)
with fc1:
    status_f = st.selectbox("Status", ["All", "Passed", "Failed"])
with fc2:
    names = sorted(set(r.get("scenario_name", "Unknown") for r in reports))
    names.insert(0, "All")
    scenario_f = st.selectbox("Scenario", names)

filtered = reports
if status_f == "Passed":
    filtered = [r for r in filtered if r.get("overall_passed", False)]
elif status_f == "Failed":
    filtered = [r for r in filtered if not r.get("overall_passed", False)]
if scenario_f != "All":
    filtered = [r for r in filtered if r.get("scenario_name", "") == scenario_f]

st.markdown(f'<div class="section-title">Results ({len(filtered)})</div>', unsafe_allow_html=True)

if filtered:
    for i, r in enumerate(filtered):
        iid = r.get("incident_id", f"INC-{i}")
        p = r.get("overall_passed", False)
        sc = r.get("scenario_name", "Unknown")
        cr = r.get("created_at", "N/A")
        badge_class = "badge-pass" if p else "badge-fail"
        badge_text = "PASSED" if p else "FAILED"

        st.markdown(f"""
        <div class="incident-row">
            <div>
                <div class="incident-id">{iid}</div>
                <div class="incident-scenario">{sc} &middot; {cr}</div>
            </div>
            <div class="incident-badge {badge_class}">{badge_text}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Details: {iid}"):
            dc1, dc2 = st.columns(2)
            with dc1:
                st.markdown(f"**Incident:** {iid}")
                st.markdown(f"**Scenario:** {sc}")
                st.markdown(f"**Created:** {cr}")
            with dc2:
                if "rto" in r:
                    st.metric("RTO", f"{r['rto'].get('total_rto_seconds', 0):.1f}s")
                if "rpo" in r:
                    st.metric("Records Lost", r["rpo"].get("records_lost", 0))
            st.json(r)
else:
    st.info("No incidents match your filters.")

st.markdown("""
<div style="text-align: center; color: #484f58; padding: 40px 0 20px 0; font-size: 0.8rem; border-top: 1px solid #30363d; margin-top: 48px;">
    DisasterZero v1.0 &middot; Incidents
</div>
""", unsafe_allow_html=True)
