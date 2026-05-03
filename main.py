import os
import json
import requests
import pandas as pd

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOL = "BTC/USD"
STATE_FILE = "state.json"


def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "watching": False,
            "alerted": False,
            "last_bar_time": None,
            "bar_a_high": None,
            "trigger_price": None
        }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_series(interval, outputsize=20):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={SYMBOL}&interval={interval}&outputsize={outputsize}&apikey={API_KEY}"
    )
    r = requests.get(url).json()

    if "values" not in r:
        raise Exception(f"API error: {r}")

    vals = list(reversed(r["values"]))
    return vals


def get_price():
    url = f"https://api.twelvedata.com/price?symbol={SYMBOL}&apikey={API_KEY}"
    r = requests.get(url).json()
    if "price" not in r:
        raise Exception(f"Price error: {r}")
    return float(r["price"])


def ema8_4h():
    vals = get_series("4h", 20)
    closes = [float(v["close"]) for v in vals]
    ema = pd.Series(closes).ewm(span=8).mean().iloc[-1]
    return ema


def last_closed_30m():
    vals = get_series("30min", 3)
    # la penúltima suele ser la última cerrada
    bar = vals[-2]
    return {
        "datetime": bar["datetime"],
        "high": float(bar["high"])
    }


def main():
    state = load_state()

    price = get_price()
    ema = ema8_4h()

    # RESET cuando vuelva arriba EMA8 4H
    if price > ema:
        state = {
            "watching": False,
            "alerted": False,
            "last_bar_time": None,
            "bar_a_high": None,
            "trigger_price": None
        }
        save_state(state)
        print("Above EMA8 4H -> reset")
        return

    # Entró debajo EMA8 4H -> activar vigilancia
    if price < ema and not state["watching"]:
        state["watching"] = True
        state["alerted"] = False

    # Si ya alertó este ciclo, no repetir
    if state["alerted"]:
        save_state(state)
        print("Already alerted this cycle")
        return

    # detectar nueva vela A cerrada
    bar = last_closed_30m()

    if state["last_bar_time"] != bar["datetime"]:
        state["last_bar_time"] = bar["datetime"]
        state["bar_a_high"] = bar["high"]
        state["trigger_price"] = bar["high"] * 1.0015

    # trigger intravela
    if state["trigger_price"] and price >= state["trigger_price"]:
        msg = (
            f"🔔 BTC Trigger Detectado\n"
            f"Precio actual: {price:,.2f}\n"
            f"EMA8 4H: {ema:,.2f}\n"
            f"High vela A: {state['bar_a_high']:,.2f}\n"
            f"Trigger: {state['trigger_price']:,.2f}\n"
            f"Estado: debajo EMA8 4H"
        )
        send(msg)
        state["alerted"] = True

    save_state(state)
    print("Done")


if __name__ == "__main__":
    main()
