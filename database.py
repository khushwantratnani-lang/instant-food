"""Database layer for Instant Food (MySQL).

Prices are stored as whole pence (integers) so totals never suffer from
floating-point rounding errors. Every query is parameterised.
"""
import hashlib
import hmac
import os
import re

import mysql.connector
from mysql.connector import Error as MySQLError  # noqa: F401  (re-exported for the GUI)
from mysql.connector import IntegrityError

import config

CATEGORIES = ["Starters", "Mains", "Desserts", "Drinks"]
STATUSES = ["Pending", "Preparing", "Out for delivery", "Delivered", "Cancelled"]
DELIVERY_FEE_PENCE = 250

MAX_NAME, MAX_DESC, MAX_ADDRESS, MAX_PHONE = 80, 200, 200, 30

SEED_MENU = [
    ("Garlic Bread", "Starters", 450, "Toasted baguette with garlic butter"),
    ("Samosa Chaat", "Starters", 595, "Crispy samosas with yoghurt and tamarind"),
    ("Chicken Wings", "Starters", 650, "Six wings in a smoky BBQ glaze"),
    ("Margherita Pizza", "Mains", 995, "Tomato, mozzarella and fresh basil"),
    ("Butter Chicken", "Mains", 1195, "Creamy tomato curry with basmati rice"),
    ("Beef Burger", "Mains", 1095, "Brioche bun, cheddar, house sauce and fries"),
    ("Paneer Wrap", "Mains", 895, "Grilled paneer, peppers and mint chutney"),
    ("Chocolate Brownie", "Desserts", 525, "Warm brownie with vanilla ice cream"),
    ("Gulab Jamun", "Desserts", 475, "Two syrup-soaked dumplings"),
    ("Mango Lassi", "Drinks", 350, "Chilled yoghurt and mango drink"),
    ("Cola", "Drinks", 200, "330ml can"),
    ("Fresh Lemonade", "Drinks", 300, "Still, with mint"),
]

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS menu_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(80) NOT NULL UNIQUE,
        category VARCHAR(20) NOT NULL,
        price_pence INT UNSIGNED NOT NULL,
        description VARCHAR(200) NOT NULL DEFAULT '',
        available TINYINT(1) NOT NULL DEFAULT 1,
        CHECK (price_pence > 0)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        customer_name VARCHAR(80) NOT NULL,
        phone VARCHAR(30) NOT NULL,
        address VARCHAR(200) NOT NULL,
        total_pence INT UNSIGNED NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'Pending',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_orders_phone (phone)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL,
        item_name VARCHAR(80) NOT NULL,
        price_pence INT UNSIGNED NOT NULL,
        quantity INT UNSIGNED NOT NULL,
        CHECK (quantity > 0),
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS admins (
        username VARCHAR(50) PRIMARY KEY,
        salt VARBINARY(16) NOT NULL,
        password_hash VARBINARY(32) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


# ---------- formatting helpers ----------
def money(pence):
    """Format whole pence as a pounds string, e.g. 1195 -> '£11.95'."""
    return "£{:.2f}".format(int(pence) / 100)


def parse_price(text):
    """Turn user input like '9.95' or '£9.95' into pence. Raises ValueError."""
    cleaned = text.strip().replace("£", "")
    if not cleaned:
        raise ValueError("Price is required")
    try:
        value = float(cleaned)
    except ValueError:
        raise ValueError("Price must be a number, for example 9.95")
    if not 0 < value <= 1000:
        raise ValueError("Price must be between 0.01 and 1000")
    return int(round(value * 100))


def fmt_time(value):
    """MySQL gives datetime objects; show them as 'DD Mon HH:MM'."""
    try:
        return value.strftime("%d %b %H:%M")
    except AttributeError:
        return str(value)


# ---------- connection ----------
def connect(db_name=None):
    """Connect to MySQL, creating the database first if it does not exist."""
    name = db_name or config.DB_NAME
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Database name may only contain letters, numbers and underscores")
    conn = mysql.connector.connect(
        **config.DB_CONFIG, use_pure=True, charset="utf8mb4", autocommit=True, connection_timeout=5
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS `{}` CHARACTER SET utf8mb4".format(name))
    cur.close()
    conn.database = name
    return conn


def _run(conn, sql, args=(), fetch=None):
    """Run one statement. fetch is 'all', 'one' or None. Returns (rows, lastrowid)."""
    conn.ping(reconnect=True, attempts=2, delay=1)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, args)
        if fetch == "all":
            return cur.fetchall(), cur.lastrowid
        if fetch == "one":
            return cur.fetchone(), cur.lastrowid
        return None, cur.lastrowid
    finally:
        cur.close()


def _all(conn, sql, args=()):
    return _run(conn, sql, args, "all")[0]


def _one(conn, sql, args=()):
    return _run(conn, sql, args, "one")[0]


def init_db(conn):
    for statement in SCHEMA:
        _run(conn, statement)
    if _one(conn, "SELECT COUNT(*) AS n FROM menu_items")["n"] == 0:
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO menu_items (name, category, price_pence, description) VALUES (%s, %s, %s, %s)",
            SEED_MENU,
        )
        cur.close()
    if _one(conn, "SELECT COUNT(*) AS n FROM admins")["n"] == 0:
        add_admin(conn, "admin", "admin123")


# ---------- admins ----------
def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)


