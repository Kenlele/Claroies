# ✨ Lady卡卡 - AI 智能熱量管理與運動顧問 LINE Bot

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%20%7C%20Dash-green.svg)](https://flask.palletsprojects.com/)
[![LINE Messaging API](https://img.shields.io/badge/LINE-Messaging%20API-00C300.svg)](https://developers.line.biz/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%201.5%20Flash-orange.svg)](https://deepmind.google/technologies/gemini/)

> **Lady卡卡** 是一款結合 **多模態食物拍照辨識**、**運動熱量消耗追蹤**、**個人化 AI 減重計畫 (BMR/TDEE)**、**互動式健康數據儀表板 (Plotly Dash)** 與 **動態血條 Rich Menu** 的全方位 LINE 官方帳號應用程式。

---

## 🌟 核心功能亮點

1. 📸 **多模態飲食打卡 (文字 / 照片辨識)**
   - 支援文字輸入（例如：「我吃了一碗牛肉麵和一顆茶葉蛋」）。
   - 支援直接拍攝/上傳食物照片，利用 Google Gemini 多模態視覺技術自動解析菜色、份量並精準估算卡路里。
2. 🏃 **燃脂打卡與 MET 運動熱量計算**
   - 支援多達 20+ 種運動項目（跑步、游泳、騎車、跳繩、重訓、瑜伽等）。
   - 基於使用者體重與 MET（代謝當量）公式精準換算消耗熱量。
3. 🎯 **個人化 AI 減重攻略**
   - 依據 Mifflin-St Jeor 公式精準計算 BMR 與 TDEE。
   - 根據目標體重設定安全熱量赤字，生成週期性減重建議與飲食規劃。
4. 📊 **互動式健康數據儀表板 (Plotly Dash)**
   - 嵌入式互動圖表：今日熱量收支圓餅圖、近 15~60 天熱量收支長條圖、每日淨熱量赤字折線走勢。
   - 提供動態播放/暫停歷史數據回顧功能。
5. 🩸 **動態血條 Rich Menu 機制**
   - 當單日熱量攝取超標時，系統主動推播運動燃脂任務，並自動逐級切換 LINE Rich Menu 血條。
   - 完成運動任務後輸入「我完成任務」即刻恢復滿血！
6. 💬 **24hr AI 運動與健康顧問 (Gemini 驅動)**
   - 提供隨時在線的熱情教練陪伴與科學健身問答，多用戶對話記憶獨立隔離。
7. 🚴 **Strava 運動手錶/App 數據整合**
   - 支援 OAuth2 授權同步 Strava 運動里程與時速數據。

---

## 🏗️ 系統架構目錄

```text
├── app.py                     # 主程式入口 (Flask & LINE Webhook 路由分發)
├── config.py                  # 集中式設定模組 (支援環境變數與 INI 多來源降級)
├── access_db.py               # 資料庫操作層 (安全參數化 SQL、防止注入、連線池管理)
├── food_analyzer.py           # 飲食分析器 (Gemini 影像辨識 + JSON 結構化提取)
├── sport_caculate.py          # 運動熱量計算 (MET 公式計算 + AI 激勵回饋)
├── sport_consultant.py        # 運動顧問 (BRTR 提示詞架構運動建議)
├── personalized_plan.py       # 個人化計畫生成 (BMR/TDEE 計算與減重計畫)
├── health_dashboard.py        # 健康儀表板 (Plotly Dash + Bootstrap 響應式佈局)
├── gemini_chat_handler.py     # Gemini AI 互動小幫手 (隔離式用戶對話歷史)
├── Strava_ca.py               # Strava OAuth2 API 整合
├── flex_message_utils.py      # LINE Flex Message / Carousel 輪播卡片生成工具
├── monitoring.py              # 熱量超標監控邏輯
├── update_weight.py           # 體重更新模組
├── config.example.ini         # INI 設定檔範本 (不含機密金鑰)
├── .env.example               # 環境變數設定檔範本
├── .gitignore                 # 嚴格資安防護忽略清單 (防範金鑰與 DB 外流)
├── requirements.txt           # 精簡純淨相依套件清單
├── richmenufunc/              # Rich Menu 建立、上傳與刪除腳本
└── templates/                 # Web 前端表單範本
```

---

## 🔒 資安防護與最佳實踐 (Security Best Practices)

- 🚫 **金鑰絕不上傳**：所有 API Key、Channel Secret、資料庫檔案 (`*.db`)、服務帳號 JSON 憑證皆被 `.gitignore` 嚴格阻擋。
- 🛡️ **SQL 注入防護**：全模組採用 SQLite 參數化查詢 (`?` bindings)，杜絕字串拼接所造成的安全性漏洞。
- 🧵 **執行緒安全 (Thread-Safe)**：資料庫存取全面採用 Context Manager，避免多用戶併發請求時發生連線衝突或資源洩漏。
- 📦 **12-Factor 原則**：優先自系統環境變數 (`os.environ`) 讀取設定，方便容器化部署至雲端 (Render, Railway, GCP Cloud Run, AWS, Docker)。

---

## 🚀 快速開始 (Getting Started)

### 1. 複製專案與建立虛擬環境

```bash
git clone https://github.com/Kenlele/Claroies.git
cd Claroies

# 建立 Python 虛擬環境
python3 -m venv venv
source venv/bin/activate  # MacOS/Linux
# venv\Scripts\activate   # Windows
```

### 2. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數或組態檔

您可以複製 `.env.example` 為 `.env`，或複製 `config.example.ini` 為 `config.ini`：

```bash
cp .env.example .env
# 編輯 .env 填入您的 LINE Bot Token、Secret 與 Gemini API Key
```

或者使用 `config.ini`：

```bash
cp config.example.ini config.ini
```

### 4. 啟動伺服器

```bash
# 開發模式直接執行
python app.py

# 或使用 Gunicorn 生產級伺服器啟動
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 5. LINE Webhook 設定

將 ngrok 或雲端部署的公開 URL 填入 LINE Developers Console 的 Webhook URL：
```text
https://your-domain.ngrok-free.app/callback
```

---

## 📄 License

MIT License. Developed with ❤️ by Lady卡卡 開發團隊.
