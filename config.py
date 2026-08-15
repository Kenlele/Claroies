"""
Centralized Configuration Module for Calories Line Bot (Lady卡卡)
Supports reading from environment variables, .env file, and config.ini with graceful fallbacks.
"""

import os
from configparser import ConfigParser
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent

class Config:
    def __init__(self, ini_path: str = "config.ini"):
        self._ini_parser = ConfigParser()
        self._ini_file_path = BASE_DIR / ini_path
        if self._ini_file_path.exists():
            self._ini_parser.read(self._ini_file_path, encoding="utf-8")

    def _get(self, section: str, key: str, env_var: str, default: str = "") -> str:
        """Fetch config from environment variable first, then INI file, then default."""
        env_val = os.getenv(env_var)
        if env_val is not None and env_val != "":
            return env_val
        if self._ini_parser.has_section(section) and self._ini_parser.has_option(section, key):
            return self._ini_parser.get(section, key).strip()
        return default

    # LineBot Settings
    @property
    def LINE_CHANNEL_ACCESS_TOKEN(self) -> str:
        return self._get("LineBot", "CHANNEL_ACCESS_TOKEN", "LINE_CHANNEL_ACCESS_TOKEN")

    @property
    def LINE_CHANNEL_SECRET(self) -> str:
        return self._get("LineBot", "CHANNEL_SECRET", "LINE_CHANNEL_SECRET")

    # Flask Settings
    @property
    def FLASK_HOST(self) -> str:
        return self._get("Flask", "HOST", "FLASK_HOST", "0.0.0.0")

    @property
    def FLASK_PORT(self) -> int:
        port_str = self._get("Flask", "PORT", "PORT", "5000")
        try:
            return int(port_str)
        except ValueError:
            return 5000

    @property
    def FLASK_SECRET_KEY(self) -> str:
        val = self._get("Flask", "SECRET_KEY", "FLASK_SECRET_KEY")
        return val if val else os.urandom(24).hex()

    # Gemini Settings
    @property
    def GEMINI_API_KEY(self) -> str:
        return self._get("Gemini", "API_KEY", "GEMINI_API_KEY")

    @property
    def GEMINI_MODEL(self) -> str:
        return self._get("Gemini", "MODEL", "GEMINI_MODEL", "gemini-1.5-flash-latest")

    # Public Web URL (e.g. ngrok / domain)
    @property
    def WEBSITE_URL(self) -> str:
        url = self._get("ngrok", "website_url", "WEBSITE_URL", "").rstrip("/")
        return url

    # Strava API Settings
    @property
    def STRAVA_CLIENT_ID(self) -> str:
        return self._get("STRAVA", "CLIENT_ID", "STRAVA_CLIENT_ID")

    @property
    def STRAVA_CLIENT_SECRET(self) -> str:
        return self._get("STRAVA", "CLIENT_SECRET", "STRAVA_CLIENT_SECRET")

    # Azure OpenAI Settings
    @property
    def AZURE_OPENAI_API_KEY(self) -> str:
        return self._get("AzureOpenAI", "API_KEY", "AZURE_OPENAI_API_KEY")

    @property
    def AZURE_OPENAI_API_BASE(self) -> str:
        return self._get("AzureOpenAI", "API_BASE", "AZURE_OPENAI_API_BASE")

    @property
    def AZURE_OPENAI_API_VERSION(self) -> str:
        return self._get("AzureOpenAI", "API_VERSION", "AZURE_OPENAI_API_VERSION", "2024-07-01-preview")

    @property
    def AZURE_OPENAI_DEPLOYMENT_NAME(self) -> str:
        return self._get("AzureOpenAI", "DEPLOYMENT_NAME_GPT4o", "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    # Google Vision / Credentials Path
    @property
    def GOOGLE_VISION_CREDENTIALS(self) -> str:
        path = self._get("GoogleVision", "CREDENTIALS_PATH", "GOOGLE_VISION_CREDENTIALS", "")
        if path and not os.path.isabs(path):
            path = str(BASE_DIR / path)
        return path

    # Rich Menu List
    @property
    def RICH_MENU_IDS(self) -> List[str]:
        return [
            "richmenu-94f3bf5f154159dfda9fd72465a8fae2",
            "richmenu-e2b9fa51177550d4c412aa12424257ec",
            "richmenu-e6a249c50cf34d0a73d0fbe364f6c299",
            "richmenu-40c68086b6010bdaa6165b1e30757938",
            "richmenu-3fcdd5d43a2a3ed17fd9e99fea2dabac",
        ]


# Singleton instance
settings = Config()
