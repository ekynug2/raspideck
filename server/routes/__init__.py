"""Route blueprints for RaspiDeck Server."""

from __future__ import annotations

from routes.admin_api import admin_api_bp
from routes.player_api import player_api_bp
from routes.web import web_bp

__all__ = ["admin_api_bp", "player_api_bp", "web_bp"]
