# app/services/rss_ingest.py

import json
import logging
import os
import time
from datetime import datetime, timezone
from hashlib import sha1

import feedparser
import requests

from .metrics import METRICS
from .schema import NewsItem

log = logging.getLogger(__name__)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _first_nonempty(*values):
    for v in values:
        if v:
            return v
    return ''


def _entry_timestamp(entry):
    # Prefer parsed timestamps from feedparser; fall back to now
    try:
        if entry.get('published_parsed'):
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.published_parsed)
        if entry.get('updated_parsed'):
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.updated_parsed)
        if entry.get('created_parsed'):
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.created_parsed)
    except Exception:
        pass
    return _now_iso()


def _entry_excerpt(entry):
    txt = _first_nonempty(entry.get('summary'), entry.get('description'), '')
    if not txt:
        return None
    s = str(txt).strip()
    return s[:1024] if s else None


def _entry_image(entry):
    try:
        # Common locations: media_content, media_thumbnail, image hrefs
        media = entry.get('media_content') or entry.get('media_thumbnail')
        if isinstance(media, list) and media:
            url = media[0].get('url') or media[0].get('href')
            if url:
                return str(url)[:2048]
        # Some feeds put images in links array with rel="enclosure"
        for link in entry.get('links', []) or []:
            if (link.get('rel') == 'enclosure') and str(link.get('type', '')).startswith('image/'):
                u = link.get('href')
                if u:
                    return str(u)[:2048]
    except Exception:
        pass
    return None


def _stable_id(source_name, entry):
    # Prefer explicit id/link; otherwise hash key fields
    entry_id = _first_nonempty(entry.get('id'), entry.get('guid'), entry.get('link'))
    if entry_id:
        return str(entry_id)[:256]
    raw = (source_name or '') + '|' + _first_nonempty(entry.get('title'), '') + '|' + _first_nonempty(entry.get('link'), '') + '|' + _entry_timestamp(entry)
    return sha1(raw.encode('utf-8')).hexdigest()


class RSSIngester:
    """Fetches and normalizes RSS/Atom feeds into NewsItem objects with robust HTTP fetching."""
    def __init__(self, timeout=15, user_agent='WebbabyRSS/1.0 (+https://thewebbaby)'):
        self.timeout = int(timeout)
        self.user_agent = str(user_agent)

    def _fetch_bytes(self, url):
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5',
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.content

    def fetch_sources(self, sources, limit_per_source=30):
        """Fetch multiple feeds and return a sorted list of NewsItem objects (newest first)."""
        result = []
        seen_ids = set()
        for url in sources or []:
            try:
                raw = self._fetch_bytes(url)
                feed = feedparser.parse(raw)
                feed_title = _first_nonempty(feed.feed.get('title'), url) if getattr(feed, 'feed', None) else url
                entries = (feed.entries or [])[: int(limit_per_source)]
                METRICS.increment('rss.sources_ok')
                for entry in entries:
                    try:
                        ni = self._normalize_entry(entry, feed_title)
                        if ni.id in seen_ids:
                            continue
                        seen_ids.add(ni.id)
                        result.append(ni)
                        METRICS.increment('rss.items_ok')
                    except Exception as exc:
                        METRICS.increment('rss.items_error')
                        log.error("rss_ingest: entry error from %s: %s", url, exc)
                if not entries:
                    METRICS.increment('rss.sources_empty')
            except Exception as exc:
                METRICS.increment('rss.sources_error')
                log.error("rss_ingest: fetch error for %s: %s", url, exc)

        # Sort using parsed timestamps (schema.NewsItem computes _ts)
        result.sort(key=lambda x: (getattr(x, '_ts', 0.0), x.title), reverse=True)
        return result

    def _normalize_entry(self, entry, source_name):
        title = _first_nonempty(entry.get('title'), '').strip()[:512]
        url = _first_nonempty(entry.get('link'), '').strip()[:2048]
        published = _entry_timestamp(entry)
        excerpt = _entry_excerpt(entry)
        image = _entry_image(entry)
        entry_id = _stable_id(source_name, entry)

        return NewsItem(
            id=entry_id,
            source=str(source_name)[:255],
            title=title,
            url=url,
            published_at=published,
            tags=[],
            excerpt=excerpt,
            image=image
        )

    def save_news_json(self, path, items):
        """Persist NewsItem list to JSON at the given path (creates parent dirs)."""
        try:
            directory = os.path.dirname(os.path.abspath(path))
            if directory and not os.path.isdir(directory):
                os.makedirs(directory, exist_ok=True)
            payload = [it.to_dict() for it in items or []]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            METRICS.increment('rss.saved_ok')
            return True
        except Exception as exc:
            METRICS.increment('rss.saved_error')
            log.error("rss_ingest: save error to %s: %s", path, exc)
            return False
