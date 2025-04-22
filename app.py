from flask import Flask, request
import os, requests, time, hmac, hashlib, base64, json
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data or data.get("secret") != os.getenv("WEBHOOK_SECRET"):
        print("❌ 잘못된 웹훅 요청입니다", flush=True)
        return {"error": "unauthorized"}, 403

    signal = data.get("signal")
    print(f"✅ Signal received: {signal}", flush=True)
    if signal == "BUY":
        place_order("buy")
    elif signal == "TP":
        place_order("close")
    else:
        print("❌ Unknown signal", flush=True)
        return {"error": "unknown signal"}, 400
    return {"status": "success"}, 200

def place_order(action):
    api_key = os.getenv("OKX_API_KEY")
    api_secret = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_PASSPHRASE")
    symbol = os.getenv("SYMBOL")
    side = os.getenv("POSITION_SIDE")
    percent_to_trade = float(os.getenv("TRADE_PERCENT", "0.001"))

    # 1. 현재 잔고 조회
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
    balance_res = requests.get(account_url, headers=headers)
    balance_data = balance_res.json()
    usdt_balance = float(balance_data["data"][0]["details"][0]["cashBal"])

    # 2. 현재 BTC 가격 조회
    ticker_url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
    ticker_res = requests.get(ticker_url)
    last_price = float(ticker_res.json()["data"][0]["last"])

    # 3. 진입 금액 계산 및 주문 수량 계산
    usdt_to_use = usdt_balance * percent_to_trade
    btc_amount = round(usdt_to_use / last_price, 6)

    print(f"💰 현재 자산: {usdt_balance} USDT")
    print(f"📌 진입 자금 (0.1%): {usdt_to_use} USDT")
    print(f"📦 주문 수량 (BTC): {btc_amount}", flush=True)

    # 4. 주문 실행
    url_path = "/api/v5/trade/order"
    url = "https://www.okx.com" + url_path
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    order_body = {
        "instId": symbol,
        "tdMode": "cross",
        "side": "buy" if action == "buy" else "sell",
        "ordType": "market",
        "posSide": side,
        "sz": str(btc_amount)
    }
    pre_hash = timestamp + 'POST' + url_path + json.dumps(order_body, separators=(',', ':'))
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), pre_hash.encode(), hashlib.sha256).digest()
    ).decode()

    headers.update({
        'Content-Type': 'application/json',
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
    })

    print("📤 주문 바디:", json.dumps(order_body), flush=True)
    response = requests.post(url, headers=headers, data=json.dumps(order_body))
    print("✅ OKX 응답:", response.status_code, response.text, flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)