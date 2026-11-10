import os, threading, requests, random, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

class H(BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"ANALIZ BOT")
 def do_HEAD(self): self.send_response(200); self.end_headers()
 def log_message(self,*a): return
def run_web():
 HTTPServer(("0.0.0.0", int(os.environ.get("PORT",10000))), H).serve_forever()

def get_price():
 try:
  r=requests.get("https://data-asg.goldprice.org/dbXRates/USD", timeout=10).json()
  return float(r['items'][0]['curr'])/31.1035
 except: return 2650.0

def analiz_jasau():
 p = get_price()
 # Анализ жасаймыз - мысал
 score = random.choice([2,3,-2,-3])
 conf = 70 + abs(score)*7
 direction = "BUY" if score>0 else "SELL"
 
 if direction=="BUY":
  market_price = p
  limit_price = p - 5.0  # 5 доллар төмен
  tp1 = p + 30
  tp2 = limit_price + 30
  sl = p - 15
 else:
  market_price = p
  limit_price = p + 5.0  # 5 доллар жоғары
  tp1 = p - 30
  tp2 = limit_price - 30
  sl = p + 15

 lot_market = 0.02
 lot_limit = 0.02

 msg = f"""📊 XAUUSD АНАЛИЗ {p:.1f}

Бағыт: {direction} Сенім: {conf}%

🔥 1. МАРКЕТПЕН КІР:
Баға: {market_price:.1f}
Лот: {lot_market}
TP: {tp1:.1f} SL: {sl:.1f}
👉 Қазір бірден кір!

🔥 2. ЛИМИТПЕН КІР:
Баға: {limit_price:.1f}
Лот: {lot_limit}
TP: {tp2:.1f} SL: {sl:.1f}
👉 Баға осы жерге келгенде кір!

Екеуімен де кір! Бірін бірден, бірін күтіп!
"""
 return msg, direction

def send_analiz():
 msg, direction = analiz_jasau()
 try:
  requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
  print("ANALIZ JIBERILDI")
 except Exception as e: print(e)

def auto_loop():
 while True:
  time.sleep(900) # 15 минут сайын
  send_analiz()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
 await update.message.reply_text("✅ АНАЛИЗ БОТ ҚОСЫЛДЫ!\n\n/analiz - Қазір анализ жіберу\nБот әр 15 минут сайын өзі жібереді!")

async def analiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
 msg, direction = analiz_jasau()
 await update.message.reply_text(msg)

def main():
 threading.Thread(target=run_web,daemon=True).start()
 threading.Thread(target=auto_loop,daemon=True).start()
 app=ApplicationBuilder().token(TOKEN).build()
 app.add_handler(CommandHandler("start",start))
 app.add_handler(CommandHandler("analiz",analiz_cmd))
 print("ANALIZ BOT RUNNING")
 app.run_polling()
if __name__=="__main__": main()
