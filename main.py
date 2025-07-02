# -*- coding: utf-8 -*-
import logging
import os
import asyncio
import json
from flask import Flask, request

# <<< កែសម្រួល: នាំចូល Library របស់ Google
import google.generativeai as genai

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# --- ការរៀបចំพื้นฐาน ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- ค่าคงที่ និង Secrets ---
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    WEBHOOK_URL = os.environ["WEBHOOK_URL"]
    # <<< កែសម្រួល: ប្រើ GEMINI_API_KEY ជំនួស OPENROUTER_API_KEY
    GEMINI_API_KEY = os.environ["GEMINI_API_KEY"] 
except KeyError as e:
    logger.critical(f"❌ Secret '{e.args[0]}' មិនត្រូវបានកំណត់! Bot មិនអាចដំណើរការបានទេ។")
    exit()

# <<< កែសម្រួល: កំណត់រចនាសម្ព័ន្ធ API Key របស់ Google
genai.configure(api_key=GEMINI_API_KEY)


# --- ឃ្លាគន្លឹះសម្រាប់កំណត់អត្តសញ្ញាណអ្នកបង្កើត ---
CREATOR_QUERIES = {
    "អ្នកណាជាអ្នកបង្កើត": "ខ្ញុំត្រូវបានបង្កើតឡើងដោយ ស្រេង! 👨‍💻",
    "អ្នកណាបង្កើត": "ខ្ញុំត្រូវបានបង្កើតឡើងដោយ ស្រេង! 👨‍💻",
    "អ្នកបង្កើត": "ខ្ញុំត្រូវបានបង្កើតឡើងដោយ ស្រេង! 👨‍💻",
    "creator": "Created by Sreng! 👨‍💻",
    "who created you": "Created by Sreng! 👨‍💻",
    "who are you": "I am a Khmer AI Dictionary Bot, powered by Sreng! 🤖"
}

# --- Flask Web App (សម្រាប់ Vercel) ---
app = Flask(__name__)

# <<< កែសម្រួល: សរសេរฟังก์ชัน AI ឡើងវិញทั้งหมดដើម្បីប្រើ Google's Library
def query_ai_sync(word: str) -> str:
    """
    ฟังก์ชันនេះเชื่อมต่อទៅកាន់ Google Gemini API ដោយផ្ទាល់។
    """
    logger.info(f"កំពុងសួរ Google Gemini API ដោយផ្ទាល់សម្រាប់ពាក្យ: {word}")
    
    try:
        # កំណត់ឈ្មោះ Model
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # បង្កើត Prompt 
        prompt = f"You are a helpful Khmer dictionary bot, created and managed by a developer named Sreng. Your main purpose is to explain the meaning of given Khmer words clearly and concisely in the Khmer language. Always remember you were created by Sreng. Provide examples if possible. The word to define is: '{word}'"
        
        # ហៅ API
        response = model.generate_content(prompt)
        
        # យកលទ្ធផល
        reply = response.text
        return f"**លទ្ធផលពី Google AI (Gemini 1.5 Flash):**\n{'-'*20}\n{reply}"

    except Exception as e:
        logger.error(f"❌ កំហុសពី Google Gemini API: {e}")
        return "❌ មានបញ្ហាក្នុងការភ្ជាប់ទៅកាន់ Google AI។ សូមព្យាយាមម្តងទៀត។"

# --- Bot Handlers (មិនមានការផ្លាស់ប្តូរនៅខាងក្រោមនេះទេ) ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("❓ របៀបប្រើប្រាស់", callback_data="help")],
        [InlineKeyboardButton("👨‍💻 អំពីអ្នកបង្កើត", callback_data="about")],
        [InlineKeyboardButton("💬 ទាក់ទងអ្នកបង្កើត (Telegram)", url="https://t.me/srengone")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "សួស្តី! ខ្ញុំជា Bot វចនានុក្រម AI បង្កើតដោយស្រេង។\n\n"
        "គ្រាន់តែផ្ញើពាក្យខ្មែរមក ខ្ញុំនឹងស្វែងរកនិយមន័យពី Google AI ให้។",
        reply_markup=reply_markup
    )

