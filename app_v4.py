import os
import sys
import json
import logging
import requests
import threading
import time
from flask import Flask, request, jsonify
from openai import OpenAI

# ============================
# Configuration
# ============================
app = Flask(__name__)

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Environment variables
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "aio_chatbot_verify_2024")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PAGE_ID = os.environ.get("PAGE_ID", "109802151273077")

# OpenAI client
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")

# Graph API version
GRAPH_API_VERSION = "v21.0"

# ============================
# Conversation History
# ============================
conversation_history = {}
conversation_history_lock = threading.Lock()
MAX_HISTORY_LEN = 10 # Store last 5 user/bot message pairs

# ============================
# Human Takeover Feature
# ============================
HUMAN_TAKEOVER_MINUTES = 15
paused_users = {}
paused_users_lock = threading.Lock()

def is_bot_paused(user_id):
    with paused_users_lock:
        if user_id in paused_users:
            paused_at = paused_users[user_id]
            elapsed = time.time() - paused_at
            if elapsed < HUMAN_TAKEOVER_MINUTES * 60:
                return True
            else:
                del paused_users[user_id]
                logger.info(f"Bot resumed for user {user_id} after {HUMAN_TAKEOVER_MINUTES} minutes")
    return False

def pause_bot_for_user(user_id):
    with paused_users_lock:
        paused_users[user_id] = time.time()
    logger.info(f"Bot PAUSED for user {user_id} for {HUMAN_TAKEOVER_MINUTES} minutes")

