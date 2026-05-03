# pip install streamlit pandas numpy yfinance ta plotly

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

USE_REGIME_FILTER = True

# =============================
# LOAD CHARTINK STOCKS
# =============================
def load_stocks():
    df = pd.read_csv("chartink.csv")
    stocks = df["Symbol"].dropna().tolist()

    # Normalize NSE format
    return [s.strip().replace(".NS", "") + ".NS" for s in stocks]

# =============================
# SAFE DATA LOADING (FIXED)
# =============================
def load_data(stock):
    df = yf.download(stock, period="6mo", interval="1d", progress=False)

    if df is None or df.empty:
        return None

    df = df.copy()
    df = df.reset_index()

    # 🔥 FORCE CLEAN 1D SERIES (FIX FOR YOUR ERROR)
    df["Open"] = df["Open"].astype(float).squeeze()
    df["High"] = df["High"].astype(float).squeeze()
    df["Low"] = df["Low"].astype(float).squeeze()
    df["Close"] = df["Close"].astype(float).squeeze()
    df["Volume"] = df["Volume"].astype(float).squeeze()

    return df

# =============================
# INDICATORS (SAFE)
# =============================
def add_indicators(df):
    df = df.copy()

    close = df["Close"].squeeze()
    volume = df["Volume"].squeeze()

    df["rsi"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    macd = ta.trend.MACD(close)
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()

    df["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()

    df["vol_avg"] = volume.rolling(20).mean()

    df["vwap"] = (close * volume).cumsum() / volume.cumsum()

    return df.dropna()

# =============================
# MARKET REGIME
# =============================
def market_regime():
    df = yf.download("^NSEI", period="3mo", interval="1d", progress=False)

    if df is None or df.empty:
        return True

    ema50 = ta.trend.EMAIndicator(df["Close"], 50).ema_indicator()

    return df["Close"].iloc[-1] > ema50.iloc[-1]

# =============================
# SCORING ENGINE
# =============================
def score(df):
    last, prev = df.iloc[-1], df.iloc[-2]

    score = 0
    reasons = []

    if last["rsi"] > prev["rsi"]:
        score += 10
        reasons.append("RSI rising")

    if last["rsi"] < 60:
        score += 5
        reasons.append("RSI healthy")

    if last["macd"] > last["signal"]:
        score += 15
        reasons.append("MACD bullish")

    if last["Close"] > last["ema20"]:
        score += 10
        reasons.append("Above EMA20")

    if last["ema20"] > last["ema50"]:
        score += 10
        reasons.append("Trend aligned")

    if last["Close"] > last["vwap"]:
        score += 10
        reasons.append("Above VWAP")

    if last["Volume"] > last["vol_avg"]:
        score += 10
        reasons.append("Volume support")

    if last["Close"] > df["Close"].iloc[-5]:
        score += 10
        reasons.append("Momentum")

    return score, reasons

# =============================
# SCANNER
# =============================
def scan(stocks):
    results = []

    regime = market_regime() if USE_REGIME_FILTER else True

    for stock in stocks:
        try:
            df = load_data(stock)

            if df is None or len(df) < 60:
                continue

            df = add_indicators(df)

            score_val, reasons = score(df)

            if USE_REGIME_FILTER and not regime:
                score_val *= 0.8

            results.append({
                "Stock": stock,
                "Score": round(score_val, 2),
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
    fig.add_hline(y=stop, annotation_text="Stop")

    return fig, entry, target, stop

# =============================
# UI
# =============================
st.title("🚀 Fixed Smart Multi-Strategy Engine")

stocks = load_stocks()

st.write(f"Loaded {len(stocks)} Chartink stocks")

if st.button("Run Scan"):
    results = scan(stocks)

    # fallback so NEVER empty UI
    if len(results) == 0:
        st.warning("No strong setups → showing fallback top stocks")
        results = results[:FALLBACK_TOP_N]

    df = pd.DataFrame(results)

    st.dataframe(df)

    selected = st.selectbox("Select Stock", df["Stock"])

    fig, entry, target, stop = plot(selected)

    if fig:
        st.plotly_chart(fig)

        st.subheader("Trade Plan")
        st.write(f"Entry: {entry}")
        st.write(f"Target: {target}")
        st.write(f"Stop: {stop}")

        st.subheader("Why this stock?")
        st.write(df[df["Stock"] == selected]["Reasons"].values[0])
