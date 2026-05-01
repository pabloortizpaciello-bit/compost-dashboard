import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from datetime import timedelta

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compost Monitor",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Dark earthy theme */
.stApp {
    background-color: #0f1a0f;
    color: #d4e8c2;
}

.main .block-container {
    padding-top: 1.5rem;
    max-width: 1400px;
}

/* Header */
.dash-header {
    font-family: 'Space Mono', monospace;
    font-size: 1.6rem;
    font-weight: 700;
    color: #7ec850;
    letter-spacing: -0.02em;
    margin-bottom: 0.1rem;
}
.dash-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: #5a7a4a;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
}

/* Metric cards */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.5rem;
}
.metric-card {
    background: #162216;
    border: 1px solid #2a3d20;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
}
.metric-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    color: #5a7a4a;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.3rem;
}
.metric-value {
    font-family: 'Space Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--accent);
    line-height: 1;
}
.metric-unit {
    font-size: 0.7rem;
    color: #5a7a4a;
    margin-left: 0.2rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0a120a;
    border-right: 1px solid #1e2e18;
}
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #7ec850;
    font-family: 'Space Mono', monospace;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Buttons */
.stDownloadButton > button {
    background: #1e3318 !important;
    color: #7ec850 !important;
    border: 1px solid #3a5e28 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.05em !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background: #2a4a20 !important;
    border-color: #7ec850 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #162216;
    border-radius: 8px;
    gap: 0;
    padding: 2px;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: #5a7a4a;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.4rem 1rem;
    border-radius: 6px;
}
.stTabs [aria-selected="true"] {
    background: #2a4a20 !important;
    color: #7ec850 !important;
}

/* Checkbox label color */
.stCheckbox label {
    color: #d4e8c2 !important;
    font-size: 0.85rem !important;
}

