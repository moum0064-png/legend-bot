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

# التركيز على زوج واحد فقط (يمكنك تغييره متى شئت مثل "EURGBP" أو "USDJPY")
TARGET_SYMBOL = "EURUSD"

# إحصائيات الأداء العامة
stats_lock = threading.Lock()
global_stats = {
    "wins": 0,
    "losses": 0,
    "wins_m1": 0,
    "total": 0
}

last_signal_time = 0
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

def check_pending_signals(df, symbol):
    global pending_signals, global_stats
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
                            res_msg = f"✅ **نتيجة صفقة 1M: رابحة (WIN)** 🎯\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n✨ *ربح من الدخول الأساسي (بدون مضاعفة ✅)*"
                        else:
                            global_stats["wins_m1"] += 1
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
                            global_stats["total"] += 1
                            loss_msg = f"❌ **نتيجة صفقة 1M: خاسرة (LOSS)** ⚠️\n💱 الزوج: `{symbol}` | الاتجاه: `{sig_type}`\n💰 الدخول: `{entry_price}` | الإغلاق: `{current_close}`\n📉 *فشلت الصفقة مع المضاعفة*"
                            send_telegram_message(loss_msg)
                else:
                    remaining_signals.append(sig)
            else:
                remaining_signals.append(sig)
                
        pending_signals = remaining_signals

def run_bot_loop():
    global last_signal_time, pending_signals
    print(f"🚀 Started aggressive single-pair bot for {TARGET_SYMBOL}...")
    send_telegram_message(f"🟢 **تم تفعيل وضع الجلسات السريعة الجبار على زوج واحد (`{TARGET_SYMBOL}`) بزخم عنيف!**")
    
    while True:
        try:
            df = fetch_market_data(TARGET_SYMBOL)
            if df is not None:
                check_pending_signals(df, TARGET_SYMBOL)
                
                # استراتيجية سريعة وعنيفة تعتمد على RSI والزخم (توليد صفقات مكثفة)
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
                df['bb_mid'] = df['close'].rolling(window=10).mean()
                df['bb_std'] = df['close'].rolling(window=10).std()
                df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 1.8)
                df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 1.8)
                
                i = len(df) - 2
                if i >= 5:
                    current_time = time.time()
                    # استراحة قصيرة جداً (60 ثانية فقط) لضمان ضخ صفقات مستمرة كل دقيقة
                    if current_time - last_signal_time >= 60:
                        close_p = df['close'].iloc[i]
                        open_p = df['open'].iloc[i]
                        rsi_val = df['rsi'].iloc[i]
                        bb_up = df['bb_upper'].iloc[i]
                        bb_low = df['bb_lower'].iloc[i]
                        current_open = df['open'].iloc[-1]
                        
                        signal_type = None
                        # شروط عنيفة سريعة للاختراق
                        if close_p > bb_up and rsi_val > 55 and close_p > open_p:
                            signal_type = 'CALL'
                        elif close_p < bb_low and rsi_val < 45 and close_p < open_p:
                            signal_type = 'PUT'
                            
                        if signal_type:
                            last_signal_time = current_time
                            emoji = 'صعود - CALL' if signal_type == 'CALL' else 'هبوط - PUT'
                            emoji_icon = '🟢' if signal_type == 'CALL' else '🔴'
                            
                            now_dt = datetime.now()
                            next_candle_dt = (now_dt + timedelta(minutes=1)).replace(second=0, microsecond=0)
                            target_ts = int(next_candle_dt.timestamp()) + 60
                            
                            time_str = next_candle_dt.strftime('%H:%M:%S')
                            end_1m = (next_candle_dt + timedelta(minutes=1)).strftime('%H:%M:%S')
                            end_5m = (next_candle_dt + timedelta(minutes=5)).strftime('%H:%M:%S')
                            
                            msg = (
                                f"⚡ **LEGEND-X CHINESE SESSION PRO** ⚡\n"
                                f"━━━━━━━━━━━━━━━━━━━\n"
                                f"💱 الزوج: `{TARGET_SYMBOL}` (جلسة مكثفة)\n"
                                f"📊 الإشارة: `{signal_type}` {emoji_icon} `({emoji})`\n"
                                f"⏰ الفريم: `1M` | وقت الدخول: `{time_str}`\n"
                                f"⏳ نهاية صفقة الدقيقة: `{end_1m}`\n"
                                f"⏳ نهاية صفقة الـ 5 دقائق: `{end_5m}`\n"
                                f"🔥 *صفقة سريعة بنظام الزخم العنيف (مضاعفة أولى عند اللزوم)*"
                            )
                            
                            send_telegram_message(msg)
                            with stats_lock:
                                pending_signals.append({
                                    'symbol': TARGET_SYMBOL,
                                    'type': signal_type,
                                    'price': current_open,
                                    'step': 1,
                                    'target_ts': target_ts
                                })
            
        except Exception as e:
            print(f"Error in aggressive loop: {e}")
        
        time.sleep(15) # فحص متواصل وسريع جداً

def send_periodic_results():
    global global_stats
    while True:
        time.sleep(300)
        try:
            with stats_lock:
                wins = global_stats["wins"]
                wins_m1 = global_stats["wins_m1"]
                losses = global_stats["losses"]
                total = global_stats["total"]
                
                total_wins = wins + wins_m1
                win_rate = (total_wins / total) * 100 if total > 0 else 0.0
                
                report = (
                    f"📊 **الملخص الدوري للجلسة (كل 5 دقائق)** 📊\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 إجمالي الصفقات: `{total}`\n"
                    f"✅ ربح أساسي: `{wins}` ✅\n"
                    f"✅ ربح مضاعفة: `{wins_m1}` ✅1\n"
                    f"❌ صفقات خاسرة: `{losses}`\n"
                    f"📈 نسبة الفوز: `{win_rate:.1f}%`\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 *LEGEND-X CHINESE SESSIONS*"
                )
                send_telegram_message(report)
        except Exception as e:
            print(f"Error in periodic results: {e}")

if __name__ == "__main__":
    print(f"🚀 بدء التشغيل بنظام الجلسات الصينية السريعة لزوج {TARGET_SYMBOL}...")
    
    bot_thread = threading.Thread(target=run_bot_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    report_thread = threading.Thread(target=send_periodic_results)
    report_thread.daemon = True
    report_thread.start()
    
    while True:
        time.sleep(3600)
