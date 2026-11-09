import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import ccxt
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Render үшін ---
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"SMC + Orderflow Bot is running!")
        def log_message(self, format, *args):
            return
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SYMBOL = "XAU/USD"
TIMEFRAME = "15m"

# --- СЕНІҢ НАСТРОЙКАҢ ---
DEPOSIT = 100      # Депозитің $ - осыны өзіңе қарай өзгерт
LEVERAGE = 10      # Плечо
TARGET_PROFIT = 60 # Қанша $ алғың келеді
POSITION_SIZE = DEPOSIT * LEVERAGE  # 100*10 = 1000$ позиция

exchange = ccxt.binance()

# Ашық сделканы сақтаймыз
active_trade = {
    "direction": None,  # LONG / SHORT
    "entry": 0,
    "tp": 0,
    "be_warned": False,
    "confidence": 0
}

def get_candles(limit=100):
    return exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)

def get_price():
    return exchange.fetch_ticker(SYMBOL)['last']

# ================= SMC =================
def check_smc():
    try:
        candles = get_candles(100)
        last_close = candles[-1][4]
        highs, lows = [], []
        for i in range(2, len(candles)-2):
            h, l = candles[i][2], candles[i][3]
            if h > candles[i-1][2] and h > candles[i-2][2] and h > candles[i+1][2] and h > candles[i+2][2]:
                highs.append((i, h))
            if l < candles[i-1][3] and l < candles[i-2][3] and l < candles[i+1][3] and l < candles[i+2][3]:
                lows.append((i, l))
        if not highs or not lows:
            return 0, 0, "SMC: Swing жоқ"
        last_sh, last_sl = highs[-1][1], lows[-1][1]
        prev_h = highs[-2][1] if len(highs)>=2 else last_sh
        prev_l = lows[-2][1] if len(lows)>=2 else last_sl

        bos_up = last_close > last_sh
        bos_down = last_close < last_sl
        sweep_low = min(c[3] for c in candles[-3:]) < prev_l and last_close > prev_l
        sweep_high = max(c[2] for c in candles[-3:]) > prev_h and last_close < prev_h
        c1, c3 = candles[-3], candles[-1]
        fvg_bull = c1[2] < c3[3]
        fvg_bear = c1[3] > c3[2]

        # Балл жинаймыз - уверенность үшін
        score = 0
        details = []
        if bos_up: score += 30; details.append("BOS UP +30")
        if bos_down: score += 30; details.append("BOS DOWN +30")
        if sweep_low: score += 25; details.append("Sweep Low +25")
        if sweep_high: score += 25; details.append("Sweep High +25")
        if fvg_bull: score += 20; details.append("FVG Bull +20")
        if fvg_bear: score += 20; details.append("FVG Bear +20")

        direction = 0
        if bos_up or sweep_low or fvg_bull:
            # LONG бағыты басым ба?
            long_pts = (30 if bos_up else 0) + (25 if sweep_low else 0) + (20 if fvg_bull else 0)
            short_pts = (30 if bos_down else 0) + (25 if sweep_high else 0) + (20 if fvg_bear else 0)
            if long_pts > short_pts:
                direction = 1
                score = long_pts
            elif short_pts > long_pts:
                direction = -1
                score = short_pts
            else:
                direction = 0

        return direction, score, " | ".join(details) if details else "SMC: Күту"
    except Exception as e:
        return 0, 0, f"SMC Қате: {e}"

# ================= ORDERFLOW =================
def check_orderflow():
    try:
        candles = get_candles(30)
        cvd = sum(c[5] if c[4] > c[1] else -c[5] for c in candles)
        last5 = sum(c[5] if c[4] > c[1] else -c[5] for c in candles[-5:])
        avg_vol = sum(c[5] for c in candles[:-1]) / (len(candles)-1)
        vol_strong = candles[-1][5] > avg_vol * 1.5

        if cvd > 0 and last5 > 0:
            pts = 30 + (15 if vol_strong else 0)
            return 1, pts, f"Orderflow LONG | CVD: {int(cvd)} | Көлем күшті: {vol_strong}"
        if cvd < 0 and last5 < 0:
            pts = 30 + (15 if vol_strong else 0)
            return -1, pts, f"Orderflow SHORT | CVD: {int(cvd)} | Көлем күшті: {vol_strong}"
        return 0, 0, f"Orderflow Бейтарап | CVD: {int(cvd)}"
    except Exception as e:
        return 0, 0, f"OF Қате: {e}"

# ================= АНАЛИЗ + УВЕРЕННОСТЬ =================
def analyze():
    smc_dir, smc_pts, smc_text = check_smc()
    of_dir, of_pts, of_text = check_orderflow()

    # Екеуі бір бағыт болса ғана
    if smc_dir != 0 and smc_dir == of_dir:
        # Уверенность: SMC 55% + OF 45% = 100%
        # SMC макс 75, OF макс 45. Нормалаймыз
        confidence = min(100, int((smc_pts / 75 * 55) + (of_pts / 45 * 45)))
        direction = "LONG" if smc_dir == 1 else "SHORT"
        return direction, confidence, smc_text, of_text
    return None, 0, smc_text, of_text

