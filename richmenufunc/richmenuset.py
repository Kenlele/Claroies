"""
Set Default Rich Menu for Lady卡卡.
"""

import logging
import sys
from pathlib import Path
import requests

parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RichMenuSetter")


def set_default_rich_menu(rich_menu_id: str):
    channel_access_token = settings.LINE_CHANNEL_ACCESS_TOKEN
    headers = {"Authorization": f"Bearer {channel_access_token}"}
    url = f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}"
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        logger.info(f"已成功將 {rich_menu_id} 設為全域預設 Rich Menu。")
    else:
        logger.error(f"設置預設 Rich Menu 失敗: {response.status_code} - {response.text}")


if __name__ == "__main__":
    target_id = settings.RICH_MENU_IDS[0] if settings.RICH_MENU_IDS else "richmenu-94f3bf5f154159dfda9fd72465a8fae2"
    set_default_rich_menu(target_id)