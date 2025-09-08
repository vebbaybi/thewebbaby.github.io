# tests/test_weather.py

import unittest
import json
import os
from unittest.mock import patch
from tempfile import TemporaryDirectory
from app.services.weather import WeatherService
from app.services.cache import CacheManager

class TestWeatherService(unittest.TestCase):
    def setUp(self):
        self.service = WeatherService(
            api_url='https://api.example.com/weather',
            api_key='test_key',
            city='Test City',
            timeout=5
        )
        self.temp_dir = TemporaryDirectory()
        self.output_path = os.path.join(self.temp_dir.name, 'weather.json')
        self.mock_response = {
            'main': {'temp': 20.5},
            'weather': [{'description': 'clear sky', 'icon': '01d'}]
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fetch_weather_success(self):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.mock_response
            mock_get.return_value.raise_for_status.return_value = None
            data = self.service.fetch_weather()
            self.assertIsNotNone(data)
            self.assertEqual(data['source'], 'weather')
            self.assertEqual(data['title'].split(': ')[1].split(', ')[0], '20.5°C')
            self.assertEqual(data['excerpt'], 'Clear sky')
            self.assertTrue(data['image'].endswith('01d.png'))
            mock_get.assert_called_once()

    def test_fetch_weather_error(self):
        with patch('requests.get', side_effect=Exception('API error')):
            data = self.service.fetch_weather()
            self.assertIsNone(data)

    def test_save_weather_json(self):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.mock_response
            mock_get.return_value.raise_for_status.return_value = None
            success = self.service.save_weather_json(self.output_path)
            self.assertTrue(success)
            with open(self.output_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            self.assertEqual(data['source'], 'weather')
            self.assertEqual(data['title'].split(': ')[1].split(', ')[0], '20.5°C')

    def test_get_cached_weather(self):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.mock_response
            mock_get.return_value.raise_for_status.return_value = None
            self.service.save_weather_json(self.output_path)
            data, etag, last_modified = self.service.get_cached_weather(self.output_path)
            self.assertIsNotNone(data)
            self.assertIsNotNone(etag)
            self.assertIsNotNone(last_modified)
            self.assertEqual(data['source'], 'weather')

    def test_get_cached_weather_missing_file(self):
        data, etag, last_modified = self.service.get_cached_weather('/invalid/path.json')
        self.assertIsNone(data)
        self.assertIsNone(etag)
        self.assertIsNone(last_modified)

if __name__ == '__main__':
    unittest.main()