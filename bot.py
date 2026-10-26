import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# خادم ويب وهمي لرضا موقع Render المجاني عن الـ Port
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# بدء خادم الويب في خلفية النظام
t = threading.Thread(target=run_web_server)
t.daemon = True
t.start()

# بياناتك الخاصة بالتيليجرام
TELEGRAM_BOT_TOKEN = "7023463264:AAEL8N3HR5GxRhf0T9M_IW0VfY7_r797Ifs"
TELEGRAM_CHANNEL_ID = "-1002330262707"

SYMBOL = "EURUSD"
RSI_PERIOD = 7
ADX_PERIOD = 14
ADX_MIN_LEVEL = 25.0
EMA_PERIOD = 20

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال التيليجرام: {e}")

def calculate_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_adx(high, low, close, period):
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    tr_smoothed = tr.rolling(window=period).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).sum() / tr_smoothed)
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).sum() / tr_smoothed)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    return adx

def check_market_and_signal():
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/chart/{SYMBOL}=X?interval=1m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        data = res.json()
        
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': quotes['open'],
            'high': quotes['high'],
            'low': quotes['low'],
            'close': quotes['close']
        }).dropna()
        
        df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
        df['adx'] = calculate_adx(df['high'], df['low'], df['close'], ADX_PERIOD)
        df['ema'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
        
        i = len(df) - 2
        if i < 1:
            return
            
        rsi_prev = df['rsi'].iloc[i]
        rsi_prev2 = df['rsi'].iloc[i-1]
        adx_main = df['adx'].iloc[i]
        close_price = df['close'].iloc[i]
        ema_val = df['ema'].iloc[i]
        
        # صفقة صعود (CALL)
        if rsi_prev2 <= 30.0 and rsi_prev > 30.0 and adx_main >= ADX_MIN_LEVEL and close_price > ema_val:
            msg = (
                f"🚨 **Chinese Momentum Signal** 🚨\n"
                f"💱 **Pair:** {SYMBOL} (M1)\n"
                f"📈 **Action:** CALL (صعود)\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M')}\n"
                f"💡 *الدخول مع بداية الشمعة الحالية لمدة دقيقة واحدة*"
            )
            send_telegram_message(msg)
            print("تم إرسال إشارة صعود بنجاح!")
            
        # صفقة هبوط (PUT)
        elif rsi_prev2 >= 70.0 and rsi_prev < 70.0 and adx_main >= ADX_MIN_LEVEL and close_price < ema_val:
            msg = (
                f"🚨 **Chinese Momentum Signal** 🚨\n"
                f"💱 **Pair:** {SYMBOL} (M1)\n"
                f"📉 **Action:** PUT (هبوط)\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M')}\n"
                f"💡 *الدخول مع بداية الشمعة الحالية لمدة دقيقة واحدة*"
            )
            send_telegram_message(msg)
            print("تم إرسال إشارة هبوط بنجاح!")

    except Exception as e:
        print(f"خطأ أثناء جلب السوق: {e}")

if __name__ == "__main__":
    print("🚀 بدأ تشغيل البوت على Render بنجاح 24/7...")
    send_telegram_message("🟢 **تم تفعيل بوت الإشارات الشامل عبر Render بنجاح ويعمل الآن!**")
    
    while True:
        check_market_and_signal()
        time.sleep(60)
