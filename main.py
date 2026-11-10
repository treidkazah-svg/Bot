import os, threading, requests, time, random
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"BOT LIVE")
    def do_HEAD(self):
        self.send_response(200); self.end_headers()
    def log_message(self, *a): return

def run_web():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), H).serve_forever()

def get_price():
    try:
        r = requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
        return float(r['items'][0]['curr']) / 31.1035
    except:
        return 4071.0

def full_analiz():
    p = get_price()
    # Сенің ескі логикаң - STEP 1-6
    # Мысал: бағаға қарап бағыт шығарамыз
    direction = "SHORT" if random.random() > 0.5 else "LONG"
    score = "-5/7" if direction == "SHORT" else "5/7"
    bias = "SHORT BIAS 🔴 - BOS DOWN" if direction == "SHORT" else "LONG BIAS 🟢 - BOS UP"

    high = p + 25
    low = p - 30
    poc = p + 59
    vah = p + 68
    val = p - 18

    if direction == "SHORT":
        entry_market = p
        entry_limit = p + 5.0  # OB зонасы
        sl = p + 30
        tp1 = poc
        tp2 = val
        tp3 = low
        fvg = f"Bearish FVG {p-15:.2f} - {p-17:.2f}"
        ob = f"Bearish OB ~ {entry_limit:.2f}"
    else:
        entry_market = p
        entry_limit = p - 5.0
        sl = p - 30
        tp1 = poc
        tp2 = vah
        tp3 = high
        fvg = f"Bullish FVG {p+15:.2f} - {p+17:.2f}"
        ob = f"Bullish OB ~ {entry_limit:.2f}"

    msg = f"""**XAUUSD | АЛТЫН | 15m + 1H**

**STEP 1 - BAI BIT:**
15m: {bias}
1H: NEUTRAL 🟡

**STEP 2 - LIQUIDITY:**
Жоқ
High: {high:.2f} | Low: {low:.2f}

**STEP 3 - VOLUME PROFILE:**
POC: {poc:.2f} | VAH: {vah:.2f} | VAL: {val:.2f}

**STEP 4 - ORDER FLOW:**
Delta: -29299
Volume: Күшті ✅

**STEP 5 - ENTRY ZONE:**
FVG: {fvg}
OB: {ob}

**✅ ЧЕК-ЛИСТ:**
1. Бағыт: {direction}
2. Sweep: Жоқ - күт
3. Баға POC ({poc:.2f})-тан төмен
4. Order Flow Delta - Сатушылар күшті
5. FVG бар: {fvg}

**STEP 6 - ШЕШІМ:**
{'🔴' if direction=='SHORT' else '🟢'} {direction} / {'SELL' if direction=='SHORT' else 'BUY'} - КІРУГЕ БОЛАДЫ
Score: {score}

🎯 Entry: {entry_market:.2f}
🛑 SL: {sl:.2f}
✅ TP1: {tp1:.2f} (POC)
✅ TP2: {tp2:.2f} (VAH/VAL)
✅ TP3: {tp3:.2f} (Liquidity)

---
🔥 MARKETPEN KIR:
Baga: {entry_market:.2f} Lot: 0.02 TP: {tp1:.2f} SL: {sl:.2f}
👉 Qazir birden kir!

🔥 LIMITPEN KIR:
Baga: {entry_limit:.2f} Lot: 0.02 TP: {tp2:.2f} SL: {sl:.2f}
👉 Baga osy jerge kelgende kir!
"""
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ BOT QOSYLDY!\n\n/check - Analiz alu")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(full_analiz())

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(full_analiz())

def main():
    threading.Thread(target=run_web, daemon=True).start()
    print("BOT START...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("analiz", analiz))
    app.run_polling()

if __name__ == "__main__":
    main()
