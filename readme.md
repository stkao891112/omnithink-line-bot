# OmniThink AI 智囊團 (LINE 版) 🤖💬

> **把專屬 AI 軍師與智囊團裝進你的 LINE！**
> 
>基於 **FastAPI** + **LINE Messaging API (v3)** + **Google Gemini API** 打造的個人化 AI 決策與自動對話服務。支援多輪上下文對話記憶、自動重置記憶指令，以及完善的本地測試與連線驗證工具。

---

## 🌟 核心功能特色

- 🤖 **Gemini AI 自動對話**：採用 Google Gemini API (`gemini-1.5-flash`)，提供高品質、快速的中文 AI 自動回應。
- 🧠 **多輪對話記憶 (Context Memory)**：
  - 依使用者專屬 LINE `user_id` 建立獨立對話 Session。
  - AI 能夠自動記住上文對話脈絡（如名字、討論主題等）。
  - 支援發送 `重置`、`清空` 或 `/reset` 指令一鍵清除歷史對話記憶。
- ⚡ **高效能 Webhook 伺服器**：
  - 基於 **FastAPI** 框架，極速非同步處理能力。
  - 完整實作 `X-Line-Signature` HMAC 簽章安全驗證。
  - 優化 LINE Webhook Verify 測試機制，防止連線逾時。
- 🛠️ **完整開發測試工具組**：
  - `test_connection.py`：一鍵驗證 `.env` 金鑰、Gemini API 連線與 LINE Bot Token。
  - `simulate_chat.py`：免建 Webhook，直接在本地終端機與 Gemini AI 實時對話。

---

## 📂 專案資料夾結構

```text
omnithink-line-bot/
├── .env                # ⚠️ 環境變數機密檔 (已加入 .gitignore，絕對不要上傳 GitHub)
├── .env.example        # 環境變數設定範本檔
├── .gitignore          # Git 忽略檔案設定
├── requirements.txt    # Python 依賴套件清單
├── main.py             # FastAPI 主程式 (含 Webhook 處理與 Gemini 多輪對話)
├── test_connection.py  # API 連線與金鑰驗證腳本
├── simulate_chat.py    # 本地終端機 AI 對話模擬器
└── README.md           # 本說明文件
```

---

## 🚀 快速開始 (Quick Start)

### 1. 複製專案與安裝套件

```powershell
# 建立並啟動 Python 虛擬環境
python -m venv .venv
.venv\Scripts\activate

# 安裝所需 Python 套件
pip install -r requirements.txt
```

### 2. 設定環境變數 (.env)

複製 `.env.example` 並命名為 `.env`，填入您的金鑰資訊：

```ini
# LINE Messaging API 資訊
LINE_CHANNEL_SECRET=your_line_channel_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here

# Google Gemini API 資訊
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

### 3. 連線與功能測試

在啟動 Web伺服器前，可先執行連線測試腳本：

```powershell
python test_connection.py
```

若要在本地終端機測試 AI 對話：

```powershell
python simulate_chat.py
```

---

## 📡 啟動 Webhook 服務與 LINE 串接

### 1. 啟動 FastAPI 本地伺服器

```powershell
uvicorn main:app --reload
```
預設服務會在 `http://127.0.0.1:8000` 運行。

### 2. 開啟公網穿透 (Cloudflare Tunnel 或 SSH Tunnel)

LINE 伺服器需要 HTTPS 網址推播 Webhook 事件。可使用 Cloudflare Tunnel 或 Windows 內建 SSH 穿透：

```powershell
# 使用 Windows 內建 SSH 免安裝穿透
ssh -R 80:localhost:8000 nokey@localhost.run

# 或使用 Cloudflare Tunnel (需下載 cloudflared.exe)
.\cloudflared.exe tunnel --url http://localhost:8000
```

### 3. 設定 LINE Developers Console

1. 開啟 [LINE Developers Console](https://developers.line.biz/) 並進入您的 Messaging API Channel。
2. 切換至 **Messaging API** 頁籤：
   - 在 **Webhook URL** 填入：`https://您的公網網址/callback`
   - 點擊 **Save** 儲存並點擊 **Verify** 測試連線（顯示 **Success**）。
   - 開啟 **Use webhook** 開關（轉為綠色）。
3. 在 **Auto-reply messages** 點擊 Edit 將 LINE 預設的「自動回應訊息」改為**「停用 / Disabled」**。

---

## 🛡️ 安全注意事項 (Security)

- 絕對不可將包含真正金鑰的 `.env` 檔案 commit 上傳至 GitHub。
- 本專案已將 `.env` 與 `.venv` 加入 `.gitignore` 列表中。

---

## 📄 授權條款 (License)

MIT License
