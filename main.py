import os
import json
import requests

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "btc_state.json"
SYMBOL = "BTC/USD"


# =========================
# UTIL
# =========================

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "watching": False,
            "a_high": None,
            "a_close": None,
            "expiry": 0,
            "prev": 0
        }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# =========================
# DATA
# =========================

def get_price():
    url = (
        "https://api.twelvedata.com/price"
        f"?symbol={SYMBOL}"
        f"&apikey={API_KEY}"
    )

    data = requests.get(url).json()

    if "price" not in data:
        raise Exception(f"TwelveData error: {data}")

    return float(data["price"])


def get_series(interval="30min", size=25):
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={SYMBOL}"
        f"&interval={interval}"
        f"&outputsize={size}"
        f"&apikey={API_KEY}"
    )

    data = requests.get(url).json()

    if "values" not in data:
        raise Exception(f"TwelveData error: {data}")

    return list(reversed(data["values"]))


# =========================
# SCORE (solo informativo)
# =========================

def quality_score(vb, vsma, ha, hb, ca, cb):
    score = 0

    # volumen relativo
    vr = vb / vsma if vsma else 0
    if vr > 1.5:
        score += 40
    elif vr > 1:
        score += 25
    else:
        score += 10

    # fuerza breakout
    strength = (hb - ha) / ha
    if strength > 0.008:
        score += 30
    elif strength > 0.003:
        score += 15
    else:
        score += 5

    # momentum
    if cb > ca:
        score += 20

    return score


# =========================
# MAIN
# =========================

def main():
    state = load_state()

    price = get_price()
    bars = get_series("30min", 25)

    bar_a = bars[-2]
    bar_b = bars[-1]

    ha = float(bar_a["high"])
    hb = float(bar_b["high"])
    ca = float(bar_a["close"])
    cb = float(bar_b["close"])

    vols = [float(x.get("volume", 0)) for x in bars[-12:]]
    vb = vols[-1]
    vsma = sum(vols[:-1]) / len(vols[:-1]) if vols[:-1] else 0

    # =====================
    # activar vigilancia
    # =====================
    if not state["watching"]:
        state["watching"] = True
        state["a_high"] = ha
        state["a_close"] = ca
        state["expiry"] = 20

        send(
            f"👀 BTC vigilancia iniciada\n"
            f"Ref high: {ha}\n"
            f"Precio: {price}"
        )

    # =====================
    # rolling pivot
    # =====================
    else:

        # rompe pivot
        if hb >= state["a_high"]:

            score = quality_score(
                vb,
                vsma,
                state["a_high"],
                hb,
                state["a_close"],
                cb
            )

            vr = vb / vsma if vsma else 0

            send(
                f"🔔 BTC PIVOT 30m\n"
                f"Score: {score}/100\n"
                f"Price: {price}\n"
                f"VolRatio: {vr:.2f}x"
            )

            # reset ciclo
            state["watching"] = False
            state["a_high"] = None
            state["a_close"] = None
            state["expiry"] = 0

        else:
            # rolling update
            state["a_high"] = ha
            state["a_close"] = ca
            state["expiry"] -= 1

            if state["expiry"] <= 0:
                state["watching"] = False
                state["a_high"] = None
                state["a_close"] = None

    state["prev"] = price

    save_state(state)


if __name__ == "__main__":
    main()
