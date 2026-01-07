import telebot
import requests
import random
import time
import json
import math
from flask import Flask, request, jsonify
from threading import Thread
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive

# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
# 🔥 CONFIGURATION
# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
BOT_TOKEN = '8517524208:AAFizxu5oKczDuWNgawlfnfkQ7WcFP-pFgM'
ADMIN_ID = 6243881362

# 🔑 SMS API (SendMySMS)
SMS_API_URL = "https://sendmysms.net/api.php"
SMS_USER = "swygen"
SMS_KEY = "353f2fdf74fd02928be4330f7efb78b7"

# 🗄️ DATABASE (JSONBin - Your Provided Credentials)
JSONBIN_API_KEY = '$2a$10$bXRSqzPAb3ta4IK/7CWN0O3aLAY0gEexojcL2efrYIWYM0m.iOrhu'
BIN_ID = '695e450bd0ea881f405a8edb'
JSON_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='Markdown')
app = Flask(__name__)

# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
# 🗄️ DATABASE MANAGER
# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
def get_db():
    headers = {'X-Master-Key': JSONBIN_API_KEY}
    try:
        req = requests.get(JSON_URL, headers=headers)
        if req.status_code == 200:
            # Handle JSONBin structure
            data = req.json().get('record', {})
            return data.get('requests', [])
        return []
    except:
        return []

def update_db(new_entry):
    headers = {
        'Content-Type': 'application/json',
        'X-Master-Key': JSONBIN_API_KEY
    }
    try:
        # 1. Get existing data
        current_list = get_db()
        
        # 2. Add new entry to the TOP (Index 0)
        current_list.insert(0, new_entry)
        
        # 3. Limit to last 200 entries to prevent overflow
        if len(current_list) > 200:
            current_list = current_list[:200]
            
        # 4. Save back to JSONBin
        requests.put(JSON_URL, json={'requests': current_list}, headers=headers)
    except Exception as e:
        print(f"DB Save Error: {e}")

# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
# 📨 SMS & API HANDLER
# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
def send_sms(phone, message):
    try:
        data = {
            "user": SMS_USER,
            "key": SMS_KEY,
            "to": phone,
            "msg": message
        }
        res = requests.post(SMS_API_URL, data=data)
        return res.text
    except: return "Connection Failed"

@app.route('/send_otp', methods=['GET'])
def api_handle():
    phone = request.args.get('phone')
    if not phone: return jsonify({"status": "error", "message": "Missing Phone"}), 400

    otp = str(random.randint(100000, 999999))
    timestamp = time.strftime("%d-%b %I:%M %p")
    
    # ✅ Exact Message Format Requested
    msg_body = f"BD INVESTMENT Verification Code: {otp}\nValid for 10 minutes.\nDo not share this code with anyone."
    
    # Send SMS
    status_resp = send_sms(phone, msg_body)
    
    # Save Log
    log_data = {
        "time": timestamp,
        "phone": phone,
        "otp": otp,
        "status": "Sent" if "success" in status_resp.lower() or len(status_resp) < 20 else "Error"
    }
    # Save in background thread
    Thread(target=update_db, args=(log_data,)).start()

    # Notify Admin
    try:
        bot.send_message(
            ADMIN_ID, 
            f"🔔 **New OTP Request**\n📱 Phone: `{phone}`\n🔢 Code: `{otp}`"
        )
    except: pass

    return jsonify({"status": "success", "otp": otp}), 200

@app.route('/')
def home(): return "✅ System is Online"

# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
# 🤖 BOT INTERFACE (Reply Keyboard)
# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
def main_menu():
    mk = ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add(KeyboardButton("🟢 System Status"), KeyboardButton("📂 View Requests"))
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    # Only Admin Access Check
    if m.chat.id != ADMIN_ID:
        bot.send_message(m.chat.id, "⛔ **Access Denied.**\nThis bot is for Admin use only.")
        return

    msg = (
        f"🤖 **OTP Admin Panel**\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"✅ Database: **JSONBin Connected**\n"
        f"📡 Gateway: **SendMySMS Active**\n\n"
        f"👇 নিচের মেনু থেকে অপশন সিলেক্ট করুন।"
    )
    bot.send_message(m.chat.id, msg, reply_markup=main_menu())

# --- 🟢 STATUS BUTTON ---
@bot.message_handler(func=lambda m: m.text == "🟢 System Status")
def check_status(m):
    bot.reply_to(m, "✅ **Bot is Fully Operational!**\nServer: Online (Render)\nDatabase: Active")

# --- 📂 VIEW REQUESTS (PAGINATION) ---
@bot.message_handler(func=lambda m: m.text == "📂 View Requests")
def view_requests_init(m):
    show_page(m.chat.id, 1)

def show_page(chat_id, page, msg_id=None):
    requests_list = get_db()
    
    if not requests_list:
        text = "📭 **Database is Empty**\nNo OTP requests found yet."
        if msg_id: bot.edit_message_text(text, chat_id, msg_id)
        else: bot.send_message(chat_id, text)
        return

    # Pagination Logic (10 items per page)
    per_page = 10
    total_items = len(requests_list)
    total_pages = math.ceil(total_items / per_page)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    current_items = requests_list[start_idx:end_idx]

    # Build Message
    text = f"📋 **Request Logs (Page {page}/{total_pages})**\nTotal: {total_items} records\n━━━━━━━━━━━━━━━━\n"
    
    for item in current_items:
        # Safe get in case keys change
        t = item.get('time', 'N/A')
        p = item.get('phone', 'N/A')
        o = item.get('otp', 'N/A')
        s = item.get('status', 'Unknown')
        
        icon = "✅" if s == "Sent" else "❌"
        text += f"{icon} `{t}`\n📱 `{p}` | 🔢 `{o}`\n────────────────\n"

    # Inline Buttons (Next/Prev)
    mk = InlineKeyboardMarkup()
    btns = []
    
    if page > 1:
        btns.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    
    btns.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        btns.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    mk.add(*btns)
    mk.add(InlineKeyboardButton("🔄 Refresh Logs", callback_data="page_1"))

    # Send or Edit
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=mk)
        except: pass # Ignore if content didn't change
    else:
        bot.send_message(chat_id, text, reply_markup=mk)

# --- CALLBACK HANDLER ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('page_'))
def handle_pagination(call):
    try:
        page = int(call.data.split('_')[1])
        show_page(call.message.chat.id, page, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(e)

@bot.callback_query_handler(func=lambda call: call.data == "ignore")
def ignore_click(call):
    bot.answer_callback_query(call.id)

# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
# 🔥 RUNNER
# ━─━─━─━─━─━─━─━─━─━─━─━─━─━
def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    keep_alive()
    bot.infinity_polling(skip_pending=True)