import os
import requests
import pandas as pd

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TICKERS = open("tickers.txt").read().splitlines()

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_weekly_close(symbol):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={symbol}&interval=1week&outputsize=12&apikey={API_KEY}"
    )
    r = requests.get(url).json()

    if "values" not in r:
        return None

    closes = [float(x["close"]) for x in reversed(r["values"])]
    return pd.Series(closes)

def ema8(series):
    return series.ewm(span=8).mean().iloc[-1]

def get_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    r = requests.get(url).json()
    if "price" not in r:
        return None
    return float(r["price"])

def check():
    alerts = []

    for t in TICKERS:
        closes = get_weekly_close(t)
        price = get_price(t)

        if closes is None or price is None:
            continue

        ema = ema8(closes)

        diff = ((price / ema) - 1) * 100

        if abs(diff) < 0.3:
            side = "↑ arriba" if price > ema else "↓ abajo"
            alerts.append(
                f"🔔 {t} cruzando EMA8W ({side})\n"
                f"Precio: {price:.2f}\n"
                f"EMA8W: {ema:.2f}\n"
                f"Distancia: {diff:.2f}%"
            )

    if alerts:
        send("\n\n".join(alerts))

check()