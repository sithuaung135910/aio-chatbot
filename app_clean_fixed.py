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
# Human Takeover Feature
# Bot pauses for 10 minutes when admin replies
# ============================
HUMAN_TAKEOVER_MINUTES = 10
# {user_id: timestamp_when_paused}
paused_users = {}
paused_users_lock = threading.Lock()

def is_bot_paused(user_id):
    """Check if bot is paused for this user"""
    with paused_users_lock:
        if user_id in paused_users:
            paused_at = paused_users[user_id]
            elapsed = time.time() - paused_at
            if elapsed < HUMAN_TAKEOVER_MINUTES * 60:
                return True
            else:
                # Pause expired, remove it
                del paused_users[user_id]
                logger.info(f"Bot resumed for user {user_id} after {HUMAN_TAKEOVER_MINUTES} minutes")
    return False

def pause_bot_for_user(user_id):
    """Pause bot for a specific user (admin took over)"""
    with paused_users_lock:
        paused_users[user_id] = time.time()
    logger.info(f"Bot PAUSED for user {user_id} for {HUMAN_TAKEOVER_MINUTES} minutes")

# ============================
# System Prompt
# ============================
SYSTEM_PROMPT = """သင်သည် "All in One Digital Marketing" ၏ Customer Service Assistant ဖြစ်သည်။

စည်းကမ်းများ:
- မြန်မာဘာသာဖြင့်သာ ဖြေပါ
- တိုတောင်းရှင်းလင်းစွာ ဖြေပါ (2-3 ကြောင်းသာ)
- "ရှင့်" ထည့်ပြောပါ၊ Friendly ဖြစ်ပါ
- Robot မဟုတ်ဘဲ လူတစ်ယောက်လို သဘာဝကျကျ ဖြေပါ
- Emoji အနည်းငယ်သာ သုံးပါ
- မသိတာ မဖြေဘဲ ဖုန်းဆက်သွယ်ဖို့ ညွှန်ပါ
- Client က Facebook page link (facebook.com/...) ပို့လာရင် "ဟုတ်ကဲ့ရှင့် ကြည့်ပေးပါမယ်နော် 🙏" လို့သာ ပြန်ဖြေပါ၊ link ကို analyze မလုပ်နိုင်ဘူးလို့ မပြောနဲ့
- Website link၊ URL တွေ ပို့လာရင် ကြည့်ပေးမယ်ဟု ယဉ်ကျေးစွာ ဖြေပါ

ကုမ္ပဏီ: All in One Digital Marketing
- 2021 ကနေ Meta Certified Media Buying Professional များဖြင့် ဝန်ဆောင်မှုပေးနေ
- လုပ်ငန်း ၁၀၀ ကျော် ကူညီပေးနေ

ဝန်ဆောင်မှုများ:
Media Buying 🚀 | Content Writing ✍️ | Logo & Design ™️ | Social Media Design 🖼️ | Motion Video 🎬 | Page Setup | Error Fix 🔧 | Follower+++ | FB Class 💻 | TikTok Class | TikTok Service 🎵 | Monthly Package 📦 | Blue Mark 🔵 | Monetization 💸 | Consultation 🧑‍💻

Boost ဈေးနှုန်း (Service fee အပါ):
$5=29,000ks | $10=57,500ks | $15=86,250ks | $20=115,000ks | $50=287,500ks | $100=575,000ks
(ဈေးနှုန်း ပြောင်းနိုင်သည် | ငွေလွဲပြီး Boost စတင်)

ဆက်သွယ်ရန်: ဖုန်း 09-400-175-900 | Viber 098-990-033-15

ငွေလွဲ Account များ (ငွေလွဲမည်/Kpay/account number မေးလာလျှင် အောက်ပါအတိုင်း ပြောပြပါ):
KBZ Pay - 09420933977 | Name: Khaing Zin Latt
UAB Pay - 09899003315 | Name: Yan Lin Htet
Wave Pay - 09899003315 | Name: Yan Lin Htet
AYA Pay - 09899003315 | Name: Yan Lin Htet
AYA Saving Bank: 20015034608 | Name: Yan Lin Htet
KBZ Saving: 13330113300744501 | Name: Yan Lin Htet
KBZ Special: 12651113300744501 | Name: Yan Lin Htet

ငွေလွဲပြီးရင် Transaction History Screenshot နဲ့ ID Number ပေးပို့ပေးပါဟု မေ့မမေ့ ပြောပါ 🙏"""

# Track processed message IDs to avoid duplicates
processed_messages = set()
MAX_PROCESSED = 1000

