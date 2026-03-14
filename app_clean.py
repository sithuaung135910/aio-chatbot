import os
import sys
import json
import hmac
import hashlib
import logging
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# Configure logging to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================
# Configuration (Set these in environment variables or .env file)
# ============================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "aio_chatbot_verify_2024")
APP_SECRET = os.environ.get("APP_SECRET", "YOUR_APP_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# ============================
# Business Knowledge Base (FAQ)
# ============================
BUSINESS_CONTEXT = """
သင်သည် "All in One Digital Marketing" ၏ Customer Support AI Assistant ဖြစ်ပါသည်။
မြန်မာဘာသာဖြင့်သာ ဖြေဆိုပါ။ ယဉ်ကျေးသိမ်မွေ့ပြီး ကူညီပေးရန် အမြဲသင့်ရှိပါ။

=== ကုမ္ပဏီ အကြောင်း ===
- နာမည်: All in One Digital Marketing
- တည်နေရာ: Pinlon Street, North Dagon Township, Yangon, Myanmar
- ဖုန်း: 09400175900 / +95 9 899 003315
- Email: allinonedigitalmarketing@gmail.com
- Slogan: "Low Budget & Maximum Results"
- 2021 ခုနှစ်မှ စတင်ဝန်ဆောင်မှုပေးနေပြီး Meta Certified Media Buying Professional များဖြင့် ဆောင်ရွက်ပါသည်။

=== ဝန်ဆောင်မှုများ ===

1. **Boost Service (Media Buying / Facebook Ads)**
   - Facebook & Instagram Ads များ Run ပေးခြင်း
   - Target Audience သတ်မှတ်ပေးခြင်း
   - Budget အနည်းဆုံး 5,000 ကျပ်မှ စတင်နိုင်
   - Campaign Setup, Optimization, Reporting ပါဝင်
   - Boost အပ်ရန်: Inbox မှ ဆက်သွယ်ပါ သို့မဟုတ် 09400175900 သို့ ခေါ်ဆိုပါ
   - Package များ: Basic, Standard, Premium (တိကျသော ဈေးနှုန်းအတွက် Inbox ဆက်သွယ်ပါ)

2. **Content & Copy Writing**
   - Post Content ရေးပေးခြင်း
   - Ad Copy ရေးပေးခြင်း
   - Caption ရေးပေးခြင်း

3. **Logo & Graphic Design**
   - Logo Design
   - Banner Design
   - Post Design

4. **Motion Video Graphic**
   - Video Ads ပြုလုပ်ပေးခြင်း
   - Animated Content

5. **Page Setting Service**
   - Facebook Page Setup
   - Business Manager Setup
   - Pixel Installation

6. **Account & Page Error Fix Service**
   - Disabled Account ပြန်ဖွင့်ပေးခြင်း
   - Page Error ဖြေရှင်းပေးခြင်း

7. **FB Marketing Packages**
   - Monthly Marketing Package
   - Full Service Package

8. **TikTok Service**
   - TikTok Ads
   - TikTok Content

9. **Blue Mark Service**
   - Facebook Verification (Blue Tick)

10. **Online Registration**
    - Business Registration
    - Online Services Registration

=== Boost Service အပ်ခြင်း လုပ်ငန်းစဉ် ===
1. Inbox မှ ဆက်သွယ်ပါ
2. သင့် Business/Product အကြောင်း ပြောပြပါ
3. Budget နှင့် Target Audience သတ်မှတ်ပါ
4. Package ရွေးချယ်ပါ
5. Payment ပြုလုပ်ပါ
6. Campaign စတင်ပါ

=== အဖြေပေးနည်း လမ်းညွှန် ===
- Boost Service အကြောင်း မေးလျှင် အသေးစိတ် ရှင်းပြပြီး ဆက်သွယ်ရန် ညွှန်ကြားပါ
- ဈေးနှုန်း မေးလျှင် Package အပေါ် မူတည်ကြောင်း ပြောပြီး Inbox ဆက်သွယ်ရန် ပြောပါ
- မသိသော မေးခွန်းများအတွက် Team ထံ ဆက်သွယ်ရန် ညွှန်ကြားပါ
- အမြဲ ယဉ်ကျေးသိမ်မွေ့စွာ ဖြေဆိုပါ
"""

# ============================
# Quick Reply Templates
# ============================
def get_welcome_message():
    return {
        "text": "မင်္ဂလာပါ! All in One Digital Marketing မှ ကြိုဆိုပါတယ် 🙏\n\nကျွန်တော်တို့ရဲ့ AI Assistant ဖြစ်ပါတယ်။ ဘာများ ကူညီပေးရမလဲ?",
        "quick_replies": [
            {
                "content_type": "text",
                "title": "📢 Boost Service",
                "payload": "BOOST_SERVICE"
            },
            {
                "content_type": "text",
                "title": "🎨 Design Service",
                "payload": "DESIGN_SERVICE"
            },
            {
                "content_type": "text",
                "title": "📦 Package များ",
                "payload": "PACKAGES"
            },
            {
                "content_type": "text",
                "title": "📞 ဆက်သွယ်ရန်",
                "payload": "CONTACT"
            }
        ]
    }

def get_boost_service_message():
    return {
        "text": "📢 Boost Service (Facebook & Instagram Ads)\n\n✅ Facebook & Instagram Ads Run ပေးခြင်း\n✅ Target Audience သတ်မှတ်ပေးခြင်း\n✅ Budget Planning\n✅ Campaign Optimization\n✅ Monthly Report\n\n💰 Budget: 5,000 ကျပ်မှ စတင်နိုင်\n🏆 Meta Certified Professional များဖြင့် ဆောင်ရွက်\n\nBoost Service အပ်ချင်ပါသလား?",
        "quick_replies": [
            {
                "content_type": "text",
                "title": "✅ အပ်ချင်တယ်",
                "payload": "BOOST_ORDER"
            },
            {
                "content_type": "text",
                "title": "💰 ဈေးနှုန်း မေးမည်",
                "payload": "BOOST_PRICE"
            },
            {
                "content_type": "text",
                "title": "🔙 နောက်သို့",
                "payload": "BACK_MAIN"
            }
        ]
    }

def get_boost_order_message():
    return {
        "text": "🎉 ကောင်းပါတယ်! Boost Service အပ်ရန်:\n\n📱 Inbox: m.me/allinonedigitalmarketing1359\n📞 ဖုန်း: 09400175900\n📞 ဖုန်း: +95 9 899 003315\n📧 Email: allinonedigitalmarketing@gmail.com\n\nကျွန်တော်တို့ Team မှ အမြန်ဆုံး ပြန်လည်ဆက်သွယ်ပေးပါမည် 🙏\n\nသင့် Business/Product အကြောင်း အနည်းငယ် ပြောပြပေးနိုင်ပါသလား?"
    }

def get_contact_message():
    return {
        "text": "📞 ဆက်သွယ်ရန်:\n\n📱 ဖုန်း: 09400175900\n📱 ဖုန်း: +95 9 899 003315\n📧 Email: allinonedigitalmarketing@gmail.com\n📍 တည်နေရာ: Pinlon Street, North Dagon Township, Yangon\n🕐 ဖွင့်ချိန်: Always Open\n\nFacebook Page: All in One Digital Marketing"
    }

# ============================
# AI Response Function
# ============================
def get_ai_response(user_message, sender_id):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": BUSINESS_CONTEXT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "ဆောရီးပါ၊ ယခုအချိန်တွင် ပြဿနာတစ်ခု ဖြစ်နေပါသည်။ ကျေးဇူးပြု၍ 09400175900 သို့ တိုက်ရိုက်ဆက်သွယ်ပါ။"

# ============================
# Send Message to Facebook
# ============================
def send_message(recipient_id, message_data):
    url = f"https://graph.facebook.com/v19.0/me/messages"
    headers = {"Content-Type": "application/json"}
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": message_data,
        "messaging_type": "RESPONSE"
    }
    
    response = requests.post(url, headers=headers, params=params, json=payload)
    if response.status_code != 200:
        print(f"Send message error: {response.status_code} - {response.text}")
    return response

