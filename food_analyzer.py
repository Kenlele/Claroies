"""
Food Calorie Analyzer Module for Lady卡卡.
Analyzes food text descriptions and food photos using Gemini / Azure OpenAI
to extract food items, portions, and estimated calorie counts, then stores them in DB.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from access_db import Dailydata
from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


def extract_numbers(input_string: Any) -> int:
    """Extract integer number from string or value safely."""
    if isinstance(input_string, (int, float)):
        return int(input_string)
    numbers = re.findall(r"\d+", str(input_string))
    if numbers:
        return int(numbers[0])
    return 0


class FoodCalorieAnalyzer:
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.daily_data = Dailydata(self.user_id)

    def _get_gemini_client(self) -> ChatGoogleGenerativeAI:
        """Initialize Google Gemini client using unified settings."""
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.2,
        )

    def _analyze_food_from_image_url(self, image_urls: List[str]) -> str:
        """Analyze food in image URLs using Gemini Multimodal vision capabilities."""
        user_messages: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "請幫我分析這張圖片中的食物，並告訴我食物名稱與份量。"
                    "請提供具體的食物名稱和對應的份量，回覆格式例如：食物名稱為XXXXX，份量為XXX單位，"
                    "並一律使用繁體中文回答。"
                ),
            }
        ]
        for url in image_urls:
            user_messages.append({"type": "image_url", "image_url": url})

        try:
            human_messages = HumanMessage(content=user_messages)
            llm_gemini = self._get_gemini_client()
            response = llm_gemini.invoke([human_messages])
            result_str = self._ensure_str_message(response)
            logger.info(f"Image analysis result: {result_str}")
            return result_str
        except Exception as e:
            logger.error(f"Error analyzing food image: {e}")
            return "圖片有點不清楚～方便提供給我更清楚的圖片喔。"

    def _extract_food_info(self, user_input: str) -> Union[List[Dict[str, Any]], str]:
        """Extract food items, portions, and calories as structured JSON using LLM."""
        prompt = f"""
你是一位專業的營養師與卡路里分析專家。請分析使用者輸入的飲食內容，提取食物名稱、份量與卡路里估算，並嚴格以繁體中文與 JSON 陣列格式返回。

規則：
1. 僅返回合法 JSON 陣列，不要包含任何額外的 Markdown 標記（如 ```json）或非 JSON 字符。
2. 若使用者輸入不明確、不是食物或非飲食內容（例如詢問天氣、問候、運動），請返回空陣列 `[]`。
3. 每個項目需包含：food_name (食物名稱), food_quantity (份量), total_calories (總熱量數值，如 '350大卡'), serving_size_unit (單位), single_calories (單份熱量), food_detail (熱量簡要說明)。

JSON 範例格式：
[
    {{
        "food_name": "漢堡",
        "food_quantity": "2個",
        "total_calories": "700大卡",
        "serving_size_unit": "1個",
        "single_calories": "350大卡",
        "food_detail": "一個普通漢堡約350大卡，2個約700大卡。"
    }}
]

使用者飲食輸入內容：
"{user_input}"
"""
        # Try Gemini first
        try:
            llm = self._get_gemini_client()
            response = llm.invoke([HumanMessage(content=prompt)])
            content = self._ensure_str_message(response).strip()

            # Clean json fences if present
            if content.startswith("```"):
                content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                content = re.sub(r"\n?```$", "", content).strip()

            json_info = json.loads(content)
            if not json_info:
                return "無法辨識食物，請提供更清楚的食物名稱與份量描述。"
            return json_info
        except Exception as e:
            logger.warning(f"Gemini food extraction error: {e}, falling back to Azure OpenAI if available.")

        # Fallback to Azure OpenAI if configured
        if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_API_BASE:
            try:
                from openai import AzureOpenAI

                client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_API_BASE,
                )
                completion = client.chat.completions.create(
                    model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": "你是一位營養師，只返回合法的 JSON 陣列。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=800,
                )
                content = completion.choices[0].message.content.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                    content = re.sub(r"\n?```$", "", content).strip()
                json_info = json.loads(content)
                if not json_info:
                    return "無法辨識食物，請提供更清楚的食物名稱與份量描述。"
                return json_info
            except Exception as ex:
                logger.error(f"Azure OpenAI food extraction failed: {ex}")

        return "辨識食物時發生錯誤，請稍後再試。"

    def _store_food_calories(self, food_json: List[Dict[str, Any]]) -> str:
        """Store extracted food calorie records into DB and construct summary text."""
        if not food_json or not isinstance(food_json, list):
            return "我看不太出這是什麼食物，可以描述一下吃了什麼或份量嗎～"

        food_calories_list = []
        total_calories_sum = 0

        for item in food_json:
            food_name = item.get("food_name", "食物")
            food_quantity = item.get("food_quantity", "1份")
            # Support both total_calories and legacy typo tatal_calories
            raw_cal = item.get("total_calories") or item.get("tatal_calories") or "0"
            total_calories = extract_numbers(raw_cal)

            food_name_portion = f"{food_quantity}{food_name}"
            food_calories_list.append(f"{food_name_portion} 約 {total_calories} 大卡")
            total_calories_sum += total_calories

            try:
                self.daily_data.add_data(
                    food_name=food_name_portion,
                    food_calories=total_calories,
                    exercise_name="",
                    exercise_duration=0,
                    calories_burned=0,
                )
                logger.info(f"已記錄食物: {food_name_portion} - {total_calories} 大卡")
            except Exception as e:
                logger.error(f"存入資料庫失敗: {e}")

        food_details = "，".join(food_calories_list)
        return f"幫你算好囉～{food_details}，這餐總共大約含有 {total_calories_sum} 大卡，已經幫你記下來啦！"

    def store_analyze_calories_from_image(self, image_urls: List[str]) -> str:
        """End-to-end pipeline: image recognition -> info extraction -> database save."""
        description = self._analyze_food_from_image_url(image_urls)
        if description in ["請提供更清楚的食物描述或更清晰的圖片。", "圖片有點不清楚～方便提供給我更清楚的圖片喔。"]:
            return description

        if not description:
            return "照片好像看不出裡面有什麼食物，再拍一張清楚一點的給我試試！"

        json_result = self._extract_food_info(description)
        if isinstance(json_result, str):
            return json_result
        return self._store_food_calories(json_result)

    def store_analyze_calories_from_text(self, user_input: str) -> str:
        """End-to-end pipeline: text input -> info extraction -> database save."""
        json_result = self._extract_food_info(user_input)
        if isinstance(json_result, str):
            return json_result
        return self._store_food_calories(json_result)

    def _ensure_str_message(self, response: Any) -> str:
        """Safely extract string content from LangChain response object."""
        if isinstance(response, str):
            return response
        if hasattr(response, "content"):
            if isinstance(response.content, str):
                return response.content
            return str(response.content)
        return str(response)
