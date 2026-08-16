"""
Sport Calorie Calculator Module for Lady卡卡.
Extracts sport/exercise activities, calculates MET-based calories burned,
and generates encouraging AI feedback.
"""

import logging
import re
from typing import Any, Optional, Tuple

from access_db import Dailydata, Userdata
from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# MET (Metabolic Equivalent of Task) values for various physical activities
MET_VALUES = {
    "跑步": 9.8,
    "慢跑": 7.0,
    "快走": 4.8,
    "散步": 2.5,
    "步行": 3.5,
    "游泳": 8.0,
    "騎腳踏車": 7.5,
    "腳踏車": 7.5,
    "單車": 7.5,
    "自行車": 7.5,
    "跳繩": 11.0,
    "爬山": 6.5,
    "健行": 5.5,
    "爬樓梯": 8.0,
    "瑜伽": 3.0,
    "瑜珈": 3.0,
    "重訓": 6.0,
    "健身": 6.0,
    "有氧運動": 7.0,
    "拳擊": 9.0,
    "舞蹈": 5.0,
    "籃球": 6.5,
    "羽毛球": 5.5,
    "羽球": 5.5,
    "足球": 7.5,
    "乒乓球": 4.0,
    "排球": 4.0,
}


class CalorieAnalyzer:
    def __init__(self, user_id: str):
        self.user_id = str(user_id)

    def _get_llm(self) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
        )

    def handle_user_input(self, user_input: str) -> str:
        """Parse exercise input, calculate calories burned, record into DB, and generate AI feedback."""
        # 1. Fetch user weight from database
        userdata = Userdata(self.user_id)
        user_record = userdata.search_data("u_id", self.user_id)
        weight = float(user_record.get("weight", 70)) if user_record else 70.0

        # 2. Extract exercise info
        exercise_name, duration_minutes, distance_km = self.extract_exercise_info(user_input)

        if not exercise_name or duration_minutes is None:
            return "要告訴我完整的運動名稱跟時間喔（例如：『跑步 30分鐘』或『騎車 1小時 10公里』），這樣我才算得出熱量！"

        # 3. Calculate calories burned
        calories_burned = self.calculate_calories_burned(exercise_name, duration_minutes, weight)

        # 4. Save to daily database
        self.store_calorie_data(exercise_name, duration_minutes, calories_burned)

        # 5. Generate AI response
        distance_str = f"{distance_km} 公里" if distance_km is not None else "未指定距離"
        response = self.gemini_generate_response(
            exercise_name, duration_minutes, distance_str, calories_burned
        )
        return response

    def extract_exercise_info(self, user_input: str) -> Tuple[Optional[str], Optional[int], Optional[float]]:
        """Extract exercise name, duration in minutes, and optional distance in km."""
        sports_pattern = "|".join(sorted(MET_VALUES.keys(), key=lambda x: -len(x)))
        exercise_match = re.search(rf"({sports_pattern})", user_input)
        exercise_name = exercise_match.group(1) if exercise_match else None

        # Extract duration
        duration_minutes: Optional[int] = None
        hour_match = re.search(r"(\d+(\.\d+)?)\s*(?:個)?(?:小時|hr|h)", user_input, re.IGNORECASE)
        min_match = re.search(r"(\d+)\s*(?:分鐘|min)", user_input, re.IGNORECASE)

        if hour_match and min_match:
            hours = float(hour_match.group(1))
            mins = int(min_match.group(1))
            duration_minutes = int(hours * 60 + mins)
        elif hour_match:
            hours = float(hour_match.group(1))
            duration_minutes = int(hours * 60)
        elif min_match:
            duration_minutes = int(min_match.group(1))
        elif "半小時" in user_input:
            duration_minutes = 30

        # Extract distance
        distance_km: Optional[float] = None
        km_match = re.search(r"(\d+(\.\d+)?)\s*(?:公里|km)", user_input, re.IGNORECASE)
        m_match = re.search(r"(\d+)\s*(?:公尺|m)", user_input, re.IGNORECASE)

        if km_match:
            distance_km = float(km_match.group(1))
        elif m_match:
            distance_km = round(float(m_match.group(1)) / 1000.0, 2)

        return exercise_name, duration_minutes, distance_km

    def calculate_calories_burned(self, exercise_name: str, duration_minutes: float, weight: float) -> int:
        """Calculate burned calories based on MET value and duration."""
        met = MET_VALUES.get(exercise_name, 6.0)
        calories = met * weight * (duration_minutes / 60.0)
        return max(1, int(round(calories)))

    def gemini_generate_response(
        self, exercise_name: str, duration_minutes: int, distance_display: str, calories_burned: int
    ) -> str:
        """Generate motivating and encouraging feedback from Lady卡卡."""
        prompt = f"""
你是一位說話自然、熱情親切的運動教練「Lady卡卡」。
使用者剛做完運動：
- 運動：{exercise_name}
- 時間：{duration_minutes} 分鐘
- 距離：{distance_display}
- 消耗熱量：{calories_burned} 大卡

請用自然流暢、像朋友/教練聊天的口語口吻誇獎他：
1. 誇獎他的堅持與運動成果。
2. 提醒運動完記得多喝水、拉拉筋伸展，並適度補充蛋白質。
3. 嚴格使用繁體中文，字數在 120 字以內，不要用 Markdown 符號（如 ** 或 * 或 #），不要有死板的機器人感。
"""
        try:
            llm = self._get_llm()
            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip() if hasattr(response, "content") else str(response).strip()
            # Clean asterisks
            content = content.replace("**", "").replace("*", "")
            return f"運動項目：{exercise_name}，時間：{duration_minutes} 分鐘，消耗熱量：約 {calories_burned} 大卡。\n\n{content}"
        except Exception as e:
            logger.error(f"Error generating sport response: {e}")
            return f"太棒啦！你完成了 {duration_minutes} 分鐘的{exercise_name}，消耗了差不多 {calories_burned} 大卡！運動完記得多喝水、拉拉筋放鬆一下喔！💪"

    def store_calorie_data(self, exercise_name: str, duration_minutes: int, calories_burned: int):
        """Persist exercise calorie data into database."""
        daily_data = Dailydata(self.user_id)
        try:
            daily_data.add_data(
                food_name="",
                food_calories=0,
                exercise_name=exercise_name,
                exercise_duration=duration_minutes,
                calories_burned=calories_burned,
            )
            logger.info(f"Exercise logged: {exercise_name}, {duration_minutes}m, {calories_burned}kcal")
        except Exception as e:
            logger.error(f"Failed to store exercise data: {e}")
