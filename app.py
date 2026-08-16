"""
Lady卡卡 Calories Management Line Bot Application
Senior-architected Flask & LINE Messaging API server.
Features:
- Food calorie intake logging (Text & Multimodal Photo Recognition)
- Exercise calorie expenditure tracking (MET-based)
- Personalized weight loss planning (BMR, TDEE, Mifflin-St Jeor)
- Interactive Health Dashboard (Plotly Dash)
- AI Coach Q&A with Gemini
- Strava OAuth2 activity sync
- Dynamic Rich Menu switching
"""

import io
import logging
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from access_db import Dailydata, Userdata
from config import settings
from flex_message_utils import generate_diet_flex_messages, generate_flex_messages
from food_analyzer import FoodCalorieAnalyzer
from gemini_chat_handler import GeminiChatHandler
from health_dashboard import HealthDashboard
from langchain_google_genai import ChatGoogleGenerativeAI
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    BubbleContainer,
    CarouselContainer,
    FlexSendMessage,
    ImageMessage,
    MessageAction,
    MessageEvent,
    QuickReply,
    QuickReplyButton,
    TextMessage,
    TextSendMessage,
    URIAction,
)
from monitoring import check_calories
from personalized_plan import generate_plan
from PIL import Image
from sport_caculate import CalorieAnalyzer
from sport_consultant import get_activity_advice
from Strava_ca import StravaAPI
from update_weight import WeightUpdater

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("LinecaApp")


