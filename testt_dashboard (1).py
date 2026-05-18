"""
TestT EMI Dashboard — Streamlit (WiFi version)
===============================================
Polls the Arduino MKR web server directly over your phone hotspot.
No manual CSV copying needed — just connect to the same hotspot as the Arduino.

How it works:
  1. Turn on your phone hotspot (COMPOST_LOGGER / compost123)
  2. Arduino connects and shows its IP on the OLED (e.g. 192.168.43.50)
  3. Run this script on your laptop (connected to the same hotspot)
  4. Enter the IP in the sidebar
  5. Dashboard auto-downloads the CSV from the Arduino every 60 seconds

Usage:
  pip install streamlit pandas plotly requests
  streamlit run testt_dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import io
import time
from datetime import datetime

# ─── DEFAULT CONFIG ──────────────────────────────────────────────────────────
DEFAULT_ARDUINO_IP = "192.168.43.50"   # update to match your OLED display
ARDUINO_PORT       = 80
DOWNLOAD_ENDPOINT  = "/download"
REFRESH_EVERY      = 60               # seconds between auto-refresh
REQUEST_TIMEOUT    = 15               # seconds before giving up

ERROR_SENTINEL = -999.0

VALID_RANGES = {
    "T1_C":    (-10,  80),
    "T2_C":    (-10,  80),
    "T3_C":    (-10,  80),
    "O2_pct":  (  0,  30),
    "CO2_ppm": (  0,  200000),
}
SENSOR_COLORS = {
    "T1_C":    "#e05c5c",
    "T2_C":    "#5c9ee0",
    "T3_C":    "#5ce08a",
    "O2_pct":  "#e0bc5c",
    "CO2_ppm": "#b05ce0",
}
SENSOR_UNITS = {
    "T1_C":    "°C",
    "T2_C":    "°C",
    "T3_C":    "°C",
    "O2_pct":  "%",
    "CO2_ppm": "ppm",
}

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="TestT EMI Dashboard", layout="wide", page_icon="🌡️")

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Connection")
    arduino_ip = st.text_input(
        "Arduino IP address",
        value=DEFAULT_ARDUINO_IP,
        help="Check the OLED on the Arduino — it shows the IP once connected to WiFi.",
    )
    st.caption(f"Polling: `http://{arduino_ip}{DOWNLOAD_ENDPOINT}`")
    st.markdown("---")
    st.markdown("**Steps to connect:**")
    st.markdown("1. Turn on phone hotspot")
    st.markdown("2. Arduino OLED shows IP")
    st.markdown("3. Connect laptop to same hotspot")
    st.markdown("4. Paste IP above")
    st.markdown("---")
    manual_refresh = st.button("🔄 Refresh now")


# ─── Fetch CSV from Arduino ──────────────────────────────────────────────────
def fetch_csv(ip):
    url = f"http://{ip}:{ARDUINO_PORT}{DOWNLOAD_ENDPOINT}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text, None
    except requests.exceptions.ConnectionError:
        return None, f"Cannot reach Arduino at **{ip}** — is the hotspot on and the Arduino connected?"
    except requests.exceptions.Timeout:
        return None, f"Timed out after {REQUEST_TIMEOUT}s — Arduino may be busy writing to SD, will retry."
    except Exception as e:
        return None, f"Error: {e}"


def parse_csv(text):
    try:
        df = pd.read_csv(io.StringIO(text), parse_dates=["Timestamp"])
        for col in ["T1_C", "T2_C", "T3_C", "O2_pct", "CO2_ppm"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col] = df[col].where(df[col] != ERROR_SENTINEL, other=float("nan"))
        return df, None
    except Exception as e:
        return None, str(e)


# ─── Flag bad rows ────────────────────────────────────────────────────────────
def flag_bad_rows(df):
    issues = []
    sensor_cols = [c for c in ["T1_C", "T2_C", "T3_C", "O2_pct", "CO2_ppm"] if c in df.columns]
    for _, row in df.iterrows():
        bad = []
        for col in sensor_cols:
            val = row[col]
            if pd.isna(val):
                bad.append(f"{col}=MISSING")
            elif col in VALID_RANGES:
                lo, hi = VALID_RANGES[col]
                if val < lo or val > hi:
                    bad.append(f"{col}={val:.2f} (out of range {lo}–{hi})")
        if bad:
            issues.append({
                "Timestamp": row.get("Timestamp", ""),
                "VFD_State": row.get("VFD_State", ""),
                "Issue":     ", ".join(bad),
            })
    return pd.DataFrame(issues)


# ─── Sensor plot ─────────────────────────────────────────────────────────────
def make_sensor_fig(df, col, label, unit, color):
    fig = go.Figure()
    if col not in df.columns:
        fig.add_annotation(text=f"{col} not in CSV", showarrow=False)
        return fig

    ts   = df["Timestamp"]
    vals = df[col]
    lo, hi     = VALID_RANGES.get(col, (-1e9, 1e9))
    good_mask  = vals.notna()
    oor_mask   = good_mask & ((vals < lo) | (vals > hi))
    clean_mask = good_mask & ~oor_mask
    bad_mask   = vals.isna()

    # Clean line
    fig.add_trace(go.Scatter(
        x=ts[clean_mask], y=vals[clean_mask],
        mode="lines+markers", name=label,
        line=dict(color=color, width=2), marker=dict(size=4),
    ))
    # Out-of-range (orange diamond)
    if oor_mask.any():
        fig.add_trace(go.Scatter(
            x=ts[oor_mask], y=vals[oor_mask],
            mode="markers", name=f"{label} out-of-range",
            marker=dict(color="orange", size=9, symbol="diamond"),
        ))
    # Missing/error (red X)
    if bad_mask.any():
        y_ref = float(vals[clean_mask].min()) if clean_mask.any() else 0
        fig.add_trace(go.Scatter(
            x=ts[bad_mask], y=[y_ref] * int(bad_mask.sum()),
            mode="markers", name=f"{label} ERROR",
            marker=dict(color="red", size=10, symbol="x"),
        ))

    # VFD ON shading
    if "VFD_State" in df.columns:
        in_on, start_t = False, None
        for _, r in df.iterrows():
            state = str(r.get("VFD_State", "")).strip().upper()
            t = r["Timestamp"]
            if state == "ON" and not in_on:
                in_on, start_t = True, t
            elif state != "ON" and in_on:
                in_on = False
                fig.add_vrect(x0=start_t, x1=t,
                              fillcolor="rgba(100,200,100,0.12)", line_width=0)
        if in_on and start_t is not None and not df.empty:
            fig.add_vrect(x0=start_t, x1=df["Timestamp"].iloc[-1],
                          fillcolor="rgba(100,200,100,0.12)", line_width=0)

    fig.update_layout(
        height=280, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.14),
        xaxis_title="Time", yaxis_title=f"{label} ({unit})",
        plot_bgcolor="#1a1a2e", paper_bgcolor="#0f0f1a",
        font=dict(color="#dddddd"),
        xaxis=dict(gridcolor="#333355"), yaxis=dict(gridcolor="#333355"),
    )
    return fig


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    st.title("🌡️ TestT EMI Test — Live Dashboard")

    status_box = st.empty()
    st.markdown("---")

    # --- Fetch ---
    csv_text, err = fetch_csv(arduino_ip)

    if err:
        status_box.error(f"❌ {err}")
        if "last_df" in st.session_state:
            st.warning("⚠️ Showing last successfully downloaded data — Arduino unreachable right now.")
            df       = st.session_state["last_df"]
            csv_text = st.session_state.get("last_csv", "")
        else:
            st.info("No cached data. Connect to the same hotspot as the Arduino and enter the IP in the sidebar.")
            time.sleep(REFRESH_EVERY)
            st.rerun()
            return
    else:
        df, parse_err = parse_csv(csv_text)
        if parse_err:
            status_box.error(f"❌ Could not parse CSV: {parse_err}")
            time.sleep(REFRESH_EVERY)
            st.rerun()
            return
        st.session_state["last_df"]  = df
        st.session_state["last_csv"] = csv_text
        status_box.success(
            f"✅ Connected to Arduino at **{arduino_ip}** — "
            f"{len(df)} rows | updated {datetime.now().strftime('%H:%M:%S')}"
        )

    # Save-to-computer button in sidebar
    if csv_text:
        with st.sidebar:
            st.markdown("---")
            st.download_button(
                label="💾 Save CSV to computer",
                data=csv_text,
                file_name=f"TestT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )

    # --- Metrics ---
    bad_df  = flag_bad_rows(df)
    vfd_on  = (df["VFD_State"].str.strip().str.upper() == "ON").sum()  if "VFD_State" in df.columns else 0
    vfd_off = (df["VFD_State"].str.strip().str.upper() == "OFF").sum() if "VFD_State" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total rows",     len(df))
    c2.metric("VFD ON rows",    vfd_on)
    c3.metric("VFD OFF rows",   vfd_off)
    c4.metric("⚠️ Bad readings", len(bad_df))

    st.markdown("---")

    # --- Temperature plots ---
    st.subheader("Temperature Sensors")
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        st.plotly_chart(make_sensor_fig(df, "T1_C", "T1", "°C", SENSOR_COLORS["T1_C"]), use_container_width=True)
    with tc2:
        st.plotly_chart(make_sensor_fig(df, "T2_C", "T2", "°C", SENSOR_COLORS["T2_C"]), use_container_width=True)
    with tc3:
        st.plotly_chart(make_sensor_fig(df, "T3_C", "T3", "°C", SENSOR_COLORS["T3_C"]), use_container_width=True)

    # --- Gas plots ---
    st.subheader("Gas Sensors")
    gc1, gc2 = st.columns(2)
    with gc1:
        st.plotly_chart(make_sensor_fig(df, "O2_pct",  "O2",  "%",   SENSOR_COLORS["O2_pct"]),  use_container_width=True)
    with gc2:
        st.plotly_chart(make_sensor_fig(df, "CO2_ppm", "CO2", "ppm", SENSOR_COLORS["CO2_ppm"]), use_container_width=True)

    # --- Stats ---
    st.markdown("---")
    st.subheader("Sensor Summary")
    sensor_cols = [c for c in ["T1_C", "T2_C", "T3_C", "O2_pct", "CO2_ppm"] if c in df.columns]
    rows = []
    for col in sensor_cols:
        lo, hi = VALID_RANGES.get(col, (-1e9, 1e9))
        s = df[col]
        rows.append({
            "Sensor":       col,
            "Unit":         SENSOR_UNITS.get(col, ""),
            "Mean":         f"{s.mean():.2f}" if s.notna().any() else "—",
            "Min":          f"{s.min():.2f}"  if s.notna().any() else "—",
            "Max":          f"{s.max():.2f}"  if s.notna().any() else "—",
            "Missing":      int(s.isna().sum()),
            "Out of range": int(((s < lo) | (s > hi)).sum()),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- Bad rows ---
    if not bad_df.empty:
        st.markdown("---")
        st.subheader(f"⚠️ Corrupted / Missing Readings ({len(bad_df)} rows)")
        st.dataframe(bad_df, use_container_width=True, hide_index=True)
    else:
        st.success("✅ No corrupted or out-of-range readings found.")

    # --- Raw data ---
    with st.expander("📄 Raw data (last 100 rows)"):
        st.dataframe(df.tail(100), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(
        "🟩 Green shading = VFD ON period  |  "
        "🔴 Red X = missing / error value (-999)  |  "
        "🟠 Orange diamond = out of expected range"
    )

    # --- Auto-refresh ---
    time.sleep(REFRESH_EVERY)
    st.rerun()


if __name__ == "__main__":
    main()
