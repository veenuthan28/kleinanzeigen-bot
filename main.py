import os
import logging
import json
import requests
import time
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from threading import Thread
from flask import Flask

# --- KONFIGURATION ---
# Wir holen den Token sicher aus den Umgebungsvariablen von Render
TOKEN = os.environ.get('TOKEN') 
CHECK_INTERVAL = 60  # Alle 10 Minuten (600 Sekunden)

# --- WEB SERVER (DAMIT ES NICHT EINSCHLÄFT) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot lebt!"

def run_http():
    # Wichtig für Render: Port muss flexibel sein oder 10000
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- BOT LOGIK ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_searches = {}

def get_new_ads(search_term, seen_ids):
    url = f"https://www.kleinanzeigen.de/s-{search_term.replace(' ', '-')}/k0"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return []
        soup = BeautifulSoup(response.text, 'html.parser')
        ads = soup.find_all('article', class_='aditem')
        new_items = []
        for ad in ads:
            ad_id = ad.get('data-adid')
            if ad_id and ad_id not in seen_ids:
                main = ad.find('div', class_='aditem-main')
                if main:
                    t = main.find('a')
                    title = t.text.strip()
                    link = "https://www.kleinanzeigen.de" + t['href']
                    price = main.find('p', class_='aditem-main--middle--price-shipping--price').text.strip()
                    new_items.append({'id': ad_id, 'title': title, 'price': price, 'link': link})
        return new_items
    except: return []

async def start(update: Update, context):
    await update.message.reply_text("Befehle:\n/produkt start [name]\n/produkt end [name]")

async def produkt(update: Update, context):
    chat_id = update.effective_chat.id
    args = context.args
    if len(args) < 2: return
    action, term = args[0].lower(), " ".join(args[1:])
    
    if chat_id not in user_searches: user_searches[chat_id] = {}
    
    if action == "start":
        if term not in user_searches[chat_id]:
            user_searches[chat_id][term] = []
            await update.message.reply_text(f"Suche gestartet: {term}")
    elif action == "end":
        if term in user_searches[chat_id]:
            del user_searches[chat_id][term]
            await update.message.reply_text(f"Gelöscht: {term}")

async def check(context):
    for chat_id, searches in user_searches.items():
        for term, seen_ids in searches.items():
            new = get_new_ads(term, seen_ids)
            for ad in new:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=f"Neu: {ad['title']}\n{ad['price']}\n{ad['link']}")
                    user_searches[chat_id][term].append(ad['id'])
                except: pass
            time.sleep(2)

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('produkt', produkt))
    app.job_queue.run_repeating(check, interval=CHECK_INTERVAL, first=10)
    app.run_polling()