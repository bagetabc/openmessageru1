#!/usr/bin/env python3
"""Local-only test asset service for the Telegram Desktop companion prototype.

This service does NOT connect to Telegram, Fragment, or telecom networks.
All Stars, usernames, and phone-like identifiers are fictional local records.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("LOCAL_ADMIN_DB", ROOT / "data" / "admin.sqlite3"))
ADMIN_TOKEN = os.environ.get("LOCAL_ADMIN_TOKEN", "")
HOST = "127.0.0.1"
PORT = int(os.environ.get("LOCAL_ADMIN_PORT", "8765"))
ASSET_TYPES = {"stars", "username", "phone"}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, enabled INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS balances (
        user_id TEXT PRIMARY KEY, stars INTEGER NOT NULL DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, asset_type TEXT NOT NULL,
        asset_value TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    for key in ASSET_TYPES:
        db.execute("INSERT OR IGNORE INTO settings(key, enabled) VALUES (?, 1)", (key,))
    db.commit()
    return db


def snapshot():
    with connect() as db:
        settings = {r["key"]: bool(r["enabled"]) for r in db.execute("SELECT * FROM settings")}
        balances = [dict(r) for r in db.execute("SELECT user_id, stars FROM balances ORDER BY user_id")]
        assets = [dict(r) for r in db.execute(
            "SELECT id, user_id, asset_type, asset_value, created_at FROM assets ORDER BY id DESC LIMIT 100"
        )]
    return {"settings": settings, "balances": balances, "assets": assets}


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalTestAdmin/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        # Set LOCAL_ADMIN_TOKEN before exposing the service beyond localhost.
        supplied = self.headers.get("X-Admin-Token", "")
        return bool(ADMIN_TOKEN) and secrets.compare_digest(supplied, ADMIN_TOKEN)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 16_384:
            raise ValueError("Invalid request size")
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            content = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if path == "/api/state":
            if not self.authorized():
                return self.send_json(401, {"error": "Admin token required"})
            return self.send_json(200, snapshot())
        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/issue", "/api/settings"}:
            return self.send_json(404, {"error": "Not found"})
        if not self.authorized():
            return self.send_json(401, {"error": "Admin token required"})
        try:
            payload = self.read_json()
            with connect() as db:
                if path == "/api/settings":
                    settings = payload.get("settings", {})
                    for key, enabled in settings.items():
                        if key not in ASSET_TYPES or not isinstance(enabled, bool):
                            raise ValueError("Invalid setting")
                        db.execute("UPDATE settings SET enabled=? WHERE key=?", (int(enabled), key))
                    db.commit()
                    return self.send_json(200, snapshot())

                user_id = str(payload.get("user_id", "")).strip()
                asset_type = str(payload.get("asset_type", "")).strip()
                if not user_id or len(user_id) > 80:
                    raise ValueError("Enter a valid local user ID")
                if asset_type not in ASSET_TYPES:
                    raise ValueError("Unknown test asset type")
                enabled = db.execute("SELECT enabled FROM settings WHERE key=?", (asset_type,)).fetchone()
                if not enabled or not enabled["enabled"]:
                    raise ValueError("This test asset type is disabled")

                if asset_type == "stars":
                    amount = payload.get("amount")
                    if not isinstance(amount, int) or isinstance(amount, bool) or not 1 <= amount <= 1_000_000:
                        raise ValueError("Stars amount must be an integer from 1 to 1000000")
                    db.execute("INSERT OR IGNORE INTO balances(user_id, stars) VALUES (?, 0)", (user_id,))
                    db.execute("UPDATE balances SET stars=stars+? WHERE user_id=?", (amount, user_id))
                    value = str(amount)
                elif asset_type == "username":
                    value = str(payload.get("value", "")).strip().lstrip("@")
                    if not value or len(value) > 32 or not value.replace("_", "a").isalnum():
                        raise ValueError("Enter a valid local username")
                    value = "@" + value
                else:
                    # Deliberately invalid as a real phone number: local test identifier only.
                    value = "TEST-888-" + secrets.token_hex(4).upper()

                db.execute(
                    "INSERT INTO assets(user_id, asset_type, asset_value) VALUES (?, ?, ?)",
                    (user_id, asset_type, value),
                )
                db.commit()
            return self.send_json(200, snapshot())
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})


if __name__ == "__main__":
    if not ADMIN_TOKEN:
        raise SystemExit("Set LOCAL_ADMIN_TOKEN before starting the local admin service.")
    print(f"Local test admin: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
