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
            TextSendMessage(text="卡卡在！有什麼飲食或運動問題都可以直接問我喔～如果想結束對話輸入『掰掰』或『結束』就行啦！"),
        )

    def stop_gemini_chat(self, user_states: Dict[str, Any], user_id: str, reply_token: str):
        """Exit AI conversational assistant mode."""
        user_states.setdefault(user_id, {})["in_gemini_chat"] = False
        self.line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="好喔，已經退出小幫手對話囉！隨時點下方選單都可以回到主要功能～"),
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
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="目前系統有點忙碌，稍等一下再試試看喔！"))
        except Exception as ex:
            logger.error(f"Error in Gemini chat: {ex}")
            self.line_bot_api.reply_message(reply_token, TextSendMessage(text="目前連線有點忙碌，稍等一下再問我一次喔！"))

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
你是一位說話自然、口語、親切像好朋友一樣的運動與健康顧問「Lady卡卡」。
使用者的名字是：{nickname}。

【對話紀錄】：
{history_context}

【使用者剛才說】：
{user_message}

【回覆要求】：
1. 請用自然流暢、像朋友聊天的繁體中文口吻回答，不要有死板的客服腔或 AI 機器人感。
2. 字數控制在 150 字以內，不要用 Markdown 的「**」或「#」符號。
3. 如果對方問運動或飲食，給予實用又安全的小建議；如果對方講不合理的運動方式（例如連續跑步300小時），用幽默輕鬆的方式提醒他注意安全。
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
            return f"嘿 {nickname}！運動跟健康都是慢慢累積的，按照自己的節奏來就好，卡卡為你加油！💪"