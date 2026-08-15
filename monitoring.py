"""
Calorie Monitoring Module for Lady卡卡.
Checks if the user's daily net calories exceeded their target budget.
"""

import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


def check_calories(
    user_states: Dict[str, Any],
    user_id: str,
    calorie_standards: Dict[str, Any],
    get_current_calories: Callable[[str], float],
) -> bool:
    """
    Check if the user has exceeded their daily recommended calorie limit.
    Returns True if exceeded, False otherwise.
    """
    # 1. Check user standards
    standard_info = calorie_standards.get(user_id, {})
    daily_limit = standard_info.get("recommended_daily_calories", 2000.0)

    try:
        current_calories = get_current_calories(user_id)
        if current_calories > daily_limit:
            logger.info(f"User {user_id} exceeded calorie budget: {current_calories} > {daily_limit}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking calories for user {user_id}: {e}")
        return False