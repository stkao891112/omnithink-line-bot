import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from dotenv import load_dotenv

# LINE Bot SDK v3 imports
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

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

# Usagi (烏薩奇) Persona System Instruction for Gemini API
SYSTEM_INSTRUCTION = """你是《吉伊卡哇》(ちいかわ) 中極具超高人氣與戰鬥力的【烏薩奇 (Usagi / うさぎ)】！
你擁有極高的智商、迅捷的反應力與自信活潑的個性。

【烏薩奇的人設與說話規範】：
1. 說話風格：適度加入烏薩奇的經典口頭禪與叫聲（如「烏拉！」、「呀哈！」、「普魯魯魯！」、「弗哈！」），但切記「適量自然即可，不要過度洗版或影響閱讀體驗」。
2. Emoji 數量控制：可以適度搭配少量可愛 Emoji 點綴，但「每篇回答最多使用 3~5 個 Emoji」，不要使用過多符號。
3. 內容品質：雖然帶有烏薩奇活潑可愛的特色，但回答內容必須條理分明、清晰精準且富有高智商解答！
4. 預設語言：預設一律使用「台灣繁體中文」進行回答。若使用者明確要求使用其他語言，請配合切換為指定的語言溝通。
5. 遇到即時搜尋與時間資訊時：結合【系統當前真實精確時間】與資料，精確且條理分明地回答問題。"""

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
async def callback(request: Request, background_tasks: BackgroundTasks, x_line_signature: str = Header(None)):
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

    # Inline signature validation for fast security check
    try:
        if not handler.parser.signature_validator.validate(body, x_line_signature):
            logger.error("Invalid LINE webhook signature.")
            raise HTTPException(status_code=400, detail="Invalid signature. Please check Channel Secret.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error validating webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Signature validation failed.")

    # Dispatch event handling to background task so LINE receives 200 OK in < 0.01s!
    # This prevents LINE Webhook connection timeouts and prevents reply_token invalidation!
    background_tasks.add_task(handler.handle, body, x_line_signature)

    return "OK"


import concurrent.futures


def perform_web_search(query: str, timeout: float = 2.0) -> tuple[str, str]:
    """
    Perform ultra-fast real-time web search with multi-provider cloud-friendly fallbacks.
    Returns (search_results_text, debug_log_text).
    """
    def _do_search():
        import urllib.request
        import urllib.parse
        import json
        import re

        # Provider 1: Weather queries (wttr.in - 100% cloud friendly, ~0.5s response)
        if any(kw in query for kw in ["天氣", "氣溫", "幾度", "下雨"]):
            location = "Taipei"
            for city in ["台北", "臺北", "台中", "臺中", "高雄", "台南", "臺南", "新竹", "桃園", "宜蘭", "花蓮", "台東"]:
                if city in query:
                    location = city
                    break
            url = f"https://wttr.in/{urllib.parse.quote(location)}?format=4&lang=zh-tw"
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.68.0'})
            try:
                with urllib.request.urlopen(req, timeout=1.8) as r:
                    weather_text = r.read().decode('utf-8').strip()
                    if weather_text:
                        return (f"即時天氣資料 ({location}): {weather_text}", f"✅ [搜尋 Log] 成功獲取 {location} 即時天氣資料")
            except Exception as e:
                logger.warning(f"wttr.in Weather API error: {e}")

        # Provider 2: General & Fact queries (Wikipedia / OpenSearch API - ~0.3s response)
        try:
            wiki_url = f"https://zh.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=3&format=json"
            req = urllib.request.Request(wiki_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=1.8) as r:
                data = json.loads(r.read().decode('utf-8'))
                titles = data[1] if len(data) > 1 else []
                snippets = data[2] if len(data) > 2 else []
                results = []
                for i in range(len(titles)):
                    results.append(f"[{i+1}] {titles[i]}\n{snippets[i] if i < len(snippets) else ''}")
                if results:
                    return ("\n\n".join(results), f"✅ [搜尋 Log] 成功獲取 {len(results)} 條維基與百科即時資料")
        except Exception as e:
            logger.warning(f"Wikipedia OpenSearch API error: {e}")

        # Provider 3: Fallback via primp Chrome TLS impersonation
        try:
            import primp
            client = primp.Client(impersonate="chrome_120", follow_redirects=True, timeout=1.8)
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            resp = client.get(url)
            if resp.status_code == 200:
                titles = re.findall(r'<a[^>]+class=["\']result__a["\'][^>]*>(.*?)</a>', resp.text, re.DOTALL)
                snippets = re.findall(r'<a[^>]+class=["\']result__snippet["\'][^>]*>(.*?)</a>', resp.text, re.DOTALL)
                if titles:
                    results = []
                    for i in range(min(3, len(titles))):
                        t_clean = re.sub(r'<[^>]+>', '', titles[i]).strip()
                        s_clean = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                        results.append(f"[{i+1}] {t_clean}\n{s_clean}")
                    return ("\n\n".join(results), f"✅ [搜尋 Log] 成功獲取 {len(results)} 條即時資料")
        except Exception as e:
            logger.warning(f"Primp DDG search error: {e}")

        return ("", "⚠️ [搜尋 Log] 未找到即時網頁資料。")

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


