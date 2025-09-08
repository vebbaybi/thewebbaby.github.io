# tests/test_rss_ingest.py

import unittest
import json
import os
from unittest.mock import patch
from tempfile import TemporaryDirectory
from app.services.rss_ingest import RSSIngester
from app.services.schema import NewsItem

class TestRSSIngester(unittest.TestCase):
    def setUp(self):
        self.ingester = RSSIngester(timeout=5, user_agent='TestRSS/1.0')
        self.temp_dir = TemporaryDirectory()
        self.output_path = os.path.join(self.temp_dir.name, 'news.json')
        self.mock_feed = {
            'feed': {'title': 'Test Feed'},
            'entries': [
                {
                    'id': 'entry1',
                    'title': 'Test News',
                    'link': 'https://example.com/news',
                    'published': '2025-09-07T12:00:00Z',
                    'published_parsed': (2025, 9, 7, 12, 0, 0, 0, 250, 0),
                    'summary': 'Test summary'
                }
            ]
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fetch_sources_success(self):
        with patch('feedparser.parse', return_value=self.mock_feed) as mock_parse:
            items = self.ingester.fetch_sources(['https://example.com/rss'], limit_per_source=1)
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertIsInstance(item, NewsItem)
            self.assertEqual(item.id, 'entry1')
            self.assertEqual(item.source, 'Test Feed')
            self.assertEqual(item.title, 'Test News')
            self.assertEqual(item.url, 'https://example.com/news')
            self.assertEqual(item.published_at, '2025-09-07T12:00:00Z')
            self.assertEqual(item.excerpt, 'Test summary')
            self.assertEqual(item.tags, [])
            self.assertIsNone(item.image)
            mock_parse.assert_called_once_with('https://example.com/rss', agent='TestRSS/1.0', timeout=5)

    def test_fetch_sources_empty_feed(self):
        with patch('feedparser.parse', return_value={'feed': {}, 'entries': []}):
            items = self.ingester.fetch_sources(['https://empty.com/rss'])
            self.assertEqual(items, [])

    def test_fetch_sources_error(self):
        with patch('feedparser.parse', side_effect=Exception('Connection error')):
            items = self.ingester.fetch_sources(['https://error.com/rss'])
            self.assertEqual(items, [])

    def test_save_news_json(self):
        items = [NewsItem(
            id='entry1',
            source='Test Feed',
            title='Test News',
            url='https://example.com/news',
            published_at='2025-09-07T12:00:00Z',
            excerpt='Test summary'
        )]
        self.ingester.save_news_json(self.output_path, items)
        with open(self.output_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], 'entry1')
        self.assertEqual(data[0]['title'], 'Test News')

    def test_save_news_json_error(self):
        invalid_path = '/invalid/path/news.json'
        items = [NewsItem(id='entry1', source='Test', title='Test', url='https://example.com', published_at='2025-09-07T12:00:00Z')]
        try:
            self.ingester.save_news_json(invalid_path, items)
        except Exception as e:
            self.assertIn('Error saving news', str(e))

if __name__ == '__main__':
    unittest.main()