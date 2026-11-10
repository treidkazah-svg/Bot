import os
import numpy as np
import yfinance as yf
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

@app.route('/')
def home():
    return "Gold Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ---------- АЛТЫН ДАННЫЕ ----------
def get_gold(interval="15m", period="5d"):
    # GC=F = Gold Futures, XAUUSD-пен бірдей жүреді
    # interval: 15m, 1h, 4h
    df = yf.download("GC=F", interval=interval, period=period, progress=False, auto_adjust=True)
    # yfinance кейде MultiIndex қайтарады, түзетеміз
    if hasattr(df.columns, 'get_level_values'):
        try:
            df.columns = df.columns.get_level_values(0)
        except:
            pass
    highs = df['High'].values.astype(float)
    lows = df['Low'].values.astype(float)
    closes = df['Close'].values.astype(float)
    vols = df['Volume'].values.astype(float)
    vols = np.nan_to_num(vols, nan=1000)
    return highs, lows, closes, vols

def volume_profile(highs, lows, closes, vols):
    p_min, p_max = lows.min(), highs.max()
    bins = np.linspace(p_min, p_max, 21)
    vp = np.zeros(20)
    for i in range(len(closes)):
        idx = np.digitize(closes[i], bins) - 1
        idx = max(0, min(19, idx))
        vp[idx] += vols[i]
    poc_idx = np.argmax(vp)
    poc = (bins[poc_idx] + bins[poc_idx+1]) / 2
    total = vp.sum()
    sorted_idx = np.argsort(vp)[::-1]
    cum = 0
    va = []
    for idx in sorted_idx:
        cum += vp[idx]
        va.append(idx)
        if cum >= total * 0.7:
            break
    vah = bins[max(va)+1]
    val = bins[min(va)]
    return poc, vah, val

def smc_full(highs, lows, closes):
    price = closes[-1]
    last_high_50 = highs[-51:-1].max()
    last_low_50 = lows[-51:-1].min()
    if price > last_high_50:
        bias = "LONG BIAS 🟢"
        structure = "BOS UP"
    elif price < last_low_50:
        bias = "SHORT BIAS 🔴"
        structure = "BOS DOWN"
    else:
        bias = "NEUTRAL 🟡"
        structure = "Рейндж"

    last_high_20 = highs[-21:-1].max()
    last_low_20 = lows[-21:-1].min()
    sweep = "Жоқ"
    sweep_score = 0
    if highs[-2] > last_high_20 and closes[-1] < last_high_20:
        sweep = "SELL SWEEP ⚠️ - Жоғарыдан ликвидность алды"
        sweep_score = -2
    elif lows[-2] < last_low_20 and closes[-1] > last_low_20:
        sweep = "BUY SWEEP ⚠️ - Төменнен ликвидность алды"
        sweep_score = 2

    fvg = "Жоқ"
    fvg_price = None
    if lows[-1] > highs[-3]:
        fvg = f"Bullish FVG {highs[-3]:.2f} - {lows[-1]:.2f}"
        fvg_price = (highs[-3] + lows[-1]) / 2
    elif highs[-1] < lows[-3]:
        fvg = f"Bearish FVG {lows[-3]:.2f} - {highs[-1]:.2f}"
        fvg_price = (lows[-3] + highs[-1]) / 2

    if closes[-1] > closes[-5]:
        ob = f"Bullish OB ~ {lows[-5]:.2f}"
        ob_price = lows[-5]
    else:
        ob = f"Bearish OB ~ {highs[-5]:.2f}"
        ob_price = highs[-5]

    return bias, structure, sweep, sweep_score, fvg, fvg_price, ob, ob_price, last_high_20, last_low_20

