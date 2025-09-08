# app/services/rss_build.py

import logging
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape

from .content import Bulletin
from .metrics import METRICS
from .schema import NewsItem

log = logging.getLogger(__name__)


def _to_rfc2822(dt_str_or_iso):
    # Accept ISO-8601 or already RFC strings; convert to RFC 2822 (pubDate)
    if not dt_str_or_iso:
        return ''
    s = str(dt_str_or_iso)
    try:
        # Try ISO-8601
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return format_datetime(dt, usegmt=True)
    except Exception:
        # If it's already a HTTP/RFC style, keep as-is but escape downstream
        return s


def _now_rfc2822():
    dt = datetime.now(timezone.utc)
    return format_datetime(dt, usegmt=True)


class RSSBuilder:
    """Builds RSS 2.0 XML from bulletins and news items with proper channel metadata."""
    def __init__(self, base_url, site_name):
        self.base_url = str(base_url or '').rstrip('/')
        self.site_name = str(site_name or '')[:255]

    def build_rss_xml(self, bulletins, news_items):
        """Generate RSS 2.0 XML string. Returns '' on error."""
        try:
            items_xml = []

            for bulletin in bulletins or []:
                if not isinstance(bulletin, Bulletin):
                    METRICS.increment('rss.build.bulletin_invalid')
                    log.warning("rss_build: invalid bulletin: %r", bulletin)
                    continue
                items_xml.append(self._build_item(
                    title=bulletin.title,
                    link=self.base_url + '/webbabyguard',
                    guid=bulletin.id,
                    description=(bulletin.body_md or '')[:500],
                    pub_date=_to_rfc2822(f"{bulletin.date}T00:00:00Z" if bulletin.date else '')
                ))

            for ni in news_items or []:
                if not isinstance(ni, NewsItem):
                    METRICS.increment('rss.build.item_invalid')
                    log.warning("rss_build: invalid news item: %r", ni)
                    continue
                items_xml.append(self._build_item(
                    title=ni.title,
                    link=ni.url,
                    guid=ni.id,
                    description=(ni.excerpt or '')[:500],
                    pub_date=_to_rfc2822(ni.published_at)
                ))

            channel_title = f"{self.site_name} — Webbabyguard"
            channel_link = self.base_url + '/webbabyguard'
            last_build = _now_rfc2822()

            xml = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<rss version="2.0">',
                '<channel>',
                f'<title>{escape(channel_title)}</title>',
                f'<link>{escape(channel_link)}</link>',
                '<description>Curated tech and project bulletins</description>',
                f'<lastBuildDate>{escape(last_build)}</lastBuildDate>',
            ]
            xml.extend(items_xml)
            xml.append('</channel>')
            xml.append('</rss>')
            METRICS.increment('rss.build_ok')
            return '\n'.join(xml)
        except Exception as exc:
            METRICS.increment('rss.build_error')
            log.error("rss_build: build error: %s", exc)
            return ''

    def _build_item(self, title, link, guid, description, pub_date):
        return (
            '<item>\n'
            f'<title>{escape(str(title)[:512])}</title>\n'
            f'<link>{escape(str(link)[:2048])}</link>\n'
            f'<guid isPermaLink="false">{escape(str(guid)[:128])}</guid>\n'
            f'<description>{escape(str(description)[:500])}</description>\n'
            f'<pubDate>{escape(str(pub_date)[:64])}</pubDate>\n'
            '</item>'
        )
