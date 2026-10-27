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

# قائمة جميع أزواج العملات الرئيسية للسوق الحقيقي
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP", "EURJPY"]

# متغيرات الإحصائيات لتتبع الربح (ITM) والخسارة (OTM)
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
            'close': quotes['close'],
            'volume': quotes.get('volume', [1000]*len(timestamps))
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
                
                # فحص النتيجة (ITM صفقات ناجحة / OTM صفقات خاسرة)
                is_win = False
                if sig_type == 'CALL' and last_close > entry_price:
                    is_win = True
                elif sig_type == 'PUT' and last_close < entry_price:
                    is_win = True
                
                if is_win:
                    current_hour_stats["wins"] += 1
                    res_msg = f"✅ **نتيجة الصفقة: ITM (ربح ناجح)** 🎯\n💱 الزوج: `{symbol}` (Market)\n📈 الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                else:
                    current_hour_stats["losses"] += 1
                    res_msg = f"❌ **نتيجة الصفقة: OTM (خسارة)** ⚠️\n💱 الزوج: `{symbol}` (Market)\n📈 الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                
                current_hour_stats["total"] += 1
                send_telegram_message(res_msg)
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def process_symbol(symbol):
    global pending_signals
    df = fetch_market_data(symbol)
    if df is None:
        return
    
    # تتبع النتائج الفورية للصفقة السابقة لهذا الزوج
    check_pending_signals(symbol, df)
    
    # حساب المتوسطات المتحركة للاتجاه (EMA 20 و EMA 50)
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['vol_sma'] = df['volume'].rolling(window=10).mean()
    
    i = len(df) - 2
    if i < 2:
        return
        
    close_prev = df['close'].iloc[i]
    open_prev = df['open'].iloc[i]
    ema20 = df['ema20'].iloc[i]
    ema50 = df['ema50'].iloc[i]
    vol = df['volume'].iloc[i]
    vol_avg = df['vol_sma'].iloc[i]
    
    # سعر افتتاح الشمعة الحالية (الشمعة القادمة لدخول الصفقة)
    current_open = df['open'].iloc[-1]
    
    # شروط مرنة وسريعة لاصطياد الفرص دون تأخير مبالغ فيه
    is_uptrend = close_prev > ema20
    is_downtrend = close_prev < ema20
    
    signal_type = None
    if is_uptrend and close_prev > open_prev:
        signal_type = 'CALL'
    elif is_downtrend and close_prev < open_prev:
        signal_type = 'PUT'
        
    if signal_type:
        emoji = '🟢 (صعود - CALL)' if signal_type == 'CALL' else '🔴 (هبوط - PUT)'
        msg = (
            f"⚡ **LEGEND FAST DIRECT SIGNAL** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 الزوج: `{symbol}` (سوق حقيقي)\n"
            f"📊 الإشارة: **{signal_type} {emoji}**\n"
            f"⏰ الفريم: `1M` | الوقت: `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"💡 *الدخول مع افتتاح الشمعة القادمة لمدة دقيقة*"
        )
        
        send_telegram_message(msg)
        with stats_lock:
            pending_signals.append({'symbol': symbol, 'type': signal_type, 'price': current_open})
        print(f"تم إرسال إشارة سريعة لـ {symbol} بسعر {current_open}")

def run_bot_loop():
    while True:
        # فحص جميع الأزواج بشكل متوازي وسريع جداً
        threads = []
        for symbol in SYMBOLS:
            t = threading.Thread(target=process_symbol, args=(symbol,))
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        # الانتظار 30 ثانية فقط قبل الدورة التالية لتسريع التدفق
        time.sleep(30)

def send_periodic_results():
    global current_hour_stats
    with stats_lock:
        wins = current_hour_stats["wins"]
        losses = current_hour_stats["losses"]
        total = current_hour_stats["total"]
        
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        
        report = (
            f"📊 **تقرير أداء الصفقات السريعة (ITM / OTM)** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي الصفقات: `{total}`\n"
            f"✅ صفقات ناجحة (ITM): `{wins}`\n"
            f"❌ صفقات خاسرة (OTM): `{losses}`\n"
            f"📈 نسبة الفوز المحققة: `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *LEGEND - FAST MARKET BOT*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت الفحص السريع والمتوازي لجميع الأزواج...")
    send_telegram_message("🟢 **تم تفعيل وضع الفحص السريع والمتوازي لجميع الأزواج الحقيقية! سترى تدفق الصفقات الآن!**")
    
    # تشغيل حلقة البوت في خيط مستقل
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # إرسال التقارير الدورية كل 10 دقائق
    while True:
        time.sleep(600)
        send_periodic_results()
