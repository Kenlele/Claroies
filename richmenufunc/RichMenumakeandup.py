"""
Rich Menu Generator and Uploader for Lady卡卡.
Creates 5-stage HP bar Rich Menus and uploads their corresponding sliced images.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
import requests

# Add parent directory to sys.path for config import
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RichMenuMaker")

channel_access_token = settings.LINE_CHANNEL_ACCESS_TOKEN
headers = {
    "Authorization": f"Bearer {channel_access_token}",
}


def create_rich_menu(name: str, chat_bar_text: str, image_path: str):
    """Create a 6-grid Rich Menu and upload its background image."""
    body = {
        "size": {"width": 2500, "height": 1686},
        "selected": False,
        "name": name,
        "chatBarText": chat_bar_text,
        "areas": [
            {"bounds": {"x": 0, "y": 0, "width": 833, "height": 843}, "action": {"type": "message", "text": "燃脂打卡"}},
            {"bounds": {"x": 0, "y": 843, "width": 833, "height": 843}, "action": {"type": "message", "text": "運動建議"}},
            {"bounds": {"x": 833, "y": 0, "width": 833, "height": 843}, "action": {"type": "message", "text": "飲食打卡"}},
            {"bounds": {"x": 833, "y": 843, "width": 833, "height": 843}, "action": {"type": "message", "text": "我的狀態"}},
            {"bounds": {"x": 1666, "y": 0, "width": 834, "height": 843}, "action": {"type": "message", "text": "健康數據"}},
            {"bounds": {"x": 1666, "y": 843, "width": 834, "height": 843}, "action": {"type": "message", "text": "AI減肥攻略"}},
        ],
    }

    create_url = "https://api.line.me/v2/bot/richmenu"
    response = requests.post(create_url, headers={**headers, "Content-Type": "application/json"}, data=json.dumps(body))

    if response.status_code != 200:
        logger.error(f"Failed to create rich menu: {response.text}")
        return None

    rich_menu_id = response.json().get("richMenuId")
    logger.info(f"Created Rich Menu ID: {rich_menu_id}")

    # Wait for LINE backend sync
    time.sleep(2)

    # Validate image file
    abs_image_path = os.path.join(parent_dir, image_path) if not os.path.isabs(image_path) else image_path
    if not os.path.exists(abs_image_path):
        logger.error(f"Image not found at {abs_image_path}")
        return rich_menu_id

    # Upload image binary
    try:
        with open(abs_image_path, "rb") as f:
            image_data = f.read()
            upload_url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
            img_headers = {**headers, "Content-Type": "image/jpeg"}
            img_res = requests.post(upload_url, headers=img_headers, data=image_data)
            if img_res.status_code == 200:
                logger.info(f"Successfully uploaded image for {name} ({rich_menu_id})")
            else:
                logger.error(f"Failed to upload image: {img_res.status_code} - {img_res.text}")
    except Exception as e:
        logger.error(f"Exception uploading image: {e}")

    return rich_menu_id


if __name__ == "__main__":
    image_paths = [
        "thintofat/1-1.jpg",
        "thintofat/1-2.jpg",
        "thintofat/1-3.jpg",
        "thintofat/1-4.jpg",
        "thintofat/1-5.jpg",
    ]

    created_ids = []
    for i, path in enumerate(image_paths):
        rid = create_rich_menu(f"Lady卡卡_血條_{i+1}", "點擊查看健康選單", path)
        if rid:
            created_ids.append(rid)

    print("\n================== 創建完成的 RICH MENU IDS ==================")
    for idx, rid in enumerate(created_ids):
        print(f"RICH_MENU_{idx+1} = '{rid}'")