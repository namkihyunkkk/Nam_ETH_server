from flask import Flask, request
import os, requests, time, hmac, hashlib, base64, json
from dotenv import load_dotenv

# ❤️ 환경 변수 로드
load_dotenv()
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data or data.get("secret") != os.getenv("WEBHOOK_SECRET"):
        print("❌ 잘못된 웹흐크 요청입니다", flush=True)
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

    # 1. 현재 번호 조회
    balance_ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    balance_url_path = "/api/v5/account/balance?ccy=USDT"
    balance_pre_hash = balance_ts + 'GET' + balance_url_path
    balance_signature = base64.b64encode(
        hmac.new(api_secret.encode(), balance_pre_hash.encode(), hashlib.sha256).digest()
    ).decode()
    balance_headers = {
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': balance_signature,
        'OK-ACCESS-TIMESTAMP': balance_ts,
        'OK-ACCESS-PASSPHRASE': passphrase
    }
    balance_url = "https://www.okx.com" + balance_url_path
    balance_res = requests.get(balance_url, headers=balance_headers)
    balance_data = balance_res.json()
    usdt_balance = float(balance_data["data"][0]["details"][0]["cashBal"])

    # 2. 가격 조회
    ticker_url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
    ticker_res = requests.get(ticker_url)
    last_price = float(ticker_res.json()["data"][0]["last"])

    # 3. 계산
    usdt_to_use = usdt_balance * percent_to_trade
    coin_amount = round(usdt_to_use / last_price, 6)

    print(f"💰 현재 자산: {usdt_balance} USDT")
    print(f"📌 진입 자금 ({percent_to_trade*100}%): {usdt_to_use} USDT")
    print(f"📦 주문 수량: {coin_amount}", flush=True)

    # 4. 주문 실행
    order_ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    order_url_path = "/api/v5/trade/order"
    order_url = "https://www.okx.com" + order_url_path
    order_body = {
        "instId": symbol,
        "tdMode": "cross",
        "side": "buy" if action == "buy" else "sell",
        "ordType": "market",
        "posSide": side,
        "sz": str(coin_amount)
    }
    order_body_json = json.dumps(order_body, separators=(',', ':'))
    order_pre_hash = order_ts + 'POST' + order_url_path + order_body_json
    order_signature = base64.b64encode(
        hmac.new(api_secret.encode(), order_pre_hash.encode(), hashlib.sha256).digest()
    ).decode()

    order_headers = {
        'Content-Type': 'application/json',
        'OK-ACCESS-KEY': api_key,
        'OK-ACCESS-SIGN': order_signature,
        'OK-ACCESS-TIMESTAMP': order_ts,
        'OK-ACCESS-PASSPHRASE': passphrase
    }

    print("📤 주문 바디:", order_body_json, flush=True)
    response = requests.post(order_url, headers=order_headers, data=order_body_json)
    print("✅ OKX 응답:", response.status_code, response.text, flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)