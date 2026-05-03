# ==========================================
# INSTALL:
# pip install streamlit yfinance pandas numpy ta plotly
# RUN:
# streamlit run final_trading_engine.py
# ==========================================

import pandas as pd
import numpy as np
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as go

# =============================
# CONFIG
# =============================
MIN_SCORE = 25
FALLBACK_TOP_N = 10

# =============================
# LOAD CHARTINK STOCKS
# =============================
def load_stocks():
    df = pd.read_csv("chartink.csv")
    stocks = df["Symbol"].dropna().tolist()

    # Ensure NSE format
    return [s.strip().replace(".NS", "") + ".NS" for s in stocks]

# =============================
# SAFE DATA LOADER (CRITICAL FIX)
# =============================
def load_data(stock):
    df = yf.download(stock, period="6mo", interval="1d", progress=False)

    if df is None or df.empty:
        return None

    df = df.copy().reset_index()

    # FORCE CLEAN NUMERIC ARRAYS
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col].values.ravel(), errors="coerce")

    return df.dropna()

# =============================
# INDICATORS (FIXED 1D ISSUE)
# =============================
def add_indicators(df):
    df = df.copy()

    close = pd.Series(df["Close"].values.ravel())
    volume = pd.Series(df["Volume"].values.ravel())

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close)
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()

    # EMAs
    df["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()

    # Volume avg
    df["vol_avg"] = volume.rolling(20).mean()

    # VWAP
    df["vwap"] = (close * volume).cumsum() / volume.cumsum()

    return df.dropna()

# =============================
# SCORING ENGINE
# =============================
def score(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    s = 0
    reasons = []

    if last["rsi"] > prev["rsi"]:
        s += 10
        reasons.append("RSI rising")

    if last["rsi"] < 60:
        s += 5
        reasons.append("RSI healthy")

    if last["macd"] > last["signal"]:
        s += 15
        reasons.append("MACD bullish")

    if last["Close"] > last["ema20"]:
        s += 10
        reasons.append("Above EMA20")

    if last["ema20"] > last["ema50"]:
        s += 10
        reasons.append("Uptrend structure")

    if last["Close"] > last["vwap"]:
        s += 10
        reasons.append("Above VWAP")

    if last["Volume"] > last["vol_avg"]:
        s += 10
        reasons.append("Volume support")

    if last["Close"] > df["Close"].iloc[-5]:
        s += 10
        reasons.append("Momentum")

    return s, reasons

# =============================
# SCANNER
# =============================
def scan(stocks):
    results = []

    for stock in stocks:
        try:
            df = load_data(stock)

            if df is None or len(df) < 60:
                continue

            df = add_indicators(df)

            if len(df) < 2:
                continue

            s, reasons = score(df)

            if s >= MIN_SCORE:
                results.append({
                    "Stock": stock,
                    "Score": round(s, 2),
                    "Reasons": ", ".join(reasons)
                })

        except:
            continue

    results = sorted(results, key=lambda x: x["Score"], reverse=True)

    return results

# =============================
# CHART
# =============================
def plot(stock):
    df = load_data(stock)

    if df is None:
        return None, None, None, None

    df = add_indicators(df)

    entry = df["Close"].iloc[-1]
    support = df["Low"].rolling(20).min().iloc[-1]

    stop = support * 0.98
    target = entry + 2 * (entry - stop)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"]
    ))

    fig.add_trace(go.Scatter(x=df["Date"], y=df["ema20"], name="EMA20"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["ema50"], name="EMA50"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["vwap"], name="VWAP"))

    fig.add_hline(y=entry, annotation_text="Entry")
    fig.add_hline(y=target, annotation_text="Target")
    fig.add_hline(y=stop, annotation_text="Stop Loss")

    return fig, entry, target, stop

# =============================
# UI
# =============================
st.title("🚀 Final Smart Trading Engine (Crash-Free)")

stocks = load_stocks()

st.write(f"Loaded {len(stocks)} Chartink stocks")

if st.button("Run Scan"):
    results = scan(stocks)

    # 🔥 GUARANTEED OUTPUT (FALLBACK)
    if len(results) == 0:
        st.warning("No strong setups found → showing fallback top stocks")
        results = scan(stocks)[:FALLBACK_TOP_N]

    df = pd.DataFrame(results)

    st.dataframe(df)

    selected = st.selectbox("Select Stock", df["Stock"])

    fig, entry, target, stop = plot(selected)

    if fig:
        st.plotly_chart(fig)

        st.subheader("Trade Plan")
        st.write(f"Entry: {entry}")
        st.write(f"Target: {target}")
        st.write(f"Stop Loss: {stop}")

        st.subheader("Why this stock?")
        st.write(df[df["Stock"] == selected]["Reasons"].values[0])
