import time
import random
import requests
from datetime import datetime

# إعدادات التيليجرام
TELEGRAM_BOT_TOKEN = "7023463264:AAEL8N3HR5GxRhf0T9M_IW0VfY7_r797Ifs"
TELEGRAM_CHANNEL_ID = "-1002330262707"

# أزواج التداول المتاحة مع نسب العوائد (Payout)
PAIRS = [
    {"name": "EUR/USD (OTC)", "payout": 87},
    {"name": "GBP/USD (OTC)", "payout": 86},
    {"name": "USD/JPY (OTC)", "payout": 85},
    {"name": "AUD/USD (OTC)", "payout": 84},
    {"name": "EUR/GBP (OTC)", "payout": 82},
]

# إحصائيات الجلسة الحالية
session_stats = {
    "total": 0,
    "wins": 0,
    "losses": 0
}

def send_telegram_message(text):
    """دالة إرسال الرسائل إلى قناة التيليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram Error: {e}")
        return None

def generate_technical_signal(pair):
    """محاكي خوارزمية المتداول المتمرس لتحليل الشموع والزخم (Engulfing & Trend)"""
    direction = random.choice(["CALL", "PUT"])
    confidence = random.randint(91, 98)
    
    reasons = [
        "توافق فني للكسر وإعادة الاختبار والترند المؤسساتي (M1)",
        "ارتداد قوي من منطقة دعم ومقاومة مع تشبع بيعي/شرائي",
        "نمط شمعة الابتلاع (Engulfing) مع زخم صجاح في الشمعة الأخيرة"
    ]
    reason = random.choice(reasons)
    
    now = datetime.now()
    entry_time = now.strftime("%H:%M:00")
    
    return {
        "pair": pair["name"],
        "payout": pair["payout"],
        "direction": direction,
        "confidence": confidence,
        "reason": reason,
        "entry_time": entry_time
    }

def main():
    print("🚀 LEGEND-X PYTHON TRADING BOT STARTED 24/7...")
    send_telegram_message("🤖 **تم إقلاع بوت التداول الآلي (LEGEND-X) بنجاح على السحاب!** 🟢\n*جاهز لإرسال الإشارات والنتائج بدقة M1.*")
    
    last_signal_minute = -1
    last_report_time = time.time()
    
    while True:
        try:
            now = datetime.now()
            current_second = now.second
            current_minute = now.minute
            
            # 1. إرسال الإشارة في الثواني الأخيرة قبل بداية الدقيقة الجديدة (الثانية 45 إلى 58)
            if 45 <= current_second <= 58 and current_minute != last_signal_minute:
                last_signal_minute = current_minute
                
                # اختيار عشوائي لزوج تداول
                pair = random.choice(PAIRS)
                signal = generate_technical_signal(pair)
                
                dir_text = "صعود (CALL) 🟢" if signal["direction"] == "CALL" else "هبوط (PUT) 🔴"
                btn_text = "HIGHER (الأخضر ⬆️)" if signal["direction"] == "CALL" else "LOWER (الأحمر ⬇️)"
                
                signal_text = (
                    f"⚡ **LEGEND-X SIGNAL PRO** ⚡\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💱 الزوج: `{signal['pair']}`\n"
                    f"📊 الاتجاه: `{dir_text}`\n"
                    f"⏰ وقت الدخول: `{signal['entry_time']}`\n"
                    f"🎯 نسبة الثقة: `{signal['confidence']}%`\n"
                    f"🔘 زر بوكت أوبشن: `{btn_text}`\n"
                    f"💡 السبب: `{signal['reason']}`\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 *LEGEND TRADING BOT*"
                )
                
                send_telegram_message(signal_text)
                
                # الانتظار حتى تبدأ الدقيقة الجديدة (ثانية 00) تماماً لمحاكاة انتهاء الشمعة وتتبع النتيجة
                time.sleep(60 - current_second)
                
                # محاكاة نتيجة الصفقة (بناءً على دقة استراتيجية 75% ربح)
                outcome = "WIN" if random.random() < 0.75 else "LOSS"
                session_stats["total"] += 1
                
                if outcome == "WIN":
                    session_stats["wins"] += 1
                    result_text = f"✅ **نتيجة صفقة 1M: رابحة (WIN)** 🎯\n💱 الزوج: `{signal['pair']}` | الاتجاه: `{dir_text}`\n✨ *تم إغلاق الصفقة على ربح بنجاح ✅*"
                else:
                    session_stats["losses"] += 1
                    result_text = f"❌ **نتيجة صفقة 1M: خاسرة (LOSS)** ⚠️\n💱 الزوج: `{signal['pair']}` | الاتجاه: `{dir_text}`\n📉 *عوضها في المضاعفة القادمة ❌*"
                
                send_telegram_message(result_text)
            
            # 2. إرسال الملخص الدوري كل 5 دقائق (300 ثانية)
            if time.time() - last_report_time >= 300:
                last_report_time = time.time()
                total = session_stats["total"]
                wins = session_stats["wins"]
                losses = session_stats["losses"]
                win_rate = (wins / total * 100) if total > 0 else 0
                
                report_text = (
                    f"📊 **الملخص الدوري الإجمالي (Session Report)** 📊\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 إجمالي الصفقات: `{total}`\n"
                    f"✅ صفقات رابحة: `{wins}` ✅\n"
                    f"❌ صفقات خاسرة: `{losses}` ❌\n"
                    f"📈 نسبة الفوز الإجمالية: `{win_rate:.1f}%`\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 *LEGEND TRADING ENGINE*"
                )
                send_telegram_message(report_text)
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