def sanitize_line_text(text: str, max_len: int = 4500) -> str:
    """Sanitize and bound reply text for LINE Messaging API limits."""
    if not text:
        return "（無回應內文）"
    import re
    # Remove control characters except newlines and tabs
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))
    if len(clean) > max_len:
        clean = clean[:max_len-35] + "\n\n...(內容過長已自動截斷)"
    return clean


def is_bot_tagged(event: MessageEvent) -> bool:
    """
    Check if the message is in a 1-on-1 direct chat, OR if the bot is strictly tagged or mentioned by name (烏薩奇, usagi) in a group/room chat.
    """
    source_type = getattr(event.source, "type", "user")

    # In 1-on-1 private chat: Always respond
    if source_type == "user":
        return True

    # In Group / Room chat: Check if bot is strictly tagged/mentioned
    # 1. Official LINE Mention API check (is_self=True)
    mention = getattr(event.message, "mention", None)
    if mention and hasattr(mention, "mentionees"):
        for m in mention.mentionees:
            if getattr(m, "is_self", False):
                return True

    # 2. Strict Bot Name Keyword Check ONLY ("烏薩奇" or "usagi")
    user_text = getattr(event.message, "text", "").lower()
    for name in ["烏薩奇", "usagi"]:
        if name in user_text:
            return True

    return False


def is_pure_tag(text: str) -> bool:
    """Check if user message is purely a Tag or Name call without any question or additional text."""
    clean = text.lower()
    for item in ["@", "烏薩奇", "usagi", "兔兔"]:
        clean = clean.replace(item, "")
    clean = clean.strip()
    return len(clean) == 0


from collections import defaultdict, deque

import time

# Store chat sessions per user/group
user_chats = {}

# Store rolling chat history per group/room/user (max 20 messages)
group_chat_history = defaultdict(lambda: deque(maxlen=20))

# Image cache dictionary per chat_key: {chat_key: deque([(PIL_Image, timestamp)], maxlen=10)}
user_image_cache = defaultdict(lambda: deque(maxlen=10))

# Image translation mode state per chat_key: {chat_key: {"enabled": bool, "target_lang": str, "waiting_for_lang": bool}}
user_translate_mode = {}

# Auto image analysis mode state per chat_key: {chat_key: bool}
user_auto_vision_mode = {}