/* Slider */
.stSlider label {
    color: #7ec850 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* Select box */
.stSelectbox label, .stMultiSelect label {
    color: #7ec850 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* Status chip */
.fan-on  { background:#1a3a1a; color:#7ec850; border:1px solid #3a7a2a; padding:2px 10px; border-radius:20px; font-family:'Space Mono',monospace; font-size:0.75rem; display:inline-block; }
.fan-off { background:#2a1a0a; color:#c88a3a; border:1px solid #7a5020; padding:2px 10px; border-radius:20px; font-family:'Space Mono',monospace; font-size:0.75rem; display:inline-block; }

/* Warning / info box */
.warn-box { background:#1a1200; border:1px solid #4a3a00; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#c8b050; }
.info-box { background:#0a1a2a; border:1px solid #1a3a5a; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#5ab0e8; }

/* Divider */
hr { border-color: #1e2e18 !important; margin: 1rem 0 !important; }

/* Data table */
.stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Column config ─────────────────────────────────────────────────────────────
TIMESTAMP_COL = "Timestamp"

NUMERIC_COLS = {
    "O2_raw_%":   {"label": "O₂ Raw",        "unit": "%",    "color": "#4fc3f7", "accent": "#4fc3f7"},
    "O2_avg_%":   {"label": "O₂ Avg",        "unit": "%",    "color": "#7ec850", "accent": "#7ec850"},
    "CO2_ppm":    {"label": "CO₂",           "unit": "ppm",  "color": "#ff8a65", "accent": "#ff8a65"},
    "CO2_%":      {"label": "CO₂",           "unit": "%",    "color": "#ffb74d", "accent": "#ffb74d"},
    "Temp_C":     {"label": "Temp (probe)",  "unit": "°C",   "color": "#ef5350", "accent": "#ef5350"},
    "RTC_C":      {"label": "Temp (RTC)",    "unit": "°C",   "color": "#ec407a", "accent": "#ec407a"},
    # older firmware columns
    "Hz":         {"label": "Fan Speed",     "unit": "Hz",   "color": "#ab47bc", "accent": "#ab47bc"},
    "Step":       {"label": "Fan Step",      "unit": "",     "color": "#26c6da", "accent": "#26c6da"},
    # newer firmware columns
    "CycleSec":   {"label": "Cycle Time",    "unit": "s",    "color": "#ab47bc", "accent": "#ab47bc"},
    "CycleNum":   {"label": "Cycle #",       "unit": "",     "color": "#26c6da", "accent": "#26c6da"},
    "Spikes":     {"label": "O₂ Spikes",     "unit": "",     "color": "#ffa726", "accent": "#ffa726"},
    "I2C_err":    {"label": "I2C Errors",    "unit": "",     "color": "#ef5350", "accent": "#ef5350"},
}

CATEGORICAL_COLS = ["FanState"]  # newer firmware; gracefully absent in older CSVs

# ── Helpers ───────────────────────────────────────────────────────────────────
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


def detect_columns(df):
    present_numeric = [c for c in NUMERIC_COLS if c in df.columns]
    present_cat = [c for c in CATEGORICAL_COLS if c in df.columns]
    return present_numeric, present_cat


def apply_rolling(df, cols, window):
    df_out = df.copy()
    for col in cols:
        if col in df_out.columns:
            df_out[f"{col}_roll"] = df_out[col].rolling(window=window, min_periods=1, center=True).mean()
    return df_out


def flag_anomalies(series, threshold=3.0):
    """Return boolean mask of outliers using rolling z-score."""
    roll_mean = series.rolling(30, min_periods=5, center=True).mean()
    roll_std  = series.rolling(30, min_periods=5, center=True).std()
    z = (series - roll_mean) / (roll_std + 1e-9)
    return z.abs() > threshold


def build_plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#111a11",
        font=dict(family="DM Sans, sans-serif", color="#d4e8c2", size=11),
        xaxis=dict(gridcolor="#1e2e18", linecolor="#2a3d20", tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#1e2e18", linecolor="#2a3d20", tickfont=dict(size=10)),
        legend=dict(bgcolor="rgba(15,26,15,0.8)", bordercolor="#2a3d20", borderwidth=1,
                    font=dict(size=10, family="Space Mono, monospace")),
        margin=dict(l=50, r=20, t=40, b=40),
        hovermode="x unified",
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Upload")
    uploaded = st.file_uploader("Drop your CSV here", type=["csv"], label_visibility="collapsed")
    st.markdown("---")

    if uploaded:
        df_raw = load_csv(uploaded)
        numeric_cols, cat_cols = detect_columns(df_raw)

        st.markdown("### ⏱ Time Range")
        t_min = df_raw[TIMESTAMP_COL].min()
        t_max = df_raw[TIMESTAMP_COL].max()
        total_hours = max((t_max - t_min).total_seconds() / 3600, 1)

        range_mode = st.radio("Select by", ["Last N hours", "Last N days", "Full range"],
                               label_visibility="collapsed")
        if range_mode == "Last N hours":
            n_hours = st.slider("Hours", 1, min(int(total_hours), 720), min(24, int(total_hours)))
            t_start = t_max - timedelta(hours=n_hours)
        elif range_mode == "Last N days":
            n_days = st.slider("Days", 1, max(1, int(total_hours // 24)), min(3, max(1, int(total_hours // 24))))
            t_start = t_max - timedelta(days=n_days)
        else:
            t_start = t_min

        df = df_raw[df_raw[TIMESTAMP_COL] >= t_start].copy()

        st.markdown("---")
        st.markdown("### 📊 Variables")
        default_sel = [c for c in ["O2_avg_%", "CO2_%", "Temp_C"] if c in numeric_cols]
        selected_cols = []
        for col in numeric_cols:
            info = NUMERIC_COLS[col]
            checked = col in default_sel
            if st.checkbox(f"{info['label']} ({info['unit']})", value=checked, key=col):
                selected_cols.append(col)

        st.markdown("---")
        st.markdown("### 〰 Rolling Average")
        rolling_window = st.slider("Window (rows)", 1, 120, 10)
        show_raw       = st.checkbox("Show raw data too", value=False)

        st.markdown("---")
        st.markdown("### ⚠️ Anomaly Overlay")
        show_anomalies = st.checkbox("Highlight O₂ spikes", value=True)

    else:
        df = None
        selected_cols = []
        rolling_window = 10
        show_raw = False
        show_anomalies = True

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown('<div class="dash-header">🌿 Compost Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="dash-sub">Arduino Sensor Dashboard — O₂ · CO₂ · Temperature · Fan Control</div>', unsafe_allow_html=True)

if df is None:
    st.markdown("""
    <div class="info-box">
    👈 Upload a CSV from your Arduino to get started.<br>
    Expected columns: <code>Timestamp, O2_raw_%, O2_avg_%, CO2_ppm, CO2_%, Temp_C, RTC_C, FanState, CycleSec, CycleNum, Spikes, I2C_err</code>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Metrics row ───────────────────────────────────────────────────────────────
key_metrics = [
    ("O2_avg_%",  "#7ec850"),
    ("CO2_ppm",   "#ff8a65"),
    ("Temp_C",    "#ef5350"),
    ("RTC_C",     "#ec407a"),
]

metrics_html = '<div class="metric-grid">'
for col, accent in key_metrics:
    if col in df.columns:
        last_val = df[col].dropna().iloc[-1] if not df[col].dropna().empty else float("nan")
        info = NUMERIC_COLS[col]
        metrics_html += f"""
        <div class="metric-card" style="--accent:{accent}">
            <div class="metric-label">{info['label']}</div>
            <div class="metric-value">{last_val:.1f}<span class="metric-unit">{info['unit']}</span></div>
        </div>"""

# Fan state
if "FanState" in df.columns:
    last_fan = df["FanState"].dropna().iloc[-1] if not df["FanState"].dropna().empty else "?"
    chip_class = "fan-on" if str(last_fan).upper() == "ON" else "fan-off"
    metrics_html += f"""
    <div class="metric-card" style="--accent:#7ec850">
        <div class="metric-label">Fan</div>
        <div style="margin-top:4px"><span class="{chip_class}">{last_fan}</span></div>
    </div>"""
elif "Hz" in df.columns:
    last_hz = df["Hz"].dropna().iloc[-1] if not df["Hz"].dropna().empty else 0
    chip_class = "fan-on" if float(last_hz) > 0 else "fan-off"
    metrics_html += f"""
    <div class="metric-card" style="--accent:#ab47bc">
        <div class="metric-label">Fan Speed</div>
        <div style="margin-top:4px"><span class="{chip_class}">{last_hz} Hz</span></div>
    </div>"""

# Row count
metrics_html += f"""
<div class="metric-card" style="--accent:#5a7a4a">
    <div class="metric-label">Rows</div>
    <div class="metric-value" style="font-size:1.1rem">{len(df):,}</div>
</div>"""
metrics_html += "</div>"
st.markdown(metrics_html, unsafe_allow_html=True)

# ── Anomaly warnings ──────────────────────────────────────────────────────────
if "O2_avg_%" in df.columns and show_anomalies:
    mask = flag_anomalies(df["O2_avg_%"])
    n_anom = mask.sum()
    if n_anom > 0:
        st.markdown(f'<div class="warn-box">⚠️ <b>{n_anom} anomalous O₂ readings</b> detected in this time window (rolling z-score > 3σ). Shown as red markers on the chart.</div>', unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Time Series", "🔍 Data Preview", "💾 Download"])

# ─────────────────────── TAB 1: CHART ────────────────────────────────────────
with tab1:
    if not selected_cols:
        st.info("Select at least one variable in the sidebar.")
    else:
        df_plot = apply_rolling(df, selected_cols, rolling_window)
        theme = build_plotly_theme()

        # Separate O2/CO2 vs Temp to allow dual-axis grouping
        temp_cols   = [c for c in selected_cols if "Temp" in c or "RTC" in c]
        sensor_cols = [c for c in selected_cols if c not in temp_cols]

        has_two_axes = bool(sensor_cols) and bool(temp_cols)
        rows = 2 if has_two_axes else 1

        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            subplot_titles=(["Sensors", "Temperature"] if has_two_axes else None),
        )

        def add_traces(cols_list, row):
            for col in cols_list:
                info = NUMERIC_COLS[col]
                color = info["color"]
                roll_col = f"{col}_roll"

                if show_raw and col in df_plot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_plot[TIMESTAMP_COL], y=df_plot[col],
                        name=f"{info['label']} raw",
                        line=dict(color=color, width=0.8, dash="dot"),
                        opacity=0.35,
                        hovertemplate=f"<b>{info['label']}</b>: %{{y:.2f}} {info['unit']}<extra></extra>",
                    ), row=row, col=1)

                if roll_col in df_plot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_plot[TIMESTAMP_COL], y=df_plot[roll_col],
                        name=f"{info['label']}",
                        line=dict(color=color, width=2),
                        hovertemplate=f"<b>{info['label']}</b>: %{{y:.2f}} {info['unit']}<extra></extra>",
                    ), row=row, col=1)

                # Anomaly markers for O2
                if show_anomalies and col in ("O2_raw_%", "O2_avg_%") and col in df_plot.columns:
                    mask = flag_anomalies(df_plot[col])
                    if mask.any():
                        fig.add_trace(go.Scatter(
                            x=df_plot.loc[mask, TIMESTAMP_COL],
                            y=df_plot.loc[mask, col],
                            mode="markers",
                            name="⚠ Spike",
                            marker=dict(color="#ff1744", size=7, symbol="x"),
                            hovertemplate="<b>⚠ O₂ Spike</b>: %{y:.2f}%<extra></extra>",
                        ), row=row, col=1)

        add_traces(sensor_cols, 1)
        if has_two_axes:
            add_traces(temp_cols, 2)

        # FanState as background shading on row 1
        # Support both newer firmware (FanState) and older (Step/Hz)
        if "FanState" in df_plot.columns and len(df_plot) > 1:
            fan_on = df_plot["FanState"].str.upper() == "ON"
        elif "Hz" in df_plot.columns and len(df_plot) > 1:
            fan_on = df_plot["Hz"].fillna(0) > 0
        else:
            fan_on = None
            in_block = False
            block_start = None
            for i, (ts, is_on) in enumerate(zip(df_plot[TIMESTAMP_COL], fan_on)):
                if is_on and not in_block:
                    block_start = ts
                    in_block = True
                elif not is_on and in_block:
                    fig.add_vrect(x0=block_start, x1=ts, fillcolor="#7ec850",
                                  opacity=0.07, layer="below", line_width=0, row=1, col=1)
                    in_block = False
            if in_block:
                fig.add_vrect(x0=block_start, x1=df_plot[TIMESTAMP_COL].iloc[-1],
                              fillcolor="#7ec850", opacity=0.07, layer="below", line_width=0, row=1, col=1)

        fig.update_layout(
            height=480 if not has_two_axes else 600,
            **theme,
        )
        fig.update_xaxes(gridcolor="#1e2e18", linecolor="#2a3d20")
        fig.update_yaxes(gridcolor="#1e2e18", linecolor="#2a3d20")

        st.plotly_chart(fig, use_container_width=True)

        if "FanState" in df_plot.columns:
            st.markdown('<span style="color:#5a7a4a;font-size:0.75rem">🟢 Green shading = Fan ON periods</span>', unsafe_allow_html=True)

# ─────────────────────── TAB 2: DATA PREVIEW ─────────────────────────────────
with tab2:
    st.markdown(f'<span style="color:#5a7a4a;font-size:0.8rem;font-family:Space Mono">Showing {len(df):,} rows · {t_start.strftime("%Y-%m-%d %H:%M")} → {t_max.strftime("%Y-%m-%d %H:%M")}</span>', unsafe_allow_html=True)

    # Summary stats
    with st.expander("📊 Summary Statistics"):
        show_stat_cols = [c for c in selected_cols if c in df.columns]
        if show_stat_cols:
            stats = df[show_stat_cols].describe().T
            stats.index = [NUMERIC_COLS.get(c, {}).get("label", c) for c in stats.index]
            st.dataframe(stats.style.format("{:.3f}"), use_container_width=True)

    st.dataframe(
        df.reset_index(drop=True),
        use_container_width=True,
        height=400,
    )

# ─────────────────────── TAB 3: DOWNLOAD ─────────────────────────────────────
with tab3:
    st.markdown("#### Download filtered data")

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    fname = f"compost_filtered_{t_start.strftime('%Y%m%d_%H%M')}_{t_max.strftime('%Y%m%d_%H%M')}.csv"

    st.download_button(
        label="⬇ Download CSV",
        data=csv_bytes,
        file_name=fname,
        mime="text/csv",
    )

    st.markdown(f"""
    <div class="info-box">
    <b>File:</b> {fname}<br>
    <b>Rows:</b> {len(df):,}<br>
    <b>Range:</b> {t_start.strftime('%Y-%m-%d %H:%M')} → {t_max.strftime('%Y-%m-%d %H:%M')}<br>
    <b>Columns:</b> {', '.join(df.columns.tolist())}
    </div>
    """, unsafe_allow_html=True)
