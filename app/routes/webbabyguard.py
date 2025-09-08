# app/routes/webbabyguard.py

import json

from flask import (Blueprint, current_app, make_response, render_template,
                   request)

from ..services.cache import CacheManager
from ..services.content import load_bulletins
from ..services.metrics import METRICS
from ..services.schema import NewsItem, coerce_news_list

webbabyguard_bp = Blueprint("webbabyguard", __name__)
_cache = CacheManager()


def _load_news_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or []
            return data
    except Exception as e:
        current_app.logger.error("webbabyguard: failed reading news.json: %s", e)
        return []


@webbabyguard_bp.route("/webbabyguard")
def webbabyguard():
    try:
        # Load bulletins and convert to NewsItem objects
        bulletins = load_bulletins(current_app.config["BULLETINS_YAML"])
        b_items = []
        for bulletin in bulletins:
            # Convert each bulletin to NewsItem using the imported class
            news_item = NewsItem(
                id=bulletin.get('id', ''),
                source=bulletin.get('source', ''),
                title=bulletin.get('title', ''),
                url=bulletin.get('url', ''),
                published_at=bulletin.get('published_at', ''),
                tags=bulletin.get('tags', []),
                excerpt=bulletin.get('excerpt', ''),
                image=bulletin.get('image', '')
            )
            b_items.append(news_item)

        # Load and process news JSON into NewsItem objects
        raw_news = _load_news_json(current_app.config["NEWS_JSON"])
        n_items = coerce_news_list(raw_news)  # This returns NewsItem objects

        # Combine and sort all NewsItem objects
        items = b_items + n_items
        items.sort(key=lambda x: getattr(x, "_ts", 0.0), reverse=True)

        # Pagination
        page = int(request.args.get("page", 1))
        page_size = current_app.config["NEWS_PAGE_SIZE"]
        start = (page - 1) * page_size
        end = start + page_size
        total_pages = max(1, (len(items) + page_size - 1) // page_size)
        page_items = items[start:end]

        # Generate ETag from NewsItem data
        payload_for_etag = json.dumps([item.to_dict() for item in page_items], ensure_ascii=False)
        resp = make_response(render_template("pages/webbabyguard.html", 
                                           items=page_items, 
                                           page=page, 
                                           total_pages=total_pages))
        resp.headers["ETag"] = _cache.generate_etag(payload_for_etag)
        
        # Last-Modified headers
        lm_bul = _cache.file_last_modified_utc(current_app.config["BULLETINS_YAML"])
        lm_news = _cache.file_last_modified_utc(current_app.config["NEWS_JSON"])
        resp.headers["Last-Modified"] = lm_bul or lm_news or ""
        
        METRICS.increment("page_views_webbabyguard")
        return resp
        
    except Exception as e:
        current_app.logger.error("webbabyguard: render error: %s", e)
        METRICS.increment("errors")
        return render_template("pages/error_500.html"), 500