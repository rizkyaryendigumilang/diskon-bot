# test_app.py — Automated Unit & Integration Tests for DiskonBot
import os
import unittest
import sqlite3
from starlette.testclient import TestClient

# Import application modules
import config
import database
import converter
from server import app

class TestConverter(unittest.TestCase):
    def test_shopee_long_url_conversion(self):
        url = "https://shopee.co.id/Kaos-Pria-Keren-i.12345.67890"
        result = converter.process_single_link(url)
        self.assertIn("d_id=", result)
        self.assertIn("12345", result)
        self.assertIn("67890", result)

    def test_shopee_product_path_url(self):
        url = "https://shopee.co.id/product/98765/43210"
        result = converter.process_single_link(url)
        self.assertIn("d_id=", result)
        self.assertIn("98765", result)
        self.assertIn("43210", result)

    def test_shortlink_passthrough(self):
        shortlink = "https://s.shopee.co.id/xyz123"
        result = converter.process_single_link(shortlink)
        self.assertEqual(result, shortlink)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        database.init_db()

    def test_settings_retrieval_and_update(self):
        initial = database.get_settings()
        self.assertIn("category", initial)
        self.assertIn("min_discount", initial)
        self.assertIn("interval", initial)

        # Update settings
        database.update_all_settings(category="elektronik", min_discount=30, interval=45, is_paused=0)
        updated = database.get_settings()
        self.assertEqual(updated["category"], "elektronik")
        self.assertEqual(updated["min_discount"], 30)
        self.assertEqual(updated["interval"], 45)
        self.assertEqual(updated["is_paused"], 0)

        # Restore
        database.update_all_settings(category=initial["category"], min_discount=initial["min_discount"], interval=initial["interval"], is_paused=initial["is_paused"])

    def test_posted_items_lifecycle(self):
        test_id = "test_item_unit_12345"
        database.mark_item_posted(test_id, title="Unit Test Product")
        
        # Verify item exists in query
        items = database.get_all_posted_items(limit=10, search="Unit Test Product")
        matching = [it for it in items if it.get("product_id") == test_id]
        self.assertTrue(len(matching) > 0)

        # Cleanup
        deleted = database.delete_posted_item(test_id)
        self.assertTrue(deleted)

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dashboard_html_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Affiliate Bot Engine", response.text)

    def test_engine_status_endpoint(self):
        response = self.client.get("/api/engine/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("engine", data)
        self.assertIn("settings", data)
        self.assertIn("stats", data)

    def test_auth_login_valid_telegram_id(self):
        response = self.client.post("/api/auth/login", json={"username_or_id": "8503838227", "password": ""})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("token", data)

    def test_auth_login_invalid(self):
        response = self.client.post("/api/auth/login", json={"username_or_id": "invalid_user", "password": "wrong_password"})
        self.assertEqual(response.status_code, 401)

    def test_convert_endpoint(self):
        response = self.client.post("/api/convert", json={"url": "https://shopee.co.id/product/1111/2222"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("d_id=", data.get("affiliate_url", ""))

    def test_items_list_endpoint(self):
        response = self.client.get("/api/items?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertIn("total", data)

if __name__ == "__main__":
    unittest.main()
