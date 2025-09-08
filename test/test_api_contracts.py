# tests/test_api_contracts.py

import unittest
import json
from unittest.mock import patch
from flask import Flask
from app import create_app
from app.services.schema import NewsItem

class TestAPIContracts(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.mock_news = [
            NewsItem(
                id='news1',
                source='Test',
                title='Test News',
                url='https://example.com',
                published_at='2025-09-07T12:00:00Z',
                excerpt='Test excerpt'
            ).to_dict()
        ]

    def test_news_api(self):
        with patch('builtins.open', mock_open(read_data=json.dumps(self.mock_news))):
            response = self.client.get('/api/news?page=1')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['id'], 'news1')
            self.assertIn('ETag', response.headers)
            self.assertIn('Last-Modified', response.headers)

    def test_news_api_error(self):
        with patch('builtins.open', side_effect=Exception('File error')):
            response = self.client.get('/api/news')
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.get_json()['error'], 'Internal server error')

    def test_weather_api(self):
        with patch('app.services.weather.WeatherService.get_cached_weather') as mock_weather:
            mock_weather.return_value = (self.mock_news[0], 'etag123', 'Wed, 07 Sep 2025 12:00:00 GMT')
            response = self.client.get('/api/weather')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['id'], 'news1')
            self.assertEqual(response.headers['ETag'], 'etag123')

    def test_weather_api_error(self):
        with patch('app.services.weather.WeatherService.get_cached_weather', return_value=(None, None, None)):
            response = self.client.get('/api/weather')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()['error'], 'Weather data unavailable')

    def test_rss_api(self):
        with patch('builtins.open', mock_open(read_data='<rss>mock</rss>')):
            response = self.client.get('/api/rss')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/rss+xml')
            self.assertEqual(response.data.decode('utf-8'), '<rss>mock</rss>')

    def test_theme_api(self):
        response = self.client.post('/api/theme', json={'theme': 'dark'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['theme'], 'dark')
        self.assertIn('theme=dark', response.headers['Set-Cookie'])

    def test_theme_api_invalid(self):
        response = self.client.post('/api/theme', json={'theme': 'invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'Invalid theme')

    def test_health_api(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('metrics', data)

if __name__ == '__main__':
    unittest.main()