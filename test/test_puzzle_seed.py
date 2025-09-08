# tests/test_puzzle_seed.py

import unittest
import os
from unittest.mock import patch, MagicMock
from flask import Flask
from app import create_app

class TestPuzzleSeed(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.mock_images = ['image1.webp', 'image2.jpg']

    def test_puzzle_route(self):
        with patch('os.listdir', return_value=self.mock_images):
            with patch('os.path.isdir', return_value=True):
                response = self.client.get('/puzzle')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'image1.webp', response.data)
                self.assertIn(b'image2.jpg', response.data)
                self.assertIn('ETag', response.headers)
                self.assertIn('Last-Modified', response.headers)

    def test_puzzle_route_empty_dir(self):
        with patch('os.listdir', return_value=[]):
            with patch('os.path.isdir', return_value=True):
                response = self.client.get('/puzzle')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'puzzle.html', response.data)

    def test_puzzle_route_error(self):
        with patch('os.listdir', side_effect=Exception('Dir error')):
            response = self.client.get('/puzzle')
            self.assertEqual(response.status_code, 500)
            self.assertIn(b'error_500.html', response.data)

if __name__ == '__main__':
    unittest.main()