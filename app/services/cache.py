# app/services/cache.py

import hashlib
import logging
import os
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

log = logging.getLogger(__name__)


def _rfc7231(dt):
    """
    Format a datetime in RFC 7231 (HTTP-date) format, always GMT.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return format_datetime(dt, usegmt=True)


class CacheManager:
    """
    Manages caching utilities like ETags and Last-Modified headers.
    - Streaming file hashing to avoid large memory usage
    - RFC 7231 compliant Last-Modified formatting
    - Helpers for conditional requests (If-None-Match / If-Modified-Since)
    """

    @staticmethod
    def generate_etag(content, weak=False):
        """
        Generate a hex SHA-256 ETag for the given content.

        Args:
            content: bytes or str
            weak: if True, mark as weak validator (prefix 'W/'). Note: header quoting is the caller's responsibility.

        Returns:
            String ETag (hex digest), optionally prefixed with 'W/'.
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        if not isinstance(content, bytes):
            raise ValueError('Content must be bytes or string')

        digest = hashlib.sha256(content).hexdigest()
        return ('W/' + digest) if weak else digest

    @staticmethod
    def file_etag(path, chunk_size=65536, weak=False):
        """
        Generate an ETag for a file's content by streaming the file.

        Args:
            path: filesystem path
            chunk_size: read size in bytes
            weak: if True, prefix with 'W/'

        Returns:
            hex digest string or None on error.
        """
        if not os.path.isfile(path):
            log.warning("file_etag: file not found: %s", path)
            return None
        try:
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    h.update(chunk)
            digest = h.hexdigest()
            return ('W/' + digest) if weak else digest
        except Exception as exc:
            log.error("file_etag: error hashing %s: %s", path, exc)
            return None

    @staticmethod
    def file_last_modified_utc(path):
        """
        Get the last modified time of a file in RFC 7231 format (GMT).

        Args:
            path: filesystem path

        Returns:
            RFC 7231 string or None if not found/error.
        """
        if not os.path.isfile(path):
            log.warning("file_last_modified_utc: not found: %s", path)
            return None
        try:
            mtime = os.path.getmtime(path)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            return _rfc7231(dt)
        except Exception as exc:
            log.error("file_last_modified_utc: error for %s: %s", path, exc)
            return None

    @staticmethod
    def parse_http_datetime(http_date):
        """
        Parse HTTP-date (RFC 7231) to aware datetime UTC.

        Returns:
            datetime or None on failure.
        """
        if not http_date:
            return None
        try:
            dt = parsedate_to_datetime(str(http_date))
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        except Exception:
            return None

    @staticmethod
    def check_not_modified(if_none_match, if_modified_since, current_etag, last_modified_http):
        """
        Evaluate conditional request headers.

        Args:
            if_none_match: raw header value (can contain multiple ETags)
            if_modified_since: raw header value (HTTP-date)
            current_etag: current entity tag (same format as set in response, without quotes)
            last_modified_http: current Last-Modified as RFC 7231 string

        Returns:
            True if the response can be 304 Not Modified, else False.
        """
        # ETag precedence (strong/weak comparison is simplistic here: compares raw token equalities)
        if if_none_match:
            # Header can be "*" or a list of comma-separated quoted tags; we accept bare hex or quoted.
            tokens = [t.strip() for t in str(if_none_match).split(',')]
            for tok in tokens:
                tok_unquoted = tok.strip().strip('"')
                if tok_unquoted == '*' or tok_unquoted == str(current_etag).strip().strip('"'):
                    return True

        # If-Modified-Since (only applies when ETag didn't match above)
        if if_modified_since and last_modified_http:
            since_dt = CacheManager.parse_http_datetime(if_modified_since)
            last_dt = CacheManager.parse_http_datetime(last_modified_http)
            if since_dt and last_dt and last_dt <= since_dt:
                return True

        return False
