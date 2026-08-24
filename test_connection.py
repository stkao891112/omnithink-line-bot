import os
import sys
from dotenv import load_dotenv

# Ensure UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables from .env
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

print("=" * 60)
print("🔍 OmniThink LINE Bot 連線測試工具")
print("=" * 60)

has_error = False

# 1. 檢查 .env 設定
print("\n[1/3] 檢查 .env 環境變數設定...")
if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
    print("❌ GEMINI_API_KEY 未設定或仍為預設值。")
    has_error = True
else:
    print("✅ GEMINI_API_KEY 已設定。")

if not LINE_CHANNEL_SECRET or LINE_CHANNEL_SECRET == "your_line_channel_secret_here":
    print("❌ LINE_CHANNEL_SECRET 未設定或仍為預設值。")
    has_error = True
else:
    print("✅ LINE_CHANNEL_SECRET 已設定。")

if not LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_ACCESS_TOKEN == "your_line_channel_access_token_here":
    print("❌ LINE_CHANNEL_ACCESS_TOKEN 未設定或仍為預設值。")
    has_error = True
else:
    print("✅ LINE_CHANNEL_ACCESS_TOKEN 已設定。")


# 2. 測試 Gemini API 連線
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    print(f"\n[2/3] 正在測試 Gemini API 連線 (使用模型: {GEMINI_MODEL_NAME})...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content("請用繁體中文回覆一句短短的 Say Hello！")
        print(f"✅ Gemini API 測試成功！AI 回應內容：\n   👉 {response.text.strip()}")
    except Exception as e:
        print(f"❌ Gemini API 連線失敗：{e}")
        has_error = True
else:
    print("\n[2/3] 跳過 Gemini API 測試 (缺少 GEMINI_API_KEY)。")


# 3. 測試 LINE Messaging API 連線
if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_ACCESS_TOKEN != "your_line_channel_access_token_here":
    print("\n[3/3] 正在測試 LINE Messaging API Token 有效性...")
    try:
        from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
        config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        with ApiClient(config) as api_client:
            line_api = MessagingApi(api_client)
            bot_info = line_api.get_bot_info()
            print(f"✅ LINE API 驗證成功！")
            print(f"   👉 機器人名稱: {bot_info.display_name}")
            print(f"   👉 Basic ID: {bot_info.basic_id}")
    except Exception as e:
        print(f"❌ LINE Messaging API 驗證失敗 (請檢查 Access Token)：{e}")
        has_error = True
else:
    print("\n[3/3] 跳過 LINE API 測試 (缺少 LINE_CHANNEL_ACCESS_TOKEN)。")

print("\n" + "=" * 60)
if not has_error:
    print("🎉 所有連線測試均已通過！您可以啟動 main.py (uvicorn main:app --reload) 囉！")
else:
    print("⚠️ 測試中有發現問題，請先修正 .env 檔案中的金鑰再試一次。")
print("=" * 60)
