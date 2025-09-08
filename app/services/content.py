# app/services/content.py

import os
import html_sanitizer
import yaml
from .schema import NewsItem


class Bulletin:
    """Represents a bulletin from bulletins.yaml with sanitized content."""
    __slots__ = ('id', 'title', 'date', 'body_md', 'tags', 'links')

    def __init__(self, id, title, date, body_md, tags=None, links=None):
        self.id = str(id or '')[:128]
        self.title = str(title or '')[:512]
        self.date = str(date or '')[:10]  # YYYY-MM-DD
        self.body_md = str(body_md or '')[:1048576]  # 1MB limit
        self.tags = tags if isinstance(tags, list) else []
        self.links = links if isinstance(links, list) else []

    def to_news_item(self):
        """Convert Bulletin to a NewsItem for RSS or news feed integration."""
        excerpt = (self.body_md.strip().splitlines()[0][:240] if self.body_md else '')
        return NewsItem(
            id=self.id,
            source='webbabyguard',
            title=self.title,
            url='',
            published_at=f'{self.date}T00:00:00Z' if self.date else '',
            tags=self.tags,
            excerpt=excerpt,
            image=None
        )

    def to_dict(self):
        """Convert Bulletin to a dictionary for serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date,
            'body_md': self.body_md,
            'tags': self.tags,
            'links': self.links
        }


# Configure sanitizer
_sanitizer = html_sanitizer.Sanitizer({
    "tags": {"p", "br", "ul", "ol", "li", "strong", "em", "code", "pre", "a"},
    "attributes": {"a": ("href", "title", "rel", "target")},
    "empty": {"br"},
    "separate": {"a", "p", "li"},
    "whitespace": {"br"},
})


def load_bulletins(path):
    """Load and sanitize bulletins from a YAML file.

    Args:
        path: Path to bulletins.yaml file.

    Returns:
        List of Bulletin objects, sorted newest first by date.
    """
    if not os.path.isfile(path):
        print(f"Bulletins file not found: {path}")
        return []

    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file) or []
    except Exception as e:
        print(f"Error loading bulletins from {path}: {e}")
        return []

    result = []
    for item in data:
        try:
            body_md = _sanitizer.sanitize(item.get('body_md', '') or '')
            result.append(Bulletin(
                id=item.get('id', ''),
                title=item.get('title', ''),
                date=item.get('date', ''),
                body_md=body_md,
                tags=item.get('tags', []),
                links=item.get('links', [])
            ))
        except Exception as e:
            print(f"Error processing bulletin {item.get('id', 'unknown')}: {e}")
            continue

    return sorted(result, key=lambda x: x.date, reverse=True)
