"""
Delete All Existing Rich Menus for Clean State Setup.
"""

import logging
import sys
from pathlib import Path

parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import settings
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RichMenuDeleter")


def delete_all_rich_menus():
    line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
    try:
        rich_menu_list = line_bot_api.get_rich_menu_list()
        logger.info(f"找到 {len(rich_menu_list)} 個 Rich Menus，開始進行刪除...")
        for menu in rich_menu_list:
            line_bot_api.delete_rich_menu(menu.rich_menu_id)
            logger.info(f"Deleted Rich Menu: {menu.rich_menu_id}")
        logger.info("已成功清空所有 Rich Menus。")
    except LineBotApiError as e:
        logger.error(f"LINE API Error: {e}")


if __name__ == "__main__":
    delete_all_rich_menus()