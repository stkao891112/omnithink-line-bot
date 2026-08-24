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

# Traditional Chinese System Instruction for Gemini API
SYSTEM_INSTRUCTION = """你是 Omni AI助手。
【重要語言規範】：必須一律使用「台灣繁體中文 (Traditional Chinese / 正體中文)」進行回答，絕對禁止使用簡體中文。
【回覆風格】：語氣親切、專業、條理分明。
【即時資料】：當訊息中提供【即時網路搜尋結果】時，請綜合參考最新搜尋內容，為使用者解答最新事實、新聞與資訊。"""

# Configure Gemini API
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION
    )
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


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Health check endpoint supporting both GET and HEAD for UptimeRobot keep-alive."""
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


import concurrent.futures


def perform_web_search(query: str, timeout: float = 1.8) -> tuple[str, str]:
    """
    Perform real-time web search using DDGS with strict timeout safety guard.
    Returns (search_results_text, debug_log_text).
    """
    def _do_search():
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=4))
                if not results:
                    return ("", "⚠️ [搜尋 Log] 未找到相關即時搜尋結果。")
                snippets = []
                for idx, item in enumerate(results, 1):
                    title = item.get("title", "")
                    body = item.get("body", "")
                    snippets.append(f"[{idx}] {title}\n{body}")
                return ("\n\n".join(snippets), f"✅ [搜尋 Log] 成功獲取 {len(results)} 條即時資料")
        except Exception as e:
            logger.error(f"Web search execution error: {e}")
            return ("", f"⚠️ [搜尋 Log 錯誤] 執行搜尋時發生異常：{e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_search)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            log_msg = f"⚠️ [搜尋 Log 提示] 網路搜尋處理超過 {timeout}s 超時，已自動切換由 Gemini 直接回答。"
            logger.warning(log_msg)
            return ("", log_msg)
        except Exception as e:
            log_msg = f"⚠️ [搜尋 Log 錯誤] 搜尋執行緒發生錯誤：{e}"
            logger.error(log_msg)
            return ("", log_msg)


RESET_COMMANDS = [
    "/reset", "/clear", "/清除記憶", "/重置記憶", "/重置", "/清空", "/清除",
    "清除記憶", "重置記憶", "清空記憶", "重置對話", "清空對話", "清除對話", "重置"
]


def is_reset_command(text: str) -> bool:
    """Check if input is a hard reset memory command."""
    clean_text = text.lower().strip()
    if clean_text in RESET_COMMANDS:
        return True
    for cmd in ["/reset", "/clear", "/清除記憶", "/重置記憶", "/重置", "/清空", "/清除"]:
        if clean_text.startswith(cmd):
            return True
    return False


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

        # Handle hard reset command
        if is_reset_command(user_text):
            if user_id in user_chats:
                del user_chats[user_id]
            if gemini_model:
                user_chats[user_id] = gemini_model.start_chat(history=[])
            logger.info(f"HARD RESET: Successfully cleared chat session for user [{user_id}]")
            reply_text = "🧹【系統通知】對話記憶與歷史已徹底重置！Gemini AI 已恢復為全新初始狀態，我們可以開始新的話題囉。"
        # Check Gemini API setup
        elif not gemini_model:
            reply_text = "⚠️ 系統尚未設定有效的 GEMINI_API_KEY，請在 .env 中填寫金鑰。"
        else:
            def _process_ai_turn():
                # Get or create multi-turn chat session for this user
                if user_id not in user_chats:
                    user_chats[user_id] = gemini_model.start_chat(history=[])
                
                chat_session = user_chats[user_id]
                
                # Real-time search trigger check
                search_keywords = ["搜尋", "查", "天氣", "新聞", "最新", "今天", "股價", "賽事", "2026", "幾度", "誰是", "哪裡", "多少"]
                is_search_cmd = any(user_text.lower().startswith(prefix) for prefix in ["/search", "搜尋", "幫我查", "查一下", "查"])
                should_search = is_search_cmd or any(kw in user_text for kw in search_keywords)

                debug_log_note = ""
                search_header = ""

                if should_search:
                    # Clean search query string
                    clean_query = user_text
                    for prefix in ["/search", "搜尋", "幫我查", "查一下", "查", "請幫我", "請問"]:
                        if clean_query.startswith(prefix):
                            clean_query = clean_query[len(prefix):].strip()
                    for suffix in ["嗎", "呢", "什麼", "怎樣", "如何", "吧"]:
                        if clean_query.endswith(suffix):
                            clean_query = clean_query[:-len(suffix)].strip()
                    
                    logger.info(f"Executing real-time web search for query: {clean_query}")
                    search_info, search_log = perform_web_search(clean_query if clean_query else user_text, timeout=1.5)

                    # Store debug log note if search had log message
                    if search_log:
                        debug_log_note = f"\n\n📌 系統狀態 Log:\n{search_log}"

                    if search_info:
                        search_header = "🌐 [已載入即時網路搜尋資料]\n\n"
                        prompt_to_send = (
                            f"【即時網路搜尋結果】:\n{search_info}\n\n"
                            f"【使用者問題】:\n{user_text}\n\n"
                            f"請綜合參考上述最新搜尋結果，使用台灣繁體中文為使用者提供精確、即時且有條理的回答。"
                        )
                    else:
                        prompt_to_send = user_text
                else:
                    prompt_to_send = user_text

                response = chat_session.send_message(prompt_to_send)
                base_reply = response.text.strip() if response and response.text else "抱歉，Gemini 未能產生回應。"
                return search_header + base_reply + debug_log_note

            # Execute AI processing turn with 4.2s hard timeout safety guard
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_process_ai_turn)
                    reply_text = future.result(timeout=4.2)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Total processing for user [{user_id}] hit 4.2s timeout safety guard.")
                reply_text = "⏱️ 【系統連線提示 Log】\n處理時間已達到 4.2 秒安全上限（LINE 硬性上限為 5 秒）。\n為避免 LINE 連線中斷，已自動停止該次生成，請再試一次或簡化提問！"
            except Exception as e:
                logger.error(f"Gemini API error for user {user_id}: {e}")
                if user_id in user_chats:
                    del user_chats[user_id]
                reply_text = f"❌ 【系統錯誤 Log】\n- 類型: {type(e).__name__}\n- 詳情: {str(e)}\n\n(已為您重置該次對話 Session)"

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