def order_flow(closes, vols):
    delta = 0
    for i in range(len(closes)-20, len(closes)):
        if closes[i] > closes[i-1]:
            delta += vols[i]
        else:
            delta -= vols[i]
    avg_vol = vols[-50:].mean()
    last_vol = vols[-1]
    vol_status = "Күшті ✅" if last_vol > avg_vol * 1.2 else "Әлсіз ⚠️"
    return delta, vol_status

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ XAU/USD (АЛТЫН) - 6 STEP-пен анализ жасап жатырмын...")

    try:
        h15, l15, c15, v15 = get_gold("15m", "5d")
        h4, l4, c4, v4 = get_gold("60m", "1mo")
        price = c15[-1]

        bias, structure, sweep, sweep_score, fvg, fvg_price, ob, ob_price, lh20, ll20 = smc_full(h15, l15, c15)
        bias4, _, _, _, _, _, _, _, _, _ = smc_full(h4, l4, c4)
        poc, vah, val = volume_profile(h15, l15, c15, v15)
        delta, vol_status = order_flow(c15, v15)

        score = 0
        checklist = []
        if "LONG" in bias:
            score += 1
            checklist.append("✅ 1. Бағыт: LONG (BOS UP)")
        elif "SHORT" in bias:
            score -= 1
            checklist.append("🔻 1. Бағыт: SHORT (BOS DOWN)")
        else:
            checklist.append("🟡 1. Бағыт: Рейндж")

        if sweep_score == 2:
            score += 2
            checklist.append("✅ 2. Sweep: BUY SWEEP болды")
        elif sweep_score == -2:
            score -= 2
            checklist.append("🔻 2. Sweep: SELL SWEEP болды")
        else:
            checklist.append("🟡 2. Sweep: Жоқ - күт")

        if price > poc:
            score += 1
            checklist.append(f"✅ 3. Баға POC ({poc:.2f})-тан жоғары")
        else:
            score -= 1
            checklist.append(f"🔻 3. Баға POC ({poc:.2f})-тан төмен")

        if delta > 0:
            score += 2
            checklist.append(f"✅ 4. Order Flow Delta + - Алушылар күшті")
        else:
            score -= 2
            checklist.append(f"🔻 4. Order Flow Delta - - Сатушылар күшті")

        if fvg_price is not None:
            checklist.append(f"✅ 5. FVG бар: {fvg}")
            score += 1 if "Bullish" in fvg else -1

        if score >= 4:
            signal = "🟢 LONG / BUY - КІРУГЕ БОЛАДЫ"
            entry = ob_price
            sl = ll20 * 0.999
            tp1, tp2, tp3 = poc, vah, lh20
        elif score <= -4:
            signal = "🔴 SHORT / SELL - КІРУГЕ БОЛАДЫ"
            entry = ob_price
            sl = lh20 * 1.001
            tp1, tp2, tp3 = poc, val, ll20
        else:
            signal = "🟡 КҮТ - Кірме!"
            entry, sl, tp1, tp2, tp3 = price, price, price, price, price

        msg = f"""🥇 **XAU/USD | АЛТЫН | 15m + 1H**

💰 Баға: {price:.2f} $

**STEP 1 - БАҒЫТ:**
15m: {bias} - {structure}
1H: {bias4}

**STEP 2 - LIQUIDITY:**
{sweep}
High: {lh20:.2f} | Low: {ll20:.2f}

**STEP 3 - VOLUME PROFILE:**
POC: {poc:.2f} | VAH: {vah:.2f} | VAL: {val:.2f}

**STEP 4 - ORDER FLOW:**
Delta: {'+' if delta>0 else ''}{delta:.0f}
Volume: {vol_status}

**STEP 5 - ENTRY ZONE:**
FVG: {fvg}
OB: {ob}

**✅ ЧЕК-ЛИСТ:**
{chr(10).join(checklist)}

**STEP 6 - ШЕШІМ:**
{signal}
Score: {score}/7

🎯 Entry: {entry:.2f}
🛑 SL: {sl:.2f}
✅ TP1: {tp1:.2f} (POC)
✅ TP2: {tp2:.2f} (VAH/VAL)
✅ TP3: {tp3:.2f} (Liquidity)
"""
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Қате: {e}\nАлтын данныесі кешігіп жатыр, 1 минуттан соң қайта /check деп жаз")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Алтын бот дайын! 🥇\n/check деп жаз")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("check", check))
    print("Gold Bot started...")
    app_bot.run_polling()
