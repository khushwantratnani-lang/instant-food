# Instant Food

A desktop food ordering app with a graphical interface, built in **Python** with **Tkinter** and a **MySQL** database. It began as a terminal program and was rebuilt as a full GUI application.

## Features

**Customers**
- Browse dishes as cards, filter by category and search by name
- Basket with quantity buttons, live subtotal, delivery fee and total
- Checkout with validated name, phone and address
- Track an order by phone number, with a progress bar: Pending, Preparing, Out for delivery, Delivered

**Staff dashboard** (login required)
- Add, edit, hide and delete dishes
- See every order, filter by status and update its progress
- Stats: total orders, orders in progress and revenue

## Setup

You need Python 3.9 or newer and MySQL (XAMPP includes it).

1. Open the **XAMPP Control Panel** and click **Start** next to **MySQL**.
2. Install the MySQL connector:
   ```
   pip install -r requirements.txt
   ```
3. Run the app:
   ```
   python app.py
   ```

The database (`instant_food`) and its tables are created automatically on first run, with a sample menu. You can browse them in phpMyAdmin at http://localhost/phpmyadmin.

If your MySQL has a password, set it in `config.py`. `schema.sql` shows the table structure and can be imported through phpMyAdmin if you prefer, but this is optional.

**Default staff login:** `admin` / `admin123`. This is for demo purposes only; change it before using the app for anything real.

## Tests

```
python -m unittest -v
```

The tests run against your MySQL server using a separate `instant_food_test` database that is removed afterwards. They cover menu management, admin login, order totals, input validation, SQL injection attempts, and orders being saved all-or-nothing.

## Project structure

| File | Purpose |
|---|---|
| `app.py` | The Tkinter interface: menu, basket, checkout, tracking and staff dashboard |
| `database.py` | All MySQL code: schema, menu, orders and admin authentication |
| `config.py` | Database connection settings |
| `schema.sql` | The database structure, for reference or phpMyAdmin import |
| `test_database.py` | Unit tests for the database layer |

## Design notes

- Prices are stored as whole pence (integers), so totals never suffer from floating-point rounding errors.
- Passwords are salted and hashed with PBKDF2 and never stored in plain text.
- Every query is parameterised, which prevents SQL injection.
- An order and its items are saved in a single transaction, so a failure never leaves half an order behind.
- Order lines keep their own copy of the dish name and price, so deleting a dish does not change past orders.
- Staff login locks out after five wrong attempts on the login screen.
