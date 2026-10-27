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

# إحصائيات الأداء العامة
stats_lock = threading.Lock()
global_stats = {
    "wins": 0,
    "losses": 0,
    "wins_m1": 0,
    "total": 0
}

# تتبع وقت آخر إشارة لكل زوج (استراحة دقيقتين لمنع التكرار المزعج)
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
    """
    تتبع الصفقات المعلقة ونظام المضاعفة الواحدة (Martingale x1) مع إرسال النتائج الفورية
    """
    global pending_signals, global_stats
    if df is None or len(df) < 3:
        return
    
    current_close = df['close'].iloc[-1]
    
    with stats_lock:
        remaining_signals = []
        for sig in pending_signals:
            if sig['symbol'] == symbol:
                sig_type = sig['type']
                step = sig['step']
                entry_price = sig['price']
                
                is_win = False
                if sig_type == 'CALL' and current_close > entry_price:
                    is_win = True
                elif sig_type == 'PUT' and current_close < entry_price:
                    is_win = True
                
                if is_win:
                    if step == 1:
                        global_stats["wins"] += 1
                        res_msg = f"✅ **نتيجة الصفقة: رابحة (WIN)** 🎯\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n✨ *ربح من الدخول الأساسي (بدون مضاعفة ✅)*"
                    else:
                        global_stats["wins_m1"] += 1
                        res_msg = f"✅1 **نتيجة الصفقة: رابحة بالمضاعفة (WIN M1)** 🎯\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n✨ *ربح بمضاعفة واحدة (✅1)*"
                    
                    global_stats["total"] += 1
                    send_telegram_message(res_msg)
                else:
                    if step == 1:
                        # فشلت الصفقة الأساسية، نقوم بفتح مضاعفة أولى (Martingale x1) فوراً على الشمعة الحالية
                        next_open = df['open'].iloc[-1]
                        remaining_signals.append({
                            'symbol': symbol,
                            'type': sig_type,
                            'price': next_open,
                            'step': 2
                        })
                        m_msg = f"⚠️ **تنبيه مضاعفة أولى (Martingale x1)** 🔄\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💡 *جاري تفعيل المضاعفة لتعويض الصفقة السابقة...*"
                        send_telegram_message(m_msg)
                    else:
                        # فشلت حتى المضاعفة الأولى
                        global_stats["losses"] += 1
                        global_stats["total"] += 1
                        loss_msg = f"❌ **نتيجة الصفقة: خاسرة (LOSS)** ⚠️\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n📉 *فشلت الصفقة مع المضاعفة الأولى*"
                        send_telegram_message(loss_msg)
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def process_symbol(symbol):
    global pending_signals, last_signal_time
    
    current_time = time.time()
    if current_time - last_signal_time[symbol] < 120:  # استراحة دقيقتين
        return

    df = fetch_market_data(symbol)
    if df is None:
        return
    
    check_pending_signals(symbol, df)
    
    # مؤشرات التحليل الاحترافي المتقدم (EMA 9/20/50 + Bollinger Bands)
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
    
    original_signal = None
    if is_strong_uptrend and close_prev > open_prev:
        original_signal = 'CALL'
    elif is_strong_downtrend and close_prev < open_prev:
        original_signal = 'PUT'
        
    if original_signal:
        # [عكس الاتجاه بالكامل لتحويل الخسائر إلى أرباح خرافية بناءً على طلبك]
        signal_type = 'PUT' if original_signal == 'CALL' else 'CALL'
        
        last_signal_time[symbol] = current_time
        emoji = 'هبوط - PUT' if signal_type == 'PUT' else 'صعود - CALL'
        emoji_icon = '🔴' if signal_type == 'PUT' else '🟢'
        
        # ضبط توقيت البداية والنهاية للشمعة القادمة بدقة على رأس الدقيقة (الثانية 00)
        now_dt = datetime.now()
        next_candle_dt = (now_dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
        time_str = next_candle_dt.strftime('%H:%M:%S')
        end_1m = (next_candle_dt + timedelta(minutes=1)).strftime('%H:%M:%S')
        end_5m = (next_candle_dt + timedelta(minutes=5)).strftime('%H:%M:%S')
        
        # التنسيق المطلوب تماماً
        msg = (
            f"⚡ **LEGEND-X PRO ANALYZER** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 الزوج: `{symbol}` (سوق حقيقي)\n"
            f"📊 الإشارة العكسية: `{signal_type}` {emoji_icon} `({emoji})`\n"
            f"⏰ وقت الإرسال والدخول: `{time_str}`\n"
            f"⏳ نهاية صفقة الدقيقة: `{end_1m}`\n"
            f"⏳ نهاية صفقة الـ 5 دقائق: `{end_5m}`\n"
            f"💡 حاول اخذ الصفقة مارجنال + ادارة رأس المال (مضاعفة أولى عند اللزوم)"
        )
        
        send_telegram_message(msg)
        with stats_lock:
            pending_signals.append({
                'symbol': symbol,
                'type': signal_type,
                'price': current_open,
                'step': 1
            })
        print(f"تم إرسال إشارة عكسية للشمعة القادمة لـ {symbol}")

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
    global global_stats
    with stats_lock:
        wins = global_stats["wins"]
        wins_m1 = global_stats["wins_m1"]
        losses = global_stats["losses"]
        total = global_stats["total"]
        
        total_wins = wins + wins_m1
        win_rate = (total_wins / total) * 100 if total > 0 else 0.0
        
        report = (
            f"📊 **الملخص الدوري للأداء العكسي (كل 5 دقائق)** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي الصفقات المنتهية: `{total}`\n"
            f"✅ ربح بدون مضاعفة: `{wins}` ✅\n"
            f"✅ ربح بمضاعفة واحدة: `{wins_m1}` ✅1\n"
            f"❌ صفقات خاسرة: `{losses}`\n"
            f"📈 نسبة الفوز الإجمالية: `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *LEGEND-X PRO REVERSED BOT*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 بدء تشغيل البوت بنظام الشمعة القادمة + عكس الاتجاه + المضاعفة...")
    send_telegram_message("🟢 **تم تفعيل النسخة الاحترافية: تحليل الشمعة القادمة + عكس الاتجاه بالكامل + مضاعفة واحدة (✅ / ✅1)!**")
    
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    while True:
        time.sleep(300)
        send_periodic_results()
