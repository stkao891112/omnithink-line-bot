import os
import sys
from dotenv import load_dotenv

# Ensure UTF-8 output encoding for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

print("=" * 60)
print("🤖 OmniThink LINE Bot - 本地 AI 對話模擬器")
print("=" * 60)
print("說明：輸入您的測試訊息，按 Enter 即可直接測試 Gemini 模型的回覆。")
print("輸入 'exit' 或 'quit' 即可結束測試。\n")

if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
    print("❌ 錯誤：GEMINI_API_KEY 未設定或仍為預設值，請先檢查 .env 檔案。")
    sys.exit(1)

import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL_NAME)

print(f"✅ 已成功加載 Gemini 模型 ({GEMINI_MODEL_NAME})！請開始輸入對話：\n")

while True:
    try:
        user_input = input("👤 您: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("👋 已結束本地對話測試。")
            break

        print("🤖 Gemini 思考中...", end="\r", flush=True)
        response = model.generate_content(user_input)
        
        reply_text = response.text.strip() if response and response.text else "（無回應）"
        print(f"🤖 AI 機器人回覆:\n{reply_text}\n")
        print("-" * 60)
    except KeyboardInterrupt:
        print("\n👋 已結束本地對話測試。")
        break
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}\n")
