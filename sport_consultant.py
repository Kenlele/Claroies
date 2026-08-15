"""
Sport Consultant Module for Lady卡卡.
Provides personalized exercise recommendations following BRTR framework:
Background, Request, Tone, Result (1 Day, 1 Week, 1 Month, Health Advice).
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple

from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# Max recommended continuous exercise hours per day
MAX_TIME_LIMITS = {
    "跑步": 2.0,
    "慢跑": 2.5,
    "騎腳踏車": 4.0,
    "自行車": 4.0,
    "游泳": 2.0,
    "健行": 6.0,
    "重訓": 2.0,
    "瑜伽": 2.0,
}


def get_gemini_client() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.7,
    )


def generate_user_description(user_data: Optional[Dict[str, Any]]) -> str:
    """Generate concise user health profile description."""
    if not user_data:
        return "基本資料未設定的健康追求者"

    age = user_data.get("age", 25)
    gender_val = user_data.get("gender")
    gender_desc = "男性" if gender_val in (1, True, "1", "male") else "女性"
    weight = float(user_data.get("weight", 60))
    height = float(user_data.get("height", 165))

    bmi = weight / ((height / 100.0) ** 2) if height > 0 else 22.0

    if bmi < 18.5:
        weight_status = "體重過輕"
    elif 18.5 <= bmi < 24.0:
        weight_status = "體重適中"
    elif 24.0 <= bmi < 27.0:
        weight_status = "體重過重"
    else:
        weight_status = "肥胖"

    return f"{age}歲{gender_desc}（身高{int(height)}cm、體重{weight}kg、BMI {bmi:.1f}、{weight_status}）"


def replace_special_symbols(text: str) -> str:
    """Format and clean output symbols for readability."""
    replaced_text = re.sub(r"\*\*(.*?)\*\*", r"「\1」", text)
    replaced_text = replaced_text.replace("* ", "• ")
    replaced_text = re.sub(r"「(.*?)」\s*:", r"「\1」:", replaced_text)
    return replaced_text


def validate_activity_time(activity_type: str, hours: float) -> Tuple[bool, float]:
    """Check if the requested exercise duration is within safe human limits."""
    max_hours = MAX_TIME_LIMITS.get(activity_type, 3.0)
    if hours > max_hours:
        return False, hours
    return True, hours


def generate_brtr_prompt(user_id: str, user_data: Optional[Dict[str, Any]], activity: Optional[str] = None) -> Tuple[bool, str]:
    """Construct BRTR prompt for Gemini."""
    user_description = generate_user_description(user_data)
    advisor_role = "專業運動與健康管理顧問"

    background = f"你是一個名字叫「Lady卡卡」的{advisor_role}，根據使用者的健康資料和運動目標提供溫暖、專業且實用的運動指導。\n"

    if activity:
        # Parse activity format e.g. "跑步 1.5小時" or "游泳 30分鐘"
        parts = activity.strip().split()
        activity_type = parts[0] if parts else "運動"
        duration_text = parts[1] if len(parts) > 1 else "30分鐘"

        current_hours = 0.5
        if "小時" in duration_text:
            val_str = duration_text.replace("小時", "").strip()
            try:
                current_hours = float(val_str)
            except ValueError:
                current_hours = 1.0
        elif "分鐘" in duration_text:
            val_str = duration_text.replace("分鐘", "").strip()
            try:
                current_hours = float(val_str) / 60.0
            except ValueError:
                current_hours = 0.5

        is_valid, _ = validate_activity_time(activity_type, current_hours)
        time_display = f"{current_hours:.1f} 小時" if current_hours >= 1.0 else f"{int(current_hours * 60)} 分鐘"

        if not is_valid:
            exceed_msg = (
                f"您選擇了進行 {activity_type} {time_display}。\n\n"
                "雖然運動對健康很有幫助，但為了避免運動傷害與身體過度負擔，"
                f"建議單次 {activity_type} 時間不超過 {MAX_TIME_LIMITS.get(activity_type, 2.0)} 小時。\n\n"
                "請記得保持充足休息與補水，持之以恆才是健康最好的捷徑喔！✨"
            )
            return False, exceed_msg

        request = f"使用者基本資料：{user_description}。他今天計畫進行【{activity_type}】約【{time_display}】。請為他制定量身打造的運動建議。\n"
    else:
        request = f"使用者基本資料：{user_description}。目前尚未確定要進行哪種運動，請為他提供一組全方位的運動計畫建議。\n"

    tone = """
【回覆規範】：
- 請使用繁體中文，語氣保持溫暖、熱情且具有激勵感。
- 請避免使用 Markdown 的「**」或「#」符號，一律以自然流暢的文字組織。
- 總字數請控制在 350 字以內，適度穿插 emoji。
"""

    result = """
【輸出格式結構】：
請嚴格分成以下五個區塊，並使用「區塊名稱」標註：
1. 簡短前言開場（在「1天」之前）
2. 「1天」：今日當下的運動安排、熱身要點與注意事項。
3. 「1週」：本週運動頻率、強度進階與休息日規劃。
4. 「1個月」：一個月後的目標設定、耐力養成與成果期許。
5. 「健康建議」：條列飲食搭配（如蛋白質補充）、運動後伸展與充足睡眠指引。
"""

    prompt = background + request + tone + result
    return True, prompt


def get_activity_advice(user_id: str, user_data: Optional[Dict[str, Any]], activity: Optional[str] = None) -> Tuple[bool, str]:
    """Public interface for generating sport advice."""
    is_valid, prompt_or_msg = generate_brtr_prompt(user_id, user_data, activity)
    if not is_valid:
        return False, prompt_or_msg

    try:
        llm = get_gemini_client()
        response = llm.invoke([HumanMessage(content=prompt_or_msg)])
        content = response.content.strip() if hasattr(response, "content") else str(response).strip()
        cleaned_content = replace_special_symbols(content)
        return True, cleaned_content
    except Exception as e:
        logger.error(f"Gemini sport advice generation failed: {e}")
        return False, "目前連線忙碌中，請稍後再試一次喔！"
