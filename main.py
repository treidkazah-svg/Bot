import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Render үшін жалған сайт (портты ашып қояды) ---
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
        def log_message(self, format, *args):
            return
    server = HTTPServer(('0.0.0.0', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# --- /start командасы ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Сәлем! 👋\n"
        "Мен істеп тұрмын!\n\n"
        "Маған кез келген хабарлама жаз, мен қайтарамын."
    )

# --- /help командасы ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Командалар:\n"
        "/start - Ботты бастау\n"
        "/help - Көмек"
    )

# --- Кез келген хабарламаға жауап ---
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Сен жаздың: {update.message.text}")

# --- Негізгі іске қосу ---
def main():
    keep_alive()
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("ҚАТЕ: BOT_TOKEN табылмады! Render-де Environment-ге сал.")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("Бот іске қосылды...")
    app.run_polling()

if __name__ == "__main__":
    main()
