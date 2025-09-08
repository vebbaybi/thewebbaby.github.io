# app/config.py

import os
from pathlib import Path


class Config:
    """Centralized configuration for the Flask application."""
    def __init__(self):
        # ----- Base paths -----
        self.BASE_DIR = Path(__file__).resolve().parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.STATIC_DIR = self.BASE_DIR / "app" / "static"
        self.STATIC_IMG_DIR = self.STATIC_DIR / "img"
        self.PLAYME_DIR = self.DATA_DIR / "playme"
        self.OPTIMIZED_IMG_DIR = self.DATA_DIR / "optimized"

        # Ensure critical directories exist
        for directory in (self.DATA_DIR, self.PLAYME_DIR, self.OPTIMIZED_IMG_DIR):
            directory.mkdir(parents=True, exist_ok=True)

        # ----- Site settings -----
        self.SITE_NAME = os.getenv("SITE_NAME", "thewebbaby")
        self.BASE_URL = os.getenv("BASE_URL", "https://thewebbaby.onrender.com").rstrip("/")
        self.CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "contact@example.com")

        # ----- Data files -----
        self.NEWS_JSON = self.DATA_DIR / "news.json"
        self.BULLETINS_YAML = self.DATA_DIR / "bulletins.yaml"
        self.WEATHER_JSON = self.DATA_DIR / "weather_snapshot.json"
        self.RSS_XML = self.DATA_DIR / "rss.xml"

        # ----- Weather settings (OpenWeather compatible) -----
        # API endpoint used by WeatherService
        self.WEATHER_API_URL = os.getenv(
            "WEATHER_API_URL",
            "https://api.openweathermap.org/data/2.5/weather"
        ).strip()
        # Backward-compat alias if older env var is set
        legacy_provider = os.getenv("WEATHER_PROVIDER_URL", "").strip()
        if legacy_provider and not os.getenv("WEATHER_API_URL"):
            self.WEATHER_API_URL = legacy_provider

        self.WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "").strip()
        self.WEATHER_CITY = os.getenv("WEATHER_CITY", "New York").strip()

        # Optional coordinates (not used by current WeatherService but kept for future)
        try:
            self.LAT = float(os.getenv("WB_LAT", "40.7128"))
            self.LON = float(os.getenv("WB_LON", "-74.0060"))
        except Exception:
            self.LAT = 40.7128
            self.LON = -74.0060

        try:
            self.WEATHER_CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "300"))
        except Exception:
            self.WEATHER_CACHE_TTL = 300

        # ----- API / Pagination -----
        try:
            self.API_CACHE_TTL = int(os.getenv("API_CACHE_TTL", "300"))
        except Exception:
            self.API_CACHE_TTL = 300

        try:
            self.NEWS_PAGE_SIZE = int(os.getenv("NEWS_PAGE_SIZE", "12"))
        except Exception:
            self.NEWS_PAGE_SIZE = 12

        # ----- Theme cookie -----
        self.THEME_COOKIE_NAME = "theme"
        self.THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

        # ----- RSS sources -----
        rss_env = os.getenv("RSS_SOURCES", "").strip()
        if rss_env:
            self.RSS_SOURCES = [s.strip() for s in rss_env.split(",") if s.strip()]
        else:
            self.RSS_SOURCES = [
                "https://planetpython.org/rss20.xml",
                "https://hnrss.org/frontpage",
                "https://realpython.com/atom.xml",
                "https://pypi.org/rss/updates.xml",
            ]

    def validate(self):
        """Validate critical configuration settings."""
        errors = []
        if not self.SITE_NAME:
            errors.append("SITE_NAME is empty")
        if not self.BASE_URL:
            errors.append("BASE_URL is empty")
        if not self.WEATHER_API_URL:
            errors.append("WEATHER_API_URL is empty")
        if not self.RSS_SOURCES:
            errors.append("RSS_SOURCES is empty")

        if errors:
            print("Configuration errors:")
            for e in errors:
                print(" - %s" % e)
            return False
        return True