def send_typing_on(recipient_id):
    url = f"https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_on"
    }
    requests.post(url, params=params, json=payload)

# ============================
# Handle Messages
# ============================
def handle_message(sender_id, message):
    text = message.get("text", "").strip()
    
    # Handle quick reply payloads
    if "quick_reply" in message:
        payload = message["quick_reply"]["payload"]
        handle_quick_reply(sender_id, payload)
        return
    
    # Handle text messages
    if text:
        # Check for greeting keywords
        greetings = ["မင်္ဂလာ", "hello", "hi", "ဟဲလို", "ဟယ်လို", "start", "စတင်", "ကြိုဆို"]
        boost_keywords = ["boost", "ဘုစ်", "boost service", "ads", "ကြော်ငြာ", "advertise", "promote", "အပ်ချင်"]
        
        text_lower = text.lower()
        
        if any(g.lower() in text_lower for g in greetings):
            send_typing_on(sender_id)
            send_message(sender_id, get_welcome_message())
        elif any(k.lower() in text_lower for k in boost_keywords):
            send_typing_on(sender_id)
            send_message(sender_id, get_boost_service_message())
        else:
            # Use AI for other questions
            send_typing_on(sender_id)
            ai_response = get_ai_response(text, sender_id)
            send_message(sender_id, {"text": ai_response})

