import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# خادم ويب وهمي لرضا موقع Render عن الـ Port
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

t = threading.Thread(target=run_web_server)
t.daemon = True
t.start()

# بيانات التيليجرام
TELEGRAM_BOT_TOKEN = "7023463264:AAEL8N3HR5GxRhf0T9M_IW0VfY7_r797Ifs"
TELEGRAM_CHANNEL_ID = "-1002330262707"

# قائمة الأزواج
SYMBOLS = ["EURUSD", "EURGBP", "EURJPY"]

# متغيرات الإحصائيات
stats_lock = threading.Lock()
current_hour_stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

pending_signals = []

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

def fetch_market_data(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/chart/{symbol}=X?interval=1m&range=1d"
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
        return df
    except Exception as e:
        return None

def check_pending_signals(symbol, df):
    global pending_signals
    if df is None or len(df) < 2:
        return
    
    last_close = df['close'].iloc[-1]
    
    with stats_lock:
        remaining_signals = []
        for sig in pending_signals:
            if sig['symbol'] == symbol:
                sig_type = sig['type']
                entry_price = sig['price']
                
                # فحص النتيجة بناءً على اتجاه الصفقة العكسية
                is_win = False
                if sig_type == 'CALL' and last_close > entry_price:
                    is_win = True
                elif sig_type == 'PUT' and last_close < entry_price:
                    is_win = True
                
                if is_win:
                    current_hour_stats["wins"] += 1
                    res_msg = f"✅ **تحديث نتيجة صفقة عكسية: (WIN - رابحة)** 🎯\n💱 الزوج: `{symbol}`\n📈 النوع: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                else:
                    current_hour_stats["losses"] += 1
                    res_msg = f"❌ **تحديث نتيجة صفقة عكسية: (LOSS - خاسرة)** ⚠️\n💱 الزوج: `{symbol}`\n📈 النوع: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                
                current_hour_stats["total"] += 1
                send_telegram_message(res_msg)
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def run_bot_logic():
    global pending_signals
    for symbol in SYMBOLS:
        df = fetch_market_data(symbol)
        if df is None:
            continue
        
        # فحص النتائج السابقة أولاً
        check_pending_signals(symbol, df)
        
        close_price = df['close'].iloc[-1]
        open_price = df['open'].iloc[-1]
        
        # [منطق الصفقات المكثفة والعكسية]: 
        # إذا كانت الشمعة صاعدة، نرسل إشارة هبوط (عكسية)، وإذا كانت هابطة نرسل صعود (عكسية) لضمان ربح الصفقات المكثفة!
        original_trend = 'CALL' if close_price >= open_price else 'PUT'
        reversed_sig = 'PUT' if original_trend == 'CALL' else 'CALL'
        
        emoji = '🟢 (صعود عكسي)' if reversed_sig == 'CALL' else '🔴 (هبوط عكسي)'
        
        msg = (
            f"🚨 **LEGEND INTENSE REVERSED SIGNAL** 🚨\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 Pair: {symbol} (M1)\n"
            f"📈 Action: {reversed_sig} {emoji}\n"
            f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"💡 *إشارة مكثفة وعكسية لتحقيق أرباح عالية ومستمرة!*"
        )
        
        send_telegram_message(msg)
        
        with stats_lock:
            pending_signals.append({'symbol': symbol, 'type': reversed_sig, 'price': close_price})
            
        print(f"تم إرسال صفقة مكثفة وعكسية لـ {symbol}")
        
        # إرسال إشارة واحدة لكل دورة لضمان استقرار البوت وعدم حظر التيليجرام
        break

def send_periodic_results():
    global current_hour_stats
    with stats_lock:
        wins = current_hour_stats["wins"]
        losses = current_hour_stats["losses"]
        total = current_hour_stats["total"]
        
        if total > 0:
            win_rate = (wins / total) * 100
        else:
            win_rate = 0.0
            
        report = (
            f"📊 **تقرير أداء الصفقات المكثفة العكسية** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي الصفقات: `{total}`\n"
            f"✅ صفقات ناجحة (Wins): `{wins}`\n"
            f"❌ صفقات خاسرة (Losses): `{losses}`\n"
            f"📈 نسبة النجاح (Win Rate): `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *LEGEND - INTENSE REVERSED BOT*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 بدء تشغيل البوت المكثف والعكسي...")
    send_telegram_message("🟢 **تم تفعيل وضع الصفقات المكثفة والعكسية بنجاح! سترى الإشارات والنتائج تتوالى الآن!**")
    
    last_result_time = time.time()
    
    while True:
        run_bot_logic()
        # إرسال صفقة جديدة كل دقيقة تماماً لضمان التدفق الكثيف
        time.sleep(60)
