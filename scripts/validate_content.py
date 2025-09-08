#!/usr/bin/env python3
# scripts/validate_content.py

import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path for imports
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from app.services.content import Bulletin, load_bulletins
from app.services.metrics import METRICS
from app.services.schema import NewsItem

log = logging.getLogger("validate_content")


def _valid_url(u):
    try:
        s = str(u or "").strip()
        if not s:
            return False
        p = urlparse(s)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


class ContentValidator:
    """Validates content files like bulletins.yaml against schemas and rules."""

    def __init__(self, bulletins_path):
        self.bulletins_path = bulletins_path
        self.errors = []

    def validate_bulletins(self):
        """Validate bulletins.yaml for schema compliance and content rules.

        Returns:
            Boolean indicating if validation passed (no errors).
        """
        self.errors = []
        if not os.path.isfile(self.bulletins_path):
            msg = "Bulletins file not found: %s" % self.bulletins_path
            self.errors.append(msg)
            log.error(msg)
            METRICS.increment("content.bulletins_missing")
            return False

        try:
            bulletins = load_bulletins(self.bulletins_path)
            METRICS.increment("content.bulletins_loaded")
        except Exception as e:
            msg = "Error loading bulletins: %s" % e
            self.errors.append(msg)
            log.error(msg)
            METRICS.increment("content.bulletins_load_error")
            return False

        for b in bulletins:
            if not isinstance(b, Bulletin):
                msg = "Invalid bulletin object: %r" % b
                self.errors.append(msg)
                log.error(msg)
                METRICS.increment("content.bulletin_invalid")
                continue
            self._validate_bulletin(b)
            self._validate_bulletin_as_news_item(b)

        ok = len(self.errors) == 0
        METRICS.increment("content.bulletins_ok" if ok else "content.bulletins_error")
        return ok

    def _validate_bulletin(self, bulletin):
        """Validate a single Bulletin object for required fields and formats."""
        if not bulletin.id:
            self._err("Bulletin missing id: %s" % bulletin.title)
        if not bulletin.title:
            self._err("Bulletin missing title: %s" % bulletin.id)
        if not bulletin.date or not self._is_valid_date(bulletin.date):
            self._err("Bulletin invalid date '%s' in %s" % (bulletin.date, bulletin.id))
        if not bulletin.body_md:
            self._err("Bulletin missing body_md: %s" % bulletin.id)
        if bulletin.tags and not all(isinstance(tag, str) and tag.strip() for tag in bulletin.tags):
            self._err("Bulletin invalid tags in %s: %r" % (bulletin.id, bulletin.tags))
        if bulletin.links:
            for link in bulletin.links:
                if not isinstance(link, dict):
                    self._err("Bulletin link is not a dict in %s: %r" % (bulletin.id, link))
                    continue
                href = link.get("href")
                if not _valid_url(href):
                    self._err("Bulletin invalid link href in %s: %r" % (bulletin.id, href))

    def _validate_bulletin_as_news_item(self, bulletin):
        """Validate that a Bulletin can be converted to a NewsItem."""
        try:
            news_item = bulletin.to_news_item()
            if not isinstance(news_item, NewsItem):
                self._err("Bulletin failed NewsItem conversion: %s" % bulletin.id)
                return
            if not news_item.id:
                self._err("NewsItem from bulletin missing id: %s" % bulletin.id)
            if not news_item.title:
                self._err("NewsItem from bulletin missing title: %s" % bulletin.id)
            pub = news_item.published_at or ""
            if not pub or not self._is_valid_date(pub[:10]):
                self._err("NewsItem from bulletin invalid published_at: %s" % bulletin.id)
        except Exception as e:
            self._err("Error converting bulletin to NewsItem %s: %s" % (bulletin.id, e))

    def _is_valid_date(self, date_str):
        """Check if a date string is in YYYY-MM-DD format."""
        try:
            if len(date_str) < 10:
                return False
            year, month, day = map(int, date_str[:10].split("-"))
            if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 9999):
                return False
            return True
        except Exception:
            return False

    def _err(self, msg):
        self.errors.append(msg)
        log.error(msg)

    def report(self):
        """Print validation results to stdout."""
        if not self.errors:
            print("Content validation passed.")
        else:
            print("Content validation failed with the following errors:")
            for error in self.errors:
                print(" - %s" % error)


def main():
    """Run content validation for bulletins.yaml."""
    cfg = None
    try:
        from app.config import Config
        cfg = Config()
        bulletins_path = cfg.BULLETINS_YAML
    except Exception:
        bulletins_path = str(REPO / "data" / "bulletins.yaml")

    # basic logging to stderr
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    validator = ContentValidator(bulletins_path)
    success = validator.validate_bulletins()
    validator.report()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
