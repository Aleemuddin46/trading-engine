# pip install yfinance pandas ta streamlit plotly numpy

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

# OPTIONAL FEATURES
USE_REGIME_FILTER = True
USE_SECTOR_BIAS = True
USE_RELATIVE_STRENGTH = True

# =============================
# LOAD CHARTINK STOCKS
# =============================
def load_stocks():
    df = pd.read_csv("chartink.csv")
    stocks = df["Symbol"].dropna().tolist()
    return [s.strip().replace(".NS", "") + ".NS" for s in stocks]

# =============================
# INDICATORS
# =============================
def add_indicators(df):
    df = df.copy()

    df["rsi"] = ta.momentum.RSIIndicator(df["Close"], 14).rsi()

    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["signal"] = macd.macd_signal()

    df["ema20"] = ta.trend.EMAIndicator(df["Close"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["Close"], 50).ema_indicator()

    df["vol_avg"] = df["Volume"].rolling(20).mean()

    df["vwap"] = (df["Close"] * df["Volume"]).cumsum() / df["Volume"].cumsum()

    df = df.dropna()

    return df

# =============================
# OPTIONAL: MARKET REGIME
# =============================
def market_regime():
    df = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
    ema50 = ta.trend.EMAIndicator(df["Close"], 50).ema_indicator()
    return df["Close"].iloc[-1] > ema50.iloc[-1]

# =============================
# CORE SCORING ENGINE
# =============================
def score_stock(df):
    last, prev = df.iloc[-1], df.iloc[-2]

    score = 0
    reasons = []

    # RSI
    if last["rsi"] > prev["rsi"]:
        score += 10
        reasons.append("RSI improving")

    if last["rsi"] < 60:
        score += 5
        reasons.append("RSI not overbought")

    # MACD
    if last["macd"] > last["signal"]:
        score += 15
        reasons.append("MACD bullish")

    # Trend
    if last["Close"] > last["ema20"]:
        score += 10
        reasons.append("Above EMA20")

    if last["ema20"] > last["ema50"]:
        score += 10
        reasons.append("Trend aligned (EMA20 > EMA50)")

    # VWAP
    if last["Close"] > last["vwap"]:
        score += 10
        reasons.append("Above VWAP")

    # Volume
    if last["Volume"] > last["vol_avg"]:
        score += 10
        reasons.append("Volume expansion")

    # Momentum
    if last["Close"] > df["Close"].iloc[-5]:
        score += 10
        reasons.append("Short-term momentum")

    return score, reasons

# =============================
# SCANNER
# =============================
def scan(stocks):
    results = []

    regime_bull = market_regime() if USE_REGIME_FILTER else True

    for stock in stocks:
        try:
            df = yf.download(stock, period="6mo", interval="1d", progress=False)

            if df is None or len(df) < 60:
                continue

            df = add_indicators(df)

            score, reasons = score_stock(df)

            # regime penalty (optional)
            if USE_REGIME_FILTER and not regime_bull:
                score *= 0.8

            results.append({
                "Stock": stock,
                "Score": round(score, 2),
                "Reasons": ", ".join(reasons)
            })

        except:
            continue

    results = sorted(results, key=lambda x: x["Score"], reverse=True)

    # fallback: ALWAYS return top N
    if len(results) == 0:
        return []

    return results

# =============================
# CHART
# =============================
def plot(stock):
    df = yf.download(stock, period="6mo", interval="1d")
    df = add_indicators(df)

    entry = df["Close"].iloc[-1]
    support = df["Low"].rolling(20).min().iloc[-1]

    stop = support * 0.98
    target = entry + 2 * (entry - stop)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"]
    ))

    fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], name="EMA20"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA50"))
    fig.add_trace(go.Scatter(x=df.index, y=df["vwap"], name="VWAP"))

    fig.add_hline(y=entry, annotation_text="Entry")
    fig.add_hline(y=target, annotation_text="Target")
    fig.add_hline(y=stop, annotation_text="Stop")

    return fig, entry, target, stop

# =============================
# UI
# =============================
st.title("🚀 Smart Multi-Strategy Chartink Engine (Final)")

stocks = load_stocks()

st.write(f"Loaded {len(stocks)} stocks from Chartink")

if st.button("Run Scan"):
    results = scan(stocks)

    if len(results) == 0:
        st.warning("No setups found — showing fallback scan")
        results = scan(stocks)[:FALLBACK_TOP_N]

    df = pd.DataFrame(results)

    st.dataframe(df)

    selected = st.selectbox("Select Stock", df["Stock"])

    fig, entry, target, stop = plot(selected)

    st.plotly_chart(fig)

    st.subheader("Trade Plan")
    st.write(f"Entry: {entry}")
    st.write(f"Target: {target}")
    st.write(f"Stop: {stop}")

    st.subheader("Why this stock?")
    st.write(df[df["Stock"] == selected]["Reasons"].values[0])