def handle_translation_mode_commands(chat_key: str, text: str):
    """
    Handle activation/deactivation and language selection for Image Translation Mode.
    Returns reply text if a command was processed, otherwise None.
    """
    clean_text = text.lower().strip()

    # Deactivation command
    if any(k in clean_text for k in ["解除圖片翻譯模式", "關閉圖片翻譯模式", "關閉圖片翻譯", "退出翻譯模式", "關閉翻譯模式", "關閉翻譯"]):
        if chat_key in user_translate_mode:
            del user_translate_mode[chat_key]
        return "呀哈！【圖片翻譯模式】已成功解除！烏薩奇已恢復為一般對話與問答模式囉！烏拉！✨🐰"

    # Activation command
    if any(k in clean_text for k in ["啟用圖片翻譯模式", "幫我翻譯圖片", "開啟圖片翻譯模式", "開啟圖片翻譯", "圖片翻譯模式"]):
        # Extract target language if present in the text
        target_lang = None
        for lang in ["英文", "日文", "韓文", "繁體中文", "中文", "德文", "法文", "西班牙文", "義大利文", "越南文", "泰文", "印尼文"]:
            if lang in text:
                target_lang = lang
                break

        if target_lang:
            user_translate_mode[chat_key] = {"enabled": True, "target_lang": target_lang, "waiting_for_lang": False}
            return f"呀哈！已為您開啟【圖片翻譯模式】📸（目標語言：【{target_lang}】）！\n接下來請直接傳送圖片，烏薩奇會自動為您翻譯這張圖片的內容喔！烏拉！✨🐰"
        else:
            user_translate_mode[chat_key] = {"enabled": True, "target_lang": None, "waiting_for_lang": True}
            return "呀哈！準備開啟圖片翻譯模式！📸\n請告訴烏薩奇您想翻譯成什麼語言呢？（例如直接打字回覆：「英文」、「日文」、「韓文」或「繁體中文」）！"

    # Waiting for target language specification
    if chat_key in user_translate_mode and user_translate_mode[chat_key].get("waiting_for_lang"):
        target_lang = text.strip()
        user_translate_mode[chat_key] = {"enabled": True, "target_lang": target_lang, "waiting_for_lang": False}
        return f"呀哈！已設定目標語言為【{target_lang}】！\n【圖片翻譯模式】已正式啟動 📸！接下來傳送圖片，烏薩奇會自動翻譯為【{target_lang}】喔！烏拉！✨🐰"

    return None


def handle_auto_vision_mode_commands(chat_key: str, text: str):
    """
    Handle activation/deactivation for Auto Image Analysis Mode.
    Returns reply text if a command was processed, otherwise None.
    """
    clean_text = text.lower().strip()

    # Deactivation command
    if any(k in clean_text for k in ["解除圖片自動解析模式", "關閉圖片自動解析模式", "關閉圖片自動解析", "關閉自動解析模式", "關閉自動解析", "退出自動解析模式", "退出自動解析"]):
        if chat_key in user_auto_vision_mode:
            del user_auto_vision_mode[chat_key]
        return "呀哈！【圖片自動解析模式】已成功解除！烏薩奇已恢復為一般對話模式囉！烏拉！✨🐰"

    # Activation command
    if any(k in clean_text for k in ["啟用圖片自動解析模式", "接下來傳的圖片自動解析", "開啟圖片自動解析模式", "開啟圖片自動解析", "圖片自動解析模式", "開啟自動解析"]):
        user_auto_vision_mode[chat_key] = True
        return "呀哈！已為您開啟【圖片自動解析模式】📸！\n接下來只需直接傳送圖片（無需輸入任何額外文字），烏薩奇就會自動為您看圖說故事與詳細解析照片細節喔！烏拉！✨🐰"

    return None


def get_recent_cached_images(chat_key: str):
    """Retrieve all permanently stored cached images (up to 10 photos) for chat_key."""
    if chat_key in user_image_cache:
        return list(user_image_cache[chat_key])
    return []


