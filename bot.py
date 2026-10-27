import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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

# الأزواج الأربعة الأساسية
SYMBOLS = ["EURUSD", "EURGBP", "EURJPY", "USDJPY"]

# متغيرات الإحصائيات
stats_lock = threading.Lock()
current_hour_stats = {
    "wins": 0,
    "losses": 0,
    "total": 0
}

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
    global pending_signals, current_hour_stats
    if df is None or len(df) < 6: # نحتاج بيانات كافية لفحص دقيقة و 5 دقائق
        return
    
    current_close = df['close'].iloc[-1]
    
    with stats_lock:
        remaining_signals = []
        for sig in pending_signals:
            if sig['symbol'] == symbol:
                sig_type = sig['type']
                entry_price = sig['price']
                entry_index = sig['index']
                
                # 1. فحص نتيجة الدقيقة الواحدة (الشموع الحالية مقارنة بسعر الدخول)
                is_win_1m = False
                if sig_type == 'CALL' and current_close > entry_price:
                    is_win_1m = True
                elif sig_type == 'PUT' and current_close < entry_price:
                    is_win_1m = True
                
                # 2. فحص محاكاة نتيجة الـ 5 دقائق (السعر بعد 5 شمعات من الدخول)
                current_idx = len(df) - 1
                target_idx = entry_index + 5
                
                is_win_5m = None
                close_5m = None
                if current_idx >= target_idx:
                    close_5m = df['close'].iloc[target_idx]
                    if sig_type == 'CALL' and close_5m > entry_price:
                        is_win_5m = True
                    else:
                        is_win_5m = False
                
                # إرسال نتيجة الدقيقة الواحدة فوراً
                if is_win_1m:
                    current_hour_stats["wins"] += 1
                    res_1m = f"✅ **نتيجة صفقة الدقيقة (1M): ITM (ربح ناجح)** 🎯\n💱 الزوج: `{symbol}`\n📈 الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق (1M): `{current_close}`"
                else:
                    current_hour_stats["losses"] += 1
                    res_1m = f"❌ **نتيجة صفقة الدقيقة (1M): OTM (خسارة)** ⚠️\n💱 الزوج: `{symbol}`\n📈 الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق (1M): `{current_close}`"
                
                current_hour_stats["total"] += 1
                
                # إضافة محاكاة الـ 5 دقائق للرسالة إذا اكتملت بوضوح
                if is_win_5m is not None:
                    res_5m_str = "✅ (ربح 5M)" if is_win_5m else "❌ (خسارة 5M)"
                    res_msg = f"{res_1m}\n🔮 **محاكاة صفقة الـ 5 دقائق:** `{res_5m_str}` (الإغلاق: `{close_5m}`)"
                else:
                    res_msg = f"{res_1m}\n🔮 *محاكاة الـ 5 دقائق: قيد الانتظار حتى اكتمال الشمعة الخامسة...*"
                
                send_telegram_message(res_msg)
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def process_symbol(symbol):
    global pending_signals, last_signal_time
    
    current_time = time.time()
    if current_time - last_signal_time[symbol] < 120:
        return

    df = fetch_market_data(symbol)
    if df is None:
        return
    
    check_pending_signals(symbol, df)
    
    # مؤشرات التحليل الاحترافي (EMA + Bollinger + Volume)
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
    df['vol_sma'] = df['volume'].rolling(window=10).mean()
    
    i = len(df) - 2
    if i < 5:
        return
        
    close_prev = df['close'].iloc[i]
    open_prev = df['open'].iloc[i]
    ema9 = df['ema9'].iloc[i]
    ema20 = df['ema20'].iloc[i]
    ema50 = df['ema50'].iloc[i]
    bb_upper = df['bb_upper'].iloc[i]
    bb_lower = df['bb_lower'].iloc[i]
    vol = df['volume'].iloc[i]
    vol_avg = df['vol_sma'].iloc[i]
    current_open = df['open'].iloc[-1]
    
    is_strong_uptrend = (ema9 > ema20) and (ema20 > ema50) and (close_prev > bb_upper * 0.99) and (vol >= vol_avg)
    is_strong_downtrend = (ema9 < ema20) and (ema20 < ema50) and (close_prev < bb_lower * 1.01) and (vol >= vol_avg)
    
    signal_type = None
    if is_strong_uptrend and close_prev > open_prev:
        signal_type = 'CALL'
    elif is_strong_downtrend and close_prev < open_prev:
        signal_type = 'PUT'
        
    if signal_type:
        last_signal_time[symbol] = current_time
        emoji = '🟢 (صعود - CALL)' if signal_type == 'CALL' else '🔴 (هبوط - PUT)'
        
        now_dt = datetime.now()
        time_str = now_dt.strftime('%H:%M:%S')
        end_1m = (now_dt + timedelta(minutes=1)).strftime('%H:%M:%S')
        end_5m = (now_dt + timedelta(minutes=5)).strftime('%H:%M:%S')
        
        msg = (
            f"⚡ **QUANT-X PRO SIGNAL + ANALYZER** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 الزوج: `{symbol}` (سوق حقيقي)\n"
            f"📊 الإشارة: **{signal_type} {emoji}**\n"
            f"⏰ وقت الإرسال: `{time_str}`\n"
            f"⏳ نهاية صفقة الدقيقة: `{end_1m}`\n"
            f"⏳ نهاية صفقة الـ 5 دقائق: `{end_5m}`\n"
            f"💡 *تحليل احترافي (EMA + Bollinger) - فحص فوري ونتائج مزدوجة*"
        )
        
        send_telegram_message(msg)
        with stats_lock:
            pending_signals.append({
                'symbol': symbol,
                'type': signal_type,
                'price': current_open,
                'index': len(df) - 1 # لحساب الـ 5 دقائق بدقة
            })
        print(f"تم إرسال إشارة مع تتبع النتائج لـ {symbol}")

def run_bot_loop():
    while True:
        threads = []
        for symbol in SYMBOLS:
            t = threading.Thread(target=process_symbol, args=(symbol,))
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        time.sleep(20)

def send_periodic_results():
    global current_hour_stats
    with stats_lock:
        wins = current_hour_stats["wins"]
        losses = current_hour_stats["losses"]
        total = current_hour_stats["total"]
        
        win_rate = (wins / total) * 100 if total > 0 else 0.0
        
        report = (
            f"📊 **تقرير أداء الجلسة الدوري (كل 5 دقائق)** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي صفقات الدقيقة المنتهية: `{total}`\n"
            f"✅ صفقات ناجحة (ITM): `{wins}`\n"
            f"❌ صفقات خاسرة (OTM): `{losses}`\n"
            f"📈 نسبة الفوز المحققة: `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *QUANT-X SESSION REPORT BOT*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 بدء تشغيل البوت مع نظام تتبع نتائج الدقيقة والـ 5 دقائق...")
    send_telegram_message("🟢 **تم تفعيل نظام النتائج الفورية (دقيقة واحدة) ومحاكاة صفقات الـ 5 دقائق بجانب ملخص الجلسة!**")
    
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    while True:
        time.sleep(300) # ملخص كل 5 دقائق
        send_periodic_results()
