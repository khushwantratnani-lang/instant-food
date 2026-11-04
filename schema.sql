-- Instant Food database schema (MySQL / MariaDB).
--
-- You do NOT need to run this: the app creates everything automatically on
-- first launch. It is included so you can see the structure and, if you like,
-- import it through phpMyAdmin (Import tab) before starting the app.

CREATE DATABASE IF NOT EXISTS instant_food CHARACTER SET utf8mb4;
USE instant_food;

CREATE TABLE IF NOT EXISTS menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    category VARCHAR(20) NOT NULL,
    price_pence INT UNSIGNED NOT NULL,
    description VARCHAR(200) NOT NULL DEFAULT '',
    available TINYINT(1) NOT NULL DEFAULT 1,
    CHECK (price_pence > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(80) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    address VARCHAR(200) NOT NULL,
    total_pence INT UNSIGNED NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_orders_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_name VARCHAR(80) NOT NULL,
    price_pence INT UNSIGNED NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    CHECK (quantity > 0),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admins (
    username VARCHAR(50) PRIMARY KEY,
    salt VARBINARY(16) NOT NULL,
    password_hash VARBINARY(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
