# Claroies (Lady卡卡 LINE 熱量與運動助理)

基於 LINE Messaging API 與 Flask 的健康熱量管理系統，支援飲食熱量記錄（文字與照片辨識）、運動消耗計算、個人化減重計畫、健康數據圖表與 Strava 整合。

---

## 專案架構

```text
├── app.py                     # 應用程式主入口 (Flask & LINE Webhook 處理)
├── config.py                  # 設定檔讀取模組 (支援環境變數與 config.ini)
├── access_db.py               # SQLite 資料庫操作模組 (使用者基本資料與每日紀錄)
├── food_analyzer.py           # 飲食分析 (文字解析與 Gemini 圖片熱量辨識)
├── sport_caculate.py          # 運動熱量計算 (MET 指標換算)
├── sport_consultant.py        # 運動建議生成 (BRTR 提示詞格式)
├── personalized_plan.py       # 個人化減重與 BMR/TDEE 計畫
├── health_dashboard.py        # Dash 健康數據儀表板
├── gemini_chat_handler.py     # Gemini 對話小幫手
├── Strava_ca.py               # Strava OAuth 與活動資料存取
├── flex_message_utils.py      # LINE Flex Message 訊息排版工具
├── monitoring.py              # 熱量超標檢查
├── update_weight.py           # 體重更新
├── config.example.ini         # INI 設定範本
├── .env.example               # 環境變數範本
├── requirements.txt           # 專案依賴套件
├── richmenufunc/              # Rich Menu 管理腳本
└── templates/                 # Web 前端模板
```

---

## 功能說明

- **飲食紀錄**：透過文字或照片輸入餐點內容，自動計算食物熱量並存入資料庫。
- **運動消耗**：輸入運動項目、時間與距離，根據 MET 公式換算消耗熱量。
- **減重計畫**：依據性別、身高、體重、年齡與活動量計算 BMR 與 TDEE，提供目標體重規劃。
- **數據圖表**：使用 Dash/Plotly 呈現熱量攝取、運動消耗與歷史淨熱量走勢。
- **Rich Menu 動態切換**：依照當日熱量累積狀況切換選單狀態。
- **Strava 連動**：支援 OAuth 授權綁定，取得最近的跑步、騎車等運動紀錄。

---

## 安裝與執行

### 1. 安裝相依套件

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 環境設定

複製設定檔範本並填入金鑰資訊：

```bash
cp .env.example .env
# 或
cp config.example.ini config.ini
```

需要設定的項目：
- LINE Channel Access Token & Secret
- Gemini API Key
- Public Website URL (ngrok 或雲端網址)
- Strava Client ID & Secret (選用)
- Azure OpenAI (選用)

### 3. 啟動服務

開發模式：
```bash
python app.py
```

正式環境部署（Gunicorn）：
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 注意事項

- 本專案已透過 `.gitignore` 排除 `config.ini`、個人 `.db` 檔與 GCP 憑證檔案，避免敏感資訊上傳。
- 上線前請確認 LINE Webhook URL 設定為 `https://<your-domain>/callback`。