# ============================
# System Prompt v4.0
# ============================
SYSTEM_PROMPT = """သင်သည် "All in One Digital Marketing" ၏ Customer Service Assistant ဖြစ်သည်။

အရေးကြီးဆုံး စည်းကမ်းများ:
- Robot မဟုတ်ဘဲ လူတစ်ယောက်လို သဘာဝကျကျ၊ ယဉ်ကျေးစွာ ဖြေပါ
- မြန်မာဘာသာဖြင့်သာ တိုတောင်းရှင်းလင်းစွာ ဖြေပါ (၂-၃ ကြောင်းသာ)
- Client ပြောထားတဲ့ စကားဝိုင်းတစ်ခုလုံးကို သေချာဖတ်ပြီး context ကို နားလည်မှ ဖြေပါ
- မသိရင်၊ မသေချာရင်၊ အလုပ်နဲ့မဆိုင်ရင် "ဟုတ်ကဲ့ရှင့် အကြောင်းပြန်ပေးပါမယ်နော်" လို့သာ ပြောပါ။ ထင်ရာ ခန့်မှန်းပြောမနေပါနဲ့။
- "ရှင့်" တစ်ခုထဲ မသုံးပါနဲ့၊ "ဟုတ်ကဲ့ရှင့်" လို့သာ သုံးပါ
- "ဟုတ်ပါသည်" ဟု လုံးဝမသုံးပါနဲ့၊ "ဟုတ်ပါတယ်ရှင့်" လို့သာ သုံးပါ
- "ဘာအကူအညီလိုပါသလဲ" ဟု လုံးဝမမေးပါနဲ့၊ "ဘာများကူညီပေးရမလဲရှင့်" လို့သာ မေးပါ
- "မေတ္တာပြုပြီး" ဆိုသောစကားကို လုံးဝမသုံးပါနဲ့။ ယင်းအစား "သေချာလေး ရှင်းပြပေးပါမယ်ရှင့်" သို့မဟုတ် "သေချာလေး ဖြေကြားပေးပါမယ်ရှင့်" ဟု သုံးပါ
- Client က "Add ထားပြီ", "ပြီးပြီ", "ဟုတ်ကဲ့" လို့ ပြောရင် ငွေလွဲ/screenshot တောင်းခံမနေပါနဲ့ - "ဟုတ်ကဲ့ရှင့် 🙏" လို့သာ ဖြေပါ
- Client က Facebook page link (facebook.com/...) ပို့လာရင် "ဟုတ်ကဲ့ရှင့် ကြည့်ပေးပါမယ်နော် 🙏" လို့သာ ပြန်ဖြေပါ
- ငွေလွဲ account ကို မမေးဘဲ ကိုယ်တိုင် မပေးပါနဲ့ - ငွေလွဲမည်/account number/Kpay မေးမှသာ ပေးပါ
- Client က ဈေးနှုန်း၊ ဘယ်လောက်လွဲရမလဲ၊ total ဘယ်လောက်၊ စုစုပေါင်းဘယ်လောက် မေးလာရင် "ဟုတ်ကဲ့ရှင့် Total Amount လေးတွက်ပြီး ပြန်ပြောပေးပါမယ်နော်" လို့သာ ဖြေပါ။ ks ပမာဏ၊ $ ပမာဏ မပြောပါနဲ့ - Admin ကိုယ်တိုင် ဖြေပါမည်
- Client က Page Promote, Page Follow တက်ဖို့ Service မေးလာရင် "$10 ကနေစပြီး အပ်လို့ရပါတယ်ရှင့်" လို့ ဖြေပါ
- Client က Account ကျသွားလို့၊ Account ပိတ်ခံရလို့၊ Page ဆယ်ချင်လို့၊ Page error fix ဖို့၊ Error fix service မေးလာရင် "ဟုတ်ကဲ့ရှင့် အကြောင်းပြန်ပေးပါမယ်" လို့သာ ဖြေပါ။ ငွေပမာဏ မတောင်းပါနဲ့၊ ဈေးနှုန်းမပြောပါနဲ့
- Client က Online Class၊ သင်တန်း၊ Course၊ Facebook Advertising Class၊ TikTok Advertising Class မေးလာရင် အောက်ပါ reply ကိုသာ ဖြေပါ - ဈေးနှုန်း မပြောပါနဲ့ Admin တွေ ဖြေပါမည်:
  "ဟုတ်ကဲ့ရှင့်
Facebook Advertising Class နဲ့
TikTok Advertising Class နှစ်ခုရှိပါမယ်နော်
အသေးစိတ်ကို ရှင်းပြပေးပါမယ်နော်"
- Client က "အသေးစိတ်ရှင်းပြပေးပါ", "ဘာတွေလုပ်ပေးလဲ", "ဘာ service တွေရှိလဲ" မေးလာရင် ဖုန်းနံပါတ်မပေးဘဲ အောက်ပါ service များကို မြန်မာဘာသာဖြင့် သေချာရှင်းပြပါ

ကုမ္ပဏီ: All in One Digital Marketing
- 2021 ကနေ Meta Certified Media Buying Professional များဖြင့် ဝန်ဆောင်မှုပေးနေ
- လုပ်ငန်း ၁၀၀ ကျော် ကူညီပေးနေ

ဝန်ဆောင်မှုများ (အသေးစိတ်ရှင်းပြချက်):
1. Media Buying 🚀 - Facebook/Instagram Ads ကို ကျွမ်းကျင်စွာ Run ပေးသည်။ Budget အနည်းဆုံး $5 မှ စတင်နိုင်သည်။
2. Content Writing ✍️ - Page Post များအတွက် Caption၊ ကြော်ငြာစာသား ရေးပေးသည်။
3. Logo & Design ™️ - Business Logo၊ Banner၊ Poster ဒီဇိုင်းများ ဖန်တီးပေးသည်။
4. Social Media Design 🖼️ - Facebook/Instagram Post ဒီဇိုင်းများ ပုံမှန်ပြုလုပ်ပေးသည်။
5. Motion Video 🎬 - ကြော်ငြာ Video၊ Reels များ ပြုလုပ်ပေးသည်။
6. Page Setup - Facebook Page အသစ်ဖွင့်ပေးခြင်း၊ Professional ဖြစ်အောင် Setup ပေးသည်။
7. Error Fix 🔧 - Page Disabled၊ Ad Account ပိတ်ခြင်း၊ Hack ဖြစ်ခြင်း ပြင်ပေးသည်။
8. Follower+++ - Page Follower/Like တိုးပေးသည်။
9. FB Class 💻 - Facebook Ads အသုံးပြုနည်း Online Class သင်ပေးသည်။
10. TikTok Class - TikTok Marketing Class သင်ပေးသည်။
11. TikTok Service 🎵 - TikTok Ads Run ပေးသည်၊ Follower တိုးပေးသည်။
12. Monthly Package 📦 - တစ်လစာ Content + Design + Boost Package ဝန်ဆောင်မှု။
13. Blue Mark 🔵 - Facebook Page Verification (Blue Tick) ဆောင်ရွက်ပေးသည်။
14. Monetization 💸 - Facebook Page Monetization ဖွင့်ပေးသည်။
15. Consultation 🧑‍💻 - Digital Marketing အကြံပေးဝန်ဆောင်မှု။

(ဈေးနှုန်းများကို Admin ကိုယ်တိုင် ဖြေကြားပေးပါမည် - Bot မှ ဈေးနှုန်း မပြောရ)

ဆက်သွယ်ရန်: ဖုန်း 09-400-175-900 | Viber 098-990-033-15

ငွေလွဲ Account (ငွေလွဲမည်/Kpay/account number မေးလာလျှင် အောက်ပါ KPay နံပါတ်ကိုသာ ပေးပါ):
KBZ Pay (KPay) - 09420933977 | Name: Khaing Zin Latt

အရေးကြီး: 09899003315 ဆိုသောနံပါတ်ကို လုံးဝမပေးရ - ထိုနံပါတ်မှာ မသုံးတော့ပါ

ငွေလွဲပြီးရင် Transaction History Screenshot နဲ့ ID Number ပေးပို့ပေးပါဟု မေ့မမေ့ ပြောပါ 🙏"""

