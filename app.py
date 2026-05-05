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

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0d1117; color: #cdd9e5; }
.main .block-container { padding-top: 1.5rem; max-width: 1400px; }
.dash-header { font-family:'IBM Plex Mono',monospace; font-size:1.5rem; font-weight:600; color:#58a6ff; margin-bottom:0.1rem; }
.dash-sub { font-size:0.8rem; color:#484f58; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1.5rem; }
.metric-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:0.6rem; margin-bottom:1.5rem; }
.metric-card { background:#161b22; border:1px solid #21262d; border-radius:8px; padding:0.8rem 1rem; border-top:2px solid var(--accent); }
.metric-label { font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:#484f58; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.3rem; }
.metric-value { font-family:'IBM Plex Mono',monospace; font-size:1.3rem; font-weight:600; color:var(--accent); line-height:1; }
.metric-unit { font-size:0.65rem; color:#484f58; margin-left:0.15rem; }
section[data-testid="stSidebar"] { background-color:#0d1117; border-right:1px solid #21262d; }
section[data-testid="stSidebar"] label { color:#8b949e !important; font-size:0.8rem !important; }
.stDownloadButton > button { background:#161b22 !important; color:#58a6ff !important; border:1px solid #30363d !important; font-family:'IBM Plex Mono',monospace !important; font-size:0.75rem !important; border-radius:6px !important; }
.stTabs [data-baseweb="tab-list"] { background:#161b22; border-radius:6px; gap:0; padding:2px; }
.stTabs [data-baseweb="tab"] { font-family:'IBM Plex Mono',monospace; font-size:0.68rem; color:#484f58; text-transform:uppercase; letter-spacing:0.05em; padding:0.35rem 0.9rem; border-radius:5px; }
.stTabs [aria-selected="true"] { background:#1c2128 !important; color:#58a6ff !important; }
.stCheckbox label { color:#cdd9e5 !important; font-size:0.83rem !important; }
.chip-on  { background:#0d2818; color:#3fb950; border:1px solid #238636; padding:1px 9px; border-radius:20px; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; display:inline-block; }
.chip-off { background:#1f1208; color:#d29922; border:1px solid #9e6a03; padding:1px 9px; border-radius:20px; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; display:inline-block; }
.info-box { background:#0d1f38; border:1px solid #1f4068; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#58a6ff; }
.warn-box { background:#1f1208; border:1px solid #9e6a03; border-radius:8px; padding:0.7rem 1rem; margin:0.5rem 0; font-size:0.82rem; color:#d29922; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
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

DEFAULT_ON = {"O2_avg_%", "CO2_ppm", "Temp_C"}

# ── Helper functions ──────────────────────────────────────────────────────────
def load_csv(file):
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
    """
    Detect the best column to use for fan ON/OFF shading.

    Preference order:
    1. FanState, if your Arduino logs ON/OFF text.
    2. Hz, if your Arduino logs fan speed/frequency.
    3. Step, if your Arduino logs control step.
    """
    for c in ["FanState", "Hz", "Step"]:
        if c in df.columns:
            return c
    return None


def get_fan_on_mask(df, fan_col):
    """
    Return True when the fan is ON and False when the fan is OFF.

    This version is more robust than the original because it can handle:
    - FanState values: ON, OFF, RUNNING, TRUE, FALSE
    - Hz values: 15, 20, 0
    - Step values: 1, 2, 0
    - Boolean-style values: 1/0, yes/no, high/low
    """
    if fan_col is None or fan_col not in df.columns:
        return pd.Series(False, index=df.index)

    values = df[fan_col]

    # Try numeric interpretation first: useful for Hz, Step, 1/0, etc.
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().sum() > 0:
        return numeric.fillna(0) > 0

    # If values are not numeric, interpret text.
    text = values.astype(str).str.strip().str.upper()
    return text.isin(["ON", "RUN", "RUNNING", "TRUE", "1", "YES", "HIGH"])


def get_fan_blocks(df, fan_col):
    """
    Convert fan ON/OFF readings into continuous ON time blocks.

    Returns a list like:
    [(start_time_1, end_time_1), (start_time_2, end_time_2)]
    """
    if df.empty or fan_col is None or fan_col not in df.columns or TIMESTAMP_COL not in df.columns:
        return []

    temp = df[[TIMESTAMP_COL, fan_col]].copy()
    temp[TIMESTAMP_COL] = pd.to_datetime(temp[TIMESTAMP_COL], errors="coerce")
    temp = temp.dropna(subset=[TIMESTAMP_COL])
    temp = temp.sort_values(TIMESTAMP_COL).reset_index(drop=True)

    if temp.empty:
        return []

    fan_mask = get_fan_on_mask(temp, fan_col).fillna(False).astype(bool)
    times = temp[TIMESTAMP_COL].tolist()

    blocks = []
    in_block = False
    block_start = None

    for ts, is_on in zip(times, fan_mask):
        if is_on and not in_block:
            block_start = ts
            in_block = True
        elif not is_on and in_block:
            blocks.append((block_start, ts))
            in_block = False

    # If the file ends while the fan is still ON, close the block at the final timestamp.
    if in_block:
        blocks.append((block_start, times[-1]))

    return blocks


def apply_rolling(series, window):
    if window <= 1:
        return series
    return series.rolling(window=window, min_periods=1, center=True).mean()


def flag_anomalies(series, threshold=3.0):
    roll_mean = series.rolling(30, min_periods=5, center=True).mean()
    roll_std = series.rolling(30, min_periods=5, center=True).std()
    z = (series - roll_mean) / (roll_std + 1e-9)
    return z.abs() > threshold


def add_fan_vrects(fig, df, fan_col):
    """
    Draw fan-ON shaded bands across all subplot rows.

    This replaces the old xref/yref add_shape approach. The old approach can shade
    too much of the plot when subplot axis names do not match exactly. Plotly's
    add_vrect with row='all' is much more reliable for shared-x subplots.
    """
    blocks = get_fan_blocks(df, fan_col)

    for t0, t1 in blocks:
        # Skip zero-width blocks.
        if pd.isna(t0) or pd.isna(t1) or t0 == t1:
            continue

        fig.add_vrect(
            x0=t0,
            x1=t1,
            fillcolor="rgba(88,166,255,0.12)",
            opacity=1,
            line_width=0,
            layer="below",
            row="all",
            col=1,
        )

    return fig


def add_fan_legend_trace(fig, n_rows):
    """
    Add a fake trace so Fan ON appears in the legend.
    """
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="rgba(88,166,255,0.35)", symbol="square"),
            name="Fan ON",
            showlegend=True,
        ),
        row=n_rows,
        col=1,
    )
    return fig


def plotly_base():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0d1117",
        font=dict(family="IBM Plex Sans, sans-serif", color="#8b949e", size=11),
        legend=dict(
            bgcolor="rgba(13,17,23,0.9)", bordercolor="#30363d", borderwidth=1,
            font=dict(size=10, family="IBM Plex Mono, monospace", color="#cdd9e5"),
        ),
        margin=dict(l=60, r=20, t=30, b=40),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#30363d",
            font=dict(color="#cdd9e5", size=11),
        ),
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**📂 Upload**")
    uploaded = st.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")

    if uploaded:
        df_raw = load_csv(uploaded)

        if TIMESTAMP_COL not in df_raw.columns or df_raw.empty:
            st.error(f"The file must contain a valid '{TIMESTAMP_COL}' column.")
            st.stop()

        fan_col = detect_fan_col(df_raw)
        present_numeric = [c for c in NUMERIC_COLS if c in df_raw.columns]

        st.markdown("---")
        st.markdown("**⏱ Time Range**")
        t_min = df_raw[TIMESTAMP_COL].min()
        t_max = df_raw[TIMESTAMP_COL].max()
        total_hours = max((t_max - t_min).total_seconds() / 3600, 1)

        range_mode = st.radio(
            "Range mode",
            ["Last N hours", "Last N days", "Full range"],
            label_visibility="collapsed",
        )

if range_mode == "Last N hours":
            n_h = st.slider("Hours", 1, min(int(total_hours), 720), min(24, int(total_hours)))
            t_start = t_max - timedelta(hours=n_h)
        elif range_mode == "Last N days":
            max_days = max(1, int(total_hours // 24))
            n_d = st.slider("Days", 1, max_days, min(3, max_days))
            t_start = t_max - timedelta(days=n_d)
        else:
            t_start = t_min

        st.markdown("**✂️ Fine-tune Range**")
        col_a, col_b = st.columns(2)
        with col_a:
            date_start = st.date_input("From", value=t_start.date(),
                                       min_value=t_min.date(), max_value=t_max.date())
            time_start = st.time_input("", value=t_start.time(), key="time_start",
                                       label_visibility="collapsed")
        with col_b:
            date_end = st.date_input("To", value=t_max.date(),
                                     min_value=t_min.date(), max_value=t_max.date())
            time_end = st.time_input("", value=t_max.time(), key="time_end",
                                     label_visibility="collapsed")

        import datetime
        t_start = pd.Timestamp(datetime.datetime.combine(date_start, time_start))
        t_end   = pd.Timestamp(datetime.datetime.combine(date_end,   time_end))

        df = df_raw[
            (df_raw[TIMESTAMP_COL] >= t_start) &
            (df_raw[TIMESTAMP_COL] <= t_end)
        ].copy().reset_index(drop=True)

        st.markdown("---")
        st.markdown("**📊 Variables**")
        selected_cols = [
            c for c in present_numeric
            if st.checkbox(
                f"{NUMERIC_COLS[c]['label']} ({NUMERIC_COLS[c]['unit']})"
                if NUMERIC_COLS[c]["unit"] else NUMERIC_COLS[c]["label"],
                value=(c in DEFAULT_ON),
                key=c,
            )
        ]

        st.markdown("---")
        st.markdown("**〰 Rolling Average**")
        rolling_window = st.slider(
            "Window (rows) — 1 = raw",
            1, 120, 1,
            help="1 = raw data. Higher = smoother. At 10s intervals: window 6 ≈ 1 min average.",
        )
        show_raw_under = False
        if rolling_window > 1:
            show_raw_under = st.checkbox("Show raw underneath (faint)", value=False)

        st.markdown("---")
        st.markdown("**⚙️ Options**")
        show_anomalies = st.checkbox("Flag O₂ anomalies", value=True)
        show_fan_band = st.checkbox("Show fan ON bands", value=True)

        # Give the user a way to override which column controls fan shading.
        if show_fan_band:
            candidate_fan_cols = [c for c in ["FanState", "Hz", "Step"] if c in df.columns]
            if candidate_fan_cols:
                default_index = candidate_fan_cols.index(fan_col) if fan_col in candidate_fan_cols else 0
                fan_col = st.selectbox(
                    "Fan shading column",
                    candidate_fan_cols,
                    index=default_index,
                    help="Use FanState if available. Otherwise use Hz if fan ON means Hz > 0.",
                )

                fan_mask_debug = get_fan_on_mask(df, fan_col)
                fan_counts = fan_mask_debug.value_counts(dropna=False)
                fan_blocks = get_fan_blocks(df, fan_col)

                st.caption("Fan detection check")
                st.write(fan_counts)
                st.caption(f"Fan ON blocks detected: {len(fan_blocks)}")

                if len(fan_blocks) == 1 and fan_mask_debug.all():
                    st.warning(
                        "The selected fan column is being interpreted as always ON, "
                        "so the whole plot will be shaded. Try selecting FanState instead of Hz/Step, "
                        "or check whether the column contains any OFF/0 values in this time range."
                    )
            else:
                fan_col = None
                st.warning("No fan column found. Expected one of: FanState, Hz, Step.")

    else:
        df = None
        selected_cols = []
        rolling_window = 1
        show_raw_under = False
        show_anomalies = True
        show_fan_band = True
        fan_col = None
        t_start = None
        t_max = None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="dash-header">🌱 Compost Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="dash-sub">Arduino · O₂ · CO₂ · Temperature · Fan</div>', unsafe_allow_html=True)

if df is None:
    st.markdown("""
    <div class="info-box">
    👈 Upload a CSV exported from your Arduino to get started.<br>
    Supports: <code>Timestamp, O2_raw_%, O2_avg_%, CO2_ppm, CO2_%, Temp_C, RTC_C, Hz, Step, FanState, Spikes, I2C_err</code>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Metric cards ──────────────────────────────────────────────────────────────
key_metrics = [
    ("O2_avg_%", "#58a6ff"),
    ("CO2_ppm", "#ffa657"),
    ("Temp_C", "#ff7b72"),
    ("RTC_C", "#ffa198"),
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

if fan_col and fan_col in df.columns:
    fan_series = df[fan_col].dropna()
    if not fan_series.empty:
        last_fan = fan_series.iloc[-1]
        is_on = bool(get_fan_on_mask(pd.DataFrame({fan_col: [last_fan]}), fan_col).iloc[0])
        chip_class = "chip-on" if is_on else "chip-off"
        label = "ON" if is_on else "OFF"
        suffix = f" · {last_fan} Hz" if fan_col == "Hz" else f" · {last_fan}"
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

# ── Anomaly warning ───────────────────────────────────────────────────────────
if "O2_avg_%" in df.columns and show_anomalies:
    n_anom = int(flag_anomalies(df["O2_avg_%"]).sum())
    if n_anom > 0:
        st.markdown(
            f'<div class="warn-box">⚠️ <b>{n_anom} anomalous O₂ readings</b> in this window '
            f'(rolling z-score > 3σ) — shown as orange markers.</div>',
            unsafe_allow_html=True,
        )

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈  Time Series", "🔍  Data Preview", "💾  Download"])

# ── TAB 1: Chart ──────────────────────────────────────────────────────────────
with tab1:
    if not selected_cols:
        st.info("Select at least one variable in the sidebar.")
    else:
        # One subplot per variable
        n_rows = len(selected_cols)
        row_heights = [1.0] * n_rows
        total = sum(row_heights)
        row_heights = [r / total for r in row_heights]

        subplot_titles = [
            f"{NUMERIC_COLS[c]['label']} ({NUMERIC_COLS[c]['unit']})"
            if NUMERIC_COLS[c]["unit"] else NUMERIC_COLS[c]["label"]
            for c in selected_cols
        ]

        fig = make_subplots(
            rows=n_rows,
            cols=1,
            shared_xaxes=True,
            row_heights=row_heights,
            vertical_spacing=0.06,
            subplot_titles=subplot_titles,
        )

        # Add fan ON bands as vertical shading across all subplots.
        # Add after make_subplots and before/after traces both works, because row='all' targets subplot grid.
        if show_fan_band and fan_col is not None and len(df) > 1:
            fig = add_fan_vrects(fig, df, fan_col)
            fig = add_fan_legend_trace(fig, n_rows)

        # Add one trace per variable on its own subplot
        for i, col in enumerate(selected_cols):
            row = i + 1
            info = NUMERIC_COLS[col]
            color = info["color"]
            y_raw = df[col]
            y_plot = apply_rolling(y_raw, rolling_window)

            # Faint raw underneath when smoothing
            if rolling_window > 1 and show_raw_under:
                fig.add_trace(
                    go.Scatter(
                        x=df[TIMESTAMP_COL],
                        y=y_raw,
                        name=f"{info['label']} raw",
                        line=dict(color=color, width=0.8),
                        opacity=0.2,
                        showlegend=False,
                        hoverinfo="skip",
                    ),
                    row=row,
                    col=1,
                )

            # Main line
            fig.add_trace(
                go.Scatter(
                    x=df[TIMESTAMP_COL],
                    y=y_plot,
                    name=info["label"],
                    line=dict(color=color, width=1.8),
                    hovertemplate=f"<b>{info['label']}</b>: %{{y:.2f}} {info['unit']}<extra></extra>",
                ),
                row=row,
                col=1,
            )

            # Anomaly markers for O2
            if show_anomalies and col in ("O2_raw_%", "O2_avg_%"):
                mask = flag_anomalies(y_raw)
                if mask.any():
                    fig.add_trace(
                        go.Scatter(
                            x=df.loc[mask, TIMESTAMP_COL],
                            y=y_raw[mask],
                            mode="markers",
                            name="⚠ O₂ spike",
                            marker=dict(
                                color="#f0883e",
                                size=8,
                                symbol="x-thin",
                                line=dict(width=2, color="#f0883e"),
                            ),
                            hovertemplate="<b>⚠ spike</b>: %{y:.2f}%<extra></extra>",
                            showlegend=(i == 0),
                        ),
                        row=row,
                        col=1,
                    )

            # Y-axis styling per subplot
            fig.update_yaxes(
                row=row,
                col=1,
                tickfont=dict(size=9, color="#8b949e"),
                gridcolor="#21262d",
                linecolor="#30363d",
                title_font=dict(size=10, color=color),
            )

        # Subplot title styling
        for annotation in fig.layout.annotations:
            annotation.font.size = 11
            annotation.font.color = "#8b949e"

        # Overall layout
        chart_height = max(300, 220 * n_rows)
        fig.update_layout(height=chart_height, **plotly_base())
        fig.update_xaxes(
            gridcolor="#21262d",
            linecolor="#30363d",
            tickfont=dict(size=10, color="#8b949e"),
        )

        st.plotly_chart(fig, use_container_width=True)

        if rolling_window > 1 and len(df) > 1:
            interval_sec = df[TIMESTAMP_COL].diff().median().total_seconds()
            smoothed_min = rolling_window * interval_sec / 60
            st.markdown(
                f'<span style="color:#484f58;font-size:0.74rem;font-family:IBM Plex Mono,monospace">'
                f'Rolling window = {rolling_window} rows ≈ {smoothed_min:.1f} min of smoothing '
                f'at your ~{interval_sec:.0f}s log interval. Set to 1 to see raw data.</span>',
                unsafe_allow_html=True,
            )

# ── TAB 2: Preview ────────────────────────────────────────────────────────────
with tab2:
    st.markdown(
        f'<span style="color:#484f58;font-size:0.78rem;font-family:IBM Plex Mono">'
        f'{len(df):,} rows · {t_start.strftime("%Y-%m-%d %H:%M")} → {t_max.strftime("%Y-%m-%d %H:%M")}</span>',
        unsafe_allow_html=True,
    )

    if fan_col and fan_col in df.columns:
        fan_mask = get_fan_on_mask(df, fan_col)
        fan_blocks = get_fan_blocks(df, fan_col)
        with st.expander("🌀 Fan detection debug"):
            st.write("Selected fan column:", fan_col)
            st.write("ON/OFF counts:")
            st.write(fan_mask.value_counts(dropna=False))
            st.write("First 10 fan ON blocks:")
            st.write(fan_blocks[:10])

    with st.expander("📊 Summary Statistics"):
        stat_cols = [c for c in selected_cols if c in df.columns]
        if stat_cols:
            stats = df[stat_cols].describe().T
            stats.index = [NUMERIC_COLS.get(c, {}).get("label", c) for c in stats.index]
            st.dataframe(stats.style.format("{:.3f}"), use_container_width=True)

    st.dataframe(df.reset_index(drop=True), use_container_width=True, height=420)

# ── TAB 3: Download ───────────────────────────────────────────────────────────
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
