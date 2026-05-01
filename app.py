import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compost Monitor",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

.stApp { background-color: #0d1117; color: #cdd9e5; }
.main .block-container { padding-top: 1.5rem; max-width: 1400px; }

.dash-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.5rem; font-weight: 600;
    color: #58a6ff; letter-spacing: -0.01em; margin-bottom: 0.1rem;
}
.dash-sub {
    font-size: 0.8rem; color: #484f58;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.5rem;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.6rem; margin-bottom: 1.5rem;
}
.metric-card {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 8px; padding: 0.8rem 1rem;
    border-top: 2px solid var(--accent);
}
.metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.6rem; color: #484f58;
    text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.3rem;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.3rem; font-weight: 600;
    color: var(--accent); line-height: 1;
}
.metric-unit { font-size: 0.65rem; color: #484f58; margin-left: 0.15rem; }

section[data-testid="stSidebar"] {
    background-color: #0d1117; border-right: 1px solid #21262d;
}
section[data-testid="stSidebar"] label {
    color: #8b949e !important; font-size: 0.8rem !important;
}

.stDownloadButton > button {
    background: #161b22 !important; color: #58a6ff !important;
    border: 1px solid #30363d !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.75rem !important; border-radius: 6px !important;
}
.stDownloadButton > button:hover {
    border-color: #58a6ff !important; background: #1c2128 !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: #161b22; border-radius: 6px; gap: 0; padding: 2px;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
    color: #484f58; text-transform: uppercase; letter-spacing: 0.05em;
    padding: 0.35rem 0.9rem; border-radius: 5px;
}
.stTabs [aria-selected="true"] {
    background: #1c2128 !important; color: #58a6ff !important;
}

.stCheckbox label { color: #cdd9e5 !important; font-size: 0.83rem !important; }

.chip-on  { background:#0d2818; color:#3fb950; border:1px solid #238636; padding:1px 9px; border-radius:20px; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; display:inline-block; }
.chip-off { background:#1f1208; color:#d29922; border:1px solid #9e6a03; padding:1px 9px; border-radius:20px; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; display:inline-block; }

.info-box { background:#0d1f38; border:1px solid #1f4068; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#58a6ff; }
.warn-box { background:#1f1208; border:1px solid #9e6a03; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#d29922; }
</style>
""", unsafe_allow_html=True)

# ── Column config ──────────────────────────────────────────────────────────────
TIMESTAMP_COL = "Timestamp"

NUMERIC_COLS = {
    "O2_raw_%":  {"label": "O₂ Raw",       "unit": "%",   "color": "#79c0ff"},
    "O2_avg_%":  {"label": "O₂ Avg",       "unit": "%",   "color": "#58a6ff"},
    "CO2_ppm":   {"label": "CO₂",          "unit": "ppm", "color": "#ffa657"},
    "CO2_%":     {"label": "CO₂ %",        "unit": "%",   "color": "#ffb77a"},
    "Temp_C":    {"label": "Temp (probe)", "unit": "°C",  "color": "#ff7b72"},
    "RTC_C":     {"label": "Temp (RTC)",   "unit": "°C",  "color": "#ffa198"},
    "Hz":        {"label": "Fan Hz",       "unit": "Hz",  "color": "#d2a8ff"},
    "Step":      {"label": "Fan Step",     "unit": "",    "color": "#bc8cff"},
    "CycleSec":  {"label": "Cycle Sec",    "unit": "s",   "color": "#d2a8ff"},
    "CycleNum":  {"label": "Cycle #",      "unit": "",    "color": "#bc8cff"},
    "Spikes":    {"label": "O₂ Spikes",    "unit": "",    "color": "#f0883e"},
    "I2C_err":   {"label": "I2C Errors",   "unit": "",    "color": "#ff7b72"},
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_csv(file) -> pd.DataFrame:
    df = pd.read_csv(
        file,
        on_bad_lines="skip",
        engine="python",
        encoding="utf-8",
        encoding_errors="ignore",
    )
    df.columns = df.columns.str.strip()
    if TIMESTAMP_COL in df.columns:
        df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL], errors="coerce")
        df = df.dropna(subset=[TIMESTAMP_COL])
        df = df.sort_values(TIMESTAMP_COL).reset_index(drop=True)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def detect_fan_col(df):
    for c in ["FanState", "Hz", "Step"]:
        if c in df.columns:
            return c
    return None


def get_fan_on_mask(df, fan_col):
    if fan_col == "FanState":
        return df[fan_col].fillna("OFF").str.upper() == "ON"
    elif fan_col in ("Hz", "Step"):
        return df[fan_col].fillna(0) > 0
    return pd.Series(False, index=df.index)


def apply_rolling(series, window):
    if window <= 1:
        return series
    return series.rolling(window=window, min_periods=1, center=True).mean()


def flag_anomalies(series, threshold=3.0):
    roll_mean = series.rolling(30, min_periods=5, center=True).mean()
    roll_std  = series.rolling(30, min_periods=5, center=True).std()
    z = (series - roll_mean) / (roll_std + 1e-9)
    return z.abs() > threshold


def plotly_base():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0d1117",
        font=dict(family="IBM Plex Sans, sans-serif", color="#8b949e", size=11),
        legend=dict(
            bgcolor="rgba(13,17,23,0.9)", bordercolor="#30363d", borderwidth=1,
            font=dict(size=10, family="IBM Plex Mono, monospace", color="#cdd9e5"),
        ),
        margin=dict(l=55, r=20, t=35, b=40),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d",
                        font=dict(color="#cdd9e5", size=11)),
    )


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**📂 Upload**")
    uploaded = st.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")

    if uploaded:
        df_raw = load_csv(uploaded)
        fan_col = detect_fan_col(df_raw)
        present_numeric = [c for c in NUMERIC_COLS if c in df_raw.columns]

        st.markdown("---")
        st.markdown("**⏱ Time Range**")
        t_min = df_raw[TIMESTAMP_COL].min()
        t_max = df_raw[TIMESTAMP_COL].max()
        total_hours = max((t_max - t_min).total_seconds() / 3600, 1)

        range_mode = st.radio("Range mode", ["Last N hours", "Last N days", "Full range"],
                              label_visibility="collapsed")
        if range_mode == "Last N hours":
            n_h = st.slider("Hours", 1, min(int(total_hours), 720), min(24, int(total_hours)))
            t_start = t_max - timedelta(hours=n_h)
        elif range_mode == "Last N days":
            max_days = max(1, int(total_hours // 24))
            n_d = st.slider("Days", 1, max_days, min(3, max_days))
            t_start = t_max - timedelta(days=n_d)
        else:
            t_start = t_min

        df = df_raw[df_raw[TIMESTAMP_COL] >= t_start].copy().reset_index(drop=True)

        st.markdown("---")
        st.markdown("**📊 Variables**")
        default_on = {"O2_avg_%", "CO2_ppm", "Temp_C"}
        selected_cols = [
            c for c in present_numeric
            if st.checkbox(
                f"{NUMERIC_COLS[c]['label']} ({NUMERIC_COLS[c]['unit']})"
                if NUMERIC_COLS[c]['unit'] else NUMERIC_COLS[c]['label'],
                value=(c in default_on),
                key=c,
            )
        ]

        st.markdown("---")
        st.markdown("**〰 Rolling Average**")
        rolling_window = st.slider(
            "Window (rows) — 1 = raw",
            1, 120, 1,
            help="1 = raw data, every point shown. Higher = smoother but hides variation. At 10s intervals: window 6 ≈ 1 min average."
        )
        show_raw_under = False
        if rolling_window > 1:
            show_raw_under = st.checkbox("Show raw underneath (faint)", value=False)

        st.markdown("---")
        st.markdown("**⚙️ Options**")
        show_anomalies = st.checkbox("Flag O₂ anomalies", value=True)
        show_fan_band  = st.checkbox("Show fan ON/OFF band", value=True)

    else:
        df = None
        selected_cols = []
        rolling_window = 1
        show_raw_under = False
        show_anomalies = True
        show_fan_band  = True
        fan_col = None

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="dash-header">🌱 Compost Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="dash-sub">Arduino · O₂ · CO₂ · Temperature · Fan</div>', unsafe_allow_html=True)

if df is None:
    st.markdown("""
    <div class="info-box">
    👈 Upload a CSV exported from your Arduino to get started.<br>
    Supports: <code>Timestamp, O2_raw_%, O2_avg_%, CO2_ppm, CO2_%, Temp_C, RTC_C, Hz, Step, FanState, Spikes, I2C_err</code>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Metric cards ───────────────────────────────────────────────────────────────
key_metrics = [
    ("O2_avg_%", "#58a6ff"),
    ("CO2_ppm",  "#ffa657"),
    ("Temp_C",   "#ff7b72"),
    ("RTC_C",    "#ffa198"),
]
metrics_html = '<div class="metric-grid">'
for col, accent in key_metrics:
    if col in df.columns:
        last = df[col].dropna()
        val = last.iloc[-1] if not last.empty else float("nan")
        info = NUMERIC_COLS[col]
        metrics_html += (
            f'<div class="metric-card" style="--accent:{accent}">'
            f'<div class="metric-label">{info["label"]}</div>'
            f'<div class="metric-value">{val:.1f}<span class="metric-unit">{info["unit"]}</span></div>'
            f'</div>'
        )

if fan_col:
    fan_series = df[fan_col].dropna()
    if not fan_series.empty:
        last_fan = fan_series.iloc[-1]
        is_on = (str(last_fan).upper() == "ON") if fan_col == "FanState" else (float(last_fan) > 0)
        chip_class = "chip-on" if is_on else "chip-off"
        label = "ON" if is_on else "OFF"
        suffix = f" · {last_fan} Hz" if fan_col == "Hz" else ""
        metrics_html += (
            f'<div class="metric-card" style="--accent:#3fb950">'
            f'<div class="metric-label">Fan</div>'
            f'<div style="margin-top:5px"><span class="{chip_class}">{label}{suffix}</span></div>'
            f'</div>'
        )

metrics_html += (
    f'<div class="metric-card" style="--accent:#484f58">'
    f'<div class="metric-label">Rows</div>'
    f'<div class="metric-value" style="font-size:1.05rem">{len(df):,}</div>'
    f'</div>'
)
metrics_html += "</div>"
st.markdown(metrics_html, unsafe_allow_html=True)

# ── Anomaly warning ────────────────────────────────────────────────────────────
if "O2_avg_%" in df.columns and show_anomalies:
    n_anom = int(flag_anomalies(df["O2_avg_%"]).sum())
    if n_anom > 0:
        st.markdown(
            f'<div class="warn-box">⚠️ <b>{n_anom} anomalous O₂ readings</b> in this window '
            f'(rolling z-score > 3σ) — shown as orange markers on the chart.</div>',
            unsafe_allow_html=True
        )

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈  Time Series", "🔍  Data Preview", "💾  Download"])

# ════════════════════════════ TAB 1: CHART ════════════════════════════════════
with tab1:
    if not selected_cols:
        st.info("Select at least one variable in the sidebar.")
    else:
        show_band = show_fan_band and fan_col is not None

        if show_band:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                row_heights=[0.84, 0.16],
                vertical_spacing=0.03,
            )
            main_row, band_row = 1, 2
        else:
            fig = make_subplots(rows=1, cols=1)
            main_row = 1

        base = plotly_base()

        # ── Sensor traces — all on one axis ───────────────────────────────────
        for col in selected_cols:
            info = NUMERIC_COLS[col]
            color = info["color"]
            y_raw  = df[col]
            y_plot = apply_rolling(y_raw, rolling_window)

            if rolling_window > 1 and show_raw_under:
                fig.add_trace(go.Scatter(
                    x=df[TIMESTAMP_COL], y=y_raw,
                    name=f"{info['label']} raw",
                    line=dict(color=color, width=0.8),
                    opacity=0.18,
                    showlegend=False,
                    hoverinfo="skip",
                ), row=main_row, col=1)

            fig.add_trace(go.Scatter(
                x=df[TIMESTAMP_COL], y=y_plot,
                name=info["label"],
                line=dict(color=color, width=1.8),
                hovertemplate=f"<b>{info['label']}</b>: %{{y:.2f}} {info['unit']}<extra></extra>",
            ), row=main_row, col=1)

            # Anomaly markers
            if show_anomalies and col in ("O2_raw_%", "O2_avg_%"):
                mask = flag_anomalies(y_raw)
                if mask.any():
                    fig.add_trace(go.Scatter(
                        x=df.loc[mask, TIMESTAMP_COL], y=y_raw[mask],
                        mode="markers", name="⚠ O₂ spike",
                        marker=dict(color="#f0883e", size=8, symbol="x-thin",
                                    line=dict(width=2, color="#f0883e")),
                        hovertemplate="<b>⚠ spike</b>: %{y:.2f}%<extra></extra>",
                    ), row=main_row, col=1)

       # ── Fan shading as vrect on every subplot ─────────────────────────────
        if show_band:
            fan_mask = get_fan_on_mask(df, fan_col)
            times = df[TIMESTAMP_COL].values
            in_block = False
            block_start = None

            # Find contiguous ON blocks and draw a vrect on every sensor row
            for ts, is_on in zip(times, fan_mask):
                if is_on and not in_block:
                    block_start = ts
                    in_block = True
                elif not is_on and in_block:
                    for row in range(1, n_sensor_rows + 1):
                        fig.add_vrect(
                            x0=block_start, x1=ts,
                            fillcolor="rgba(63,185,80,0.12)",
                            layer="below", line_width=0,
                            row=row, col=1,
                        )
                    in_block = False
            # Close last open block
            if in_block:
                for row in range(1, n_sensor_rows + 1):
                    fig.add_vrect(
                        x0=block_start, x1=times[-1],
                        fillcolor="rgba(63,185,80,0.12)",
                        layer="below", line_width=0,
                        row=row, col=1,
                    )

            # Add one invisible trace just for the legend entry
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(size=10, color="rgba(63,185,80,0.5)", symbol="square"),
                name="Fan ON",
                showlegend=True,
            ), row=1, col=1)

        # ── Shared layout ─────────────────────────────────────────────────────
        fig.update_layout(height=520 if show_band else 460, **base)
        fig.update_xaxes(
            gridcolor="#21262d", linecolor="#30363d",
            tickfont=dict(size=10, color="#8b949e"),
        )
        fig.update_yaxes(
            row=main_row, col=1,
            gridcolor="#21262d", linecolor="#30363d",
            tickfont=dict(size=10, color="#8b949e"),
        )

        st.plotly_chart(fig, use_container_width=True)

        # Rolling window info
        if rolling_window > 1 and len(df) > 1:
            interval_sec = df[TIMESTAMP_COL].diff().median().total_seconds()
            smoothed_min = rolling_window * interval_sec / 60
            st.markdown(
                f'<span style="color:#484f58;font-size:0.74rem;font-family:IBM Plex Mono,monospace">'
                f'Rolling window = {rolling_window} rows ≈ {smoothed_min:.1f} min of smoothing '
                f'at your ~{interval_sec:.0f}s log interval. Set to 1 to see raw data.</span>',
                unsafe_allow_html=True,
            )

# ════════════════════════════ TAB 2: PREVIEW ══════════════════════════════════
with tab2:
    st.markdown(
        f'<span style="color:#484f58;font-size:0.78rem;font-family:IBM Plex Mono">'
        f'{len(df):,} rows · {t_start.strftime("%Y-%m-%d %H:%M")} → {t_max.strftime("%Y-%m-%d %H:%M")}</span>',
        unsafe_allow_html=True,
    )
    with st.expander("📊 Summary Statistics"):
        stat_cols = [c for c in selected_cols if c in df.columns]
        if stat_cols:
            stats = df[stat_cols].describe().T
            stats.index = [NUMERIC_COLS.get(c, {}).get("label", c) for c in stats.index]
            st.dataframe(stats.style.format("{:.3f}"), use_container_width=True)
    st.dataframe(df.reset_index(drop=True), use_container_width=True, height=420)

# ════════════════════════════ TAB 3: DOWNLOAD ════════════════════════════════
with tab3:
    st.markdown("#### Download filtered data")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    fname = f"compost_{t_start.strftime('%Y%m%d_%H%M')}_{t_max.strftime('%Y%m%d_%H%M')}.csv"
    st.download_button("⬇ Download CSV", data=csv_bytes, file_name=fname, mime="text/csv")
    st.markdown(
        f'<div class="info-box"><b>File:</b> {fname}<br>'
        f'<b>Rows:</b> {len(df):,}<br>'
        f'<b>Range:</b> {t_start.strftime("%Y-%m-%d %H:%M")} → {t_max.strftime("%Y-%m-%d %H:%M")}</div>',
        unsafe_allow_html=True,
    )