def add_admin(conn, username, password):
    salt = os.urandom(16)
    _run(
        conn,
        "INSERT INTO admins (username, salt, password_hash) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE salt = VALUES(salt), password_hash = VALUES(password_hash)",
        (username, salt, _hash_password(password, salt)),
    )


def check_admin(conn, username, password):
    row = _one(conn, "SELECT salt, password_hash FROM admins WHERE username = %s", (username.strip(),))
    if row is None:
        return False
    return hmac.compare_digest(bytes(row["password_hash"]), _hash_password(password, bytes(row["salt"])))


# ---------- menu ----------
def _escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_menu(conn, category=None, search="", only_available=True):
    sql = "SELECT * FROM menu_items WHERE 1=1"
    args = []
    if only_available:
        sql += " AND available = 1"
    if category and category != "All":
        sql += " AND category = %s"
        args.append(category)
    if search.strip():
        sql += " AND (name LIKE %s OR description LIKE %s)"
        like = "%" + _escape_like(search.strip()) + "%"
        args += [like, like]
    sql += " ORDER BY FIELD(category, 'Starters', 'Mains', 'Desserts', 'Drinks'), name"
    return _all(conn, sql, args)


def get_menu_item(conn, item_id):
    return _one(conn, "SELECT * FROM menu_items WHERE id = %s", (item_id,))


def _check_item(name, category, description):
    name, description = name.strip(), description.strip()
    if not name:
        raise ValueError("Name is required")
    if len(name) > MAX_NAME:
        raise ValueError("Name must be {} characters or fewer".format(MAX_NAME))
    if category not in CATEGORIES:
        raise ValueError("Choose a category")
    if len(description) > MAX_DESC:
        raise ValueError("Description must be {} characters or fewer".format(MAX_DESC))
    return name, description


def _duplicate_or_invalid(err):
    if getattr(err, "errno", None) == 1062:
        return ValueError("An item with that name already exists")
    return ValueError("Those details were not accepted by the database")


def add_menu_item(conn, name, category, price_pence, description):
    name, description = _check_item(name, category, description)
    try:
        _run(conn, "INSERT INTO menu_items (name, category, price_pence, description) VALUES (%s, %s, %s, %s)",
             (name, category, price_pence, description))
    except IntegrityError as err:
        raise _duplicate_or_invalid(err)


def update_menu_item(conn, item_id, name, category, price_pence, description, available):
    name, description = _check_item(name, category, description)
    try:
        _run(conn, "UPDATE menu_items SET name=%s, category=%s, price_pence=%s, description=%s, available=%s "
                   "WHERE id=%s", (name, category, price_pence, description, 1 if available else 0, item_id))
    except IntegrityError as err:
        raise _duplicate_or_invalid(err)


def delete_menu_item(conn, item_id):
    _run(conn, "DELETE FROM menu_items WHERE id = %s", (item_id,))


# ---------- orders ----------
def create_order(conn, name, phone, address, cart):
    """cart: list of dicts with name, price_pence, quantity. Returns the new order id."""
    if not cart:
        raise ValueError("Your basket is empty")
    name, phone, address = name.strip(), phone.strip(), address.strip()
    if not name or not phone or not address:
        raise ValueError("Name, phone and address are required")
    if len(name) > MAX_NAME or len(address) > MAX_ADDRESS or len(phone) > MAX_PHONE:
        raise ValueError("One of your details is too long")
    if sum(c.isdigit() for c in phone) < 10:
        raise ValueError("Please enter a valid phone number")
    subtotal = sum(i["price_pence"] * i["quantity"] for i in cart)
    total = subtotal + DELIVERY_FEE_PENCE

    conn.ping(reconnect=True, attempts=2, delay=1)
    conn.start_transaction()  # order and its lines are saved together or not at all
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (customer_name, phone, address, total_pence, status) "
            "VALUES (%s, %s, %s, %s, 'Pending')", (name, phone, address, total))
        order_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO order_items (order_id, item_name, price_pence, quantity) VALUES (%s, %s, %s, %s)",
            [(order_id, i["name"], i["price_pence"], i["quantity"]) for i in cart])
        cur.close()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return order_id


def get_orders(conn, status=None):
    if status and status != "All":
        return _all(conn, "SELECT * FROM orders WHERE status = %s ORDER BY id DESC", (status,))
    return _all(conn, "SELECT * FROM orders ORDER BY id DESC")


def get_order(conn, order_id):
    return _one(conn, "SELECT * FROM orders WHERE id = %s", (order_id,))


def get_orders_for_phone(conn, phone):
    return _all(conn, "SELECT * FROM orders WHERE phone = %s ORDER BY id DESC", (phone.strip(),))


def get_order_items(conn, order_id):
    return _all(conn, "SELECT * FROM order_items WHERE order_id = %s ORDER BY id", (order_id,))


def set_order_status(conn, order_id, status):
    if status not in STATUSES:
        raise ValueError("Unknown status")
    _run(conn, "UPDATE orders SET status = %s WHERE id = %s", (status, order_id))


def sales_summary(conn):
    row = _one(conn, "SELECT COUNT(*) AS n, COALESCE(SUM(total_pence), 0) AS revenue "
                     "FROM orders WHERE status != 'Cancelled'")
    active = _one(conn, "SELECT COUNT(*) AS n FROM orders "
                        "WHERE status IN ('Pending', 'Preparing', 'Out for delivery')")["n"]
    return {"orders": int(row["n"]), "revenue_pence": int(row["revenue"]), "active": int(active)}
