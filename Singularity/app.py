"""
app.py
──────
Suraksha Saathi — Streamlit Command Center Dashboard

Features:
  • Live metric cards (scams caught, accuracy, KB size)
  • Live detection feed from guardian_logs.csv
  • Manual email analyser (full pipeline in the browser)
  • Knowledge Base explorer
  • Language + sensitivity settings in sidebar

Run:
    streamlit run app.py
"""

from __future__ import annotations

import os
import csv
import json
import time
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd

from context.samples import SCAM_SAMPLES
from context.matcher import find_context_match
from engine import analyze, AnalysisResult

# ────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Suraksha Saathi — Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOG_CSV = Path("guardian_logs.csv")

# ────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@700;800&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
h1, h2, h3 { font-family: 'Syne', sans-serif; font-weight: 800; }
code, .monospace { font-family: 'JetBrains Mono', monospace; }

.metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    text-align: center;
    border-top: 3px solid;
}
.danger-critical { color: #ff2d55; background: rgba(255,45,85,0.12); border-radius: 8px; padding: 2px 10px; font-weight: 700; }
.danger-high     { color: #ff9f0a; background: rgba(255,159,10,0.12); border-radius: 8px; padding: 2px 10px; font-weight: 700; }
.danger-medium   { color: #ffd60a; background: rgba(255,214,10,0.12); border-radius: 8px; padding: 2px 10px; font-weight: 700; }
.danger-low      { color: #30d158; background: rgba(48,209,88,0.12);  border-radius: 8px; padding: 2px 10px; font-weight: 700; }

.advice-box {
    background: rgba(255,159,10,0.08);
    border: 1px solid rgba(255,159,10,0.25);
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 8px;
}
.reasoning-box {
    background: rgba(48,209,88,0.06);
    border-left: 3px solid #30d158;
    border-radius: 4px;
    padding: 12px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────
# SIDEBAR SETTINGS
# ────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    lang      = st.selectbox("Alert Language", ["Hinglish", "Hindi", "English"])
    threshold = st.slider("Risk Threshold", min_value=0, max_value=10, value=5,
                          help="Emails with effective risk above this are flagged red.")
    auto_refresh = st.toggle("Auto-refresh Live Feed (10s)", value=False)
    st.divider()
    st.markdown("### 🔑 API Status")
    st.success("✅ Gemini API (Stage A + B)" if os.getenv("GEMINI_API_KEY") else "❌ GEMINI_API_KEY missing")
    st.divider()
    st.caption("Suraksha Saathi v2.0 · Multi-Agent Edition")

# ────────────────────────────────────────────────────────────────────────────
# HEADER
# ────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex;align-items:center;gap:16px;margin-bottom:8px;">
  <div style="font-size:40px">🛡️</div>
  <div>
    <h1 style="margin:0;font-size:28px;">Suraksha Saathi</h1>
    <p style="margin:0;color:#8e8e93;font-size:13px;letter-spacing:0.1em;text-transform:uppercase;">
      Hackathon prototype · Message risk review
    </p>
  </div>
</div>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────
# LIVE METRICS
# ────────────────────────────────────────────────────────────────────────────

def _load_logs() -> pd.DataFrame:
    if not LOG_CSV.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(LOG_CSV)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


df_logs = _load_logs()
today   = date.today().strftime("%Y-%m-%d")

total_today   = 0
flagged_today = 0
if not df_logs.empty and "timestamp" in df_logs.columns:
    mask = df_logs["timestamp"].astype(str).str.startswith(today)
    total_today   = mask.sum()
    flagged_today = (df_logs.loc[mask, "flagged"] == True).sum() if "flagged" in df_logs.columns else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("AI configuration", "Key set" if os.getenv("GEMINI_API_KEY") else "Key missing")
c2.metric("Flagged emails today", str(int(flagged_today)))
c3.metric("Detection accuracy", "Not evaluated")
c4.metric("📚 KB Patterns",    str(len(SCAM_SAMPLES)), delta="loaded")

st.divider()

# ────────────────────────────────────────────────────────────────────────────
# TABS
# ────────────────────────────────────────────────────────────────────────────

tab_analyse, tab_feed, tab_kb = st.tabs([
    "⚡ Analyse Email", "📋 Live Detection Feed", "🗄️ Knowledge Base"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: ANALYSER
# ══════════════════════════════════════════════════════════════════════════════

with tab_analyse:
    st.markdown("### Paste a suspicious email, SMS or WhatsApp message")

    sample_options = {
        "(choose a sample…)": "",
        "Electricity Disconnection": "Your electricity will be cut off at 9:30 PM tonight. Call 9876543210 immediately.",
        "KYC Phishing Link":         "Dear SBI Customer, your KYC expired. Click http://sbi-kyc-update.xyz now or account blocked in 24h.",
        "KBC Lottery Advance Fee":   "Congratulations! You won Rs 25 Lakhs in KBC. Pay Rs 4999 processing fee to claim.",
        "Digital Arrest (CBI)":      "This is CBI Officer Sharma. You are under Digital Arrest for money laundering. Pay Rs 2 lakh bail now.",
        "UPI PIN Reverse Trick":     "Enter your UPI PIN to receive Rs 500 cashback into your account immediately.",
    }

    chosen = st.selectbox("Or try a sample:", list(sample_options.keys()))
    email_text = st.text_area(
        "Message Text",
        value=sample_options[chosen],
        height=160,
        placeholder="Paste suspicious message here…",
    )

    if st.button("⚡ Run Multi-Agent Analysis", type="primary", use_container_width=True):
        if not email_text.strip():
            st.warning("Please enter a message first.")
        else:
            with st.spinner("⚙️ Stage 1: TF-IDF Matcher running…"):
                match, score = find_context_match(email_text)

            st.markdown("---")
            st.markdown("#### ⚙️ Stage 1 — TF-IDF Similarity Matcher")
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.progress(score, text=f"Similarity: **{score:.0%}** — matched: _{match['pattern']}_")
            with col_b:
                danger_cls = f"danger-{match['severity'].lower()}"
                st.markdown(f"<span class='{danger_cls}'>{match['severity']}</span>",
                            unsafe_allow_html=True)

            with st.expander("View matched knowledge base entry"):
                st.markdown(f"**ID:** `{match['id']}`")
                st.markdown(f"**Category:** {match['category']}")
                st.markdown(f"**Sample:** _{match['content']}_")
                st.markdown(f"**Logic:** {match['logic']}")

            with st.spinner("🧠 Stage 2: Gemini Deep Analysis reasoning…"):
                result = analyze(email_text, match, score, threshold, language={"English": "en", "Hindi": "hi", "Hinglish": "hng"}[lang])

            st.markdown("---")
            st.markdown("#### 🧠 Stage 2 — Gemini Expert Opinion")

            if result.error:
                st.error(f"Analysis error: {result.error}")
            else:
                r1, r2 = st.columns(2)
                with r1:
                    st.metric("Danger Level",     result.danger_level)
                    st.metric("Scam Type",         result.scam_type or "—")
                with r2:
                    st.metric("Response source", result.analysis_source)
                    st.metric("Flagged",             "YES 🚨" if result.flagged else "NO ✅")

                if result.psychological_tactics:
                    st.markdown("**Psychological Tactics Detected:**")
                    cols = st.columns(min(len(result.psychological_tactics), 3))
                    for i, tactic in enumerate(result.psychological_tactics):
                        cols[i % 3].markdown(f"`{tactic}`")

                if result.reasoning:
                    st.markdown("**Deep Reasoning:**")
                    st.markdown(
                        f"<div class='reasoning-box'>{result.reasoning}</div>",
                        unsafe_allow_html=True,
                    )

                if result.hinglish_advice:
                    st.markdown(
                        f"<div class='advice-box'>🏡 <strong>Hinglish Village Advice</strong><br/>"
                        f"<em>{result.hinglish_advice}</em></div>",
                        unsafe_allow_html=True,
                    )

                if result.safe_action:
                    st.success(f"✅ **Safe Action:** {result.safe_action}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: LIVE FEED
# ══════════════════════════════════════════════════════════════════════════════

with tab_feed:
    if auto_refresh:
        time.sleep(0.5)
        st.rerun()

    st.markdown("### Live Detection Feed")
    df_logs = _load_logs()

    if df_logs.empty:
        st.info("No detections logged yet. Run `main_monitor.py` to start the Watchman.")
    else:
        # Colour-code danger column
        def _highlight(row):
            colours = {"CRITICAL": "background-color:#2d0a10;color:#ff2d55",
                       "HIGH":     "background-color:#2d1a05;color:#ff9f0a",
                       "MEDIUM":   "background-color:#2d2a00;color:#ffd60a",
                       "LOW":      "background-color:#0a2d14;color:#30d158"}
            c = colours.get(str(row.get("danger_level", "")), "")
            return [c if col == "danger_level" else "" for col in row.index]

        display_cols = [c for c in
            ["timestamp","sender","subject","matched_pattern","similarity_score","danger_level","scam_type","flagged"]
            if c in df_logs.columns]

        styled = (df_logs[display_cols]
                  .tail(50)
                  .sort_values("timestamp", ascending=False)
                  .style.apply(_highlight, axis=1))

        st.dataframe(styled, use_container_width=True, height=420)

        st.download_button(
            "⬇️ Export CSV",
            data=df_logs.to_csv(index=False),
            file_name=f"suraksha_logs_{today}.csv",
            mime="text/csv",
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

with tab_kb:
    st.markdown(f"### Knowledge Base — {len(SCAM_SAMPLES)} Patterns")
    st.caption("Add more entries to `context/data.py` to extend the library.")

    search = st.text_input("🔍 Filter patterns", placeholder="type keyword…")
    filtered = [s for s in SCAM_SAMPLES
                if not search or search.lower() in (s["pattern"] + s["content"] + s["category"]).lower()]

    for sample in filtered:
        sev   = sample["severity"]
        color = {"CRITICAL":"#ff2d55","HIGH":"#ff9f0a","MEDIUM":"#ffd60a","LOW":"#30d158"}.get(sev,"#888")
        with st.expander(f"{'🔴' if sev=='CRITICAL' else '🟠' if sev=='HIGH' else '🟡' if sev=='MEDIUM' else '🟢'} {sample['pattern']}  `{sample['id']}`"):
            cols = st.columns([2, 1])
            with cols[0]:
                st.markdown(f"**Category:** {sample['category']}")
                st.markdown(f"**Sample Message:**")
                st.markdown(f"> _{sample['content']}_")
                st.markdown(f"**Why it works:** {sample['logic']}")
            with cols[1]:
                st.markdown(f"**Severity**")
                st.markdown(f"<span style='color:{color};font-weight:700;font-size:18px'>{sev}</span>", unsafe_allow_html=True)
                st.markdown(f"**Hinglish Hook:**")
                st.markdown(f"_{sample.get('hinglish_hook', sample.get('advice_hng', ''))}_")

# ────────────────────────────────────────────────────────────────────────────
# FOOTER
# ────────────────────────────────────────────────────────────────────────────

st.divider()
st.markdown(
    "<div style='text-align:center;color:#3a3a3c;font-size:12px;font-family:JetBrains Mono,monospace;'>"
    "Suraksha Saathi v2.0 · Gemini 2.0 Flash Lite + TF-IDF · Built for AI Synergy Hackathon 2026"
    "</div>",
    unsafe_allow_html=True,
)
