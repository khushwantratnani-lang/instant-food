"""Instant Food: a desktop food ordering app (Python, Tkinter and MySQL).

Run with:  python app.py
"""
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import database as db

# ---- palette: sage #A5A79B, cream #E8D2B5, wine #590907 (+ tints of the same)
SAGE = "#A5A79B"
CREAM = "#E8D2B5"
WINE = "#590907"
WINE_HOVER = "#7d1a17"
CARD = "#F5EAD9"          # lighter cream for cards
SAGE_DARK = "#8a8c80"
TEXT = "#2b0b0a"
MUTED = "#5f4a3e"
ERR = "#a31f14"
OK = "#2f6b3f"

UI = "Segoe UI"
BRAND = "Georgia"
FONT = (UI, 10)
FONT_B = (UI, 10, "bold")
FONT_S = (UI, 9)


def make_dpi_aware():
    """Crisp text on high-resolution Windows screens."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


# ---------------------------------------------------------------- widgets
def button(parent, text, command, kind="primary", **kw):
    styles = {
        "primary": dict(bg=WINE, fg=CREAM, hover=WINE_HOVER),
        "secondary": dict(bg=CARD, fg=WINE, hover=SAGE),
        "nav": dict(bg=WINE, fg=CREAM, hover=WINE_HOVER),
        "danger": dict(bg=ERR, fg="#ffffff", hover="#7d1710"),
    }
    s = styles[kind]
    outline = SAGE_DARK if kind == "secondary" else s["bg"]
    b = tk.Button(parent, text=text, command=command, bg=s["bg"], fg=s["fg"], activebackground=s["hover"],
                  activeforeground=s["fg"], relief="flat", bd=0, padx=kw.pop("padx", 16),
                  pady=kw.pop("pady", 8), font=kw.pop("font", FONT_B), cursor="hand2",
                  highlightthickness=1, highlightbackground=outline, highlightcolor=outline, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=s["hover"]))
    b.bind("<Leave>", lambda e: b.config(bg=s["bg"]))
    return b


def entry(parent, width=26, show=None, bg=CARD):
    return tk.Entry(parent, bg=bg, fg=TEXT, insertbackground=WINE, relief="flat", font=FONT, width=width,
                    show=show, highlightthickness=1, highlightbackground=SAGE, highlightcolor=WINE)


def label(parent, text="", font=FONT, fg=TEXT, bg=CREAM, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kw)


def setup_style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=CREAM, foreground=TEXT, font=FONT)
    s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30,
                borderwidth=0, font=FONT)
    s.configure("Treeview.Heading", background=SAGE, foreground=WINE, font=FONT_B, relief="flat", padding=7)
    s.map("Treeview", background=[("selected", WINE)], foreground=[("selected", CREAM)])
    s.map("Treeview.Heading", background=[("active", SAGE_DARK)])
    s.configure("TNotebook", background=CREAM, borderwidth=0)
    s.configure("TNotebook.Tab", background=SAGE, foreground=WINE, padding=(20, 9), font=FONT_B)
    s.map("TNotebook.Tab", background=[("selected", WINE)], foreground=[("selected", CREAM)],
          expand=[("selected", [0, 0, 0, 0])], padding=[("selected", (20, 9))])
    s.configure("TCombobox", fieldbackground=CARD, background=SAGE, foreground=TEXT, arrowcolor=WINE,
                padding=5, bordercolor=SAGE, lightcolor=CARD, darkcolor=CARD)
    s.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", TEXT)])
    s.configure("Vertical.TScrollbar", background=SAGE, troughcolor=CREAM, arrowcolor=WINE, bordercolor=CREAM)
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", WINE)
    root.option_add("*TCombobox*Listbox.selectForeground", CREAM)


class ScrollFrame(tk.Frame):
    """A vertically scrolling container. Put widgets in .inner"""

    def __init__(self, parent, bg=CREAM):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def scroll(self, steps):
        if self.canvas.yview() != (0.0, 1.0):  # only when the content is taller than the view
            self.canvas.yview_scroll(steps, "units")


# ---------------------------------------------------------------- app shell
class App(tk.Tk):
    def __init__(self, conn):
        super().__init__()
        self.title("Instant Food")
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.configure(bg=CREAM)
        setup_style(self)
        self.conn = conn
        self.cart = {}        # item id -> {"name", "price_pence", "quantity"}
        self.is_admin = False
        self.screen = None

        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", self._wheel)
        self.bind_all("<Button-5>", self._wheel)

        self.header = tk.Frame(self, bg=WINE)
        self.header.pack(fill="x")
        self.build_header()
        self.body = tk.Frame(self, bg=CREAM)
        self.body.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show(MenuScreen)

    def build_header(self):
        brand = tk.Frame(self.header, bg=WINE)
        brand.pack(side="left", padx=24, pady=12)
        tk.Label(brand, text="Instant Food", font=(BRAND, 22, "bold italic"), fg=CREAM, bg=WINE).pack(anchor="w")
        tk.Label(brand, text="Hungry? Sorted.", font=FONT_S, fg=SAGE, bg=WINE).pack(anchor="w")
        nav = tk.Frame(self.header, bg=WINE)
        nav.pack(side="right", padx=18)
        self.basket_btn = button(nav, "Basket (0)", lambda: self.show(MenuScreen), kind="secondary")
        self.basket_btn.pack(side="right", padx=(10, 0))
        self.admin_btn = button(nav, "Admin", self.open_admin, kind="nav")
        self.admin_btn.pack(side="right")
        button(nav, "Track order", lambda: self.show(TrackScreen), kind="nav").pack(side="right")
        button(nav, "Menu", lambda: self.show(MenuScreen), kind="nav").pack(side="right")

    def show(self, screen_class):
        for child in self.body.winfo_children():
            child.destroy()
        self.screen = screen_class(self.body, self)
        self.screen.pack(fill="both", expand=True)
        self.refresh_header()

    def open_admin(self):
        self.show(AdminScreen if self.is_admin else AdminLoginScreen)

    def refresh_header(self):
        count = sum(i["quantity"] for i in self.cart.values())
        self.basket_btn.config(text="Basket ({})".format(count))
        self.admin_btn.config(text="Dashboard" if self.is_admin else "Admin")

    def _wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                if getattr(event, "num", 0) == 4 or event.delta > 0:
                    widget.scroll(-2)
                else:
                    widget.scroll(2)
                return
            widget = widget.master

    def report_callback_exception(self, exc, val, tb):
        if isinstance(val, db.MySQLError):
            messagebox.showerror("Database problem",
                                 "Instant Food lost contact with MySQL.\n"
                                 "Check that MySQL is still running in XAMPP, then try again.\n\n{}".format(val))
        else:
            super().report_callback_exception(exc, val, tb)

    def on_close(self):
        try:
            self.conn.close()
        except Exception:
            pass
        self.destroy()


# ---------------------------------------------------------------- menu / basket
class MenuScreen(tk.Frame):
    COLUMNS = 2

    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app = app
        self.category = "All"
        self.search = tk.StringVar()
        self.add_buttons = {}
        self.pills = {}
        self.build()
        self.render_menu()
        self.render_basket()

    def build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, minsize=330)
        self.rowconfigure(0, weight=1)

        left = tk.Frame(self, bg=CREAM)
        left.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=18)
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        label(left, "What are you craving?", font=(BRAND, 20, "bold"), fg=WINE).grid(row=0, column=0, sticky="w")
        bar = tk.Frame(left, bg=CREAM)
        bar.grid(row=1, column=0, sticky="ew", pady=(12, 12))
        for name in ["All"] + db.CATEGORIES:
            b = tk.Button(bar, text=name, relief="flat", bd=0, padx=14, pady=5, font=FONT_B, cursor="hand2",
                          command=lambda n=name: self.set_category(n))
            b.pack(side="left", padx=(0, 8))
            self.pills[name] = b
        box = tk.Frame(bar, bg=CREAM)
        box.pack(side="right")
        s = entry(box, width=20)
        s.config(textvariable=self.search)
        s.pack(side="right", ipady=4)
        label(box, "Search ", fg=MUTED).pack(side="right")
        self.search.trace_add("write", lambda *a: self.render_menu())
        self.style_pills()

        self.cards = ScrollFrame(left)
        self.cards.grid(row=2, column=0, sticky="nsew")
        for c in range(self.COLUMNS):
            self.cards.inner.columnconfigure(c, weight=1, uniform="cards")

        right = tk.Frame(self, bg=SAGE)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        label(right, "Your basket", font=(BRAND, 17, "bold"), fg=WINE, bg=SAGE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 8))
        self.basket_list = ScrollFrame(right, bg=SAGE)
        self.basket_list.grid(row=1, column=0, sticky="nsew", padx=(20, 8))
        foot = tk.Frame(right, bg=SAGE)
        foot.grid(row=2, column=0, sticky="ew", padx=20, pady=16)
        self.totals = tk.Frame(foot, bg=SAGE)
        self.totals.pack(fill="x")
        self.checkout_btn = button(foot, "Checkout", self.checkout, padx=10, pady=11)
        self.checkout_btn.pack(fill="x", pady=(12, 0))

    # ---- menu cards
    def style_pills(self):
        for name, b in self.pills.items():
            active = name == self.category
            b.config(bg=WINE if active else CARD, fg=CREAM if active else WINE,
                     activebackground=WINE_HOVER if active else SAGE,
                     activeforeground=CREAM if active else WINE)

    def set_category(self, name):
        self.category = name
        self.style_pills()
        self.render_menu()

    def render_menu(self):
        inner = self.cards.inner
        for child in inner.winfo_children():
            child.destroy()
        self.add_buttons = {}
        items = db.get_menu(self.app.conn, self.category, self.search.get())
        if not items:
            label(inner, "No dishes match that search.", fg=MUTED, font=FONT).grid(pady=40)
            return
        for n, item in enumerate(items):
            card = self.make_card(inner, item)
            card.grid(row=n // self.COLUMNS, column=n % self.COLUMNS, sticky="nsew", padx=(0, 12), pady=(0, 12))
        self.cards.canvas.yview_moveto(0)

    def make_card(self, parent, item):
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=SAGE, padx=16, pady=14)
        tk.Label(card, text=item["category"].upper(), font=(UI, 8, "bold"), bg=SAGE, fg=WINE,
                 padx=8, pady=1).pack(anchor="w")
        tk.Label(card, text=item["name"], font=(BRAND, 14, "bold"), bg=CARD, fg=WINE,
                 anchor="w", justify="left").pack(fill="x", pady=(10, 2))
        desc = tk.Label(card, text=item["description"], font=FONT, bg=CARD, fg=MUTED, anchor="nw",
                        justify="left", wraplength=250, height=2)
        desc.pack(fill="x")
        card.bind("<Configure>", lambda e, d=desc: d.config(wraplength=max(120, e.width - 36)))
        foot = tk.Frame(card, bg=CARD)
        foot.pack(fill="x", pady=(12, 0))
        tk.Label(foot, text=db.money(item["price_pence"]), font=(UI, 13, "bold"), bg=CARD, fg=TEXT).pack(side="left")
        add = button(foot, "Add", lambda i=item: self.add(i), padx=18, pady=5)
        add.pack(side="right")
        self.add_buttons[item["id"]] = add
        return card

    # ---- basket
    def add(self, item):
        cart = self.app.cart
        if item["id"] in cart:
            cart[item["id"]]["quantity"] = min(20, cart[item["id"]]["quantity"] + 1)
        else:
            cart[item["id"]] = {"name": item["name"], "price_pence": item["price_pence"], "quantity": 1}
        self.render_basket()

    def change(self, item_id, delta):
        item = self.app.cart.get(item_id)
        if item is None:
            return
        item["quantity"] += delta
        if item["quantity"] <= 0:
            del self.app.cart[item_id]
        else:
            item["quantity"] = min(20, item["quantity"])
        self.render_basket()

    def render_basket(self):
        inner = self.basket_list.inner
        for child in inner.winfo_children():
            child.destroy()
        for child in self.totals.winfo_children():
            child.destroy()
        cart = self.app.cart
        if not cart:
            label(inner, "Nothing here yet.\nAdd a dish from the menu.", fg=WINE, bg=SAGE, justify="left").pack(
                anchor="w", pady=10)
            self.checkout_btn.config(state="disabled")
        else:
            self.checkout_btn.config(state="normal")
            for item_id, i in cart.items():
                self.basket_row(inner, item_id, i)
        subtotal = sum(i["price_pence"] * i["quantity"] for i in cart.values())
        fee = db.DELIVERY_FEE_PENCE if cart else 0
        for text, value, bold in (("Subtotal", subtotal, False), ("Delivery", fee, False),
                                  ("Total", subtotal + fee, True)):
            row = tk.Frame(self.totals, bg=SAGE)
            row.pack(fill="x", pady=1)
            f = (UI, 13, "bold") if bold else FONT
            tk.Label(row, text=text, font=f, bg=SAGE, fg=WINE).pack(side="left")
            tk.Label(row, text=db.money(value), font=f, bg=SAGE, fg=WINE).pack(side="right")
        self.app.refresh_header()

    def basket_row(self, parent, item_id, i):
        row = tk.Frame(parent, bg=SAGE)
        row.pack(fill="x", pady=(0, 10))
        top = tk.Frame(row, bg=SAGE)
        top.pack(fill="x")
        tk.Label(top, text=i["name"], font=FONT_B, bg=SAGE, fg=TEXT, anchor="w").pack(side="left")
        tk.Label(top, text=db.money(i["price_pence"] * i["quantity"]), font=FONT_B, bg=SAGE, fg=TEXT).pack(side="right")
        ctrl = tk.Frame(row, bg=SAGE)
        ctrl.pack(fill="x", pady=(4, 0))
        button(ctrl, "-", lambda: self.change(item_id, -1), kind="secondary", padx=9, pady=1).pack(side="left")
        tk.Label(ctrl, text=str(i["quantity"]), font=FONT_B, bg=SAGE, fg=TEXT, width=3).pack(side="left")
        button(ctrl, "+", lambda: self.change(item_id, 1), kind="secondary", padx=9, pady=1).pack(side="left")
        tk.Label(ctrl, text="{} each".format(db.money(i["price_pence"])), font=FONT_S, bg=SAGE, fg=MUTED).pack(
            side="right")

    def checkout(self):
        if self.app.cart:
            CheckoutDialog(self)


class CheckoutDialog(tk.Toplevel):
    def __init__(self, screen):
        super().__init__(screen)
        self.screen = screen
        self.title("Checkout")
        self.configure(bg=CREAM, padx=28, pady=22)
        self.resizable(False, False)
        self.transient(screen.winfo_toplevel())
        label(self, "Almost there", font=(BRAND, 18, "bold"), fg=WINE).grid(row=0, column=0, columnspan=2, sticky="w")
        cart = screen.app.cart
        subtotal = sum(i["price_pence"] * i["quantity"] for i in cart.values())
        summary = "{} item{}  |  Total with delivery: {}".format(
            sum(i["quantity"] for i in cart.values()), "" if len(cart) == 1 and
            list(cart.values())[0]["quantity"] == 1 else "s", db.money(subtotal + db.DELIVERY_FEE_PENCE))
        label(self, summary, fg=MUTED).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))
        self.fields = {}
        for r, (key, text) in enumerate((("name", "Full name"), ("phone", "Phone"), ("address", "Address")), 2):
            label(self, text, fg=MUTED).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 16))
            e = entry(self, width=30)
            e.grid(row=r, column=1, pady=6, ipady=5)
            self.fields[key] = e
        self.msg = label(self, "", fg=ERR, wraplength=360, justify="left")
        self.msg.grid(row=5, column=0, columnspan=2, sticky="w")
        row = tk.Frame(self, bg=CREAM)
        row.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        button(row, "Cancel", self.destroy, kind="secondary").pack(side="left", padx=8)
        button(row, "Place order", self.place).pack(side="left")
        self.fields["name"].focus_set()
        self.bind("<Return>", lambda e: self.place())
        self.grab_set()

    def place(self):
        app = self.screen.app
        try:
            order_id = db.create_order(app.conn, self.fields["name"].get(), self.fields["phone"].get(),
                                       self.fields["address"].get(), list(app.cart.values()))
        except ValueError as err:
            self.msg.config(text=str(err))
            return
        phone = self.fields["phone"].get().strip()
        app.cart.clear()
        self.destroy()
        self.screen.render_basket()
        messagebox.showinfo("Order placed", "Thank you! Your order number is #{}.\n\n"
                            "Use 'Track order' with the number {} to follow it.".format(order_id, phone))


# ---------------------------------------------------------------- tracking
class TrackScreen(tk.Frame):
    STEPS = ["Pending", "Preparing", "Out for delivery", "Delivered"]

    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app = app
        label(self, "Track your order", font=(BRAND, 20, "bold"), fg=WINE).pack(anchor="w", padx=28, pady=(20, 4))
        label(self, "Enter the phone number you used at checkout.", fg=MUTED).pack(anchor="w", padx=28)
        bar = tk.Frame(self, bg=CREAM)
        bar.pack(fill="x", padx=28, pady=14)
        self.phone = entry(bar, width=24)
        self.phone.pack(side="left", ipady=5)
        self.phone.bind("<Return>", lambda e: self.lookup())
        button(bar, "Find orders", self.lookup).pack(side="left", padx=10)
        self.tree = ttk.Treeview(self, columns=("id", "date", "total", "status"), show="headings",
                                 selectmode="browse", height=6)
        for col, text, w in (("id", "Order", 80), ("date", "Placed", 160), ("total", "Total", 100), ("status", "Status", 180)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(fill="x", padx=28)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_order())
        self.stepper = tk.Frame(self, bg=CREAM)
        self.stepper.pack(fill="x", padx=28, pady=(20, 6))
        self.detail = label(self, "", fg=TEXT, justify="left", anchor="w")
        self.detail.pack(fill="x", padx=28)

    def lookup(self):
        self.tree.delete(*self.tree.get_children())
        self.clear_detail()
        orders = db.get_orders_for_phone(self.app.conn, self.phone.get())
        for o in orders:
            self.tree.insert("", "end", iid=str(o["id"]), values=(
                "#{}".format(o["id"]), db.fmt_time(o["created_at"]), db.money(o["total_pence"]), o["status"]))
        if orders:
            self.tree.selection_set(self.tree.get_children()[0])
        else:
            self.detail.config(text="No orders found for that phone number.", fg=MUTED)

    def clear_detail(self):
        for child in self.stepper.winfo_children():
            child.destroy()
        self.detail.config(text="", fg=TEXT)

    def show_order(self):
        sel = self.tree.selection()
        if not sel:
            return
        order = db.get_order(self.app.conn, int(sel[0]))
        for child in self.stepper.winfo_children():
            child.destroy()
        if order["status"] == "Cancelled":
            tk.Label(self.stepper, text="This order was cancelled", bg=ERR, fg="#fff", font=FONT_B,
                     padx=14, pady=6).pack(side="left")
        else:
            reached = self.STEPS.index(order["status"])
            for n, step in enumerate(self.STEPS):
                done = n <= reached
                tk.Label(self.stepper, text=step, font=FONT_B, padx=14, pady=6,
                         bg=WINE if done else SAGE, fg=CREAM if done else WINE).pack(side="left", padx=(0, 6))
        items = db.get_order_items(self.app.conn, order["id"])
        self.detail.config(text="\n".join("{} x {}".format(i["quantity"], i["item_name"]) for i in items), fg=TEXT)


# ---------------------------------------------------------------- admin
class AdminLoginScreen(tk.Frame):
    MAX_ATTEMPTS = 5

    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app = app
        self.attempts = 0
        box = tk.Frame(self, bg=CARD, padx=40, pady=32, highlightthickness=1, highlightbackground=SAGE)
        box.place(relx=0.5, rely=0.45, anchor="center")
        label(box, "Staff login", font=(BRAND, 20, "bold"), fg=WINE, bg=CARD).grid(row=0, column=0, columnspan=2,
                                                                                    pady=(0, 18))
        label(box, "Username", fg=MUTED, bg=CARD).grid(row=1, column=0, sticky="w", pady=7)
        self.user = entry(box, bg=CREAM)
        self.user.grid(row=1, column=1, padx=(14, 0), ipady=5)
        label(box, "Password", fg=MUTED, bg=CARD).grid(row=2, column=0, sticky="w", pady=7)
        self.pw = entry(box, show="*", bg=CREAM)
        self.pw.grid(row=2, column=1, padx=(14, 0), ipady=5)
        self.msg = label(box, "", fg=ERR, bg=CARD)
        self.msg.grid(row=3, column=0, columnspan=2, pady=(8, 0))
        self.login_btn = button(box, "Log in", self.login)
        self.login_btn.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.user.focus_set()
        self.user.bind("<Return>", lambda e: self.login())
        self.pw.bind("<Return>", lambda e: self.login())

    def login(self):
        if self.attempts >= self.MAX_ATTEMPTS:
            self.msg.config(text="Too many attempts. Reopen this page to try again.")
            return
        if db.check_admin(self.app.conn, self.user.get(), self.pw.get()):
            self.app.is_admin = True
            self.app.show(AdminScreen)
        else:
            self.attempts += 1
            self.pw.delete(0, "end")
            self.msg.config(text="Wrong username or password ({} of {})".format(self.attempts, self.MAX_ATTEMPTS))


class AdminScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CREAM)
        self.app = app
        top = tk.Frame(self, bg=CREAM)
        top.pack(fill="x", padx=28, pady=(18, 10))
        label(top, "Dashboard", font=(BRAND, 20, "bold"), fg=WINE).pack(side="left")
        button(top, "Log out", self.logout, kind="secondary").pack(side="right")

        self.stat_values = {}
        stats = tk.Frame(self, bg=CREAM)
        stats.pack(fill="x", padx=28)
        for n, (key, title) in enumerate((("orders", "Orders"), ("active", "In progress"), ("revenue", "Revenue"))):
            card = tk.Frame(stats, bg=SAGE, padx=22, pady=12)
            card.grid(row=0, column=n, sticky="ew", padx=(0, 12))
            stats.columnconfigure(n, weight=1, uniform="stat")
            tk.Label(card, text=title.upper(), font=(UI, 8, "bold"), bg=SAGE, fg=WINE).pack(anchor="w")
            self.stat_values[key] = tk.Label(card, text="", font=(BRAND, 22, "bold"), bg=SAGE, fg=WINE)
            self.stat_values[key].pack(anchor="w")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=28, pady=14)
        self.menu_tab = tk.Frame(nb, bg=CREAM)
        self.orders_tab = tk.Frame(nb, bg=CREAM)
        nb.add(self.menu_tab, text="Menu")
        nb.add(self.orders_tab, text="Orders")
        self.notebook = nb
        self.build_menu_tab()
        self.build_orders_tab()
        self.refresh_all()

    def logout(self):
        self.app.is_admin = False
        self.app.show(MenuScreen)

    def refresh_all(self):
        self.refresh_menu()
        self.refresh_orders()
        s = db.sales_summary(self.app.conn)
        self.stat_values["orders"].config(text=str(s["orders"]))
        self.stat_values["active"].config(text=str(s["active"]))
        self.stat_values["revenue"].config(text=db.money(s["revenue_pence"]))

    # ---- menu management
    def build_menu_tab(self):
        tab = self.menu_tab
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(0, weight=1)
        self.menu_tree = ttk.Treeview(tab, columns=("name", "category", "price", "available"), show="headings",
                                      selectmode="browse")
        for col, text, w, anchor in (("name", "Item", 200, "w"), ("category", "Category", 90, "w"),
                                     ("price", "Price", 70, "e"), ("available", "On menu", 70, "center")):
            self.menu_tree.heading(col, text=text, anchor=anchor)
            self.menu_tree.column(col, width=w, anchor=anchor)
        self.menu_tree.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=12)
        self.menu_tree.bind("<<TreeviewSelect>>", lambda e: self.load_form())

        form = tk.Frame(tab, bg=CARD, padx=18, pady=16, highlightthickness=1, highlightbackground=SAGE)
        form.grid(row=0, column=1, sticky="nsew", pady=12)
        label(form, "Add or edit a dish", font=(BRAND, 15, "bold"), fg=WINE, bg=CARD).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.f_name, self.f_price, self.f_desc = (entry(form, width=24, bg=CREAM) for _ in range(3))
        self.f_cat = ttk.Combobox(form, values=db.CATEGORIES, state="readonly", width=22)
        self.f_avail = tk.BooleanVar(value=True)
        for r, (text, widget) in enumerate((("Name", self.f_name), ("Category", self.f_cat),
                                            ("Price (£)", self.f_price), ("Description", self.f_desc)), 1):
            label(form, text, fg=MUTED, bg=CARD).grid(row=r, column=0, sticky="w", pady=6)
            widget.grid(row=r, column=1, pady=6, padx=(10, 0), ipady=0 if widget is self.f_cat else 4)
        tk.Checkbutton(form, text="Available on menu", variable=self.f_avail, bg=CARD, fg=TEXT, selectcolor=CREAM,
                       activebackground=CARD, activeforeground=TEXT, font=FONT).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=6)
        btns = tk.Frame(form, bg=CARD)
        btns.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        button(btns, "Add new", self.add_item, padx=12).pack(side="left")
        button(btns, "Save changes", self.save_item, kind="secondary", padx=12).pack(side="left", padx=6)
        button(btns, "Delete", self.delete_item, kind="danger", padx=12).pack(side="left")
        self.menu_msg = label(form, "", fg=OK, bg=CARD, wraplength=300, justify="left")
        self.menu_msg.grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def refresh_menu(self):
        self.menu_tree.delete(*self.menu_tree.get_children())
        for r in db.get_menu(self.app.conn, only_available=False):
            self.menu_tree.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["category"], db.money(r["price_pence"]), "Yes" if r["available"] else "No"))

    def selected_item(self):
        sel = self.menu_tree.selection()
        return int(sel[0]) if sel else None

    def load_form(self):
        item_id = self.selected_item()
        if item_id is None:
            return
        r = db.get_menu_item(self.app.conn, item_id)
        if r is None:
            return
        for widget, value in ((self.f_name, r["name"]), (self.f_price, "{:.2f}".format(r["price_pence"] / 100)),
                              (self.f_desc, r["description"])):
            widget.delete(0, "end")
            widget.insert(0, value)
        self.f_cat.set(r["category"])
        self.f_avail.set(bool(r["available"]))

    def say(self, text, good=True):
        self.menu_msg.config(text=text, fg=OK if good else ERR)

    def read_form(self):
        return self.f_name.get(), self.f_cat.get(), db.parse_price(self.f_price.get()), self.f_desc.get()

    def add_item(self):
        try:
            name, cat, price, desc = self.read_form()
            db.add_menu_item(self.app.conn, name, cat, price, desc)
        except ValueError as err:
            self.say(str(err), good=False)
            return
        self.say("Added {}.".format(name.strip()))
        self.refresh_all()

    def save_item(self):
        item_id = self.selected_item()
        if item_id is None:
            self.say("Select a dish in the list first.", good=False)
            return
        try:
            name, cat, price, desc = self.read_form()
            db.update_menu_item(self.app.conn, item_id, name, cat, price, desc, self.f_avail.get())
        except ValueError as err:
            self.say(str(err), good=False)
            return
        self.say("Saved changes to {}.".format(name.strip()))
        self.refresh_all()

    def delete_item(self):
        item_id = self.selected_item()
        if item_id is None:
            self.say("Select a dish in the list first.", good=False)
            return
        name = self.menu_tree.item(str(item_id), "values")[0]
        if messagebox.askyesno("Delete dish", "Remove {} from the menu for good?\n"
                               "(Past orders keep their record.)".format(name)):
            db.delete_menu_item(self.app.conn, item_id)
            self.say("Deleted {}.".format(name))
            self.refresh_all()

    # ---- orders
    def build_orders_tab(self):
        tab = self.orders_tab
        bar = tk.Frame(tab, bg=CREAM)
        bar.pack(fill="x", pady=(12, 8))
        label(bar, "Show", fg=MUTED).pack(side="left")
        self.filter = tk.StringVar(value="All")
        fc = ttk.Combobox(bar, textvariable=self.filter, state="readonly", width=16, values=["All"] + db.STATUSES)
        fc.pack(side="left", padx=8)
        fc.bind("<<ComboboxSelected>>", lambda e: self.refresh_orders())
        self.orders_tree = ttk.Treeview(tab, columns=("id", "date", "customer", "total", "status"), show="headings",
                                        selectmode="browse", height=8)
        for col, text, w, anchor in (("id", "Order", 60, "w"), ("date", "Placed", 120, "w"),
                                     ("customer", "Customer", 170, "w"), ("total", "Total", 90, "center"),
                                     ("status", "Status", 140, "w")):
            self.orders_tree.heading(col, text=text, anchor=anchor)
            self.orders_tree.column(col, width=w, anchor=anchor)
        self.orders_tree.pack(fill="both", expand=True)
        self.orders_tree.bind("<<TreeviewSelect>>", lambda e: self.show_order())
        bottom = tk.Frame(tab, bg=CREAM)
        bottom.pack(fill="x", pady=12)
        self.order_detail = label(bottom, "Select an order to see its details.", fg=MUTED, justify="left",
                                  anchor="w", wraplength=560)
        self.order_detail.pack(side="left", fill="x", expand=True)
        self.new_status = ttk.Combobox(bottom, values=db.STATUSES, state="readonly", width=16)
        self.new_status.pack(side="left", padx=8)
        button(bottom, "Update status", self.update_status).pack(side="left")

    def refresh_orders(self):
        self.orders_tree.delete(*self.orders_tree.get_children())
        for o in db.get_orders(self.app.conn, self.filter.get()):
            self.orders_tree.insert("", "end", iid=str(o["id"]), values=(
                "#{}".format(o["id"]), db.fmt_time(o["created_at"]), o["customer_name"],
                db.money(o["total_pence"]), o["status"]))

    def show_order(self):
        sel = self.orders_tree.selection()
        if not sel:
            return
        o = db.get_order(self.app.conn, int(sel[0]))
        lines = ["{} x {}".format(i["quantity"], i["item_name"]) for i in db.get_order_items(self.app.conn, o["id"])]
        self.order_detail.config(fg=TEXT, text="{}  |  {}\n{}".format(o["phone"], o["address"], ", ".join(lines)))
        self.new_status.set(o["status"])

    def update_status(self):
        sel = self.orders_tree.selection()
        if not sel or not self.new_status.get():
            messagebox.showinfo("Orders", "Select an order and a status first.")
            return
        db.set_order_status(self.app.conn, int(sel[0]), self.new_status.get())
        self.refresh_all()
        if str(sel[0]) in self.orders_tree.get_children():
            self.orders_tree.selection_set(str(sel[0]))


# ---------------------------------------------------------------- start-up
def main():
    make_dpi_aware()
    try:
        conn = db.connect()
        db.init_db(conn)
    except db.MySQLError as err:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Instant Food: cannot reach MySQL",
            "Could not connect to MySQL.\n\n"
            "1. Open the XAMPP Control Panel and click Start next to MySQL.\n"
            "2. If your MySQL has a password, set it in config.py.\n\n"
            "Details: {}".format(err))
        return
    App(conn).mainloop()


if __name__ == "__main__":
    main()
