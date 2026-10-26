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

# إعدادات متوازنة (تضمن كثرة الصفقات وقوتها)
RSI_PERIOD = 7
ADX_PERIOD = 14
ADX_MIN_LEVEL = 5  # قيمة متوازنة لتلتقط صفقات كثيرة ومستمرة
EMA_PERIOD = 20

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
                
                is_win = False
                if sig_type == 'CALL' and last_close > entry_price:
                    is_win = True
                elif sig_type == 'PUT' and last_close < entry_price:
                    is_win = True
                
                if is_win:
                    current_hour_stats["wins"] += 1
                    res_msg = f"✅ **تحديث نتيجة صفقة (WIN - رابحة)** 🎯\n💱 الزوج: `{symbol}`\n📈 النوع: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                else:
                    current_hour_stats["losses"] += 1
                    res_msg = f"❌ **تحديث نتيجة صفقة (LOSS - خاسرة)** ⚠️\n💱 الزوج: `{symbol}`\n📈 النوع: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{last_close}`"
                
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
        
        # فحص النتائج السابقة بدقة
        check_pending_signals(symbol, df)
        
        df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
        df['adx'] = calculate_adx(df['high'], df['low'], df['close'], ADX_PERIOD)
        df['ema'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
        
        i = len(df) - 2
        if i < 1:
            continue
            
        rsi_prev = df['rsi'].iloc[i]
        rsi_prev2 = df['rsi'].iloc[i-1]
        adx_val = df['adx'].iloc[i]
        close_price = df['close'].iloc[i]
        ema_val = df['ema'].iloc[i]
        
        # شروط متوازنة تضمن كثرة الصفقات ودقتها العالية
        is_call = (rsi_prev2 <= 30.0 and rsi_prev > 30.0 and adx_val >= ADX_MIN_LEVEL and close_price > ema_val)
        is_put = (rsi_prev2 >= 70.0 and rsi_prev < 70.0 and adx_val >= ADX_MIN_LEVEL and close_price < ema_val)
        
        if is_call:
            msg = (
                f"🚨 **LEGEND PREMIUM SIGNAL** 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💱 الزوج: `{symbol}` (M1)\n"
                f"📈 الاتجاه: **CALL 🟢 (صعود)**\n"
                f"⏰ التوقيت: `{datetime.now().strftime('%H:%M')}`\n"
                f"💡 *الدخول مع افتتاح الشمعة لمدة دقيقة واحدة*"
            )
            send_telegram_message(msg)
            with stats_lock:
                pending_signals.append({'symbol': symbol, 'type': 'CALL', 'price': close_price})
            print(f"تم إرسال إشارة صعود لـ {symbol}")
            
        elif is_put:
            msg = (
                f"🚨 **LEGEND PREMIUM SIGNAL** 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💱 الزوج: `{symbol}` (M1)\n"
                f"📉 الاتجاه: **PUT 🔴 (هبوط)**\n"
                f"⏰ التوقيت: `{datetime.now().strftime('%H:%M')}`\n"
                f"💡 *الدخول مع افتتاح الشمعة لمدة دقيقة واحدة*"
            )
            send_telegram_message(msg)
            with stats_lock:
                pending_signals.append({'symbol': symbol, 'type': 'PUT', 'price': close_price})
            print(f"تم إرسال إشارة هبوط لـ {symbol}")

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
            f"📊 **تقرير الأداء وسجل النتائج** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي الصفقات: `{total}`\n"
            f"✅ صفقات ناجحة (Wins): `{wins}`\n"
            f"❌ صفقات خاسرة (Losses): `{losses}`\n"
            f"📈 نسبة النجاح (Win Rate): `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *LEGEND - LIVE SIGNALS*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 البوت يعمل بالنسخة المتوازنة (صفقات نشطة ونتائج فورية)...")
    send_telegram_message("🟢 **تم ضبط البوت ليرسل صفقات نشطة بشكل متكرر مع تتبع دقيق للنتائج!**")
    
    last_result_time = time.time()
    
    while True:
        run_bot_logic()
        
        if time.time() - last_result_time >= 600:
            send_periodic_results()
            last_result_time = time.time()
            
        time.sleep(60)
