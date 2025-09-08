# app/routes/pages.py

import os

from flask import Blueprint, current_app, render_template

from ..services.metrics import METRICS

pages_bp = Blueprint("pages", __name__)


def _read_aboutme_txt():
    try:
        path = current_app.config["BASE_DIR"] / "aboutme.txt"
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        current_app.logger.error("about: failed to read aboutme.txt: %s", e)
        return "About text not available."


@pages_bp.app_context_processor
def inject_nav():
    return dict(
        site_name=current_app.config["SITE_NAME"],
        nav_items=[
            {"href": "/", "label": "Home"},
            {"href": "/about", "label": "About"},
            {"href": "/projects", "label": "Projects"},
            {"href": "/cdfe", "label": "CDFE"},
            {"href": "/webbabyguard", "label": "Webbabyguard"},
            {"href": "/puzzle", "label": "Puzzle"},
            {"href": "/contact", "label": "Contact"},
        ],
    )


@pages_bp.route("/")
def home():
    METRICS.increment("page_views_home")
    return render_template("pages/home.html")


@pages_bp.route("/about")
def about():
    content = _read_aboutme_txt()
    METRICS.increment("page_views_about")
    return render_template("pages/about.html", content=content)


@pages_bp.route("/projects")
def projects():
    METRICS.increment("page_views_projects")
    return render_template("pages/projects.html")


@pages_bp.route("/projects/<project_id>")
def project_detail(project_id):
    METRICS.increment("page_views_project_%s" % project_id)
    return render_template("pages/project_detail.html", project_id=project_id)


@pages_bp.route("/skills")
def skills():
    METRICS.increment("page_views_skills")
    return render_template("pages/skills.html")


@pages_bp.route("/resume")
def resume():
    METRICS.increment("page_views_resume")
    return render_template("pages/resume.html")


@pages_bp.route("/cdfe")
def cdfe():
    METRICS.increment("page_views_cdfe")
    return render_template("pages/cdfe.html")


@pages_bp.route("/contact")
def contact():
    METRICS.increment("page_views_contact")
    return render_template("pages/contact.html")
