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

# متغيرات الإحصائيات العامة والدورية
stats_lock = threading.Lock()
global_stats = {
    "wins": 0,
    "losses": 0,
    "wins_m1": 0,
    "total": 0
}

# إحصائيات خاصة بكل زوج على حدة
symbol_stats = {sym: {"wins": 0, "losses": 0} for sym in SYMBOLS}

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

def process_pending_signals(symbol, df):
    """
    فحص الصفقات المعلقة بنظام المضاعفة الواحدة (Martingale x1)
    بدون إرسال رسائل مزعجة فورية، فقط لتحديث العدادات بصمت.
    """
    global pending_signals, global_stats, symbol_stats
    if df is None or len(df) < 3:
        return
    
    current_close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    
    with stats_lock:
        remaining_signals = []
        for sig in pending_signals:
            if sig['symbol'] == symbol:
                sig_type = sig['type']
                step = sig['step']
                entry_price = sig['price']
                
                # التحقق هل ربحت الصفقة الحالية أم لا
                is_win = False
                if sig_type == 'CALL' and current_close > entry_price:
                    is_win = True
                elif sig_type == 'PUT' and current_close < entry_price:
                    is_win = True
                
                if is_win:
                    # صفقة رابحة
                    if step == 1:
                        global_stats["wins"] += 1
                    else:
                        global_stats["wins_m1"] += 1
                    global_stats["total"] += 1
                    symbol_stats[symbol]["wins"] += 1
                else:
                    # صفقة خاسرة
                    if step == 1:
                        # لم تنجح الأساسية، نقوم بفتح مضاعفة أولى (Martingale x1) فوراً على الشمعة الحالية
                        next_open = df['open'].iloc[-1]
                        remaining_signals.append({
                            'symbol': symbol,
                            'type': sig_type,
                            'price': next_open,
                            'step': 2
                        })
                    else:
                        # فشلت حتى المضاعفة الأولى
                        global_stats["losses"] += 1
                        global_stats["total"] += 1
                        symbol_stats[symbol]["losses"] += 1
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def process_symbol(symbol):
    global pending_signals
    df = fetch_market_data(symbol)
    if df is None:
        return
    
    # تحديث نتائج الصفقات السابقة بصمت
    process_pending_signals(symbol, df)
    
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
    current_open = df['open'].iloc[-1]
    
    is_uptrend = close_prev > ema20
    is_downtrend = close_prev < ema20
    
    signal_type = None
    if is_uptrend and close_prev > open_prev:
        signal_type = 'CALL'
    elif is_downtrend and close_prev < open_prev:
        signal_type = 'PUT'
        
    if signal_type:
        emoji = '🟢 (صعود - CALL)' if signal_type == 'CALL' else '🔴 (هبوط - PUT)'
        
        # جلب إحصائيات هذا الزوج وحده لإرسالها تحت الإشارة
        with stats_lock:
            s_wins = symbol_stats[symbol]["wins"]
            s_losses = symbol_stats[symbol]["losses"]
            s_total = s_wins + s_losses
            s_wr = (s_wins / s_total * 100) if s_total > 0 else 0.0
            
            # تسجيل الصفقة الجديدة
            pending_signals.append({
                'symbol': symbol,
                'type': signal_type,
                'price': current_open,
                'step': 1
            })

        msg = (
            f"⚡ **LEGEND SIGNAL - تحليل فني مباشر** ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💱 الزوج: `{symbol}` (سوق حقيقي)\n"
            f"📊 الإشارة: **{signal_type} {emoji}**\n"
            f"⏰ الفريم: `1M` | الوقت: `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"💡 *الدخول مع افتتاح الشمعة القادمة (مع قبول مضاعفة واحدة عند اللزوم)*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📈 **إحصائيات الزوج ({symbol}):**\n"
            f"🎯 إجمالي صفقاته: `{s_total}` | ✅ رابحة: `{s_wins}` | ❌ خاسرة: `{s_losses}`"
        )
        
        send_telegram_message(msg)
        print(f"تم إرسال إشارة لـ {symbol}")

def run_bot_loop():
    while True:
        threads = []
        for symbol in SYMBOLS:
            t = threading.Thread(target=process_symbol, args=(symbol,))
            t.start()
            threads.append(t)
            
        for t in threads:
            t.join()
            
        time.sleep(30)

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
            f"📊 **الملخص الدوري لأداء البوت (كل 5 دقائق)** 📊\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 إجمالي الصفقات المنتهية: `{total}`\n"
            f"✅ ربح بدون مضاعفة: `{wins}` ✅\n"
            f"✅ ربح بمضاعفة واحدة: `{wins_m1}` ✅1\n"
            f"❌ صفقات خاسرة: `{losses}`\n"
            f"📈 نسبة الفوز الإجمالية: `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *LEGEND - MARTINGALE x1 BOT*"
        )
        send_telegram_message(report)

if __name__ == "__main__":
    print("🚀 بدء تشغيل البوت بنظام إحصائيات الزوج وملخص الـ 5 دقائق...")
    send_telegram_message("🟢 **تم تفعيل نظام إحصائيات الزوج تحت الإشارة + ملخص كل 5 دقائق + دعم مضاعفة واحدة (✅ / ✅1)!**")
    
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # إرسال التقرير الدوري كل 5 دقائق (300 ثانية)
    while True:
        time.sleep(300)
        send_periodic_results()
