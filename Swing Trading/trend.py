"""Market Breadth Dashboard: % of stocks above their 50-day moving average.

Expects a parquet file with columns: Date, Ticker, Open, High, Low, Close, Volume.

Run:
    pip install streamlit plotly pandas pyarrow
    streamlit run breadth_app.py
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Market Breadth", layout="wide")

GREEN, RED, BLUE = "#2e9e6b", "#d6455d", "#3b82f6"


@st.cache_data(show_spinner="Loading data...")
def load(path: str, mtime: float):
    df = pd.read_parquet(path, columns=["Date", "Ticker", "Close"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.drop_duplicates(["Date", "Ticker"], keep="last")
    return df.pivot(index="Date", columns="Ticker", values="Close").sort_index()


# ---------- Sidebar ----------
st.sidebar.title("Settings")
path = st.sidebar.text_input("Parquet file path", "C:\\Trading_algorithm\\Swing Trading\\nifty_500_stocks_data.parquet")
if not os.path.exists(path):
    st.error(f"File not found: {path}")
    st.stop()
ma_len = st.sidebar.number_input("Moving average (days)", 10, 200, 50)

close = load(path, os.path.getmtime(path))
sma = close.rolling(ma_len).mean()
valid = sma.notna() & close.notna()
above = (close > sma) & valid
below = (close <= sma) & valid
breadth = pd.DataFrame({"Above": above.sum(axis=1), "Below": below.sum(axis=1)})
breadth["Total"] = breadth.Above + breadth.Below
breadth = breadth[breadth.Total > 0]
breadth["Pct"] = 100 * breadth.Above / breadth.Total

day = st.sidebar.date_input("Date", breadth.index[-1].date(),
                            min_value=breadth.index[0].date(), max_value=breadth.index[-1].date())
d = breadth.index[breadth.index <= pd.Timestamp(day)][-1]  # nearest trading day

st.title("Market Breadth Dashboard")
st.caption(f"{close.shape[1]} stocks loaded | {ma_len}-day MA | showing {d:%d %b %Y}")

tab1, tab2 = st.tabs(["Overall picture", "Individual stock"])

# ---------- Tab 1: overall ----------
with tab1:
    row = breadth.loc[d]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Above {ma_len}DMA", int(row.Above))
    c2.metric(f"Below {ma_len}DMA", int(row.Below))
    c3.metric("% above", f"{row.Pct:.1f}%")
    prev = breadth.Pct.shift(5).loc[d]
    c4.metric("Change vs 5 days ago", f"{row.Pct - prev:+.1f} pts" if pd.notna(prev) else "n/a")

    left, right = st.columns([1, 2])
    with left:
        fig = go.Figure(go.Pie(labels=["Above", "Below"], values=[row.Above, row.Below], hole=0.6,
                               marker_colors=[GREEN, RED], sort=False))
        fig.update_layout(height=340, margin=dict(t=10, b=10), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = go.Figure(go.Scatter(x=breadth.index, y=breadth.Pct, line=dict(color=BLUE), name="% above"))
        for y, col in [(80, RED), (50, "gray"), (20, GREEN)]:
            fig.add_hline(y=y, line_dash="dot", line_color=col)
        fig.add_vline(x=d, line_color="orange")
        fig.update_layout(height=340, margin=dict(t=30, b=10), title=f"% of stocks above {ma_len}DMA over time",
                          yaxis=dict(range=[0, 100], title="%"))
        st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_bar(x=breadth.index, y=breadth.Above, name="Above", marker_color=GREEN)
    fig.add_bar(x=breadth.index, y=-breadth.Below, name="Below", marker_color=RED)
    fig.update_layout(barmode="relative", height=300, margin=dict(t=30, b=10),
                      title="Daily count above (up) vs below (down)")
    st.plotly_chart(fig, use_container_width=True)

    snap = pd.DataFrame({"Close": close.loc[d], f"{ma_len}DMA": sma.loc[d]}).dropna()
    snap["Distance %"] = 100 * (snap.Close / snap[f"{ma_len}DMA"] - 1)
    snap["Status"] = snap["Distance %"].apply(lambda x: "Above" if x > 0 else "Below")
    snap = snap.sort_values("Distance %", ascending=False)
    fig = go.Figure(go.Bar(x=snap.index, y=snap["Distance %"],
                           marker_color=[GREEN if v > 0 else RED for v in snap["Distance %"]]))
    fig.update_layout(height=320, margin=dict(t=30, b=10), title="Distance from moving average (%) by stock")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(snap.round(2), use_container_width=True)

# ---------- Tab 2: single stock ----------
with tab2:
    sym = st.selectbox("Stock", list(close.columns))
    s = pd.DataFrame({"Close": close[sym], "MA": sma[sym]}).dropna(subset=["Close"])
    s["Above"] = s.Close > s.MA
    cross = s.Above.astype(int).diff()
    up, dn = s[(cross == 1)], s[(cross == -1)]

    fig = go.Figure()
    fig.add_scatter(x=s.index, y=s.Close, name="Close", line=dict(color=BLUE))
    fig.add_scatter(x=s.index, y=s.MA, name=f"{ma_len}DMA", line=dict(color="orange", dash="dash"))
    fig.add_scatter(x=up.index, y=up.Close, mode="markers", name="Crossed above",
                    marker=dict(color=GREEN, size=9, symbol="triangle-up"))
    fig.add_scatter(x=dn.index, y=dn.Close, mode="markers", name="Crossed below",
                    marker=dict(color=RED, size=9, symbol="triangle-down"))
    fig.add_vline(x=d, line_color="gray", line_dash="dot")
    fig.update_layout(height=450, margin=dict(t=30, b=10), title=sym)
    st.plotly_chart(fig, use_container_width=True)

    valid_s = s.dropna(subset=["MA"])
    last = valid_s.loc[:d].iloc[-1]
    streak = (valid_s.loc[:d].Above != valid_s.loc[:d].Above.iloc[-1]).cumsum()
    streak_len = int((streak == streak.iloc[-1]).sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Above" if last.Above else "Below")
    m2.metric("Distance from MA", f"{100 * (last.Close / last.MA - 1):+.2f}%")
    m3.metric("Current streak (days)", streak_len)
    m4.metric("% of days above MA", f"{100 * valid_s.Above.mean():.0f}%")

    st.subheader("Is this stock helping or hurting breadth?")
    st.caption("Share of all stocks above their MA vs this stock's own state (green band = stock above MA)")
    fig = go.Figure(go.Scatter(x=breadth.index, y=breadth.Pct, line=dict(color="gray"), name="Market % above"))
    band = valid_s.Above.astype(int) * 100
    fig.add_bar(x=band.index, y=band, marker_color=GREEN, opacity=0.15, name=f"{sym} above MA")
    fig.update_layout(height=280, margin=dict(t=10, b=10), yaxis=dict(range=[0, 100]))
    st.plotly_chart(fig, use_container_width=True)