# Event handler for TextMessage
if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event: MessageEvent):
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", "default_user")
        source_type = getattr(event.source, "type", "user")
        chat_key = getattr(event.source, "group_id", None) or getattr(event.source, "room_id", None) or user_id
        logger.info(f"Received message from [{user_id}] (source: {source_type}, chat_key: {chat_key}): {user_text}")

        # Record message into rolling chat history buffer for group context memory
        group_chat_history[chat_key].append(f"【用戶{user_id[-4:]}】: {user_text}")

        # LINE Verify test event check (skip calling Gemini/reply for dummy tokens)
        DUMMY_REPLY_TOKENS = ["00000000000000000000000000000000", "ffffffffffffffffffffffffffffffff"]
        if event.reply_token in DUMMY_REPLY_TOKENS:
            logger.info("Received LINE Webhook Verify test event. Skipping Gemini call.")
            return

        # Check if bot is tagged/mentioned in group/room chat
        if not is_bot_tagged(event):
            logger.info(f"Recorded message in {source_type} context buffer without replying (untagged).")
            return

        # Handle hard reset command
        if is_reset_command(user_text):
            if chat_key in user_chats:
                del user_chats[chat_key]
            group_chat_history[chat_key].clear()
            if chat_key in user_translate_mode:
                del user_translate_mode[chat_key]
            if chat_key in user_auto_vision_mode:
                del user_auto_vision_mode[chat_key]
            if gemini_model:
                user_chats[chat_key] = gemini_model.start_chat(history=[])
            logger.info(f"HARD RESET: Successfully cleared chat session for [{chat_key}]")
            reply_text = "🧹【系統通知】對話記憶與群組歷史已徹底重置！烏薩奇已恢復為全新初始狀態囉。"
        # Check Image Translation Mode commands
        elif handle_translation_mode_commands(chat_key, user_text):
            reply_text = handle_translation_mode_commands(chat_key, user_text)
        # Check Auto Image Analysis Mode commands
        elif handle_auto_vision_mode_commands(chat_key, user_text):
            reply_text = handle_auto_vision_mode_commands(chat_key, user_text)
        # Check Gemini API setup
        elif not gemini_model:
            reply_text = "⚠️ 系統尚未設定有效的 GEMINI_API_KEY，請在 .env 中填寫金鑰。"
        else:
            def _process_ai_turn():
                # Get or create multi-turn chat session for this chat_key
                if chat_key not in user_chats:
                    user_chats[chat_key] = gemini_model.start_chat(history=[])
                
                chat_session = user_chats[chat_key]
                
                # Compute dynamic current local time in Taiwan (UTC+8)
                import datetime
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now = now_utc.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
                weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
                current_time_info = f"【系統當前真實精確時間 (台灣時間 UTC+8)】：{now.year} 年 {now.month} 月 {now.day} 日 (星期{weekday_map[now.weekday()]})"

                # Format group context if history exists
                context_header = ""
                if source_type != "user" and len(group_chat_history[chat_key]) > 1:
                    recent_context = "\n".join(group_chat_history[chat_key])
                    context_header = f"【群組近期對話歷史紀錄 (請參考成員們剛才討論的話題脈絡)】:\n{recent_context}\n\n"

                # Check pure tag without question
                if is_pure_tag(user_text):
                    prompt_to_send = (
                        f"{context_header}"
                        f"{current_time_info}\n\n"
                        f"【使用者動作】: 使用者單純 Tag/點名了你（沒有輸入其他發問文字）。\n"
                        f"【特別要求】：請在回答的第一句高喊「到~~~~~~」，緊接著配上烏薩奇經典的叫聲與口頭禪（烏拉！呀哈！普魯魯魯！等）！"
                    )
                    response = chat_session.send_message(prompt_to_send)
                    base_reply = response.text.strip() if response and response.text else "到~~~~~~！！ 呀哈！ 烏拉呀哈！ 普魯魯魯魯！"
                    return base_reply

                # Real-time search trigger check
                search_keywords = ["搜尋", "查", "天氣", "新聞", "最新", "今天", "日期", "時間", "幾號", "星期", "股價", "賽事", "2026", "幾度", "誰是", "哪裡", "多少"]
                is_search_cmd = any(user_text.lower().startswith(prefix) for prefix in ["/search", "搜尋", "幫我查", "查一下", "查"])
                should_search = is_search_cmd or any(kw in user_text for kw in search_keywords)

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
                    search_info, search_log = perform_web_search(clean_query if clean_query else user_text, timeout=2.2)

                    if search_info:
                        search_header = "🌐 [已載入即時網路搜尋資料]\n\n"
                        prompt_to_send = (
                            f"{context_header}"
                            f"{current_time_info}\n\n"
                            f"【即時網路搜尋與氣象資料】:\n{search_info}\n\n"
                            f"【使用者問題/Tag】:\n{user_text}\n\n"
                            f"請綜合參考群組對話歷史與搜尋資料，為群組回答正確且有對話脈絡的內容。"
                        )
                    else:
                        prompt_to_send = f"{context_header}{current_time_info}\n\n【使用者問題/Tag】:\n{user_text}"
                else:
                    prompt_to_send = f"{context_header}{current_time_info}\n\n【使用者問題/Tag】:\n{user_text}"

                cached_imgs = get_recent_cached_images(chat_key)
                if cached_imgs:
                    logger.info(f"Found {len(cached_imgs)} recent cached image(s) for chat_key [{chat_key}]. Combining image(s) with text question for Gemini Vision!")
                    prompt_to_send_with_img = f"【使用者隨圖片發問的問題】:\n{prompt_to_send}\n\n請務必看圖並結合使用者的文字發問，用烏薩奇的口吻做出精確回答。"
                    content_list = [prompt_to_send_with_img] + cached_imgs
                    response = gemini_model.generate_content(content_list)
                    if chat_key in user_image_cache:
                        user_image_cache[chat_key].clear()
                else:
                    response = chat_session.send_message(prompt_to_send)

                base_reply = response.text.strip() if response and response.text else "抱歉，Gemini 未能產生回應。"
                return search_header + base_reply

            # Execute AI processing turn with dynamic timeout (60.0s for Vision images, 15.0s for text)
            has_cached_img = bool(get_recent_cached_images(chat_key))
            turn_timeout = 60.0 if has_cached_img else 15.0
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_process_ai_turn)
                    reply_text = future.result(timeout=turn_timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Total processing for user [{user_id}] hit {turn_timeout}s timeout safety guard.")
                if has_cached_img:
                    reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
                else:
                    reply_text = "哈？這個問題處理時間過長，烏薩奇不知道！烏拉呀哈～！✨🐰"
            except Exception as e:
                logger.error(f"Gemini API error for user {user_id}: {e}")
                if chat_key in user_chats:
                    del user_chats[chat_key]
                if has_cached_img:
                    reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
                else:
                    reply_text = f"❌ 【系統錯誤 Log】\n- 類型: {type(e).__name__}\n- 詳情: {str(e)}\n\n(已為您重置該次對話 Session)"

        # Sanitize reply_text to strictly obey LINE Messaging API 5000 chars limit & UTF-8 control chars
        safe_reply_text = sanitize_line_text(reply_text)

        # Reply to LINE user with automatic push_message fallback
        try:
            with ApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                try:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=safe_reply_text)]
                        )
                    )
                    logger.info("Successfully sent reply message via reply_token.")
                except Exception as reply_err:
                    logger.warning(f"reply_message failed ({reply_err}), attempting fallback push_message to user [{user_id}]...")
                    if hasattr(reply_err, "body"):
                        logger.warning(f"LINE Reply API Error Body: {getattr(reply_err, 'body', '')}")

                    # Fallback to PushMessage using user_id if reply_token expired
                    if user_id and user_id != "default_user":
                        from linebot.v3.messaging import PushMessageRequest
                        line_bot_api.push_message(
                            PushMessageRequest(
                                to=user_id,
                                messages=[TextMessage(text=safe_reply_text)]
                            )
                        )
                        logger.info(f"Successfully delivered message to user [{user_id}] via fallback push_message!")
        except Exception as e:
            logger.error(f"Failed to send LINE reply or push: {e}")


