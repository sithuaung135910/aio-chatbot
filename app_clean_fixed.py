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

# System prompt for the AI
SYSTEM_PROMPT = """You are a helpful customer service assistant for "All in One Digital Marketing" - a digital marketing agency in Myanmar.

Your role:
- Respond in Burmese (Myanmar language) by default
- If the customer writes in English, respond in English
- Be friendly, professional, and helpful
- Help customers with questions about digital marketing services including:
  * Facebook/Instagram Boost Services
  * Social Media Marketing
  * Graphic Design Services
  * Marketing Packages
  * Website Development
  * SEO Services
- If you don't know specific pricing, politely tell them you'll connect them with the team
- Keep responses concise and under 500 characters when possible
- Use appropriate emojis sparingly to be friendly

Important: You represent "All in One Digital Marketing". Always be professional and helpful."""

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
        return "မင်္ဂလာပါ! All in One Digital Marketing မှ ကြိုဆိုပါတယ်။ ခဏစောင့်ပေးပါ၊ ကျွန်တော်တို့ team မှ မကြာမီ ပြန်လည်ဆက်သွယ်ပေးပါမယ်။ 🙏"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
            temperature=0.7,
            timeout=15
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "မင်္ဂလာပါ! ကျွန်တော်တို့ All in One Digital Marketing ကို ဆက်သွယ်ပေးတဲ့အတွက် ကျေးဇူးတင်ပါတယ်။ ခဏစောင့်ပေးပါ၊ team မှ ပြန်လည်ဆက်သွယ်ပေးပါမယ်။ 🙏"


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
        # Clean up old messages to prevent memory leak
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
        # Handle attachments (images, stickers, etc.)
        attachments = message.get("attachments", [])
        if attachments:
            send_message(sender_id, "ပုံ/ဖိုင် လက်ခံရရှိပါတယ်! သင့်အတွက် ဘာကူညီပေးရမလဲ? 😊")
        return
    
    logger.info(f"Processing message from {sender_id}: {message_text}")
    
    # Send typing indicator
    send_typing_indicator(sender_id)
    
    # Get AI response
    ai_response = get_ai_response(message_text)
    
    # Send response
    send_message(sender_id, ai_response)


def handle_postback(sender_id, payload):
    """Handle postback events (button clicks)"""
    logger.info(f"Postback from {sender_id}: {payload}")
    
    if payload == "GET_STARTED":
        welcome_msg = "မင်္ဂလာပါ! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏\n\nကျွန်တော်တို့ ဝန်ဆောင်မှုများ:\n📢 Facebook/Instagram Boost Service\n🎨 Graphic Design\n📦 Marketing Packages\n🌐 Website Development\n\nသိချင်တာရှိရင် မေးလို့ရပါတယ်!"
        send_message(sender_id, welcome_msg)
    elif payload == "BOOST_SERVICE":
        msg = "📢 Boost Service အကြောင်း သိချင်ပါသလား?\n\nFacebook နဲ့ Instagram boost service များ ပေးနေပါတယ်။ ဘယ်လို boost လုပ်ချင်လဲ ပြောပြပေးပါ။ ကျွန်တော်တို့ team မှ အသေးစိတ် ရှင်းပြပေးပါမယ်! 🚀"
        send_message(sender_id, msg)
    elif payload == "PACKAGES":
        msg = "📦 Marketing Package များ\n\nကျွန်တော်တို့မှာ အမျိုးမျိုးသော package များ ရှိပါတယ်။ သင့်လုပ်ငန်းအတွက် အသင့်တော်ဆုံး package ကို ရွေးချယ်ပေးပါမယ်။ ဘယ်လို service လိုချင်လဲ ပြောပြပေးပါ! 📊"
        send_message(sender_id, msg)
    elif payload == "CONTACT":
        msg = "📞 ဆက်သွယ်ရန်\n\nAll in One Digital Marketing\n💬 Messenger မှာ တိုက်ရိုက် စာပို့ပေးပါ\n📱 ဖုန်းဖြင့် ဆက်သွယ်လိုပါက ပြောပြပေးပါ\n\nကျွန်တော်တို့ team မှ အမြန်ဆုံး ပြန်လည်ဆက်သွယ်ပေးပါမယ်! 🙏"
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
                    if not sender_id:
                        logger.warning("No sender ID found")
                        continue
                    
                    logger.info(f"Sender ID: {sender_id}")
                    
                    if "message" in event:
                        message = event["message"]
                        # Skip echo messages
                        if message.get("is_echo"):
                            logger.info("Skipping echo message")
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
        "version": "2.0",
        "openai": "configured" if client else "not configured"
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200


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
                "text": "မင်္ဂလာပါ! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏 Boost Service, Design, Marketing Package များ အတွက် ကျွန်တော်တို့ကို ဆက်သွယ်ပါ။"
            }
        ],
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {
                        "type": "postback",
                        "title": "📢 Boost Service",
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
