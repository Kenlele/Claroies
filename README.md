# Claroies (Lady卡卡 LINE 熱量與運動小助理)

這是一個用 Python (Flask) 加上 LINE Bot 做的熱量與運動記錄小工具。  
主要功能包括：輸入文字或直接拍食物照片自動算卡路里、記錄運動消耗熱量、根據個人身體數值算 BMR/TDEE 減重計畫、用 Dash 畫圖表看熱量走勢，還有串接 Strava 抓運動紀錄。

---

## 檔案結構

```text
├── app.py                     # 主程式（處理 Flask 路由跟 LINE Webhook）
├── config.py                  # 讀取設定（支援 .env 環境變數或 config.ini）
├── access_db.py               # SQLite 資料庫讀寫（存個人資料跟每天的飲食運動紀錄）
├── food_analyzer.py           # 算食物熱量（文字解析 + Gemini 圖片辨識）
├── sport_caculate.py          # 算運動消耗（用 MET 公式換算）
├── sport_consultant.py        # 運動建議生成（BRTR 格式）
├── personalized_plan.py       # 個人化減肥計畫（算 BMR、TDEE 跟目標熱量赤字）
├── health_dashboard.py        # Dash 網頁圖表（看卡路里收支走勢）
├── gemini_chat_handler.py     # Gemini 聊天小幫手
├── Strava_ca.py               # 串接 Strava 抓運動資料
├── flex_message_utils.py      # 產生 LINE Flex 卡片與輪播訊息
├── monitoring.py              # 檢查今天卡路里有沒有超標
├── update_weight.py           # 更新體重資料
├── config.example.ini         # INI 設定檔範本
├── .env.example               # 環境變數範本
├── requirements.txt           # 套件清單
├── richmenufunc/              # Rich Menu 選單上傳與設定腳本
└── templates/                 # 網頁表單模板
```

---

## 主要在做什麼？

1. **飲食打卡**：打字說吃了什麼，或直接拍食物照片丟給機器人，會自動估算熱量並存起來。
2. **燃脂打卡**：輸入做了什麼運動、多久、跑了幾公里，會自動用 MET 公式算出消耗多少大卡。
3. **減肥攻略**：填好身高體重年齡後，輸入想瘦到幾公斤，會自動幫你算 BMR / TDEE 跟建議每天吃多少。
4. **健康圖表**：點進儀表板網頁可以看到今天的熱量圓餅圖，以及最近幾天的熱量收支與淨赤字折線圖。
5. **血條選單**：今天要是吃超標了，選單血條會掉，機器人會提醒你去運動，運動完輸入「我完成任務」血條就會回滿。
6. **Strava 整合**：綁定 Strava 帳號後可以直接查最近一次的運動里程跟配速。

---

## 怎麼跑起來？

### 1. 裝套件

建議開虛擬環境：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定金鑰

把範本複製一份出來填入你的 Key：
```bash
cp .env.example .env
# 或用 config.ini
cp config.example.ini config.ini
```

必填項目：
- LINE Channel Access Token & Secret
- Gemini API Key
- WEBSITE_URL（ngrok 或部署後的對外網址）

### 3. 本地啟動

```bash
python app.py
```

如果有用 ngrok，記得把 Webhook URL 設定到 LINE 後台：
`https://<你的ngrok網址>/callback`

---

## 小提醒

- 敏感金鑰（`config.ini`、`*.db`、Google 憑證等）都已經在 `.gitignore` 裡面了，不用擔心推上 GitHub 會外洩。
