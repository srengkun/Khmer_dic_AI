import logging
import os
import asyncio
import requests
import psycopg2 # Import the PostgreSQL adapter
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants and Secrets ---
# Get credentials from Vercel Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
DATABASE_URL = os.environ.get("POSTGRES_URL") # Vercel provides this variable
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# The Flask app is the main entry point for Vercel
app = Flask(__name__)

# --- Database Management Functions (Updated for PostgreSQL) ---
def db_connect():
    """Establishes a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        return None

def log_user(user: Update.effective_user):
    """Logs user activity for the /stats command in PostgreSQL."""
    sql = """
        INSERT INTO users (user_id, first_name, username, chat_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id)
        DO UPDATE SET
            chat_count = users.chat_count + 1,
            last_seen = CURRENT_TIMESTAMP;
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (user.id, user.first_name, user.username))
                conn.commit()
    except Exception as e:
        logger.error(f"Failed to log user {user.id}: {e}")

def query_db_sync(word: str) -> str or None:
    """Searches the PostgreSQL DB. Returns result string or None if not found."""
    sql = "SELECT word, pos, definition FROM dictionary WHERE word = %s"
    try:
        with db_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (word.strip(),))
                results = cursor.fetchall()
        
        if not results:
            return None

        reply_message = f"**លទ្ធផលពីវចនានុក្រមមូលដ្ឋាន:**\n{'-'*20}\n"
        for row in results:
            khmer_word, pos, definition = row
            reply_message += f"📖 **{khmer_word}**\n*( {pos} )*\n**និយមន័យ:** `{definition}`\n—\n"
        return reply_message
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return "❌ មានបញ្ហាក្នុងការស្វែងរកពីវចនានុក្រមមូលដ្ឋាន។"

def query_ai_fallback_sync(word: str) -> str:
    """Gets definition from AI if word not found locally."""
    if not OPENROUTER_API_KEY:
        return "❌ រកមិនឃើញពាក្យនេះទេ ហើយមុខងារ AI មិនត្រូវបានតំឡើង។"

    logger.info(f"Querying AI for word: {word}")
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = {"model": "meta-llama/llama-4-scout:free", "messages": [{"role": "system", "content": "You are a helpful Khmer dictionary. Explain the meaning of the given Khmer word clearly and concisely in Khmer."}, {"role": "user", "content": word}]}
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=40)
        res.raise_for_status()
        reply = res.json()["choices"][0]["message"]["content"]
        return f"**លទ្ធផលពី AI :**\n{'-'*20}\n{reply}"
    except Exception as e:
        logger.error(f"AI API Error: {e}")
        return f"❌ មានបញ្ហាក្នុងការភ្ជាប់ទៅកាន់ AI។"

# --- Bot Handlers (Handlers are the same as before) ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    keyboard = [[InlineKeyboardButton("❓ របៀបប្រើប្រាស់", callback_data="help")], [InlineKeyboardButton("👤 អំពីអ្នកបង្កើត", url="https://t.me/srengone")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "សួស្តី! ខ្ញុំជា Bot វចនានុក្រម ខ្មែរ-ខ្មែរ ដែលមានជាង ៤៤,០០០ពាក្យ។\n\n"
        "ប្រសិនបើរកមិនឃើញ, ខ្ញុំនឹងសួរ AI ដើម្បីជួយឆ្លើយ។\n\n"
        "បង្កើត និងរៀបចំដោយ: @srengone",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    help_text = (
        "**របៀបប្រើប្រាស់វចនានុក្រម Bot**\n\n"
        "» គ្រាន់តែវាយពាក្យខ្មែរដែលអ្នកចង់ស្វែងរក រួចផ្ញើមកកាន់ខ្ញុំ។\n"
        "» **ឧទាហរណ៍**: វាយពាក្យ `កសិកម្ម`\n\n"
        "ប្រសិនបើមានបញ្ហា ឬចម្ងល់ សូមទាក់ទងមកកាន់អ្នកបង្កើត៖ @srengone"
    )
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text=help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("អ្នកមិនមានសិទ្ធិប្រើប្រាស់ពាក្យបញ្ជានេះទេ។")
        return
    
    stats_text = ""
    try:
        with db_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                cursor.execute("SELECT user_id, first_name, username, chat_count, last_seen FROM users ORDER BY last_seen DESC LIMIT 10")
                recent_users = cursor.fetchall()

        stats_text = f"📊 **ស្ថិតិ Bot**\n\n👤 អ្នកប្រើប្រាស់សរុប: `{total_users}`\n\n**អ្នកប្រើប្រាស់ចុងក្រោយ (10):**\n"
        for user in recent_users:
            stats_text += f"- ID: `{user[0]}`, ឈ្មោះ: {user[1]}, Chats: `{user[3]}`\n"
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        stats_text = "❌ មិនអាចទាញយកស្ថិតិបានទេ។"

    await update.message.reply_text(stats_text, parse_mode='Markdown')


async def lookup_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    word_to_find = update.message.text.strip()
    
    local_definition = query_db_sync(word_to_find)
    
    if local_definition:
        await update.message.reply_text(local_definition, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"រកមិនឃើញ «{word_to_find}» ក្នុងវចនានុក្រមមូលដ្ឋាន... កំពុងសួរ AI ជំនួសវិញ។ សូមរង់ចាំ។")
        ai_definition = query_ai_fallback_sync(word_to_find)
        await update.message.reply_text(ai_definition, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'help':
        await help_command(update, context)

# --- Main Application Setup ---
# Setup application and handlers once when the module is loaded
ptb_app = Application.builder().token(BOT_TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CommandHandler("stats", stats_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lookup_word))

# --- Flask Webhook Routes ---
@app.route("/")
def index():
    """A simple page to confirm the bot is running."""
    return "Hello! Your Telegram Bot is alive and running."

@app.route("/api", methods=["POST"])
async def webhook():
    """The main webhook endpoint that receives updates from Telegram."""
    update_data = request.get_json()
    logger.info("Received update from Telegram.")
    try:
        update = Update.de_json(update_data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
    return "ok", 200

# Note: The set_webhook endpoint is removed for security. 
# It's better to set the webhook manually once after deployment.
# You can do this by visiting the URL in your browser:
# https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_VERCEL_URL>/api
