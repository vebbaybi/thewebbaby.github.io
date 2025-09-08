# app/services/schema.py

import logging
from datetime import datetime, timezone
from hashlib import sha1
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)


def _as_str(value, max_len=None, default=''):
    s = '' if value is None else str(value)
    if max_len is not None and len(s) > max_len:
        return s[:max_len]
    return s if s else default


def _normalize_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = [t.strip() for t in tags.split(',')]
    elif isinstance(tags, (list, tuple, set)):
        raw = [str(t).strip() for t in tags]
    else:
        return []

    seen = set()
    out = []
    for t in raw:
        if not t:
            continue
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _parse_datetime(dt_str):
    """
    Try multiple common datetime formats and return (datetime, iso_string).
    Falls back to None if parsing fails.
    """
    s = _as_str(dt_str).strip()
    if not s:
        return None, None

    # Try strict ISO-8601 first (Python 3.11 handles many variants).
    try:
        d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d, d.isoformat()
    except Exception:
        pass

    # Try RFC 2822 / RSS pubDate
    try:
        d = parsedate_to_datetime(s)
        if d is not None:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d, d.isoformat()
    except Exception:
        pass

    # Try a couple of common strptime patterns (lenient fallback)
    fmts = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in fmts:
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d, d.isoformat()
        except Exception:
            continue

    return None, None


def _valid_url(u):
    s = _as_str(u)
    if not s:
        return ''
    try:
        p = urlparse(s)
        if p.scheme in ('http', 'https') and p.netloc:
            return s
    except Exception:
        pass
    return ''


def _stable_id(source, title, url, published_iso, fallback):
    base = (source or '') + '|' + (title or '') + '|' + (url or '') + '|' + (published_iso or '')
    digest = sha1(base.encode('utf-8')).hexdigest()
    return fallback or digest


class NewsItem:
    """
    Represents a news item with standardized fields for RSS and bulletins.
    - Ensures normalized strings and lengths
    - Validates/normalizes published_at to ISO-8601 (UTC) when possible
    - Ensures tags are lowercase, unique, and ordered by first appearance
    - Provides deterministic id when missing
    """
    __slots__ = (
        'id', 'source', 'title', 'url', 'published_at',
        'tags', 'excerpt', 'image', '_ts'
    )

    def __init__(self, id, source, title, url, published_at, tags=None, excerpt=None, image=None):
        # Normalize core fields
        self.source = _as_str(source, 255)
        self.title = _as_str(title, 512)
        self.url = _valid_url(url)[:2048]
        self.excerpt = _as_str(excerpt, 1024, default=None) if excerpt is not None else None
        self.image = _valid_url(image)[:2048] if image else None
        self.tags = _normalize_tags(tags)

        # Datetime normalization
        dt, iso = _parse_datetime(published_at)
        if iso:
            self.published_at = _as_str(iso, 64)
            try:
                self._ts = dt.timestamp()
            except Exception:
                self._ts = 0.0
        else:
            # Keep the original string (trimmed) to avoid data loss; but sorting will push unknowns last
            raw = _as_str(published_at, 64)
            self.published_at = raw
            self._ts = 0.0

        # Deterministic ID (fallback to hash when missing/empty)
        fallback_id = _stable_id(self.source, self.title, self.url, self.published_at, '')
        self.id = _as_str(id) or fallback_id

    def to_dict(self):
        """Convert NewsItem to a dictionary for JSON serialization."""
        return {
            'id': self.id,
            'source': self.source,
            'title': self.title,
            'url': self.url,
            'published_at': self.published_at,
            'tags': self.tags,
            'excerpt': self.excerpt,
            'image': self.image
        }

    @classmethod
    def from_dict(cls, data):
        """Strict constructor from a dict-like object."""
        if data is None:
            raise ValueError("NewsItem.from_dict received None")
        get = data.get
        return cls(
            id=get('id', ''),
            source=get('source', ''),
            title=get('title', ''),
            url=get('url', ''),
            published_at=get('published_at', ''),
            tags=get('tags', []),
            excerpt=get('excerpt'),
            image=get('image')
        )

    def __repr__(self):
        return f"<NewsItem id={self.id!s} source={self.source!s} title={self.title!s}>"

    def __eq__(self, other):
        if not isinstance(other, NewsItem):
            return False
        return self.id == other.id


def coerce_news_list(items):
    """
    Convert an iterable of dictionaries or NewsItem objects into a list of NewsItem,
    sorted newest-first by published_at (using parsed timestamps; unparsable dates sort last).
    Invalid entries are skipped with an error logged.
    """
    if not items:
        return []

    result = []
    for idx, item in enumerate(items):
        try:
            if isinstance(item, NewsItem):
                ni = item
            else:
                ni = NewsItem.from_dict(item)
            # Drop entries missing both title and url (likely useless/broken)
            if not ni.title and not ni.url:
                log.warning("Dropping news item with no title and no url at index %s", idx)
                continue
            result.append(ni)
        except Exception as exc:
            log.error("Error coercing news item at index %s: %s", idx, exc)
            continue

    # Sort by parsed timestamp desc, then by title to stabilize order
    result.sort(key=lambda x: (x._ts, x.title), reverse=True)
    return result