# Event handler for ImageMessage (Gemini Vision Image Reading & Caching)
if handler:
    @handler.add(MessageEvent, message=ImageMessageContent)
    def handle_image_message(event: MessageEvent):
        user_id = getattr(event.source, "user_id", "default_user")
        source_type = getattr(event.source, "type", "user")
        chat_key = getattr(event.source, "group_id", None) or getattr(event.source, "room_id", None) or user_id
        logger.info(f"Received IMAGE message from [{user_id}] (source: {source_type}, chat_key: {chat_key}): {event.message.id}")

        DUMMY_REPLY_TOKENS = ["00000000000000000000000000000000", "ffffffffffffffffffffffffffffffff"]
        if event.reply_token in DUMMY_REPLY_TOKENS:
            return

        # Store image into user_image_cache permanently (rolling max 10 photos)
        try:
            import io
            import PIL.Image
            with ApiClient(line_config) as api_client:
                line_bot_blob_api = MessagingApiBlob(api_client)
                image_bytes = line_bot_blob_api.get_message_content(event.message.id)

            img = PIL.Image.open(io.BytesIO(image_bytes))
            user_image_cache[chat_key].append(img)
            logger.info(f"Cached image permanently for chat_key [{chat_key}] (total stored: {len(user_image_cache[chat_key])}).")
        except Exception as e:
            logger.error(f"Error fetching/caching image from LINE API: {e}")
            return

        # Check if Image Translation Mode is active and target language is specified
        trans_mode = user_translate_mode.get(chat_key)
        if trans_mode and trans_mode.get("enabled") and trans_mode.get("target_lang"):
            target_lang = trans_mode["target_lang"]
            logger.info(f"Image Translation Mode ACTIVE for [{chat_key}] (target_lang: {target_lang}). Executing auto-translation...")

            def _process_image_translation():
                try:
                    prompt = (
                        f"【任務：圖片翻譯模式】\n"
                        f"請詳細辨識這張圖片上的所有文字與內容，將其完整翻譯為【{target_lang}】！\n"
                        f"請以烏薩奇的口吻（適度搭配叫聲與烏拉！呀哈！），為使用者做出：\n"
                        f"1. 圖片內容簡覽\n"
                        f"2. 【原文內容】\n"
                        f"3. 【{target_lang}翻譯結果】"
                    )
                    response = gemini_model.generate_content([prompt, img])
                    return response.text.strip() if response and response.text else f"呀哈！烏薩奇辨識完圖片了，但沒有找到需要翻譯成【{target_lang}】的文字喔！"
                except Exception as e:
                    logger.error(f"Error processing image translation: {e}")
                    return "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_process_image_translation)
                    reply_text = future.result(timeout=60.0)
            except concurrent.futures.TimeoutError:
                reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
            except Exception as e:
                reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
        # 1-on-1 private chat OR Auto Image Analysis Mode: Auto-analyze images directly
        elif source_type == "user" or user_auto_vision_mode.get(chat_key):
            logger.info(f"Executing automatic vision analysis for [{chat_key}] (source: {source_type})...")

            def _process_auto_vision():
                try:
                    prompt = (
                        "【任務：圖片自動解析模式】\n"
                        "請詳細辨識並描述這張圖片的內容、畫面細節、人物/物件、文字或美食！\n"
                        "請以烏薩奇的口吻（適度搭配叫聲與烏拉！呀哈！），為使用者做出豐富有趣的圖片解析與評價！"
                    )
                    response = gemini_model.generate_content([prompt, img])
                    return response.text.strip() if response and response.text else "呀哈！本烏薩奇看到圖片了，這張圖片太神奇了！"
                except Exception as e:
                    logger.error(f"Error processing auto vision: {e}")
                    return "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_process_auto_vision)
                    reply_text = future.result(timeout=60.0)
            except concurrent.futures.TimeoutError:
                reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
            except Exception as e:
                reply_text = "哈？圖片太複雜了，烏薩奇不知道！烏拉呀哈～！✨🐰"
        else:
            # In Group/Room chats with Auto Vision OFF: Silently cache image without replying (0 spam in group!)
            # Group members can subsequent Tag @烏薩奇 with text questions about the image.
            logger.info(f"Silently cached group image for [{chat_key}] without replying.")
            return

        safe_reply_text = sanitize_line_text(reply_text)
        try:
            with ApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                try:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=safe_reply_text)]
                        )
                    )
                    logger.info("Successfully sent image reply via reply_token.")
                except Exception as reply_err:
                    if user_id and user_id != "default_user":
                        line_bot_api.push_message(
                            PushMessageRequest(
                                to=user_id,
                                messages=[TextMessage(text=safe_reply_text)]
                            )
                        )
                        logger.info(f"Successfully delivered image reply to user [{user_id}] via fallback push_message!")
        except Exception as e:
            logger.error(f"Failed to reply or push for image: {e}")
