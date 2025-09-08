# app/routes/puzzle.py

import json
import os
import random

from flask import (Blueprint, current_app, make_response, render_template,
                   request)

from ..services.cache import CacheManager
from ..services.metrics import METRICS

puzzle_bp = Blueprint("puzzle", __name__)
_cache = CacheManager()


def _manifest_path():
    return current_app.config["DATA_DIR"] / "playme" / "manifest.json"


def _load_manifest():
    path = _manifest_path()
    try:
        if not os.path.isfile(path):
            return {"images": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {"images": []}
    except Exception as e:
        current_app.logger.error("puzzle: failed to load manifest: %s", e)
        return {"images": []}


@puzzle_bp.route("/puzzle")
def puzzle():
    try:
        manifest = _load_manifest()
        images = manifest.get("images", [])
        seed = request.cookies.get("puzzle_seed")
        if not seed:
            chosen = images[random.randrange(len(images))]["file"] if images else ""
            resp = make_response(render_template("pages/puzzle.html", seed=chosen))
            resp.set_cookie("puzzle_seed", chosen, max_age=current_app.config["THEME_COOKIE_MAX_AGE"], secure=True, samesite="Lax", httponly=True, path="/puzzle")
        else:
            resp = make_response(render_template("pages/puzzle.html", seed=seed))

        et_payload = json.dumps(images, ensure_ascii=False)
        resp.headers["ETag"] = _cache.generate_etag(et_payload)
        resp.headers["Last-Modified"] = _cache.file_last_modified_utc(_manifest_path()) or ""
        METRICS.increment("page_views_puzzle")
        return resp
    except Exception as e:
        current_app.logger.error("puzzle: render error: %s", e)
        METRICS.increment("errors")
        return render_template("pages/error_500.html"), 500
