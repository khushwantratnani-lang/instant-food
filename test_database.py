"""Tests for the database layer. Run with:  python -m unittest -v

These run against your real MySQL server but only touch a separate database
called instant_food_test, which is created and removed automatically.
"""
import unittest

import database as db

TEST_DB = "instant_food_test"


class DatabaseTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        conn = db.connect(TEST_DB)
        db._run(conn, "DROP DATABASE IF EXISTS `{}`".format(TEST_DB))
        conn.close()

    def setUp(self):
        self.conn = db.connect(TEST_DB)
        for table in ("order_items", "orders", "menu_items", "admins"):
            db._run(self.conn, "DROP TABLE IF EXISTS " + table)
        db.init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def cola(self):
        return db._one(self.conn, "SELECT * FROM menu_items WHERE name = 'Cola'")

    def test_init_is_repeatable(self):
        db.init_db(self.conn)
        db.init_db(self.conn)
        self.assertEqual(len(db.get_menu(self.conn)), len(db.SEED_MENU))

    def test_menu_filters_and_order(self):
        menu = db.get_menu(self.conn)
        self.assertEqual(menu[0]["category"], "Starters")
        self.assertEqual(menu[-1]["category"], "Drinks")
        drinks = db.get_menu(self.conn, "Drinks")
        self.assertTrue(drinks and all(r["category"] == "Drinks" for r in drinks))
        self.assertEqual([r["name"] for r in db.get_menu(self.conn, search="burger")], ["Beef Burger"])

    def test_search_is_safe_against_injection_and_wildcards(self):
        self.assertEqual(db.get_menu(self.conn, search="'; DROP TABLE menu_items; --"), [])
        self.assertEqual(len(db.get_menu(self.conn)), len(db.SEED_MENU))
        self.assertEqual(db.get_menu(self.conn, search="%"), [])

    def test_admin_login(self):
        self.assertTrue(db.check_admin(self.conn, "admin", "admin123"))
        self.assertFalse(db.check_admin(self.conn, "admin", "wrong"))
        self.assertFalse(db.check_admin(self.conn, "nobody", "admin123"))
        self.assertFalse(db.check_admin(self.conn, "admin", ""))

    def test_password_is_not_stored_in_plain_text(self):
        row = db._one(self.conn, "SELECT * FROM admins")
        self.assertNotIn(b"admin123", bytes(row["password_hash"]))

    def test_changing_admin_password(self):
        db.add_admin(self.conn, "admin", "newpass99")
        self.assertTrue(db.check_admin(self.conn, "admin", "newpass99"))
        self.assertFalse(db.check_admin(self.conn, "admin", "admin123"))

    def test_add_edit_hide_delete_menu_item(self):
        db.add_menu_item(self.conn, "Test Dish", "Mains", 999, "desc")
        item = db._one(self.conn, "SELECT * FROM menu_items WHERE name='Test Dish'")
        db.update_menu_item(self.conn, item["id"], "Test Dish", "Mains", 1050, "new", False)
        item = db.get_menu_item(self.conn, item["id"])
        self.assertEqual(item["price_pence"], 1050)
        self.assertEqual(item["available"], 0)
        self.assertNotIn("Test Dish", [r["name"] for r in db.get_menu(self.conn)])
        self.assertIn("Test Dish", [r["name"] for r in db.get_menu(self.conn, only_available=False)])
        db.delete_menu_item(self.conn, item["id"])
        self.assertIsNone(db.get_menu_item(self.conn, item["id"]))

    def test_menu_validation(self):
        with self.assertRaises(ValueError):
            db.add_menu_item(self.conn, "Cola", "Drinks", 200, "")       # duplicate
        with self.assertRaises(ValueError):
            db.add_menu_item(self.conn, "cola", "Drinks", 200, "")       # duplicate, different case
        with self.assertRaises(ValueError):
            db.add_menu_item(self.conn, "  ", "Drinks", 200, "")         # blank
        with self.assertRaises(ValueError):
            db.add_menu_item(self.conn, "X" * 81, "Drinks", 200, "")     # too long
        with self.assertRaises(ValueError):
            db.add_menu_item(self.conn, "Thing", "Pets", 200, "")        # bad category
        item = self.cola()
        with self.assertRaises(ValueError):
            db.update_menu_item(self.conn, item["id"], "Beef Burger", "Drinks", 200, "", True)

    def test_parse_price(self):
        self.assertEqual(db.parse_price("9.95"), 995)
        self.assertEqual(db.parse_price("£12"), 1200)
        self.assertEqual(db.parse_price("0.1"), 10)
        for bad in ("", "abc", "0", "-3", "5000", "nan"):
            with self.assertRaises(ValueError):
                db.parse_price(bad)

    def test_money_format(self):
        self.assertEqual(db.money(1195), "£11.95")
        self.assertEqual(db.money(5), "£0.05")

    def test_order_total_includes_delivery_and_saves_items(self):
        cart = [{"name": "Cola", "price_pence": 200, "quantity": 2},
                {"name": "Beef Burger", "price_pence": 1095, "quantity": 1}]
        oid = db.create_order(self.conn, "Sam", "07123456789", "1 High St", cart)
        order = db.get_orders(self.conn)[0]
        self.assertEqual(order["id"], oid)
        self.assertEqual(order["total_pence"], 200 * 2 + 1095 + db.DELIVERY_FEE_PENCE)
        self.assertEqual(order["status"], "Pending")
        self.assertEqual(len(db.get_order_items(self.conn, oid)), 2)
        self.assertTrue(db.fmt_time(order["created_at"]))

    def test_order_validation(self):
        cart = [{"name": "Cola", "price_pence": 200, "quantity": 1}]
        with self.assertRaises(ValueError):
            db.create_order(self.conn, "Sam", "07123456789", "1 High St", [])
        with self.assertRaises(ValueError):
            db.create_order(self.conn, "", "07123456789", "1 High St", cart)
        with self.assertRaises(ValueError):
            db.create_order(self.conn, "Sam", "123", "1 High St", cart)
        with self.assertRaises(ValueError):
            db.create_order(self.conn, "S" * 200, "07123456789", "1 High St", cart)
        self.assertEqual(db.get_orders(self.conn), [])

    def test_failed_order_leaves_nothing_behind(self):
        bad_cart = [{"name": "Cola", "price_pence": 200, "quantity": 0}]  # violates CHECK (quantity > 0)
        with self.assertRaises(db.MySQLError):
            db.create_order(self.conn, "Sam", "07123456789", "1 High St", bad_cart)
        self.assertEqual(db.get_orders(self.conn), [])

    def test_old_orders_survive_menu_deletion(self):
        item = self.cola()
        oid = db.create_order(self.conn, "Sam", "07123456789", "1 High St",
                              [{"name": item["name"], "price_pence": item["price_pence"], "quantity": 1}])
        db.delete_menu_item(self.conn, item["id"])
        self.assertEqual(db.get_order_items(self.conn, oid)[0]["item_name"], "Cola")

    def test_status_updates_summary_and_tracking(self):
        cart = [{"name": "Cola", "price_pence": 200, "quantity": 1}]
        a = db.create_order(self.conn, "A", "07123456789", "x", cart)
        b = db.create_order(self.conn, "B", "07123456789", "y", cart)
        c = db.create_order(self.conn, "C", "07999999999", "z", cart)
        db.set_order_status(self.conn, a, "Delivered")
        db.set_order_status(self.conn, b, "Cancelled")
        s = db.sales_summary(self.conn)
        self.assertEqual((s["orders"], s["active"], s["revenue_pence"]), (2, 1, 900))
        self.assertIsInstance(s["revenue_pence"], int)
        with self.assertRaises(ValueError):
            db.set_order_status(self.conn, a, "Teleported")
        self.assertEqual(len(db.get_orders_for_phone(self.conn, "07123456789")), 2)
        self.assertEqual([o["id"] for o in db.get_orders(self.conn, "Pending")], [c])

    def test_changes_made_elsewhere_are_visible(self):
        """Edits made in phpMyAdmin (another connection) must show up in the app."""
        other = db.connect(TEST_DB)
        db._run(other, "UPDATE menu_items SET price_pence = 777 WHERE name = 'Cola'")
        other.close()
        self.assertEqual(self.cola()["price_pence"], 777)


if __name__ == "__main__":
    unittest.main()
