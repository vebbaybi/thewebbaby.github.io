# app/routes/__init__.py

from flask import Flask

from .api import api_bp
from .assets import assets_bp
from .pages import pages_bp
from .puzzle import puzzle_bp
from .webbabyguard import webbabyguard_bp


def register_blueprints(app):
    app.register_blueprint(pages_bp)
    app.register_blueprint(webbabyguard_bp)
    app.register_blueprint(puzzle_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(assets_bp)