# Track processed message IDs to avoid duplicates
processed_messages = set()
processed_messages_lock = threading.Lock()
MAX_PROCESSED = 1000

# ============================
# Helper Functions
# ============================
def get_ai_response(user_id, user_message):
    if not client:
        logger.error("OpenAI client not initialized")
        return "မင်္ဂလာပါရှင့်! ခဏစောင့်ပေးပါ၊ မကြာမီ ပြန်ဆက်သွယ်ပေးပါမယ် 🙏"

    with conversation_history_lock:
        # Get history for this user
        history = conversation_history.get(user_id, [])
        
        # Add current user message to history
        history.append({"role": "user", "content": user_message})
        
        # Trim history to MAX_HISTORY_LEN
        if len(history) > MAX_HISTORY_LEN:
            history = history[-MAX_HISTORY_LEN:]
        
        # Update history
        conversation_history[user_id] = history

    messages_for_api = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ] + history

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_for_api,
            max_tokens=200,
            temperature=0.5, # Reduced for more deterministic responses
            timeout=20
        )
        ai_response = response.choices[0].message.content.strip()
        
        # Add AI response to history
        with conversation_history_lock:
            conversation_history[user_id].append({"role": "assistant", "content": ai_response})
            
        return ai_response

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "မင်္ဂလာပါရှင့်! ခဏစောင့်ပေးပါ၊ မကြာမီ ပြန်ဆက်သွယ်ပေးပါမယ် 🙏"

def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE"
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {recipient_id}")
        else:
            logger.error(f"Send message error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Send message exception: {e}")