class Lineca:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.secret_key = settings.FLASK_SECRET_KEY

        # Initialize LINE Bot API & Webhook Handler
        self.line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

        # Initialize Strava API Client
        redirect_uri = f"{settings.WEBSITE_URL}/strava_callback" if settings.WEBSITE_URL else "/strava_callback"
        self.strava_api = StravaAPI(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            redirect_uri=redirect_uri,
        )

        # Initialize Gemini LLM client
        self.llm_gemini = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
        )

        # Initialize AI Chat Assistant
        self.gemini_chat_handler = GeminiChatHandler(self.line_bot_api, self.llm_gemini)

        # Initialize Health Dashboard
        self.dashboard = HealthDashboard(self.app)

        # Rich Menu IDs
        self.rich_menu_ids = settings.RICH_MENU_IDS

        # User runtime states and timers
        self.user_states: Dict[str, Dict[str, Any]] = {}
        self.calorie_standards: Dict[str, Dict[str, Any]] = {}
        self.calorie_tracker: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.timers: Dict[str, threading.Timer] = {}

        # Register routes and event handlers
        self.setup_routes()

    # --------------------------------------------------------------------------
    # Route and Event Handler Setup
    # --------------------------------------------------------------------------
    def setup_routes(self):
        @self.app.route("/callback", methods=["POST"])
        def callback():
            signature = request.headers.get("X-Line-Signature", "")
            body = request.get_data(as_text=True)

            try:
                self.handler.handle(body, signature)
            except InvalidSignatureError:
                logger.error("Invalid LINE signature. Check channel secret and token.")
                abort(400)
            except Exception as e:
                logger.error(f"Error handling webhook: {e}")
            return "OK"

        @self.app.route("/favicon.ico")
        def favicon():
            static_dir = os.path.join(self.app.root_path, "static")
            return send_from_directory(static_dir, "favicon.ico", mimetype="image/vnd.microsoft.icon")

        @self.app.route("/dashboard/<user_id>")
        def display_dashboard(user_id):
            return self.dashboard.render_dashboard(user_id)

        @self.app.route("/strava_callback")
        def strava_callback():
            code = request.args.get("code")
            user_id = request.args.get("state")
            if code and user_id:
                try:
                    token_response = self.strava_api.get_strava_token(code)
                    if token_response and "access_token" in token_response:
                        self.strava_api.save_strava_tokens(user_id, token_response)
                        return "<h3>🎉 Strava 授權成功！您可以回到 LINE 輸入 'strava' 查看最新運動數據。</h3>"
                    return "<h3>❌ 授權失敗，請確認授權設定後重試。</h3>"
                except Exception as e:
                    logger.error(f"Strava callback error: {e}")
                    return "<h3>❌ 授權過程中發生錯誤，請稍後重試。</h3>"
            return "<h3>❌ 無效的授權請求。</h3>"

        # Web Form for User Profile (Optional web view)
        @self.app.route("/form/<user_id>", methods=["GET", "POST"])
        def user_form(user_id):
            user_db = Userdata(user_id)
            if request.method == "POST":
                data = request.get_json() or {}
                name = data.get("name", "")
                gender = data.get("gender", "male")
                age = data.get("age", 25)
                height = data.get("height", 165)
                weight = data.get("weight", 60)
                user_db.add_data(name=name, gender=(gender == "male"), age=age, height=height, weight=weight)
                return jsonify({"status": "success", "message": "個人資料更新成功！"})

            user_record = user_db.search_data("u_id", user_id) or {}
            return render_template("user_form.html", u_id=user_id, user_dict=user_record)

        # ----------------------------------------------------------------------
        # Text Message Webhook Event
        # ----------------------------------------------------------------------
        @self.handler.add(MessageEvent, message=TextMessage)
        def handle_message(event):
            user_id = event.source.user_id
            user_message = event.message.text.strip()
            reply_token = event.reply_token

            self.ensure_user_state(user_id)
            current_state = self.user_states[user_id].get("state")
            current_date = datetime.now().strftime("%Y-%m-%d")

            # Initialize daily calorie tracker for today if missing
            if user_id not in self.calorie_tracker:
                self.calorie_tracker[user_id] = {}
            if current_date not in self.calorie_tracker[user_id]:
                self.calorie_tracker[user_id][current_date] = {"food_calories": 0.0, "calories_burned": 0.0}

            # 1. Global Navigation Keywords (Can break out of any pending state)
            function_keywords = ["飲食打卡", "健康數據", "AI減肥攻略", "燃脂打卡", "我的狀態", "運動建議", "團隊介紹"]
            if user_message in function_keywords:
                self.user_states[user_id]["state"] = None  # Reset prior input state

                if user_message == "我的狀態":
                    return self.handle_my_status(user_id, reply_token)
                elif user_message == "團隊介紹":
                    return self.handle_team_intro(reply_token)
                elif user_message == "飲食打卡":
                    self.user_states[user_id]["state"] = "awaiting_food"
                    return self.line_bot_api.reply_message(
                        reply_token, TextSendMessage(text="請輸入您今天吃了什麼～（例如『我吃了一碗牛肉麵加一顆茶葉蛋』），或是直接拍食物照片丟給我也行！")
                    )
                elif user_message == "燃脂打卡":
                    self.user_states[user_id]["state"] = "awaiting_exercise"
                    return self.line_bot_api.reply_message(
                        reply_token, TextSendMessage(text="請輸入你做了什麼運動～（例如『跑步 30分鐘 5公里』或『騎腳踏車 1小時』）：")
                    )
                elif user_message == "AI減肥攻略":
                    return self.handle_ai_plan_entry(user_id, reply_token)
                elif user_message == "健康數據":
                    return self.handle_health_data(user_id, reply_token)
                elif user_message == "運動建議":
                    return self.handle_sport_advice_menu(user_id, reply_token)

            # 2. Check if user is currently inside AI Assistant Chat Mode
            if self.user_states[user_id].get("in_gemini_chat", False):
                handled = self.gemini_chat_handler.handle_gemini_chat(
                    self.user_states, user_id, user_message, reply_token
                )
                if handled:
                    return

            # 3. Check State-Based Ongoing Flows
            if current_state:
                # Profile Setup Flow
                if current_state == "awaiting_nickname":
                    return self.handle_nickname(user_id, user_message, reply_token)
                elif current_state == "awaiting_gender":
                    return self.handle_gender(user_id, user_message, reply_token)
                elif current_state == "awaiting_age":
                    return self.handle_age(user_id, user_message, reply_token)
                elif current_state == "awaiting_height":
                    return self.handle_height(user_id, user_message, reply_token)
                elif current_state == "awaiting_weight":
                    return self.handle_weight(user_id, user_message, reply_token)
                # Weight Update Flow
                elif current_state == "awaiting_weight_update":
                    return self.handle_weight_update(user_id, user_message, reply_token)
                # Goal Target Weight Flow
                elif current_state == "awaiting_target_weight":
                    return self.handle_target_weight(user_id, user_message, reply_token)
                # Food Logging Text Flow
                elif current_state == "awaiting_food":
                    return self.handle_food_input(user_id, user_message, current_date, reply_token)
                # Exercise Logging Text Flow
                elif current_state == "awaiting_exercise":
                    return self.handle_exercise_input(user_id, user_message, current_date, reply_token)
                # Activity Duration Flows
                elif current_state == "awaiting_running_duration":
                    return self.handle_activity_suggestion(user_id, reply_token, "跑步", user_message)
                elif current_state == "awaiting_swimming_duration":
                    return self.handle_activity_suggestion(user_id, reply_token, "游泳", user_message)
                elif current_state == "awaiting_cycling_duration":
                    return self.handle_activity_suggestion(user_id, reply_token, "騎腳踏車", user_message)

            # 4. Secondary Keyword Triggers
            if user_message == "我的基本資料":
                return self.ask_for_nickname(user_id, reply_token)

            elif user_message == "查看今日目標剩餘卡路里":
                return self.handle_view_remaining_calories(user_id, current_date, reply_token)

            elif any(kw in user_message for kw in ["瘦了", "胖了", "更新體重", "變重", "變輕"]):
                self.user_states[user_id]["state"] = "awaiting_weight_update"
                return self.line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="請告訴我您的最新體重是多少公斤（例如：65 或 65.5）？")
                )

            elif user_message == "authorize_strava":
                auth_url = self.strava_api.get_auth_url(user_id)
                return self.line_bot_api.reply_message(
                    reply_token, TextSendMessage(text=f"請點擊以下連結進行 Strava 運動數據授權：\n{auth_url}")
                )

            elif user_message == "strava":
                reply = self.strava_api.get_strava_reply(user_id)
                return self.line_bot_api.reply_message(reply_token, TextSendMessage(text=reply))

            elif user_message in ["我想要去跑步", "跑步"]:
                self.user_states[user_id]["state"] = "awaiting_running_duration"
                return self.line_bot_api.reply_message(reply_token, TextSendMessage(text="今天打算跑多久呀？（例如：30分鐘 或 1小時）"))

            elif user_message in ["我想要去游泳", "游泳"]:
                self.user_states[user_id]["state"] = "awaiting_swimming_duration"
                return self.line_bot_api.reply_message(reply_token, TextSendMessage(text="今天打算游多久呀？（例如：45分鐘 或 1小時）"))

            elif user_message in ["我想要去騎腳踏車", "騎腳踏車", "騎車"]:
                self.user_states[user_id]["state"] = "awaiting_cycling_duration"
                return self.line_bot_api.reply_message(reply_token, TextSendMessage(text="今天打算騎多久呀？（例如：1小時 或 2小時）"))

            elif user_message == "我不知道該做什麼運動":
                self.gemini_chat_handler.start_gemini_chat(self.user_states, user_id, reply_token)
                return

            elif user_message == "我完成任務":
                return self.handle_task_finished(user_id, reply_token)

            # Default Fallback: start AI helper conversation
            logger.info(f"Unrecognized input from {user_id}: {user_message}, invoking Gemini assistant.")
            response_text = self.gemini_chat_handler.invoke_gemini(user_id, user_message)
            return self.line_bot_api.reply_message(reply_token, TextSendMessage(text=response_text))

        # ----------------------------------------------------------------------
        # Image Message Webhook Event (Food Recognition)
        # ----------------------------------------------------------------------
        @self.handler.add(MessageEvent, message=ImageMessage)
        def handle_image_message(event):
            user_id = event.source.user_id
            current_date = datetime.now().strftime("%Y-%m-%d")
            reply_token = event.reply_token
            message_id = event.message.id

            self.ensure_user_state(user_id)

            content_url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
            headers = {"Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}"}

            try:
                img_response = requests.get(content_url, headers=headers, timeout=15)
                if img_response.status_code == 200:
                    img = Image.open(io.BytesIO(img_response.content))

                    # Save to static directory
                    static_dir = os.path.join(self.app.root_path, "static")
                    os.makedirs(static_dir, exist_ok=True)
                    image_filename = f"image_{message_id}.jpg"
                    image_path = os.path.join(static_dir, image_filename)
                    img.save(image_path, format="JPEG")

                    # Construct public URL
                    base_url = settings.WEBSITE_URL.rstrip("/")
                    image_url = f"{base_url}/static/{image_filename}" if base_url else url_for("static", filename=image_filename, _external=True)

                    # Food recognition
                    food_analyzer = FoodCalorieAnalyzer(user_id)
                    result_message = food_analyzer.store_analyze_calories_from_image([image_url])

                    # Process extracted calories
                    if "總共含有" in result_message:
                        cal_match = re.search(r"總共含有 (\d+) 大卡", result_message)
                        total_food_cal = int(cal_match.group(1)) if cal_match else 0

                        if user_id not in self.calorie_tracker:
                            self.calorie_tracker[user_id] = {}
                        if current_date not in self.calorie_tracker[user_id]:
                            self.calorie_tracker[user_id][current_date] = {"food_calories": 0.0, "calories_burned": 0.0}

                        self.calorie_tracker[user_id][current_date]["food_calories"] += total_food_cal

                        daily_limit = self.calorie_standards.get(user_id, {}).get("recommended_daily_calories", 2000.0)
                        food_cal = self.calorie_tracker[user_id][current_date]["food_calories"]
                        burned_cal = self.calorie_tracker[user_id][current_date]["calories_burned"]
                        remaining_cal = daily_limit - (food_cal - burned_cal)

                        reply_text = f"{result_message}\n\n📊 今日剩餘建議攝取額度：{remaining_cal:.0f} 大卡"
                        self.line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))
                        self.check_calorie_limit(user_id, current_date)
                    else:
                        self.line_bot_api.reply_message(reply_token, TextSendMessage(text=result_message))

                    self.user_states[user_id]["state"] = None
                else:
                    logger.error(f"Failed to fetch image from LINE: {img_response.status_code}")
                    self.line_bot_api.reply_message(reply_token, TextSendMessage(text="無法獲取圖片，請稍後再試。"))
            except Exception as e:
                logger.error(f"Error handling image message: {e}")
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="辨識圖片時發生錯誤，請稍後重試。"))

    # --------------------------------------------------------------------------
    # Business Logic Handlers
    # --------------------------------------------------------------------------
    def handle_my_status(self, user_id: str, reply_token: str):
        """Render status quick reply options."""
        base_url = settings.WEBSITE_URL.rstrip("/")
        quick_reply = QuickReply(
            items=[
                QuickReplyButton(
                    action=MessageAction(label="我的基本資料", text="我的基本資料"),
                    image_url=f"{base_url}/static/icons/data.jpeg",
                ),
                QuickReplyButton(
                    action=MessageAction(label="查看今日剩餘卡路里", text="查看今日目標剩餘卡路里"),
                    image_url=f"{base_url}/static/icons/fire.jpeg",
                ),
            ]
        )
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請選擇您想查看的項目：", quick_reply=quick_reply))

    def handle_team_intro(self, reply_token: str):
        """Render team member carousel."""
        base_url = settings.WEBSITE_URL.rstrip("/")
        team_members = [
            {"name": "小賴", "role": "組長 / 前端 / 系統整合", "image": f"{base_url}/static/images/member1.jpg"},
            {"name": "威廉", "role": "功能開發 / 演算法", "image": f"{base_url}/static/images/member2.jpg"},
            {"name": "JOJO", "role": "功能開發 / 數據處理", "image": f"{base_url}/static/images/member3.jpg"},
            {"name": "Vicky", "role": "功能開發 / UI設計", "image": f"{base_url}/static/images/member4.jpg"},
            {"name": "Steven", "role": "資料庫開發 / 架構", "image": f"{base_url}/static/images/member5.jpg"},
            {"name": "James", "role": "資料庫開發 / 測試", "image": f"{base_url}/static/images/member6.jpg"},
            {"name": "肥羊", "role": "功能開發 / 部署", "image": f"{base_url}/static/images/member7.jpg"},
        ]
        bubbles = [self.create_member_bubble(m["name"], m["role"], m["image"]) for m in team_members]
        flex_message = FlexSendMessage(alt_text="Lady卡卡 開發團隊介紹", contents=CarouselContainer(contents=bubbles))
        self.line_bot_api.reply_message(reply_token, flex_message)

    def handle_view_remaining_calories(self, user_id: str, current_date: str, reply_token: str):
        """Compute and display remaining daily calorie allowance."""
        base_url = settings.WEBSITE_URL.rstrip("/")
        tracker = self.calorie_tracker.get(user_id, {}).get(current_date, {"food_calories": 0.0, "calories_burned": 0.0})
        consumed = tracker.get("food_calories", 0.0)
        burned = tracker.get("calories_burned", 0.0)
        net = consumed - burned
        daily_limit = self.calorie_standards.get(user_id, {}).get("recommended_daily_calories", 2000.0)
        remaining = daily_limit - net

        quick_reply = QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label="飲食打卡", text="飲食打卡"), image_url=f"{base_url}/static/icons/food.jpeg"),
                QuickReplyButton(action=MessageAction(label="燃脂打卡", text="燃脂打卡"), image_url=f"{base_url}/static/icons/exercise.jpg"),
                QuickReplyButton(action=MessageAction(label="健康數據儀表板", text="健康數據"), image_url=f"{base_url}/static/icons/dashboard.png"),
            ]
        )
        msg = f"🍽 今日已攝取：{consumed:.0f} 大卡\n🏃 今日已燃燒：{burned:.0f} 大卡\n⚖️ 淨攝取熱量：{net:.0f} 大卡\n🎯 剩餘可攝取額度：{remaining:.0f} 大卡"
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text=msg, quick_reply=quick_reply))

    def handle_ai_plan_entry(self, user_id: str, reply_token: str):
        """Entrypoint for AI Personalized Plan generation."""
        user_data = Userdata(user_id).search_data("u_id", user_id)
        if not user_data or not user_data.get("weight"):
            self.line_bot_api.reply_message(
                reply_token, TextSendMessage(text="請先設定一下基本資料（我的狀態 ➔ 我的基本資料），這樣才能幫你算專屬的減肥計畫喔！")
            )
            return

        self.user_states[user_id]["state"] = "awaiting_target_weight"
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入你想瘦到的目標體重（公斤，例如：55 或 58.5）："))

    def handle_target_weight(self, user_id: str, user_message: str, reply_token: str):
        """Process target weight input and generate personalized plan."""
        cleaned = user_message.replace("公斤", "").replace("kg", "").strip()
        try:
            target_weight = float(cleaned)
            if target_weight < 20 or target_weight > 300:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入合理的目標體重數值（20 ~ 300 公斤）。"))
                return

            planner = generate_plan(self.llm_gemini, user_id, target_weight)
            diet_plan, standards = planner.generate_plan()

            if not diet_plan or not standards:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="無法生成減肥建議，請確認基本資料後重試。"))
                return

            flex_messages = generate_diet_flex_messages(diet_plan)
            if flex_messages:
                self.line_bot_api.reply_message(reply_token, flex_messages)
            else:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text=diet_plan))

            self.calorie_standards[user_id] = {
                "recommended_daily_calories": standards.get("recommended_daily_calories", 2000.0)
            }
            self.user_states[user_id]["state"] = None
        except ValueError:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入有效的數字格式，例如 55 或 58.5。"))

    def handle_food_input(self, user_id: str, user_message: str, current_date: str, reply_token: str):
        """Process food intake text input."""
        analyzer = FoodCalorieAnalyzer(user_id)
        result_message = analyzer.store_analyze_calories_from_text(user_message)

        if "總共含有" in result_message:
            cal_match = re.search(r"總共含有 (\d+) 大卡", result_message)
            total_food_cal = int(cal_match.group(1)) if cal_match else 0
            self.calorie_tracker[user_id][current_date]["food_calories"] += total_food_cal

            daily_limit = self.calorie_standards.get(user_id, {}).get("recommended_daily_calories", 2000.0)
            food_cal = self.calorie_tracker[user_id][current_date]["food_calories"]
            burned_cal = self.calorie_tracker[user_id][current_date]["calories_burned"]
            remaining_cal = daily_limit - (food_cal - burned_cal)

            self.line_bot_api.reply_message(
                reply_token, TextSendMessage(text=f"{result_message}\n\n📊 今日剩餘建議攝取額度：{remaining_cal:.0f} 大卡")
            )
            self.check_calorie_limit(user_id, current_date)
            self.user_states[user_id]["state"] = None
        else:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text=result_message))

    def handle_exercise_input(self, user_id: str, user_message: str, current_date: str, reply_token: str):
        """Process exercise calorie burn text input."""
        analyzer = CalorieAnalyzer(user_id)
        result_message = analyzer.handle_user_input(user_message)

        if "請提供我完整的運動名稱" in result_message:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text=result_message))
            return

        cal_match = re.search(r"消耗卡路里：(\d+) 大卡", result_message)
        exercise_cal = float(cal_match.group(1)) if cal_match else 0.0
        self.calorie_tracker[user_id][current_date]["calories_burned"] += exercise_cal

        daily_limit = self.calorie_standards.get(user_id, {}).get("recommended_daily_calories", 2000.0)
        food_cal = self.calorie_tracker[user_id][current_date]["food_calories"]
        burned_cal = self.calorie_tracker[user_id][current_date]["calories_burned"]
        remaining_cal = daily_limit - (food_cal - burned_cal)

        self.line_bot_api.reply_message(
            reply_token, TextSendMessage(text=f"{result_message}\n\n📊 今日剩餘可攝取額度：{remaining_cal:.0f} 大卡")
        )
        self.check_calorie_limit(user_id, current_date)
        self.user_states[user_id]["state"] = None

    def handle_sport_advice_menu(self, user_id: str, reply_token: str):
        """Show sport advice options."""
        base_url = settings.WEBSITE_URL.rstrip("/")
        quick_reply = QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label="跑步", text="我想要去跑步"), image_url=f"{base_url}/static/icons/running.png"),
                QuickReplyButton(action=MessageAction(label="游泳", text="我想要去游泳"), image_url=f"{base_url}/static/icons/swimming.png"),
                QuickReplyButton(action=MessageAction(label="騎自行車", text="我想要去騎腳踏車"), image_url=f"{base_url}/static/icons/bicycle.png"),
                QuickReplyButton(action=MessageAction(label="智能運動顧問", text="我不知道該做什麼運動"), image_url=f"{base_url}/static/icons/sport_advisor.png"),
            ]
        )
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請選擇您想要諮詢的運動項目：", quick_reply=quick_reply))

    def handle_activity_suggestion(self, user_id: str, reply_token: str, activity_type: str, user_message: str):
        """Generate full BRTR sport advice and carousel."""
        user_record = Userdata(user_id).search_data("u_id", user_id)
        is_valid, advice = get_activity_advice(user_id, user_record, f"{activity_type} {user_message}")

        if not is_valid:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text=advice))
        else:
            flex_messages = generate_flex_messages(advice, activity_type)
            if flex_messages:
                self.line_bot_api.reply_message(reply_token, flex_messages[:5])
            else:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text=advice))
            self.user_states[user_id]["state"] = None

    def handle_health_data(self, user_id: str, reply_token: str):
        """Send dashboard URL button."""
        base_url = settings.WEBSITE_URL.rstrip("/")
        dashboard_url = f"{base_url}/dashboard/{user_id}" if base_url else url_for("display_dashboard", user_id=user_id, _external=True)

        quick_reply = QuickReply(
            items=[
                QuickReplyButton(action=URIAction(label="開啟健康數據儀表板", uri=dashboard_url), image_url=f"{base_url}/static/icons/dashboard.png"),
                QuickReplyButton(action=MessageAction(label="返回選單", text="我的狀態"), image_url=f"{base_url}/static/icons/finish.png"),
            ]
        )
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="📊 點擊下方按鈕即可查看您的專屬健康儀表板：", quick_reply=quick_reply))

    def handle_weight_update(self, user_id: str, user_message: str, reply_token: str):
        """Update user weight."""
        cleaned = user_message.replace("公斤", "").replace("kg", "").strip()
        updater = WeightUpdater(user_id)
        msg = updater.update_weight(cleaned)
        self.user_states[user_id]["state"] = None
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text=msg))

    # --------------------------------------------------------------------------
    # Profile Input State Machine
    # --------------------------------------------------------------------------
    def ask_for_nickname(self, user_id: str, reply_token: str):
        self.user_states[user_id]["state"] = "awaiting_nickname"
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請告訴我你的暱稱或名字："))

    def handle_nickname(self, user_id: str, user_message: str, reply_token: str):
        base_url = settings.WEBSITE_URL.rstrip("/")
        user_data = Userdata(user_id)
        if not user_data.search_data("u_id", user_id):
            user_data.add_data(name=user_message)
        else:
            user_data.update_data("name", user_message)

        self.user_states[user_id]["state"] = "awaiting_gender"
        quick_reply = QuickReply(
            items=[
                QuickReplyButton(action=MessageAction(label="男", text="男"), image_url=f"{base_url}/static/icons/men.png"),
                QuickReplyButton(action=MessageAction(label="女", text="女"), image_url=f"{base_url}/static/icons/women.png"),
            ]
        )
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請選擇你的性別：", quick_reply=quick_reply))

    def handle_gender(self, user_id: str, user_message: str, reply_token: str):
        user_data = Userdata(user_id)
        is_male = user_message in ["男", "male", "Male", "1"]
        user_data.update_data("gender", 1 if is_male else 0)

        self.user_states[user_id]["state"] = "awaiting_age"
        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入你的年齡（例如：25）："))

    def handle_age(self, user_id: str, user_message: str, reply_token: str):
        try:
            age = int(user_message.strip())
            if age < 1 or age > 120:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入合理的年齡數字（1 ~ 120 歲）。"))
                return
            Userdata(user_id).update_data("age", age)
            self.user_states[user_id]["state"] = "awaiting_height"
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入你的身高（公分 cm，例如：175）："))
        except ValueError:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入有效的年齡數字喔。"))

    def handle_height(self, user_id: str, user_message: str, reply_token: str):
        try:
            height = float(user_message.strip())
            if height < 50 or height > 280:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入合理的身高數值（50 ~ 280 cm）。"))
                return
            Userdata(user_id).update_data("height", height)
            self.user_states[user_id]["state"] = "awaiting_weight"
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入你的體重（公斤 kg，例如：65.5）："))
        except ValueError:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入有效的身高數字喔。"))

    def handle_weight(self, user_id: str, user_message: str, reply_token: str):
        try:
            weight = float(user_message.strip())
            if weight < 20 or weight > 300:
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入合理的體重數值（20 ~ 300 kg）。"))
                return
            Userdata(user_id).update_data("weight", weight)
            self.user_states[user_id]["state"] = None
            self.line_bot_api.reply_message(
                reply_token, TextSendMessage(text="資料設定好囉！現在可以開始記錄飲食、運動，讓卡卡陪你一起控制熱量啦～")
            )
        except ValueError:
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="請輸入有效的體重數字喔。"))

    # --------------------------------------------------------------------------
    # Calorie Budget & Rich Menu Dynamics
    # --------------------------------------------------------------------------
    def check_calorie_limit(self, user_id: str, current_date: str):
        """Check calorie limit and switch Rich Menu if exceeded."""
        daily_limit = self.calorie_standards.get(user_id, {}).get("recommended_daily_calories", 2000.0)
        food_calories = self.calorie_tracker.get(user_id, {}).get(current_date, {}).get("food_calories", 0.0)
        burned_calories = self.calorie_tracker.get(user_id, {}).get(current_date, {}).get("calories_burned", 0.0)
        net_calories = food_calories - burned_calories
        remaining = daily_limit - net_calories

        if net_calories > daily_limit:
            logger.info(f"User {user_id} exceeded daily limit: {net_calories} > {daily_limit}")
            exceeded_amt = abs(remaining)
            burn_plan = self.burn_calories_plan(exceeded_amt, user_id)
            base_url = settings.WEBSITE_URL.rstrip("/")

            calories_text = (
                f"⚠️ 今天熱量好像吃得有點多喔！超標了差不多 {exceeded_amt:.0f} 大卡～\n\n"
                "快來看看卡卡幫你挑的燃脂運動，動一動把血條補回來吧！💪\n\n"
                f"{burn_plan}"
            )
            quick_reply = QuickReply(
                items=[
                    QuickReplyButton(action=MessageAction(label="我完成任務", text="我完成任務"), image_url=f"{base_url}/static/icons/finish.png"),
                    QuickReplyButton(action=MessageAction(label="我有空再做", text="我有空再做"), image_url=f"{base_url}/static/icons/couch.jpeg"),
                ]
            )
            try:
                self.line_bot_api.push_message(user_id, TextSendMessage(text=calories_text, quick_reply=quick_reply))
                self.switch_rich_menu(user_id)
            except Exception as e:
                logger.error(f"Failed to push calorie warning message: {e}")

    def switch_rich_menu(self, user_id: str):
        """Sequentially switch Rich Menu to show energy level bar progression."""
        current_index = self.user_states[user_id].get("current_rich_menu_index", 0)
        if current_index < len(self.rich_menu_ids) - 1:
            current_index += 1
            self.user_states[user_id]["current_rich_menu_index"] = current_index
            rich_menu_id = self.rich_menu_ids[current_index]

            try:
                self.line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
                logger.info(f"Switched Rich Menu for user {user_id} to index {current_index} ({rich_menu_id})")
            except Exception as e:
                logger.error(f"Error linking rich menu: {e}")

            # Schedule timer for next stage switch (e.g. 5 minutes or demo 30s)
            timer = threading.Timer(300, self.switch_rich_menu, [user_id])
            self.timers[user_id] = timer
            timer.start()
        else:
            if user_id in self.timers:
                self.timers[user_id].cancel()
                del self.timers[user_id]

    def handle_task_finished(self, user_id: str, reply_token: str):
        """Reset Rich Menu back to default index 0 when exercise task completed."""
        self.user_states[user_id]["current_rich_menu_index"] = 0
        if user_id in self.timers:
            self.timers[user_id].cancel()
            del self.timers[user_id]

        if self.rich_menu_ids:
            try:
                self.line_bot_api.link_rich_menu_to_user(user_id, self.rich_menu_ids[0])
            except Exception as e:
                logger.error(f"Error resetting rich menu: {e}")

        self.line_bot_api.reply_message(reply_token, TextSendMessage(text="太棒啦！任務完成，血條已經幫你補滿囉～繼續保持！"))

    def burn_calories_plan(self, remaining_calories: float, user_id: str) -> str:
        """Calculate burn time for common activities."""
        activities = {"快走": 4.8, "慢跑": 7.0, "游泳": 8.0, "跳繩": 11.0, "騎自行車": 7.5}
        user_record = Userdata(user_id).search_data("u_id", user_id)
        weight = float(user_record.get("weight", 60.0)) if user_record else 60.0

        plan_lines = []
        for activity, met in activities.items():
            hours = remaining_calories / (met * weight)
            mins = max(1, int(round(hours * 60)))
            plan_lines.append(f"• {activity}：約 {mins} 分鐘")

        return "\n".join(plan_lines)

    def create_member_bubble(self, name: str, role: str, image_url: str) -> BubbleContainer:
        """Create team card bubble."""
        return BubbleContainer(
            size="kilo",
            hero=ImageComponent(url=image_url, size="full", aspect_ratio="1:1", aspect_mode="cover"),
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(text=name, weight="bold", size="lg", align="center"),
                    TextComponent(text=role, size="sm", align="center", color="#64748B", wrap=True),
                ],
                spacing="sm",
                padding_all="md",
            ),
        )

    def ensure_user_state(self, user_id: str):
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "state": None,
                "in_gemini_chat": False,
                "current_rich_menu_index": 0,
            }

    def start(self):
        """Start Flask HTTP server."""
        logger.info(f"Starting Lady卡卡 Server on {settings.FLASK_HOST}:{settings.FLASK_PORT}")
        self.app.run(host=settings.FLASK_HOST, port=settings.FLASK_PORT, debug=False)


# WSGI application instance
bot_service = Lineca()
app = bot_service.app

if __name__ == "__main__":
    bot_service.start()