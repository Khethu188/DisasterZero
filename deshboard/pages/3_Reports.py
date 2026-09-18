import streamlit as st
import json
import os
import glob

st.set_page_config(page_title="Reports | DisasterZero", layout="wide")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")

def load_reports():
    reports = []
    if not os.path.exists(REPORTS_DIR):
        return reports
    for fp in sorted(glob.glob(os.path.join(REPORTS_DIR, "*.json")), reverse=True):
        try:
            with open(fp, "r") as f:
                data = json.load(f)
                data["_filename"] = os.path.basename(fp)
                reports.append(data)
        except Exception:
            continue
    return reports

reports = load_reports()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
:root { --bg: #0d1117; --bg2: #161b22; --border: #30363d; --t1: #e6edf3; --t2: #8b949e; --t3: #484f58; --blue: #58a6ff; --green: #3fb950; --red: #f85149; }
* { font-family: 'Inter', sans-serif; }
.stApp { background: var(--bg); }
[data-testid="stSidebar"] { background: var(--bg2); border-right: 1px solid var(--border); }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMetric"] { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
[data-testid="stMetric"] label { color: var(--t2) !important; font-weight: 600; text-transform: uppercase; font-size: 0.7rem !important; letter-spacing: 0.8px; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--t1) !important; font-weight: 800; }
.section-title { font-size: 0.7rem; font-weight: 700; color: var(--t2); text-transform: uppercase; letter-spacing: 1.2px; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.report-row { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin: 8px 0; display: flex; justify-content: space-between; align-items: center; transition: border-color 0.15s ease; }
.report-row:hover { border-color: var(--blue); }
.report-name { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 500; color: var(--t1); }
.report-meta { font-size: 0.75rem; color: var(--t2); margin-top: 2px; }
.badge { font-size: 0.7rem; font-weight: 700; padding: 3px 10px; border-radius: 4px; }
.badge-pass { background: rgba(63, 185, 80, 0.12); color: var(--green); }
.badge-fail { background: rgba(248, 81, 73, 0.12); color: var(--red); }
.stButton > button { background: #21262d; color: var(--t1); border: 1px solid var(--border); border-radius: 8px; font-weight: 600; font-size: 0.85rem; transition: all 0.15s ease; }
.stButton > button:hover { background: var(--blue); color: #fff; border-color: var(--blue); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 32px 0 8px 0;">
    <h1 style="font-size: 2rem; font-weight: 800; color: #e6edf3; letter-spacing: -1px; margin: 0;">Reports</h1>
    <p style="color: #8b949e; margin: 6px 0 0 0;">View and download disaster recovery incident reports.</p>
</div>
""", unsafe_allow_html=True)

st.markdown(f'<div class="section-title">Available Reports ({len(reports)})</div>', unsafe_allow_html=True)

if reports:
    for i, r in enumerate(reports):
        fn = r.get("_filename", f"report_{i}.json")
        iid = r.get("incident_id", "Unknown")
        sc = r.get("scenario_name", "Unknown")
        p = r.get("overall_passed", False)
        badge_class = "badge-pass" if p else "badge-fail"
        badge_text = "PASSED" if p else "FAILED"

        st.markdown(f"""
        <div class="report-row">
            <div>
                <div class="report-name">{fn}</div>
                <div class="report-meta">{iid} &middot; {sc}</div>
            </div>
            <div class="badge {badge_class}">{badge_text}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Details: {iid}"):
            dc1, dc2 = st.columns(2)
            with dc1:
                st.markdown(f"**Incident:** {iid}")
                st.markdown(f"**Scenario:** {sc}")
            with dc2:
                if "rto" in r:
                    st.metric("Total RTO", f"{r['rto'].get('total_rto_seconds', 0):.1f}s")
                if "rpo" in r:
                    st.metric("Records Lost", r["rpo"].get("records_lost", 0))

            rj = json.dumps(r, indent=2, default=str)
            st.download_button("Download JSON", data=rj, file_name=fn, mime="application/json", key=f"dl_{i}")

            with st.expander("Raw JSON"):
                st.json(r)
else:
    st.info("No reports found. Run a disaster scenario to generate reports.")

st.markdown("""
<div style="text-align: center; color: #484f58; padding: 40px 0 20px 0; font-size: 0.8rem; border-top: 1px solid #30363d; margin-top: 48px;">
    DisasterZero v1.0 &middot; Reports
</div>
""", unsafe_allow_html=True)
