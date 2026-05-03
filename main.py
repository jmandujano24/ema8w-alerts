import os
import json
import requests

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "btc_state.json"


# =========================
# UTIL
# =========================

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# =========================
# DATA
# =========================

def get_price():
    url = f"https://api.twelvedata.com/price?symbol=BTC/USD&apikey={API_KEY}"
    return float(requests.get(url).json()["price"])


def get_series(interval="30min", size=25):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol=BTC/USD&interval={interval}&outputsize={size}&apikey={API_KEY}"
    )
    r = requests.get(url).json()
    return list(reversed(r["values"]))


# =========================
# SCORE (informativo)
# =========================

def score(vb, vsma, ha, hb, ca, cb):
    s = 0

    vr = vb / vsma if vsma else 0
    if vr > 1.5:
        s += 40
    elif vr > 1:
        s += 25
    else:
        s += 10

    strength = (hb - ha) / ha
    if strength > 0.008:
        s += 30
    elif strength > 0.003:
        s += 15
    else:
        s += 5

    if cb > ca:
        s += 20

    return s


# =========================
# CORE (ROLLING PIVOT 30m)
# =========================

def main():

    state = load_state()

    price = get_price()
    bars = get_series()

    bar_a, bar_b = bars[-2], bars[-1]

    ha = float(bar_a["high"])
    hb = float(bar_b["high"])
    ca = float(bar_a["close"])
    cb = float(bar_b["close"])

    vols = [float(x.get("volume", 0)) for x in bars[-12:]]
    vb = vols[-1]
    vsma = sum(vols[:-1]) / len(vols[:-1]) if vols[:-1] else 0

    s = score(vb, vsma, ha, hb, ca, cb)

    # -------------------------
    # PIVOT
    # -------------------------
    if hb >= ha:

        send(
            f"🔔 BTC PIVOT 30m\n"
            f"Score: {s}/100\n"
            f"High A: {ha}\n"
            f"Price: {price}\n"
            f"Vol ratio: {vb/vsma if vsma else 0:.2f}"
        )


if __name__ == "__main__":
    main()