# ============================
# Helper Functions
# ============================
def get_ai_response(user_message):
    """Get AI response from OpenAI"""
    if not client:
        logger.error("OpenAI client not initialized")
        return "မင်္ဂလာပါရှင့်! ခဏစောင့်ပေးပါ၊ မကြာမီ ပြန်ဆက်သွယ်ပေးပါမယ် 🙏"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=200,
            temperature=0.7,
            timeout=15
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "မင်္ဂလာပါရှင့်! ခဏစောင့်ပေးပါ၊ မကြာမီ ပြန်ဆက်သွယ်ပေးပါမယ် 🙏"


def send_message(recipient_id, message_text):
    """Send a text message to a user via Facebook Messenger"""
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
    """Send typing indicator"""
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
    """Process incoming message and send response"""
    # Check for duplicate messages
    mid = message.get("mid", "")
    if mid and mid in processed_messages:
        logger.info(f"Duplicate message {mid}, skipping")
        return
    
    if mid:
        processed_messages.add(mid)
        if len(processed_messages) > MAX_PROCESSED:
            to_remove = list(processed_messages)[:MAX_PROCESSED // 2]
            for item in to_remove:
                processed_messages.discard(item)
    
    # Skip echo messages (messages sent by the page itself)
    if message.get("is_echo"):
        logger.info("Skipping echo message")
        return
    
    message_text = message.get("text", "")
    if not message_text:
        attachments = message.get("attachments", [])
        if attachments:
            # Only respond if bot is not paused
            if not is_bot_paused(sender_id):
                send_message(sender_id, "ပုံ/ဖိုင် ရရှိပါတယ်ရှင့်! ဘာကူညီပေးရမလဲ? 😊")
        return
    
    logger.info(f"Processing message from {sender_id}: {message_text}")
    
    # Check if bot is paused for this user (human takeover active)
    if is_bot_paused(sender_id):
        logger.info(f"Bot is paused for user {sender_id}, skipping AI response")
        return
    
    # Send typing indicator
    send_typing_indicator(sender_id)
    
    # Get AI response
    ai_response = get_ai_response(message_text)
    
    # Send response
    send_message(sender_id, ai_response)


def handle_echo_message(recipient_id, message):
    """Handle echo messages - when admin/page sends a message, pause bot for that user"""
    # Echo messages are sent by the page itself (admin reply)
    # When admin replies to a user, pause bot for that user
    mid = message.get("mid", "")
    
    # Avoid processing duplicate echo messages
    echo_key = f"echo_{mid}"
    if echo_key in processed_messages:
        return
    if mid:
        processed_messages.add(echo_key)
    
    logger.info(f"Admin replied to user {recipient_id}, pausing bot for {HUMAN_TAKEOVER_MINUTES} minutes")
    pause_bot_for_user(recipient_id)


def handle_postback(sender_id, payload):
    """Handle postback events (button clicks)"""
    logger.info(f"Postback from {sender_id}: {payload}")
    
    # Check if bot is paused
    if is_bot_paused(sender_id):
        logger.info(f"Bot is paused for user {sender_id}, skipping postback response")
        return
    
    if payload == "GET_STARTED":
        welcome_msg = "မင်္ဂလာပါရှင့်! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏\n\nBoost, Design, Marketing တွေအတွက် ဘာမေးချင်ပါသလဲ?"
        send_message(sender_id, welcome_msg)
    elif payload == "BOOST_SERVICE":
        msg = "Boost ဈေးနှုန်းများ (Service fee အပါ):\n$5=29,000ks\n$10=57,500ks\n$20=115,000ks\n$50=287,500ks\n\nငွေလွဲပြီး Boost စတင်ပေးပါတယ်ရှင့် 🚀"
        send_message(sender_id, msg)
    elif payload == "PACKAGES":
        msg = "Monthly Package တွေ ရှိပါတယ်ရှင့် 📦\nအသေးစိတ် သိချင်ရင် 09-400-175-900 ကို ဆက်သွယ်ပေးပါ!"
        send_message(sender_id, msg)
    elif payload == "CONTACT":
        msg = "📞 09-400-175-900\n📱 Viber: 098-990-033-15\n\nဖုန်းဆက်ဆိုရင် 09-400-175-900\nViber ဆိုရင် 098-990-033-15 ပါရှင့် 🙏"
        send_message(sender_id, msg)
    else:
        ai_response = get_ai_response(f"User clicked: {payload}")
        send_message(sender_id, ai_response)


# ============================
# Flask Routes
# ============================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Facebook Webhook Verification"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    logger.info(f"Webhook verification: mode={mode}, token={token}")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully!")
        return challenge, 200
    else:
        logger.warning(f"Webhook verification failed. Expected token: {VERIFY_TOKEN}, Got: {token}")
        return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming messages from Facebook"""
    logger.info("=== WEBHOOK POST RECEIVED ===")
    
    try:
        raw_data = request.data.decode('utf-8', errors='replace')
        logger.info(f"Raw data length: {len(raw_data)}")
        logger.debug(f"Raw data: {raw_data[:500]}")
    except Exception as e:
        logger.error(f"Error reading raw data: {e}")
    
    sys.stdout.flush()
    
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 200
    
    if not data:
        logger.error("No data received")
        return jsonify({"status": "error", "message": "No data"}), 200
    
    logger.info(f"Object type: {data.get('object')}")
    sys.stdout.flush()
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            messaging = entry.get("messaging", [])
            logger.info(f"Messaging events count: {len(messaging)}")
            
            for event in messaging:
                try:
                    sender_id = event.get("sender", {}).get("id")
                    recipient_id = event.get("recipient", {}).get("id")
                    if not sender_id:
                        logger.warning("No sender ID found")
                        continue
                    
                    logger.info(f"Sender ID: {sender_id}, Recipient ID: {recipient_id}")
                    
                    if "message" in event:
                        message = event["message"]
                        
                        # Check if this is an echo message (admin/page sent a message)
                        if message.get("is_echo"):
                            # Admin replied to a user - pause bot for that user (recipient)
                            if recipient_id and recipient_id != PAGE_ID:
                                thread = threading.Thread(
                                    target=handle_echo_message,
                                    args=(recipient_id, message)
                                )
                                thread.daemon = True
                                thread.start()
                            logger.info("Echo message - admin reply detected")
                            continue
                        
                        logger.info(f"Message received: {message.get('text', '[no text]')}")
                        # Process in a thread to respond quickly to Facebook
                        thread = threading.Thread(
                            target=handle_message,
                            args=(sender_id, message)
                        )
                        thread.daemon = True
                        thread.start()
                    elif "postback" in event:
                        postback = event["postback"]
                        logger.info(f"Postback received: {postback}")
                        thread = threading.Thread(
                            target=handle_postback,
                            args=(sender_id, postback.get("payload", ""))
                        )
                        thread.daemon = True
                        thread.start()
                    elif "delivery" in event or "read" in event:
                        logger.debug("Delivery/read receipt, ignoring")
                    else:
                        logger.info(f"Unknown event type: {list(event.keys())}")
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
    else:
        logger.info(f"Object is not 'page': {data.get('object')}")
    
    sys.stdout.flush()
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "bot": "All in One Digital Marketing Chatbot",
        "version": "3.0",
        "openai": "configured" if client else "not configured",
        "paused_users": len(paused_users)
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200


@app.route("/paused-users", methods=["GET"])
def get_paused_users():
    """View currently paused users (human takeover active)"""
    with paused_users_lock:
        result = {}
        for uid, ts in paused_users.items():
            elapsed = time.time() - ts
            remaining = max(0, HUMAN_TAKEOVER_MINUTES * 60 - elapsed)
            result[uid] = {
                "paused_at": ts,
                "remaining_seconds": int(remaining)
            }
    return jsonify({"paused_users": result})


@app.route("/resume-bot/<user_id>", methods=["GET"])
def resume_bot(user_id):
    """Manually resume bot for a specific user"""
    with paused_users_lock:
        if user_id in paused_users:
            del paused_users[user_id]
            logger.info(f"Bot manually resumed for user {user_id}")
            return jsonify({"status": "resumed", "user_id": user_id})
    return jsonify({"status": "not_paused", "user_id": user_id})


@app.route("/set-started-button", methods=["GET"])
def set_started_button():
    """Set Get Started button for Messenger"""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messenger_profile"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "get_started": {"payload": "GET_STARTED"},
        "greeting": [
            {
                "locale": "default",
                "text": "မင်္ဂလာပါရှင့်! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏 ဘာကူညီပေးရမလဲ?"
            }
        ],
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {
                        "type": "postback",
                        "title": "📢 Boost ဈေးနှုန်း",
                        "payload": "BOOST_SERVICE"
                    },
                    {
                        "type": "postback",
                        "title": "📦 Package များ",
                        "payload": "PACKAGES"
                    },
                    {
                        "type": "postback",
                        "title": "📞 ဆက်သွယ်ရန်",
                        "payload": "CONTACT"
                    }
                ]
            }
        ]
    }
    response = requests.post(url, params=params, json=payload, timeout=10)
    return jsonify(response.json())


# ============================
# Keep-alive ping (prevents Render cold start)
# ============================
def keep_alive():
    """Ping the server every 14 minutes to prevent Render free tier sleep"""
    while True:
        time.sleep(840)  # 14 minutes
        try:
            url = os.environ.get("RENDER_EXTERNAL_URL", "https://aio-chatbot.onrender.com")
            requests.get(f"{url}/health", timeout=10)
            logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.error(f"Keep-alive ping failed: {e}")


# Start keep-alive thread
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()
logger.info("Keep-alive thread started")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
