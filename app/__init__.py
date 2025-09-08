# app/__init__.py

import logging
import os
from datetime import datetime, timezone

from flask import Flask, g, render_template, request

from .config import Config
from .routes import register_blueprints
from .services.metrics import METRICS


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Load config object (Flask will copy UPPERCASE attributes into app.config)
    cfg = Config()
    app.config.from_object(cfg)

    # Attach shared metrics singleton for convenience
    app.metrics = METRICS
    app.metrics.increment("app_starts")

    # Ensure data dir exists
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    # Basic logging if none configured
    if not app.logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # ---- Security headers ----
    @app.after_request
    def set_security_headers(response):
        try:
            csp = (
                "default-src 'self'; "
                "img-src 'self' data: https://*.openweathermap.org; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https://api.openweathermap.org; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            response.headers["Content-Security-Policy"] = csp
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        except Exception as e:
            app.logger.error("Error setting security headers: %s", e)
        return response

    # ---- Request timing ----
    @app.before_request
    def start_timer():
        g._t0 = datetime.now(timezone.utc)

    @app.after_request
    def record_timing(response):
        try:
            t0 = getattr(g, "_t0", None)
            if t0:
                dt_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000.0
                response.headers["Server-Timing"] = "app;dur=%.1f" % dt_ms
                app.metrics.increment("requests")
                app.metrics.increment("requests_%s" % request.method.lower())
        except Exception as e:
            app.logger.error("Error recording request timing: %s", e)
        return response

    # ---- Error handlers (render templates, not static files) ----
    @app.errorhandler(403)
    def forbidden(error):
        app.metrics.increment("errors_403")
        return render_template("pages/error_403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        app.metrics.increment("errors_404")
        return render_template("pages/error_404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.metrics.increment("errors_500")
        return render_template("pages/error_500.html"), 500

    # ---- Blueprints ----
    try:
        register_blueprints(app)
    except Exception as e:
        app.logger.error("Error registering blueprints: %s", e)

    return app