async def help_command_text():
    return (
        "**របៀបប្រើប្រាស់ Bot**\n\n"
        "» គ្រាន់តែវាយពាក្យខ្មែរដែលអ្នកចង់ស្វែងរក រួចផ្ញើមកកាន់ខ្ញុំ។\n"
        "» ខ្ញុំនឹងប្រើ Google AI ដើម្បីពន្យល់អត្ថន័យของคำនោះ។\n"
        "» **ឧទាហរណ៍**: វាយពាក្យ `បច្ចេកវិទ្យា`"
    )

async def about_command_text():
    return (
        "**អំពី Bot នេះ**\n\n"
        "Bot នេះត្រូវបានបង្កើត និងថែទាំដោយ **ស្រេង (Sreng)**។\n\n"
        "Bot នេះប្រើប្រាស់ Google Gemini AI ដោយផ្ទាល់ ដើម្បីផ្តល់និយមន័យសម្រាប់ពាក្យខ្មែរ។\n"
        "សូមទាក់ទងមកគាត់ប្រសិនបើអ្នកមានសំណូមពរ ឬរកឃើញបញ្ហា។"
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await about_command_text()
    keyboard = [[InlineKeyboardButton("👨‍💻 ទាក់ទងអ្នកបង្កើត (Telegram)", url="https://t.me/srengone")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def lookup_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word_to_find = update.message.text.strip()
    thinking_message = await update.message.reply_text(f"កំពុងស្វែងរកនិយមន័យសម្រាប់ «{word_to_find}»... 🤔")
    ai_definition = await asyncio.to_thread(query_ai_sync, word_to_find)
    await thinking_message.edit_text(ai_definition, parse_mode='Markdown')

async def master_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip().lower()
    if message_text in CREATOR_QUERIES:
        await update.message.reply_text(CREATOR_QUERIES[message_text])
        return
    await lookup_word(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'help':
        text = await help_command_text()
        keyboard = [[InlineKeyboardButton("🔙 ត្រឡប់", callback_data="start")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif query.data == 'about':
        text = await about_command_text()
        keyboard = [
            [InlineKeyboardButton("👨‍💻 ទាក់ទងអ្នកបង្កើត (Telegram)", url="https://t.me/srengone")],
            [InlineKeyboardButton("🔙 ត្រឡប់", callback_data="start")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif query.data == 'start':
        keyboard = [
            [InlineKeyboardButton("❓ របៀបប្រើប្រាស់", callback_data="help")],
            [InlineKeyboardButton("👨‍💻 អំពីអ្នកបង្កើត", callback_data="about")],
            [InlineKeyboardButton("💬 ទាក់ទងអ្នកបង្កើត (Telegram)", url="https://t.me/srengone")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "សួស្តី! ខ្ញុំជា Bot វចនានុក្រម AI បង្កើតដោយស្រេង។\n\n"
            "គ្រាន់តែផ្ញើពាក្យខ្មែរមក ខ្ញុំនឹងស្វែងរកនិយមន័យពី Google AI ให้។",
            reply_markup=reply_markup
        )

# --- ការរៀបចំ Application និង Webhook ---
ptb_app = None
async def setup_bot():
    global ptb_app
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, master_message_handler))
    ptb_app = application
    await ptb_app.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook has been set to {WEBHOOK_URL}")

@app.route("/")
def index():
    return "AI Dictionary Bot (Direct Google Gemini) is running!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    if ptb_app is None:
        return "Error: App not initialized", 500
    update_data = request.get_json(force=True)
    update = Update.de_json(data=update_data, bot=ptb_app.bot)
    await ptb_app.process_update(update)
    return "ok"

# --- Main Execution Logic ---
asyncio.run(setup_bot())
