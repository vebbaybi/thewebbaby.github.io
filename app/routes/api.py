# app/routes/api.py

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, make_response, request, current_app

from ..services.cache import CacheManager
from ..services.schema import coerce_news_list
from ..services.weather import WeatherService
from ..services.metrics import METRICS

api_bp = Blueprint("api", __name__)
_cache = CacheManager()


@api_bp.get("/api/news")
def api_news():
    try:
        with open(current_app.config["NEWS_JSON"], "r", encoding="utf-8") as f:
            data = json.load(f) or []
    except Exception:
        data = []

    items = coerce_news_list(data)

    page = int(request.args.get("page", 1))
    page_size = current_app.config["NEWS_PAGE_SIZE"]
    start = (page - 1) * page_size
    end = start + page_size
    paginated = items[start:end]

    payload = [it.to_dict() for it in paginated]
    body = json.dumps(payload, ensure_ascii=False)
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["ETag"] = _cache.generate_etag(body)
    resp.headers["Last-Modified"] = _cache.file_last_modified_utc(current_app.config["NEWS_JSON"]) or ""
    resp.cache_control.max_age = current_app.config["API_CACHE_TTL"]

    METRICS.increment("api_news")
    return resp


@api_bp.get("/api/weather")
def api_weather():
    try:
        ws = WeatherService(
            api_url=current_app.config["WEATHER_API_URL"],
            api_key=current_app.config["WEATHER_API_KEY"],
            city=current_app.config["WEATHER_CITY"],
        )
        data, etag, last_modified = ws.get_cached_weather(current_app.config["WEATHER_JSON"])
        if not data:
            METRICS.increment("errors")
            return jsonify({"error": "Weather data unavailable"}), 503

        body = json.dumps(data, ensure_ascii=False)
        resp = make_response(body)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        resp.headers["ETag"] = etag or _cache.generate_etag(body)
        resp.headers["Last-Modified"] = last_modified or datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        resp.cache_control.max_age = current_app.config["WEATHER_CACHE_TTL"]

        METRICS.increment("api_weather")
        return resp
    except Exception as e:
        current_app.logger.error("api/weather: %s", e)
        METRICS.increment("errors")
        return jsonify({"error": "Internal server error"}), 500


@api_bp.get("/api/rss")
def api_rss():
    try:
        with open(current_app.config["RSS_XML"], "r", encoding="utf-8") as f:
            xml = f.read()
        resp = make_response(xml)
        resp.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
        resp.headers["ETag"] = _cache.file_etag(current_app.config["RSS_XML"]) or _cache.generate_etag(xml)
        resp.headers["Last-Modified"] = _cache.file_last_modified_utc(current_app.config["RSS_XML"]) or ""
        resp.cache_control.max_age = current_app.config["API_CACHE_TTL"]
        METRICS.increment("api_rss")
        return resp
    except Exception as e:
        current_app.logger.error("api/rss: %s", e)
        METRICS.increment("errors")
        return jsonify({"error": "Internal server error"}), 500


@api_bp.post("/api/theme")
def set_theme():
    try:
        body = request.get_json(silent=True) or {}
        theme = body.get("theme", "auto")
        if theme not in ("light", "dark", "auto"):
            METRICS.increment("errors")
            return jsonify({"error": "Invalid theme"}), 400

        resp = make_response(jsonify({"theme": theme}))
        resp.set_cookie(
            current_app.config["THEME_COOKIE_NAME"],
            theme,
            max_age=current_app.config["THEME_COOKIE_MAX_AGE"],
            secure=True,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        METRICS.increment("api_theme")
        return resp
    except Exception as e:
        current_app.logger.error("api/theme: %s", e)
        METRICS.increment("errors")
        return jsonify({"error": "Internal server error"}), 500


@api_bp.get("/api/health")
def health():
    try:
        snapshot = current_app.metrics.snapshot()
        resp = make_response(json.dumps({"status": "ok", "service": current_app.config["SITE_NAME"], "metrics": snapshot}, ensure_ascii=False))
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        resp.cache_control.max_age = 60
        METRICS.increment("api_health")
        return resp
    except Exception as e:
        current_app.logger.error("api/health: %s", e)
        METRICS.increment("errors")
        return jsonify({"status": "unhealthy"}), 500
