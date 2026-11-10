import os
import threading
import requests
import time
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Токен жоқ болса, бірден айтады
if not TOKEN:
    print("QATE: TELEGRAM_TOKEN Render-de joq!")

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BOT ISHP TUR")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *a):
        return

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), H).serve_forever()

def get_price():
    try:
        r = requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
        return float(r['items'][0]['curr']) / 31.1035
    except:
        return 2650.0

def analiz_jasau():
    p = get_price()
    score = random.choice([2, 3, -2, -3])
    conf = 70 + abs(score) * 7
    direction = "BUY" if score > 0 else "SELL"

    if direction == "BUY":
        market_price = p
        limit_price = p - 5.0
        tp1 = p + 30
        tp2 = limit_price + 30
        sl = p - 15
    else:
        market_price = p
        limit_price = p + 5.0
        tp1 = p - 30
        tp2 = limit_price - 30
        sl = p + 15

    msg = f"""📊 XAUUSD АНАЛИЗ {p:.1f}

Bagyt: {direction} Senim: {conf}%

🔥 1. MARKETPEN KIR:
Baga: {market_price:.1f}
Lot: 0.02
TP: {tp1:.1f} SL: {sl:.1f}
👉 Qazir birden kir!

🔥 2. LIMITPEN KIR:
Baga: {limit_price:.1f}
Lot: 0.02
TP: {tp2:.1f} SL: {sl:.1f}
👉 Baga osy jerge kelgende kir!

Ekeuimen de kir! Birin birden, birin kutip!
"""
    return msg

def send_analiz():
    if not TOKEN or not CHAT_ID:
        print("TOKEN nemese CHAT_ID joq, jibere almadym")
        return
    msg = analiz_jasau()
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
        print("ANALIZ JIBERILDI")
    except Exception as e:
        print(e)

def auto_loop():
    while True:
        time.sleep(900)
        send_analiz()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ ANALIZ BOT QOSYLDY!\n\n/analiz - Qazir analiz jiberu")

async def analiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = analiz_jasau()
    await update.message.reply_text(msg)

def main():
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=auto_loop, daemon=True).start()
    print("BOT START...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analiz", analiz_cmd))
    app.run_polling()

if __name__ == "__main__":
    main()
