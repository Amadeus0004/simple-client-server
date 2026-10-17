"""
Client-server demo: a small login website with a SQLite database.

    python app.py         then open http://127.0.0.1:8080 in a browser

Runs over plain HTTP on purpose, so Wireshark shows everything,
including the password, in clear text.
"""
import hashlib
import html
import os
import secrets
import socket
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8080
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.db")
sessions = {}  # session token -> username

USERS = [  # username, password, full name, role
    ("admin", "admin123", "Administrator", "admin"),
    ("alice", "password1", "Alice Johnson", "employee"),
    ("bob", "qwerty", "Bob Smith", "employee"),
]
PRODUCTS = [  # name, category, price, stock
    ("Laptop Pro 14", "Computers", 1299.00, 12),
    ("Wireless Mouse", "Accessories", 24.90, 140),
    ("Mechanical Keyboard", "Accessories", 89.50, 45),
    ("27\" Monitor", "Displays", 279.00, 20),
    ("USB-C Hub", "Accessories", 39.99, 75),
    ("Network Switch 8-port", "Networking", 59.00, 18),
    ("Wi-Fi Router AX3000", "Networking", 149.00, 9),
    ("External SSD 1TB", "Storage", 109.00, 33),
]


# ------------------------------------------------------------------ database

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt TEXT, password_hash TEXT,
                                              full_name TEXT, role TEXT);
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, category TEXT,
                                                 price REAL, stock INTEGER);
            CREATE TABLE IF NOT EXISTS login_log (id INTEGER PRIMARY KEY, time TEXT, client TEXT,
                                                  username TEXT, result TEXT);
        """)
        if not conn.execute("SELECT 1 FROM users").fetchone():
            for username, password, full_name, role in USERS:
                salt = secrets.token_hex(8)
                conn.execute("INSERT INTO users VALUES (?,?,?,?,?)",
                             (username, salt, hash_password(password, salt), full_name, role))
            conn.executemany("INSERT INTO products (name, category, price, stock) VALUES (?,?,?,?)", PRODUCTS)


def check_login(username, password):
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if user and hash_password(password, user["salt"]) == user["password_hash"]:
        return user
    return None


def log_login(client, username, result):
    with db() as conn:
        conn.execute("INSERT INTO login_log (time, client, username, result) VALUES (?,?,?,?)",
                     (time.strftime("%Y-%m-%d %H:%M:%S"), client, username, result))


# ------------------------------------------------------------------ HTML

CSS = """
body { font-family: Segoe UI, Arial, sans-serif; background: #eef1f5; margin: 0; color: #222; }
.box { max-width: 380px; margin: 80px auto; background: #fff; padding: 32px; border-radius: 10px;
       box-shadow: 0 2px 12px rgba(0,0,0,.1); }
.wide { max-width: 900px; margin: 30px auto; }
h1 { margin-top: 0; font-size: 24px; }
h2 { font-size: 18px; margin-top: 28px; }
input { width: 100%; padding: 10px; margin: 6px 0 14px; border: 1px solid #ccc; border-radius: 6px;
        box-sizing: border-box; font-size: 15px; }
button { background: #2563eb; color: #fff; border: 0; padding: 10px 18px; border-radius: 6px;
         font-size: 15px; cursor: pointer; }
.full { width: 100%; }
.error { background: #fde8e8; color: #b91c1c; padding: 10px; border-radius: 6px; margin-bottom: 14px; }
.hint { background: #f3f4f6; padding: 10px; border-radius: 6px; font-size: 13px; color: #555; margin-top: 18px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; }
th { background: #f9fafb; }
.top { display: flex; justify-content: space-between; align-items: center; }
.ok { color: #15803d; font-weight: bold; } .fail { color: #b91c1c; font-weight: bold; }
.search { display: flex; gap: 8px; } .search input { margin: 0; }
.muted { color: #777; font-size: 13px; }
a { color: #2563eb; }
"""


def page(title, body):
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS}</style></head><body>{body}</body></html>"""


def login_page(error=""):
    err = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return page("Login", f"""
<div class="box">
  <h1>Demo Company Login</h1>
  {err}
  <form method="POST" action="/login">
    <label>Username</label><input name="username" autofocus>
    <label>Password</label><input name="password" type="password">
    <button class="full">Log in</button>
  </form>
  <div class="hint">Demo accounts: <b>admin</b> / admin123 &nbsp;·&nbsp; <b>alice</b> / password1
  &nbsp;·&nbsp; <b>bob</b> / qwerty</div>
</div>""")


def dashboard_page(user, search, client):
    with db() as conn:
        products = conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY id",
                                (f"%{search}%", f"%{search}%")).fetchall()
        log = conn.execute("SELECT * FROM login_log ORDER BY id DESC LIMIT 15").fetchall()
    product_rows = "".join(
        f"<tr><td>{p['id']}</td><td>{html.escape(p['name'])}</td><td>{p['category']}</td>"
        f"<td>${p['price']:.2f}</td><td>{p['stock']}</td></tr>" for p in products
    ) or '<tr><td colspan="5" class="muted">No products match.</td></tr>'
    log_rows = "".join(
        f"<tr><td>{r['time']}</td><td>{r['client']}</td><td>{html.escape(r['username'])}</td>"
        f"<td class=\"{'ok' if r['result'] == 'SUCCESS' else 'fail'}\">{r['result']}</td></tr>" for r in log
    )
    return page("Dashboard", f"""
<div class="box wide">
  <div class="top">
    <h1>Welcome, {html.escape(user['full_name'])}</h1>
    <a href="/logout">Log out</a>
  </div>
  <p class="muted">Logged in as <b>{user['username']}</b> ({user['role']}) · the server sees you as
  <b>{client}</b></p>

  <h2>Products (from the database)</h2>
  <form class="search" method="GET" action="/dashboard">
    <input name="q" value="{html.escape(search)}" placeholder="Search products...">
    <button>Search</button>
  </form><br>
  <table><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th></tr>{product_rows}</table>

  <h2>Login log</h2>
  <table><tr><th>Time</th><th>Client</th><th>Username</th><th>Result</th></tr>{log_rows}</table>
</div>""")


# ------------------------------------------------------------------ server

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"{time.strftime('%H:%M:%S')}  {self.client_address[0]:<15} {fmt % args}")

    def client(self):
        return f"{self.client_address[0]}:{self.client_address[1]}"

    def current_user(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "session" and value in sessions:
                with db() as conn:
                    return conn.execute("SELECT * FROM users WHERE username=?", (sessions[value],)).fetchone()
        return None

    def send_html(self, content, status=200, headers=()):
        body = content.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location, headers=()):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        user = self.current_user()
        if url.path == "/":
            if user:
                self.redirect("/dashboard")
            else:
                self.send_html(login_page())
        elif url.path == "/dashboard":
            if not user:
                return self.redirect("/")
            search = parse_qs(url.query).get("q", [""])[0]
            self.send_html(dashboard_page(user, search, self.client()))
        elif url.path == "/logout":
            for part in (self.headers.get("Cookie") or "").split(";"):
                sessions.pop(part.strip().partition("=")[2], None)
            self.redirect("/", [("Set-Cookie", "session=; Max-Age=0; Path=/")])
        elif url.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_html(page("Not found", '<div class="box"><h1>404</h1><a href="/">Home</a></div>'), 404)

    def do_POST(self):
        if self.path != "/login":
            return self.send_html("Not found", 404)
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode())
        username = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]
        user = check_login(username, password)
        log_login(self.client(), username, "SUCCESS" if user else "FAILED")
        print(f"          LOGIN {'SUCCESS' if user else 'FAILED '}  user={username!r}  password={password!r}")
        if user:
            token = secrets.token_hex(16)
            sessions[token] = user["username"]
            self.redirect("/dashboard", [("Set-Cookie", f"session={token}; HttpOnly; Path=/")])
        else:
            self.send_html(login_page("Wrong username or password."), 401)


def main():
    init_db()
    ips = {"127.0.0.1"}
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    print("=" * 60)
    print(" DEMO LOGIN SITE  -  server is running")
    for ip in sorted(ips):
        print(f"   http://{ip}:{PORT}")
    print(f" Wireshark filter:  tcp.port == {PORT}")
    print("=" * 60)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
