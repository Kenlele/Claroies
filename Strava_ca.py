"""
Strava Integration Module for Lady卡卡.
Handles Strava OAuth2 authorization flow and athlete activity tracking.
"""

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class StravaAPI:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = str(client_id)
        self.client_secret = str(client_secret)
        self.redirect_uri = str(redirect_uri)
        self.user_tokens: Dict[str, Dict[str, Any]] = {}

    def get_strava_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for Strava access & refresh tokens."""
        token_url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        try:
            response = requests.post(token_url, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Strava Token exchange failed: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Strava token request exception: {e}")
            return None

    def save_strava_tokens(self, user_id: str, token_response: Dict[str, Any]):
        """Persist user Strava tokens."""
        self.user_tokens[user_id] = {
            "access_token": token_response.get("access_token"),
            "refresh_token": token_response.get("refresh_token"),
            "expires_at": token_response.get("expires_at"),
        }

    def get_strava_activities(self, access_token: str) -> Optional[list]:
        """Fetch latest athlete activities directly via Strava REST API."""
        activities_url = "https://www.strava.com/api/v3/athlete/activities?per_page=1"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(activities_url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Strava activities fetch failed: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Strava activities exception: {e}")
            return None

    def get_strava_reply(self, user_id: str) -> str:
        """Format the latest Strava activity into a friendly text message."""
        if user_id not in self.user_tokens:
            return "您尚未連結 Strava 帳號，請在選單輸入「authorize_strava」進行授權連結喔！"

        access_token = self.user_tokens[user_id].get("access_token")
        if not access_token:
            return "授權憑證已過期，請重新連結 Strava。"

        activities = self.get_strava_activities(access_token)
        if activities and len(activities) > 0:
            act = activities[0]
            name = act.get("name", "運動")
            distance_km = act.get("distance", 0) / 1000.0
            moving_time = act.get("moving_time", 0)
            moving_min = moving_time // 60
            moving_sec = moving_time % 60
            avg_speed_kph = act.get("average_speed", 0) * 3.6
            act_type = act.get("type", "運動")

            return (
                f"🏃‍♂️ 您最近一筆 Strava 運動紀錄：【{name}】\n"
                f"• 運動類型：{act_type}\n"
                f"• 運動距離：{distance_km:.2f} 公里\n"
                f"• 移動時間：{moving_min} 分 {moving_sec} 秒\n"
                f"• 平均時速：{avg_speed_kph:.2f} km/h\n\n"
                "太棒了！持續保持運動好習慣！🔥"
            )
        return "未能獲取到近期的 Strava 運動數據，請確認已在 Strava 上傳紀錄喔！"

    def get_auth_url(self, user_id: str) -> str:
        """Build Strava OAuth URL."""
        return (
            f"https://www.strava.com/oauth/authorize?client_id={self.client_id}"
            f"&response_type=code&redirect_uri={self.redirect_uri}"
            f"&scope=read,activity:read_all&approval_prompt=force&state={user_id}"
        )