def send_typing_indicator(recipient_id, action="typing_on"):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": action
    }
    try:
        requests.post(url, params=params, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Typing indicator error: {e}")

def handle_message(sender_id, message):
    mid = message.get("mid", "")
    with processed_messages_lock:
        if mid and mid in processed_messages:
            logger.info(f"Duplicate message {mid}, skipping")
            return
        if mid:
            processed_messages.add(mid)
            if len(processed_messages) > MAX_PROCESSED:
                processed_messages.clear()
    
    if message.get("is_echo"):
        logger.info("Skipping echo message")
        return
    
    message_text = message.get("text", "")
    if not message_text:
        attachments = message.get("attachments", [])
        if attachments and not is_bot_paused(sender_id):
            # Determine attachment type
            att_types = [att.get("type", "") for att in attachments]
            logger.info(f"Attachment types from {sender_id}: {att_types}")
            
            # Thumbs-up sticker / like sticker - treat as simple acknowledgement
            is_sticker = any(att.get("type") == "sticker" for att in attachments)
            # Real image (not sticker) - treat as payment screenshot
            is_real_image = any(
                att.get("type") in ("image", "photo") and not att.get("sticker_id")
                for att in attachments
            )
            
            if is_sticker:
                # Thumbs up or any sticker - just acknowledge
                send_message(sender_id, "ဟုတ်ကဲ့ရှင့် 🙏")
            elif is_real_image:
                image_reply = "ဟုတ်ကဲ့ရှင့် စစ်ပြီး အကြောင်းပြန်ပေးပါမယ်ရှင့်"
                send_message(sender_id, image_reply)
            # For other attachment types (video, audio, file), do nothing
        return
    
    logger.info(f"Processing message from {sender_id}: {message_text}")
    
    if is_bot_paused(sender_id):
        logger.info(f"Bot is paused for user {sender_id}, skipping AI response")
        return
    
    send_typing_indicator(sender_id)
    ai_response = get_ai_response(sender_id, message_text)
    send_message(sender_id, ai_response)

def handle_echo_message(user_id, message):
    """Called when admin/page sends a message to a user. Pause bot for that user."""
    mid = message.get("mid", "")
    echo_key = f"echo_{mid}"
    with processed_messages_lock:
        if echo_key in processed_messages:
            logger.info(f"Duplicate echo {mid}, skipping")
            return
        if mid:
            processed_messages.add(echo_key)
    
    echo_text = message.get("text", "").strip()
    logger.info(f"Admin sent message to user {user_id}: '{echo_text}' - pausing bot for {HUMAN_TAKEOVER_MINUTES} minutes")
    
    # Pause bot for ANY admin message (hi, or any other text)
    pause_bot_for_user(user_id)

def handle_postback(sender_id, payload):
    logger.info(f"Postback from {sender_id}: {payload}")
    if is_bot_paused(sender_id):
        logger.info(f"Bot is paused for user {sender_id}, skipping postback response")
        return
    
    if payload == "GET_STARTED":
        welcome_msg = "မင်္ဂလာပါရှင့်! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏\n\nဘာများကူညီပေးရမလဲရှင့်?"
        send_message(sender_id, welcome_msg)
    else:
        ai_response = get_ai_response(sender_id, f"User clicked: {payload}")
        send_message(sender_id, ai_response)

# ============================
# Flask Routes
# ============================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully!")
        return challenge, 200
    else:
        logger.warning(f"Webhook verification failed. Mode: {mode}, Token: {token}")
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("=== WEBHOOK POST RECEIVED ===_v4")
    data = request.get_json()
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                recipient_id = event.get("recipient", {}).get("id")
                if not sender_id:
                    continue
                
                if "message" in event:
                    message = event["message"]
                    if message.get("is_echo"):
                        # Admin sent a message - recipient_id is the user being talked to
                        # sender_id here is the PAGE (admin side)
                        # We need the user's ID which is in recipient_id
                        user_id = recipient_id  # The customer's ID
                        if user_id:
                            threading.Thread(target=handle_echo_message, args=(user_id, message)).start()
                    else:
                        threading.Thread(target=handle_message, args=(sender_id, message)).start()
                elif "read" in event:
                    # Ignore read receipts
                    pass
                elif "postback" in event:
                    payload = event["postback"].get("payload", "")
                    threading.Thread(target=handle_postback, args=(sender_id, payload)).start()
    
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "bot": "All in One Digital Marketing Chatbot",
        "version": "4.0",
        "openai": "configured" if client else "not configured",
        "paused_users": len(paused_users),
        "history_users": len(conversation_history)
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

if __name__ == '__main__':
    # This part is for local testing, not for production on Render
    app.run(debug=True, port=5001)

