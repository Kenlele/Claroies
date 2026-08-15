"""
Weight Updater Module for Lady卡卡.
Handles user weight updates and provides feedback.
"""

import logging
from typing import Union
from access_db import Userdata

logger = logging.getLogger(__name__)


class WeightUpdater:
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.user_db = Userdata(self.user_id)

    def update_weight(self, new_weight: Union[float, int, str]) -> str:
        """Update the user's weight in the database."""
        try:
            val = float(new_weight)
            if val < 2.0 or val > 500.0:
                return "請輸入合理的體重數值（2 ~ 500 kg）。"

            user_record = self.user_db.search_data("u_id", self.user_id)
            if not user_record:
                self.user_db.add_data(weight=val)
            else:
                self.user_db.update_data("weight", val)

            logger.info(f"Updated weight for user {self.user_id}: {val} kg")
            return f"🎉 您的體重已成功更新為 {val:.1f} 公斤！點選「AI減肥攻略」可重新獲得專屬個人化建議喔！✨"

        except ValueError:
            return "請輸入有效的體重數字，例如 65 或 65.5 公斤。"
        except Exception as e:
            logger.error(f"Error updating weight: {e}")
            return "更新體重時發生錯誤，請稍後再試。"