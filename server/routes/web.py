"""Web frontend routes (login, logout, dashboard, preview) for RaspiDeck Server."""

from __future__ import annotations

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from auth import is_rate_limited, record_attempt, require_auth, verify_password
from config import ADMIN_PASSWORD, SPLASH_PATH

web_bp = Blueprint("web", __name__)


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page and authentication handler."""
    if request.method == "POST":
        if is_rate_limited():
            return render_template(
                "login.html", error="Too many failed attempts. Try again later."
            ), 429

        pw = request.form.get("password")
        if pw and verify_password(pw, ADMIN_PASSWORD):
            session.clear()  # rotate session on login
            session["authenticated"] = True
            return redirect(url_for("web.dashboard"))

        record_attempt()
        return render_template("login.html", error="Invalid password")
    return render_template("login.html", error=None)


@web_bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for("web.login"))


@web_bp.route("/")
def dashboard():
    """Main digital signage management dashboard."""
    if not require_auth():
        return redirect(url_for("web.login"))
    return render_template("dashboard.html")


@web_bp.route("/preview-splash")
def preview_splash():
    """Serve boot splash PNG for web preview."""
    if not require_auth():
        return redirect(url_for("web.login"))
    if SPLASH_PATH.exists():
        return send_from_directory(SPLASH_PATH.parent, SPLASH_PATH.name)
    return "Splash not generated. Run generate_splash.py first.", 404
