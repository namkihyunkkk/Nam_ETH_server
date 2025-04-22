
from flask import Flask, request
import os, requests, time, hmac, hashlib, base64, json
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data or data.get("secret") != os.getenv("WEBHOOK_SECRET"):
        print("[ERROR] 잘못된 웹훅 요청입니다", flush=True)
        return {"error": "unauthorized"}, 403

    signal = data.get("signal")
    print("[Webhook] Signal received:", signal, flush=True)

    if signal == "BUY":
        place_order("buy")
    elif signal == "TP":
        place_order("close")
    else:
        print("[ERROR] Unknown signal", flush=True)
        return {"error": "unknown signal"}, 400
    return {"status": "success"}, 200

def place_order(action):
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    symbol = os.getenv("SYMBOL")
    side = os.getenv("POSITION_SIDE")
    percent_to_trade = float(os.getenv("TRADE_PERCENT", "0.01"))

    # 현재 잔고 조회
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    account_url = "https://www.okx.com/api/v5/account/balance?ccy=USDT"
    pre_hash = timestamp + 'GET' + '/api/v5/account/balance?ccy=USDT'
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), pre_hash.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': passphrase
    }
    res = requests.get(account_url, headers=headers)
    print("[잔고 조회 응답]:", res.status_code, res.text, flush=True)
    data = res.json()

    try:
        usdt_balance = float(data["data"][0]["details"][0]["cashBal"])
    except Exception as e:
        print("[ERROR] 잔고 파싱 실패:", e)
        return

    # 주문 수량 계산
    price_res = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={symbol}")
    last_price = float(price_res.json()["data"][0]["last"])
    usdt_to_use = round(usdt_balance * percent_to_trade, 4)
    order_amount = round(usdt_to_use / last_price, 6)

    if order_amount < 0.001:
        print("⚠️ 주문 수량이 너무 적음. 강제로 0.001로 주문", flush=True)
        order_amount = 0.001
    elif order_amount % 0.001 != 0:
        order_amount = round(order_amount - (order_amount % 0.001), 3)

    print(f"[Info] 잔고: {usdt_balance:.2f} USDT", flush=True)
    print(f"[Info] 진입금액: {usdt_to_use} USDT, 주문수량: {order_amount}", flush=True)

    url_path = "/api/v5/trade/order"
    full_url = "https://www.okx.com" + url_path
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    body = {
        "instId": symbol,
        "tdMode": "cross",
        "side": "buy" if action == "buy" else "sell",
        "ordType": "market",
        "posSide": side,
        "sz": str(order_amount)
    }
    msg = timestamp + "POST" + url_path + json.dumps(body, separators=(',', ':'))
    sign = base64.b64encode(hmac.new(api_secret.encode(), msg.encode(), hashlib.sha256).digest()).decode()
    headers.update({
        'Content-Type': 'application/json',
        'OK-ACCESS-SIGN': sign,
        'OK-ACCESS-TIMESTAMP': timestamp,
    })

    print("[Info] 주문 바디:", json.dumps(body), flush=True)
    res = requests.post(full_url, headers=headers, data=json.dumps(body))
    print("[OKX 응답]", res.status_code, res.text, flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
