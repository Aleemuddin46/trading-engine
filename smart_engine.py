# pip install yfinance pandas ta streamlit plotly numpy

import pandas as pd
import numpy as np
import yfinance as yf
import ta
import streamlit as st
import plotly.graph_objects as go

# -----------------------------
# LOAD STOCKS (from Chartink or list)
# -----------------------------
def load_stocks():
    df = pd.read_csv("chartink.csv")
    stocks = df['Symbol'].dropna().tolist()
    return [s.strip() + ".NS" for s in stocks]

# -----------------------------
# INDICATORS
# -----------------------------
def indicators(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['signal'] = macd.macd_signal()

    df['ema20'] = ta.trend.EMAIndicator(df['Close'], 20).ema_indicator()
    df['ema50'] = ta.trend.EMAIndicator(df['Close'], 50).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(df['Close'], 200).ema_indicator()

    df['vol_avg'] = df['Volume'].rolling(20).mean()

    df['vwap'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()

    return df

# -----------------------------
# STRATEGY 1: TREND FOLLOWING
# -----------------------------
def trend_score(df):
    last = df.iloc[-1]
    score = 0

    if last['Close'] > last['ema50'] > last['ema200']:
        score += 30

    if last['Close'] > last['vwap']:
        score += 15

    if 55 < last['rsi'] < 75:
        score += 15

    if last['Volume'] > last['vol_avg']:
        score += 10

    return score

# -----------------------------
# STRATEGY 2: REVERSAL
# -----------------------------
def reversal_score(df):
    last, prev = df.iloc[-1], df.iloc[-2]
    score = 0

    if last['rsi'] > prev['rsi'] and last['rsi'] < 45:
        score += 20

    if last['macd'] > last['signal']:
        score += 25

    support = df['Low'].rolling(20).min().iloc[-1]

    if last['Close'] <= support * 1.05:
        score += 15

    if last['Close'] > last['ema20']:
        score += 10

    return score

# -----------------------------
# STRATEGY 3: BREAKOUT
# -----------------------------
def breakout_score(df):
    last = df.iloc[-1]
    score = 0

    resistance = df['High'].rolling(20).max().iloc[-1]

    if last['Close'] > resistance:
        score += 30

    if last['Volume'] > 2 * df['vol_avg'].iloc[-1]:
        score += 25

    prev_range = df['High'].iloc[-5:].max() - df['Low'].iloc[-5:].min()
    if prev_range / last['Close'] < 0.05:
        score += 15

    return score

# -----------------------------
# FINAL ENGINE
# -----------------------------
def analyze(df, stock):
    t = trend_score(df)
    r = reversal_score(df)
    b = breakout_score(df)

    scores = {
        "Trend": t,
        "Reversal": r,
        "Breakout": b
    }

    best_strategy = max(scores, key=scores.get)
    best_score = scores[best_strategy]

    return best_strategy, best_score, scores

# -----------------------------
# SCANNER
# -----------------------------
def scan(stocks):
    results = []

    for stock in stocks:
        try:
            df = yf.download(stock, period="6mo", interval="1d", progress=False)
            if df.empty:
                continue

            df = indicators(df)

            best_strategy, score, all_scores = analyze(df, stock)

            if score >= 40:
                results.append({
                    "Stock": stock,
                    "Strategy": best_strategy,
                    "Score": score,
                    "Trend": all_scores["Trend"],
                    "Reversal": all_scores["Reversal"],
                    "Breakout": all_scores["Breakout"]
                })

        except:
            pass

    return sorted(results, key=lambda x: x['Score'], reverse=True)

# -----------------------------
# CHART
# -----------------------------
def chart(stock):
    df = yf.download(stock, period="6mo", interval="1d")
    df = indicators(df)

    entry = df['Close'].iloc[-1]
    support = df['Low'].rolling(20).min().iloc[-1]
    resistance = df['High'].rolling(20).max().iloc[-1]

    stop = support * 0.98
    target = entry + 2 * (entry - stop)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    ))

    fig.add_trace(go.Scatter(x=df.index, y=df['ema50'], name="EMA50"))
    fig.add_trace(go.Scatter(x=df.index, y=df['ema200'], name="EMA200"))
    fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], name="VWAP"))

    fig.add_hline(y=entry, annotation_text="Entry")
    fig.add_hline(y=target, annotation_text="Target")
    fig.add_hline(y=stop, annotation_text="Stop")

    fig.add_hline(y=support, line_dash="dot")
    fig.add_hline(y=resistance, line_dash="dot")

    return fig, entry, target, stop

# -----------------------------
# UI
# -----------------------------
st.title("🚀 Multi-Strategy Trading Engine")

if st.button("Load & Scan"):
    stocks = load_stocks()
    st.write(f"Loaded {len(stocks)} stocks")

    results = scan(stocks)

    if not results:
        st.write("No setups found")
    else:
        df = pd.DataFrame(results)
        st.dataframe(df)

        selected = st.selectbox("Select Stock", df["Stock"])

        fig, entry, target, stop = chart(selected)

        st.plotly_chart(fig)

        st.write(f"Entry: {entry}")
        st.write(f"Target: {target}")
        st.write(f"Stop: {stop}")
