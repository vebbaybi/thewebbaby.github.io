# app/services/weather.py

import json
import logging
import os
from datetime import datetime, timezone

import requests

from .schema import NewsItem
from .cache import CacheManager
from .metrics import METRICS

log = logging.getLogger(__name__)


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class WeatherService:
    """Fetches and formats weather data for storage and APIs (OpenWeather-compatible)."""
    def __init__(self, api_url, api_key, city, timeout=12):
        self.api_url = str(api_url or '').strip()
        self.api_key = str(api_key or '').strip()
        self.city = str(city or '').strip()
        self.timeout = int(timeout)
        self.cache = CacheManager()

    def fetch_weather(self):
        """Fetch current weather and normalize to a NewsItem dict. Returns None on failure."""
        if not self.api_url or not self.api_key or not self.city:
            log.error("weather: missing configuration")
            METRICS.increment('weather.config_error')
            return None

        try:
            params = {'q': self.city, 'appid': self.api_key, 'units': 'metric'}
            headers = {'User-Agent': 'WebbabyWeather/1.0'}
            resp = requests.get(self.api_url, params=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            main = data.get('main') or {}
            wx0 = (data.get('weather') or [{}])[0]
            temp = main.get('temp')
            desc = (wx0.get('description') or 'N/A').strip().capitalize()
            icon = wx0.get('icon') or ''

            ts = _now_iso()
            tnum = str(temp) if (temp is not None) else 'N/A'
            title = f"Weather in {self.city}: {tnum}°C, {desc}"

            weather_data = {
                'id': f'weather-{ts}',
                'source': 'weather',
                'title': title[:512],
                'url': '',
                'published_at': ts,
                'tags': ['weather'],
                'excerpt': desc[:240],
                'image': f'https://openweathermap.org/img/wn/{icon}.png' if icon else None
            }

            item = NewsItem(
                id=weather_data['id'],
                source=weather_data['source'],
                title=weather_data['title'],
                url=weather_data['url'],
                published_at=weather_data['published_at'],
                tags=weather_data['tags'],
                excerpt=weather_data['excerpt'],
                image=weather_data['image']
            )
            METRICS.increment('weather.fetch_ok')
            return item.to_dict()
        except Exception as exc:
            METRICS.increment('weather.fetch_error')
            log.error("weather: fetch error: %s", exc)
            return None

    def save_weather_json(self, path):
        """Fetch and save weather snapshot to JSON. Returns True/False."""
        try:
            payload = self.fetch_weather()
            if not payload:
                return False
            directory = os.path.dirname(os.path.abspath(path))
            if directory and not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            METRICS.increment('weather.saved_ok')
            return True
        except Exception as exc:
            METRICS.increment('weather.saved_error')
            log.error("weather: save error to %s: %s", path, exc)
            return False

    def get_cached_weather(self, path):
        """Return (data, etag, last_modified) from a saved snapshot, or (None, None, None)."""
        try:
            if not os.path.isfile(path):
                METRICS.increment('weather.cache_miss')
                return None, None, None
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            etag = self.cache.file_etag(path)
            last_modified = self.cache.file_last_modified_utc(path)
            METRICS.increment('weather.cache_hit')
            return data, etag, last_modified
        except Exception as exc:
            METRICS.increment('weather.cache_error')
            log.error("weather: cache read error from %s: %s", path, exc)
            return None, None, None
