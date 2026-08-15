"""
Flex Message Utility Module for Lady卡卡.
Dynamically generates stylish LINE Flex Messages and Carousels with Morandi color schemes.
"""

import random
import re
from typing import Any, Dict, List, Optional

from config import settings
from linebot.models import (
    BoxComponent,
    BubbleContainer,
    CarouselContainer,
    FlexSendMessage,
    ImageComponent,
    TextComponent,
)

# Morandi color palette for card styling
MORANDI_COLORS = ["#A39E93", "#B7A99A", "#C7B8A5", "#D1B7A1", "#E0C9B0", "#B2BEB5", "#D8C4B6"]


def get_image_url(key: str) -> str:
    """Get absolute static image URL based on current configured host."""
    base_url = settings.WEBSITE_URL.rstrip("/")
    image_map = {
        "intro": f"{base_url}/static/sports/intro_image.jpg",
        "health": f"{base_url}/static/sports/health_image.jpg",
        "running_day": f"{base_url}/static/sports/running_day_image.jpg",
        "running_week": f"{base_url}/static/sports/running_week_image.jpg",
        "running_month": f"{base_url}/static/sports/running_month_image.jpg",
        "swimming_day": f"{base_url}/static/sports/swimming_day_image.jpg",
        "swimming_week": f"{base_url}/static/sports/swimming_week_image.jpg",
        "swimming_month": f"{base_url}/static/sports/swimming_month_image.jpg",
        "cycling_day": f"{base_url}/static/sports/cycling_day_image.jpg",
        "cycling_week": f"{base_url}/static/sports/cycling_week_image.jpg",
        "cycling_month": f"{base_url}/static/sports/cycling_month_image.jpg",
        "diet_plan": f"{base_url}/static/sports/diet_plan.jpg",
        "default": f"{base_url}/static/sports/default_image.jpg",
    }
    return image_map.get(key, f"{base_url}/static/sports/default_image.jpg")


def parse_advice_to_sections(cleaned_response: str) -> Dict[str, str]:
    """Parse BRTR advice text into structured sections."""
    sections: Dict[str, str] = {}

    intro_match = re.search(r"^(.*?)「1天」", cleaned_response, re.DOTALL)
    day_match = re.search(r"「1天」(.*?)「1週」", cleaned_response, re.DOTALL)
    week_match = re.search(r"「1週」(.*?)「1個月」", cleaned_response, re.DOTALL)
    month_match = re.search(r"「1個月」(.*?)「健康建議」", cleaned_response, re.DOTALL)
    reminder_match = re.search(r"「(?:健康建議|小貼士|小提醒)」(.*?)$", cleaned_response, re.DOTALL)

    if intro_match and intro_match.group(1).strip():
        sections["介紹"] = intro_match.group(1).strip()
    if day_match and day_match.group(1).strip():
        sections["一日建議"] = day_match.group(1).strip()
    if week_match and week_match.group(1).strip():
        sections["一週建議"] = week_match.group(1).strip()
    if month_match and month_match.group(1).strip():
        sections["一個月建議"] = month_match.group(1).strip()
    if reminder_match and reminder_match.group(1).strip():
        sections["健康建議"] = reminder_match.group(1).strip()

    # Fallback if structure didn't match regex exactly
    if not sections and cleaned_response.strip():
        sections["運動建議"] = cleaned_response.strip()

    return sections


def create_bubble(title: str, content: str, image_url: str) -> Optional[BubbleContainer]:
    """Create a single BubbleContainer for Flex carousel."""
    if not content.strip():
        return None

    return BubbleContainer(
        hero=ImageComponent(
            url=image_url,
            size="full",
            aspect_ratio="20:13",
            aspect_mode="cover",
        ),
        styles={
            "body": {
                "backgroundColor": "#FFF8F0",
                "borderColor": "#E2E8F0",
                "borderWidth": "1px",
                "cornerRadius": "md",
            }
        },
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=title,
                    weight="bold",
                    size="md",
                    align="center",
                    color="#2D3748",
                ),
                TextComponent(
                    text=content,
                    wrap=True,
                    size="sm",
                    color="#4A5568",
                    align="start",
                ),
            ],
            spacing="sm",
            padding_all="md",
        ),
    )


def generate_flex_messages(advice_text: str, activity: str) -> List[FlexSendMessage]:
    """Generate Carousel Flex Messages from advice text."""
    activity_translation = {
        "游泳": "swimming",
        "跑步": "running",
        "慢跑": "running",
        "騎腳踏車": "cycling",
        "腳踏車": "cycling",
        "自行車": "cycling",
    }
    activity_english = activity_translation.get(activity, "running")
    sections = parse_advice_to_sections(advice_text)

    bubbles = []
    for section_title, section_content in sections.items():
        if not section_content.strip():
            continue

        if section_title == "介紹":
            img_key = "intro"
        elif section_title == "健康建議":
            img_key = "health"
        elif section_title == "一日建議":
            img_key = f"{activity_english}_day"
        elif section_title == "一週建議":
            img_key = f"{activity_english}_week"
        elif section_title == "一個月建議":
            img_key = f"{activity_english}_month"
        else:
            img_key = "default"

        image_url = get_image_url(img_key)
        bubble = create_bubble(section_title, section_content, image_url)
        if bubble:
            bubbles.append(bubble)

    if bubbles:
        carousel = CarouselContainer(contents=bubbles[:10])  # LINE max 10 bubbles
        return [FlexSendMessage(alt_text="Lady卡卡 運動建議", contents=carousel)]
    return []


def generate_diet_flex_messages(diet_plan: str) -> List[FlexSendMessage]:
    """Generate Carousel Flex Messages from diet plan text."""
    if not diet_plan.strip():
        return []

    # Split into meaningful paragraphs or bullet points
    paragraphs = [p.strip() for p in diet_plan.split("\n") if p.strip()]
    if not paragraphs:
        paragraphs = [diet_plan.strip()]

    bubbles = []
    image_url = get_image_url("diet_plan")

    for idx, text_block in enumerate(paragraphs):
        title = "✨ Lady卡卡 減肥攻略" if idx == 0 else f"💡 健康攻略重點 ({idx + 1})"
        formatted_content = text_block.replace("，", "，\n")
        bubble = create_bubble(title, formatted_content, image_url)
        if bubble:
            bubbles.append(bubble)

    if bubbles:
        carousel = CarouselContainer(contents=bubbles[:10])
        return [FlexSendMessage(alt_text="Lady卡卡 減肥建議", contents=carousel)]
    return []