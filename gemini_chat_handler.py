"""
Gemini Chat Handler Module for Lady卡卡.
Handles general interactive conversations and motivational Q&A with users.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

from access_db import Userdata
from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage

logger = logging.getLogger(__name__)


class GeminiChatHandler:
    def __init__(self, line_bot_api: Any, llm_gemini: Any = None):
        self.line_bot_api = line_bot_api
        self.llm_gemini = llm_gemini or ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
        )
        # Store conversational history isolated per user (max 10 recent messages)
        self.user_histories: Dict[str, List[str]] = defaultdict(list)

    def start_gemini_chat(self, user_states: Dict[str, Any], user_id: str, reply_token: str):
        """Enter AI conversational assistant mode."""
        user_states.setdefault(user_id, {})["in_gemini_chat"] = True
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="已為您開啟「Lady卡卡 AI客服小幫手」，您可以隨時向我提問任何運動與飲食問題喔！如欲結束請輸入「結束」或「掰掰」。"),
        )

    def stop_gemini_chat(self, user_states: Dict[str, Any], user_id: str, reply_token: str):
        """Exit AI conversational assistant mode."""
        user_states.setdefault(user_id, {})["in_gemini_chat"] = False
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="已退出小幫手對話，隨時點選選單回到主要功能喔！"),
        )

    def handle_gemini_chat(self, user_states: Dict[str, Any], user_id: str, user_message: str, reply_token: str) -> bool:
        """Process message if user is currently inside AI conversation mode."""
        if not user_states.get(user_id, {}).get("in_gemini_chat", False):
            return False

        # Check exit triggers
        if user_message in ["掰掰", "結束對話", "bye", "再見", "結束", "退出", "離開"]:
            self.stop_gemini_chat(user_states, user_id, reply_token)
            return True

        try:
            logger.info(f"Gemini chat processing for user {user_id}: {user_message}")
            response_text = self.invoke_gemini(user_id, user_message)
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text=response_text))
        except LineBotApiError as e:
            logger.error(f"LINE API error in Gemini chat: {e}")
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="處理您的請求時發生錯誤，請稍後再試。"))
        except Exception as ex:
            logger.error(f"Error in Gemini chat: {ex}")
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="小幫手目前有點忙碌，請稍後再試一次！"))

        return True

    def invoke_gemini(self, user_id: str, user_message: str) -> str:
        """Generate motivational AI response for the user."""
        user_data = Userdata(user_id)
        user_record = user_data.search_data("u_id", user_id)
        nickname = user_record.get("name", "夥伴") if user_record else "夥伴"

        # Maintain isolated chat history
        history = self.user_histories[user_id]
        history_context = "\n".join(history[-6:]) if history else "無"

        prompt = f"""
你是一位充滿熱情、正能量、溫暖體貼的專屬運動與體態管理顧問「Lady卡卡」。
使用者的名字是：{nickname}。

【對話歷史】：
{history_context}

【使用者本次提問】：
{user_message}

【回覆準則】：
1. 嚴格使用繁體中文，字數控制在 160 字以內。
2. 語氣溫暖愉快、鼓勵正面，適度使用 emoji。
3. 針對提問給予科學、健康且安全的運動或飲食指引。若使用者提到不切實際或極端的運動方式（如連續跑步300小時、不吃不喝），請委婉導正並提供安全方案。
4. 請不要使用 Markdown 符號（如 ** 或 * 或 #），直接使用優美流暢的文字。
"""
        try:
            human_message = HumanMessage(content=prompt)
            result = self.llm_gemini.invoke([human_message])
            content = result.content.strip() if hasattr(result, "content") else str(result).strip()
            content = content.replace("**", "").replace("*", "")

            # Record history
            self.user_histories[user_id].append(f"用戶: {user_message}")
            self.user_histories[user_id].append(f"卡卡: {content}")
            # Keep history within reasonable memory bounds
            if len(self.user_histories[user_id]) > 20:
                self.user_histories[user_id] = self.user_histories[user_id][-20:]

            return content
        except Exception as e:
            logger.error(f"Error invoking Gemini: {e}")
            return f"親愛的 {nickname}，運動和健康是最好的投資！保持規律節奏，每天進步一點點，卡卡為你加油！💪✨"