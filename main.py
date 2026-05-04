import os
import json
import requests

API_KEY = os.getenv("TWELVE_DATA_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "btc_state.json"
SYMBOL = "BTC/USD"

MA_PRIORITY = {
    "EMA10_4H": 1,
    "EMA10_D": 2,
    "EMA21_D": 3,
    "SMA50_D": 4,
}


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
            "ma": None,
            "priority": 0,
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

def fetch(interval, size=120):
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


# =========================
# MA
# =========================

def ema(values, period):
    k = 2 / (period + 1)
    out = [values[0]]

    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))

    return out[-1]


def sma(values, period):
    return sum(values[-period:]) / period


def detect_loss(price):
    candidates = []

    # 4H
    bars4h = fetch("4h", 80)
    c4h = [float(x["close"]) for x in bars4h]
    ema10_4h = ema(c4h, 10)

    if price < ema10_4h:
        candidates.append("EMA10_4H")

    # Daily
    bars1d = fetch("1day", 100)
    cd = [float(x["close"]) for x in bars1d]

    ema10_d = ema(cd, 10)
    ema21_d = ema(cd, 21)
    sma50_d = sma(cd, 50)

    if price < ema10_d:
        candidates.append("EMA10_D")

    if price < ema21_d:
        candidates.append("EMA21_D")

    if price < sma50_d:
        candidates.append("SMA50_D")

    if not candidates:
        return None

    return max(candidates, key=lambda x: MA_PRIORITY[x])


# =========================
# SCORE
# =========================

def quality_score(vb, vsma, ref_high, hb, ref_close, cb):
    score = 0

    vr = vb / vsma if vsma else 0

    if vr > 1.5:
        score += 40
    elif vr > 1:
        score += 25
    else:
        score += 10

    strength = (hb - ref_high) / ref_high

    if strength > 0.008:
        score += 30
    elif strength > 0.003:
        score += 15
    else:
        score += 5

    if cb > ref_close:
        score += 20

    return score


# =========================
# MAIN
# =========================

def main():
    state = load_state()

    price = get_price()

    trigger_ma = detect_loss(price)

    bars30 = fetch("30min", 30)
    bar_a = bars30[-2]
    bar_b = bars30[-1]

    ha = float(bar_a["high"])
    hb = float(bar_b["high"])
    ca = float(bar_a["close"])
    cb = float(bar_b["close"])

    vols = [float(x.get("volume", 0)) for x in bars30[-12:]]
    vb = vols[-1]
    vsma = sum(vols[:-1]) / len(vols[:-1]) if vols[:-1] else 0

    # activar / reemplazar vigilancia
    if trigger_ma:
        p = MA_PRIORITY[trigger_ma]

        if (not state["watching"]) or (p >= state["priority"]):
            state["watching"] = True
            state["ma"] = trigger_ma
            state["priority"] = p
            state["a_high"] = ha
            state["a_close"] = ca
            state["expiry"] = 20

            send(
                f"👀 BTC perdió {trigger_ma}\n"
                f"Precio: {price:.2f}\n"
                f"Vigilancia activada"
            )

    # rolling pivot
    if state["watching"]:

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
                f"MA: {state['ma']}\n"
                f"Score: {score}/100\n"
                f"Price: {price:.2f}\n"
                f"VolRatio: {vr:.2f}x"
            )

            state = {
                "watching": False,
                "ma": None,
                "priority": 0,
                "a_high": None,
                "a_close": None,
                "expiry": 0,
                "prev": price
            }

        else:
            state["a_high"] = ha
            state["a_close"] = ca
            state["expiry"] -= 1

            if state["expiry"] <= 0:
                send("⌛ BTC setup expiró")
                state = {
                    "watching": False,
                    "ma": None,
                    "priority": 0,
                    "a_high": None,
                    "a_close": None,
                    "expiry": 0,
                    "prev": price
                }

    state["prev"] = price
    save_state(state)


if __name__ == "__main__":
    main()
