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
            return f"體重幫你更新成 {val:.1f} 公斤囉！可以去按『AI減肥攻略』看看最新的建議～"

        except ValueError:
            return "請輸入體重數字喔，例如 65 或 65.5～"
        except Exception as e:
            logger.error(f"Error updating weight: {e}")
            return "更新體重時出了點問題，等一下再試試看喔！"