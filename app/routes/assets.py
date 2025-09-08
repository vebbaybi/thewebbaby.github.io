# app/routes/assets.py

from flask import Blueprint, send_from_directory, current_app, make_response, render_template

from ..services.cache import CacheManager
from ..services.metrics import METRICS

assets_bp = Blueprint("assets", __name__)
_cache = CacheManager()


@assets_bp.get("/robots.txt")
def robots():
    try:
        resp = make_response(render_template("seo/robots.txt.j2"))
        resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        METRICS.increment("assets_robots")
        return resp
    except Exception as e:
        current_app.logger.error("assets/robots: %s", e)
        METRICS.increment("errors")
        return "", 404


@assets_bp.get("/sitemap.xml")
def sitemap():
    try:
        pages = [
            {"url": current_app.config["BASE_URL"], "priority": "1.0"},
            {"url": current_app.config["BASE_URL"] + "/about", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/projects", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/skills", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/resume", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/cdfe", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/contact", "priority": "0.8"},
            {"url": current_app.config["BASE_URL"] + "/webbabyguard", "priority": "0.9"},
            {"url": current_app.config["BASE_URL"] + "/puzzle", "priority": "0.7"},
        ]
        resp = make_response(render_template("seo/sitemap.xml.j2", pages=pages))
        resp.headers["Content-Type"] = "application/xml; charset=utf-8"
        resp.headers["ETag"] = _cache.generate_etag(str(pages))
        METRICS.increment("assets_sitemap")
        return resp
    except Exception as e:
        current_app.logger.error("assets/sitemap: %s", e)
        METRICS.increment("errors")
        return "", 500


@assets_bp.get("/favicon.ico")
def favicon():
    try:
        icon_dir = current_app.config["STATIC_DIR"] / "img" / "favicons"
        resp = send_from_directory(icon_dir, "favicon.ico")
        resp.headers["ETag"] = _cache.file_etag(icon_dir / "favicon.ico") or ""
        resp.headers["Last-Modified"] = _cache.file_last_modified_utc(icon_dir / "favicon.ico") or ""
        METRICS.increment("assets_favicon")
        return resp
    except Exception as e:
        current_app.logger.error("assets/favicon: %s", e)
        METRICS.increment("errors")
        return "", 404
