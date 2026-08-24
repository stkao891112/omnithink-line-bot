import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv

# LINE Bot SDK v3 imports
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Google Gemini API import
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Configure Gemini API
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    logger.info(f"Gemini API configured with model: {GEMINI_MODEL_NAME}")
else:
    gemini_model = None
    logger.warning("GEMINI_API_KEY is missing or invalid. Please check your .env file.")

# Configure LINE Bot SDK
handler = WebhookHandler(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN) if LINE_CHANNEL_ACCESS_TOKEN else None

app = FastAPI(
    title="OmniThink LINE Bot",
    description="LINE Bot integrated with Google Gemini API",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "OmniThink LINE Bot service is running.",
        "gemini_configured": gemini_model is not None,
        "line_configured": handler is not None
    }


@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None)):
    """Webhook callback endpoint for LINE Messaging API."""
    if not handler:
        logger.error("LINE_CHANNEL_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_SECRET is not configured.")

    if not x_line_signature:
        logger.error("Missing X-Line-Signature header.")
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header.")

    # Read request body
    body_bytes = await request.body()
    body = body_bytes.decode("utf-8")

    # Handle webhook body and verify signature
    try:
        handler.handle(body, x_line_signature)
    except InvalidSignatureError:
        logger.error("Invalid LINE webhook signature.")
        raise HTTPException(status_code=400, detail="Invalid signature. Please check Channel Secret.")
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return "OK"


# Store chat sessions per user_id
user_chats = {}


# Event handler for TextMessage
if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event: MessageEvent):
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", "default_user")
        logger.info(f"Received message from [{user_id}]: {user_text}")

        # LINE Verify test event check (skip calling Gemini/reply for dummy tokens)
        DUMMY_REPLY_TOKENS = ["00000000000000000000000000000000", "ffffffffffffffffffffffffffffffff"]
        if event.reply_token in DUMMY_REPLY_TOKENS:
            logger.info("Received LINE Webhook Verify test event. Skipping Gemini call.")
            return

        # Handle reset command
        if user_text.lower() in ["/reset", "重置", "清空", "清除記憶"]:
            if user_id in user_chats:
                del user_chats[user_id]
            reply_text = "🧹 對話記憶已清空！我們可以開始新的話題囉。"
        # Check Gemini API setup
        elif not gemini_model:
            reply_text = "⚠️ 系統尚未設定有效的 GEMINI_API_KEY，請在 .env 中填寫金鑰。"
        else:
            try:
                # Get or create multi-turn chat session for this user
                if user_id not in user_chats:
                    user_chats[user_id] = gemini_model.start_chat(history=[])
                
                chat_session = user_chats[user_id]
                response = chat_session.send_message(user_text)
                reply_text = response.text.strip() if response and response.text else "抱歉，Gemini 未能產生回應。"
            except Exception as e:
                logger.error(f"Gemini API error for user {user_id}: {e}")
                # Reset chat session on error to prevent broken state
                if user_id in user_chats:
                    del user_chats[user_id]
                reply_text = f"⚠️ 處理對話時發生錯誤，已自動重置記憶：{str(e)}"

        # Reply to LINE user
        try:
            with ApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
            logger.info("Successfully sent reply message to LINE.")
        except Exception as e:
            logger.error(f"Failed to send LINE reply: {e}")