def calc_tp(entry, direction):
    # 50$ алу үшін қанша % керек?
    # Позиция 1000$ болса, 50$ = 5%
    percent_needed = TARGET_PROFIT / POSITION_SIZE
    if direction == "LONG":
        return entry * (1 + percent_needed)
    else:
        return entry * (1 - percent_needed)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SMC + Orderflow бот қосылды! 📈\n\n"
        "Логика:\n"
        "✅ Уверенность 90%+ болса ғана сигнал\n"
        "✅ Тейк = 50$\n"
        "✅ Баға қарсы жүрсе → БУ-ге жап деп ескертем\n\n"
        "Тексеру: /check\n"
        f"Депозит: {DEPOSIT}$ | Плечо: x{LEVERAGE} | Позиция: {POSITION_SIZE}$"
    )

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тексеріп жатырмын... ⏳")
    direction, conf, smc_text, of_text = analyze()
    price = get_price()
    if direction and conf >= 90:
        tp = calc_tp(price, direction)
        msg = (f"🚨 {direction} СИГНАЛ!\n\n"
               f"Уверенность: {conf}% 🔥\n"
               f"Кіру: {price}\n"
               f"Тейк (50$): {tp:.2f}\n"
               f"Стоп: БУ-ге қоямыз, қарсы жүрсе ескертем\n\n"
               f"SMC: {smc_text}\nOrderflow: {of_text}")
    else:
        msg = (f"⚪ Сигнал жоқ\n\nУверенность: {conf}% (керек 90%+)\n"
               f"Баға: {price}\n\nSMC: {smc_text}\nOrderflow: {of_text}")
    await update.message.reply_text(msg)

# ================= ФОНДЫҚ БАҚЫЛАУ =================
def signal_loop(app):
    import asyncio
    while True:
        try:
            # 1. Жаңа сигнал бар ма?
            if active_trade["direction"] is None:
                direction, conf, smc_text, of_text = analyze()
                if direction and conf >= 90:
                    entry = get_price()
                    tp = calc_tp(entry, direction)
                    active_trade.update({
                        "direction": direction, "entry": entry, "tp": tp,
                        "be_warned": False, "confidence": conf
                    })
                    text = (f"🚨 {direction} СИГНАЛ! Уверенность {conf}% 🔥\n\n"
                            f"Кіру: {entry}\n"
                            f"Тейк (50$): {tp:.2f}\n"
                            f"Егер баға қарсы жүрсе - БУ-ге жап деп жазам!\n\n"
                            f"SMC: {smc_text}\nOF: {of_text}")
                    if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(app.bot.send_message(chat_id=int(CHAT_ID), text=text), asyncio.get_event_loop())
            else:
                # 2. Ашық сделканы бақылау
                price = get_price()
                d = active_trade["direction"]
                entry = active_trade["entry"]
                tp = active_trade["tp"]

                # Тейкке жетті ме?
                if (d == "LONG" and price >= tp) or (d == "SHORT" and price <= tp):
                    text = f"✅ ТЕЙК АЛЫНДЫ! +50$ 🎉\n{d} | Кіру: {entry} | Шығу: {price}"
                    if CHAT_ID:
                        asyncio.run_coroutine_threadsafe(app.bot.send_message(chat_id=int(CHAT_ID), text=text), asyncio.get_event_loop())
                    active_trade.update({"direction": None, "entry": 0, "tp": 0, "be_warned": False})

                # Баға қарсы жүрді ме? -0.3% болса БУ ескерту
                elif not active_trade["be_warned"]:
                    pnl_percent = (price - entry) / entry * 100 if d == "LONG" else (entry - price) / entry * 100
                    if pnl_percent <= -0.3:  # -0.3% қарсы кетті
                        text = (f"⚠️ БУ-ГЕ ЖАП! БУ-ГЕ ЖАП!\n\n"
                                f"{d} | Кіру: {entry}\n"
                                f"Қазір: {price} ({pnl_percent:.2f}%)\n"
                                f"Баға қарсы кетіп барады! Стопты кіру нүктесіне қой, шығынсыз жап!")
                        if CHAT_ID:
                            asyncio.run_coroutine_threadsafe(app.bot.send_message(chat_id=int(CHAT_ID), text=text), asyncio.get_event_loop())
                        active_trade["be_warned"] = True
                        # БУ ескертуден кейін сделканы жабамыз, келесі сигналды күтеміз
                        # Егер БУ-де шыққың келмесе, осы жолды өшір
                        active_trade.update({"direction": None, "entry": 0, "tp": 0, "be_warned": False})

        except Exception as e:
            print(f"Loop қате: {e}")
        time.sleep(60)  # 1 минут сайын тексеру

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_now))
    threading.Thread(target=signal_loop, args=(app,), daemon=True).start()
    print("SMC + Orderflow 90% бот іске қосылды...")
    app.run_polling()

if __name__ == "__main__":
    main()
