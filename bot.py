import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# خادم ويب وهمي لرضا موقع Render عن الـ Port وابقاء البوت مستيقظاً
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    while True:
        try:
            server = HTTPServer(('0.0.0.0', port), SimpleHandler)
            server.serve_forever()
        except Exception as e:
            print(f"Web server error: {e}")
            time.sleep(5)

t = threading.Thread(target=run_web_server)
t.daemon = True
t.start()

# بيانات التيليجرام
TELEGRAM_BOT_TOKEN = "7023463264:AAEL8N3HR5GxRhf0T9M_IW0VfY7_r797Ifs"
TELEGRAM_CHANNEL_ID = "-1002330262707"

# جميع الأزواج الأربعة
SYMBOLS = ["EURUSD", "EURGBP", "EURJPY", "USDJPY"]

# إحصائيات الأداء العامة
stats_lock = threading.Lock()
global_stats = {
    "wins": 0,
    "losses": 0,
    "wins_m1": 0,
    "total": 0
}

# إحصائيات مستقلة لكل زوج لتتبع أداء كل زوج على حدة
symbol_stats = {sym: {"wins": 0, "losses": 0} for sym in SYMBOLS}

last_signal_time = {sym: 0 for sym in SYMBOLS}
pending_signals = []

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال التيليجرام: {e}")

def fetch_market_data(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/chart/{symbol}=X?interval=1m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': quotes['open'],
            'high': quotes['high'],
            'low': quotes['low'],
            'close': quotes['close'],
            'volume': quotes.get('volume', [1000]*len(timestamps))
        }).dropna()
        return df
    except Exception as e:
        return None

def check_pending_signals(symbol, df):
    global pending_signals, global_stats, symbol_stats
    if df is None or len(df) < 3:
        return
    
    with stats_lock:
        remaining_signals = []
        for sig in pending_signals:
            if sig['symbol'] == symbol:
                sig_type = sig['type']
                step = sig['step']
                entry_price = sig['price']
                target_ts = sig.get('target_ts', 0)
                
                df['ts'] = df['timestamp']
                matched = df[df['ts'] >= target_ts]
                
                if len(matched) > 0:
                    current_close = matched['close'].iloc[0]
                    current_open = matched['open'].iloc[0]
                    
                    is_win = False
                    if sig_type == 'CALL' and current_close > entry_price:
                        is_win = True
                    elif sig_type == 'PUT' and current_close < entry_price:
                        is_win = True
                    
                    if is_win:
                        if step == 1:
                            global_stats["wins"] += 1
                            symbol_stats[symbol]["wins"] += 1
                            res_msg = f"✅ **نتيجة صفقة 1M: رابحة (WIN)** 🎯\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n✨ *ربح من الدخول الأساسي (بدون مضاعفة ✅)*"
                        else:
                            global_stats["wins_m1"] += 1
                            symbol_stats[symbol]["wins"] += 1
                            res_msg = f"✅1 **نتيجة صفقة 1M: رابحة بالمضاعفة (WIN M1)** 🎯\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n✨ *ربح بمضاعفة واحدة (✅1)*"
                        
                        global_stats["total"] += 1
                        send_telegram_message(res_msg)
                    else:
                        if step == 1:
                            next_open = current_open
                            remaining_signals.append({
                                'symbol': symbol,
                                'type': sig_type,
                                'price': next_open,
                                'step': 2,
                                'target_ts': target_ts + 60
                            })
                            m_msg = f"⚠️ **تنبيه مضاعفة أولى (Martingale x1)** 🔄\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💡 *جاري تفعيل المضاعفة لتعويض الصفقة السابقة...*"
                            send_telegram_message(m_msg)
                        else:
                            global_stats["losses"] += 1
                            symbol_stats[symbol]["losses"] += 1
                            global
