"""RaspiDeck Server — digital signage hub web dashboard and player API."""
# ruff: noqa: E402 — sys.path must be modified before local imports

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure server directory is on sys.path for direct module imports
SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from flask import Flask  # noqa: E402
from flask_cors import CORS  # noqa: E402
from flask_wtf import CSRFProtect  # noqa: E402

csrf = CSRFProtect()

from config import (  # noqa: E402
    ADMIN_PASSWORD,
    ALLOWED_EXTENSIONS,
    BASE_DIR,
    DB_PATH,
    MAX_CONTENT_LENGTH,
    MEDIA_DIR,
    SECRET_KEY,
)
from db import get_db, init_db  # noqa: E402
from routes import admin_api_bp, player_api_bp, web_bp  # noqa: E402


def create_app() -> Flask:
    """Application factory for RaspiDeck Server."""
    flask_app = Flask(
        __name__,
        template_folder=str(SERVER_DIR / "templates"),
        static_folder=str(SERVER_DIR / "static"),
        static_url_path="/static",
    )
    flask_app.secret_key = SECRET_KEY
    flask_app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    flask_app.config["TEMPLATES_AUTO_RELOAD"] = True
    flask_app.jinja_env.auto_reload = True

    # Security Cookies
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if os.environ.get("HTTPS_ONLY", "false").lower() == "true":
        flask_app.config["SESSION_COOKIE_SECURE"] = True

    # ProxyFix to properly handle headers from Cloudflare Tunnel / reverse proxy
    from werkzeug.middleware.proxy_fix import ProxyFix
    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # CORS — allow cross-origin API calls (required for Cloudflare Tunnel and LAN players)
    CORS(
        flask_app,
        resources={r"/api/*": {"origins": [
            "https://raspideck.padangmerdeka.com",
            "http://localhost:*",
            "http://127.0.0.1:*",
            r"http://192\.168\..*",
        ]}},
        supports_credentials=True,
    )

    # CSRF Protection (exempt API blueprints — they use session auth via require_auth)
    csrf.init_app(flask_app)
    csrf.exempt(player_api_bp)
    csrf.exempt(admin_api_bp)

    # Initialize SQLite database schema
    init_db()

    # Register blueprints
    flask_app.register_blueprint(web_bp)
    flask_app.register_blueprint(player_api_bp)
    flask_app.register_blueprint(admin_api_bp)

    @flask_app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    return flask_app


# WSGI application instance for gunicorn (e.g. gunicorn app:app)
app = create_app()

__all__ = [
    "ADMIN_PASSWORD",
    "ALLOWED_EXTENSIONS",
    "BASE_DIR",
    "DB_PATH",
    "MEDIA_DIR",
    "SECRET_KEY",
    "app",
    "create_app",
    "get_db",
    "init_db",
]

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        port = 8000
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
