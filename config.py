"""Database settings for Instant Food.

The defaults match a fresh XAMPP install (MySQL on localhost, user "root",
no password). If your MySQL has a password, change it here or set the
environment variable IF_DB_PASSWORD.
"""
import os

DB_CONFIG = {
    "host": os.environ.get("IF_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("IF_DB_PORT", "3306")),
    "user": os.environ.get("IF_DB_USER", "root"),
    "password": os.environ.get("IF_DB_PASSWORD", ""),
}

# The database is created automatically the first time the app runs.
DB_NAME = os.environ.get("IF_DB_NAME", "instant_food")
