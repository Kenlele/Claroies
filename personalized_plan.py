"""
Personalized Weight-Loss Plan Generator for Lady卡卡.
Calculates BMR, TDEE, Calorie Deficit, and generates customized advice via Gemini.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from access_db import Dailydata, Userdata
from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class generate_plan:
    def __init__(self, llm_gemini: Any, user_id: str, target_weight: float):
        self.llm_gemini = llm_gemini or ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
        )
        self.user_id = str(user_id)
        self.target_weight = float(target_weight)

    def fetch_user_data(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch user profile from SQLite database."""
        user_data = Userdata(self.user_id)
        user_record = user_data.search_data("u_id", self.user_id)
        if not user_record:
            return None, "無法找到您的基本資料，請先在「我的狀態」更新個人基本資料喔！"
        return user_record, None

    def generate_plan(self) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Calculate BMR/TDEE standards, generate personalized strategy, and store in DB."""
        user_record, error_message = self.fetch_user_data()
        if error_message or not user_record:
            return None, {"error": error_message}

        name = user_record.get("name", "健康追求者")
        age = int(user_record.get("age", 25))
        gender_val = user_record.get("gender")
        is_male = gender_val in (1, True, "1", "male", "男")
        weight = float(user_record.get("weight", 60.0))
        height = float(user_record.get("height", 165.0))
        activity_level = float(user_record.get("activity_level", 1.375))

        # 1. Calculate BMR (Mifflin-St Jeor formula)
        if is_male:
            bmr = 10.0 * weight + 6.25 * height - 5.0 * age + 5.0
        else:
            bmr = 10.0 * weight + 6.25 * height - 5.0 * age - 161.0

        # 2. Daily Total Energy Expenditure (TDEE)
        daily_calories = bmr * activity_level

        # 3. Calculate Weight Goal & Timeline
        weight_diff = weight - self.target_weight

        if weight_diff > 0:
            # Weight loss scenario
            weeks = 12 if weight_diff <= 5.0 else 24
            total_calorie_deficit = weight_diff * 7700.0
            daily_calorie_deficit = total_calorie_deficit / (weeks * 7.0)
            daily_calorie_deficit = max(300.0, min(800.0, daily_calorie_deficit))
            recommended_daily_calories = daily_calories - daily_calorie_deficit

            min_safe_calories = 1400.0 if is_male else 1200.0
            recommended_daily_calories = max(min_safe_calories, recommended_daily_calories)
            goal_desc = f"目標在 {weeks} 週內減輕 {weight_diff:.1f} 公斤"
        elif weight_diff < 0:
            # Muscle gain scenario
            weeks = 16
            recommended_daily_calories = daily_calories + 300.0
            goal_desc = f"目標在 {weeks} 週內健康增重/增肌 {abs(weight_diff):.1f} 公斤"
            daily_calorie_deficit = -300.0
            total_calorie_deficit = 0.0
        else:
            # Maintenance scenario
            weeks = 12
            recommended_daily_calories = daily_calories
            goal_desc = "目標維持目前理想體重與健康體態"
            daily_calorie_deficit = 0.0
            total_calorie_deficit = 0.0

        # 4. Save goal and calculated target BMR to database
        try:
            daily_data = Dailydata(self.user_id)
            daily_data.add_data(
                food_name="",
                food_calories=0,
                exercise_name="",
                exercise_duration=0,
                weight_target=self.target_weight,
                bmr_target=round(recommended_daily_calories, 1),
                calories_burned=0,
            )
            logger.info(f"Updated user {self.user_id} plan: target_weight={self.target_weight}, target_bmr={recommended_daily_calories}")
        except Exception as e:
            logger.error(f"Failed to persist plan to database: {e}")

        # 5. Generate warm and encouraging advice with Gemini
        prompt = f"""
你是一位專業且充滿溫度的健康減重與體態顧問「Lady卡卡」。
請為使用者【{name}】撰寫一份專屬的個人化減肥/體態攻略：

【個人健康數據】：
- 目前體重：{weight:.1f} kg
- 目標體重：{self.target_weight:.1f} kg（{goal_desc}）
- 基礎代謝率（BMR）：{bmr:.0f} 大卡
- 每日總能量消耗（TDEE）：{daily_calories:.0f} 大卡
- 建議每日攝取熱量：{recommended_daily_calories:.0f} 大卡

【回覆要求】：
1. 請以溫暖、親切、鼓勵的語氣，肯定對方的目標，並給予清晰的飲食熱量與日常運動大方向。
2. 嚴格使用繁體中文，字數控制在 160 字以內，適度加入 emoji。
3. 請不要使用 Markdown 符號（如 ** 或 * 或 #），直接使用完整流暢的語句。
"""
        try:
            result = self.llm_gemini.invoke([HumanMessage(content=prompt)])
            refined_plan = result.content.strip() if hasattr(result, "content") else str(result).strip()
            refined_plan = refined_plan.replace("**", "").replace("*", "")
        except Exception as e:
            logger.error(f"Error calling Gemini for personalized plan: {e}")
            refined_plan = (
                f"親愛的 {name}！您的基礎代謝率為 {bmr:.0f} 大卡，為了在 {weeks} 週內達成 {self.target_weight} kg 的目標，"
                f"建議您每日攝取約 {recommended_daily_calories:.0f} 大卡。搭配規律運動與原型食物，卡卡陪你一起健康蛻變！✨"
            )

        standards = {
            "bmr": round(bmr, 1),
            "daily_calories": round(daily_calories, 1),
            "recommended_daily_calories": round(recommended_daily_calories, 1),
            "weight_loss_needed": round(weight_diff, 1),
            "total_calorie_deficit": round(total_calorie_deficit, 1),
            "daily_calorie_deficit": round(daily_calorie_deficit, 1),
            "weeks": weeks,
        }

        return refined_plan, standards