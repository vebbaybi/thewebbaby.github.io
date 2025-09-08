#!/usr/bin/env python3
# scripts/build_feeds.py

import json
import logging
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

# Add project root to sys.path for imports
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from app.config import Config
from app.services.content import load_bulletins
from app.services.metrics import METRICS
from app.services.rss_build import RSSBuilder
from app.services.rss_ingest import RSSIngester
from app.services.weather import WeatherService

log = logging.getLogger("build_feeds")


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=directory) as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


class FeedBuilder:
    """Builds and updates news and weather feeds."""

    def __init__(self, config):
        self.config = config
        self.rss_ingester = RSSIngester()
        self.weather_service = WeatherService(
            api_url=config.WEATHER_API_URL,
            api_key=config.WEATHER_API_KEY,
            city=config.WEATHER_CITY,
        )
        self.rss_builder = RSSBuilder(
            base_url=config.BASE_URL,
            site_name=config.SITE_NAME,
        )

    def build(self):
        """Fetch and save news, weather, and RSS feeds.

        Returns:
            Boolean indicating success.
        """
        success = True
        os.makedirs(os.path.dirname(self.config.NEWS_JSON), exist_ok=True)
        os.makedirs(os.path.dirname(self.config.RSS_XML), exist_ok=True)

        news_items = []
        log.info("[build_feeds] Fetching RSS sources...")
        try:
            sources = list(self.config.RSS_SOURCES) if getattr(self.config, "RSS_SOURCES", None) else []
            news_items = self.rss_ingester.fetch_sources(sources, limit_per_source=30)
            log.info("[build_feeds] Fetched %d news items", len(news_items))
            ok = self.rss_ingester.save_news_json(self.config.NEWS_JSON, news_items)
            if ok:
                log.info("[build_feeds] Saved news to %s", self.config.NEWS_JSON)
            else:
                log.error("[build_feeds] Failed to save news to %s", self.config.NEWS_JSON)
                success = False
        except Exception as e:
            log.error("[build_feeds] Error fetching/saving news: %s", e)
            METRICS.increment("feeds.news_error")
            success = False

        log.info("[build_feeds] Fetching weather...")
        try:
            if self.weather_service.save_weather_json(self.config.WEATHER_JSON):
                log.info("[build_feeds] Saved weather to %s", self.config.WEATHER_JSON)
            else:
                log.error("[build_feeds] Failed to save weather")
                success = False
        except Exception as e:
            log.error("[build_feeds] Error fetching/saving weather: %s", e)
            METRICS.increment("feeds.weather_error")
            success = False

        log.info("[build_feeds] Building RSS XML...")
        try:
            bulletins = load_bulletins(self.config.BULLETINS_YAML)
            rss_xml = self.rss_builder.build_rss_xml(bulletins, news_items)
            if rss_xml:
                _atomic_write(self.config.RSS_XML, rss_xml)
                log.info("[build_feeds] Saved RSS XML to %s", self.config.RSS_XML)
            else:
                log.error("[build_feeds] Failed to build RSS XML")
                success = False
        except Exception as e:
            log.error("[build_feeds] Error building/saving RSS XML: %s", e)
            METRICS.increment("feeds.rss_error")
            success = False

        METRICS.increment("feeds.build_ok" if success else "feeds.build_error")
        return success


def main():
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        cfg = Config()
    except Exception as e:
        print("Error loading config: %s" % e)
        sys.exit(1)

    builder = FeedBuilder(cfg)
    success = builder.build()
    print("[build_feeds] Done.")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