def handle_quick_reply(sender_id, payload):
    send_typing_on(sender_id)
    
    if payload == "BOOST_SERVICE":
        send_message(sender_id, get_boost_service_message())
    elif payload == "BOOST_ORDER":
        send_message(sender_id, get_boost_order_message())
    elif payload == "BOOST_PRICE":
        ai_response = get_ai_response("Boost Service ဈေးနှုန်း ဘယ်လောက်လဲ?", sender_id)
        send_message(sender_id, {"text": ai_response})
    elif payload == "DESIGN_SERVICE":
        ai_response = get_ai_response("Design Service တွေ ဘာတွေ ရှိလဲ?", sender_id)
        send_message(sender_id, {"text": ai_response})
    elif payload == "PACKAGES":
        ai_response = get_ai_response("Package တွေ ဘာတွေ ရှိလဲ?", sender_id)
        send_message(sender_id, {"text": ai_response})
    elif payload == "CONTACT":
        send_message(sender_id, get_contact_message())
    elif payload == "BACK_MAIN":
        send_message(sender_id, get_welcome_message())
    else:
        ai_response = get_ai_response(payload, sender_id)
        send_message(sender_id, {"text": ai_response})

# ============================
# Flask Routes
# ============================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Facebook Webhook Verification"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge, 200
    else:
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming messages from Facebook"""
    logger.info("=== WEBHOOK POST RECEIVED ===")
    logger.info(f"Raw data: {request.data.decode('utf-8', errors='replace')}")
    sys.stdout.flush()
    
    # Skip signature verification for now (APP_SECRET not set)
    
    data = request.get_json()
    logger.info(f"Parsed JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
    sys.stdout.flush()
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            messaging = entry.get("messaging", [])
            logger.info(f"Messaging events count: {len(messaging)}")
            for event in messaging:
                sender_id = event["sender"]["id"]
                logger.info(f"Sender ID: {sender_id}")
                
                if "message" in event:
                    logger.info(f"Message received: {event['message']}")
                    handle_message(sender_id, event["message"])
                elif "postback" in event:
                    logger.info(f"Postback received: {event['postback']}")
                    handle_quick_reply(sender_id, event["postback"]["payload"])
    else:
        logger.info(f"Object is not 'page': {data.get('object')}")
    
    sys.stdout.flush()
    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "bot": "All in One Digital Marketing Chatbot",
        "version": "1.0"
    })

@app.route("/set-started-button", methods=["GET"])
def set_started_button():
    """Set Get Started button for Messenger"""
    url = f"https://graph.facebook.com/v19.0/me/messenger_profile"
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
    response = requests.post(url, params=params, json=payload)
    return jsonify(response.json())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
