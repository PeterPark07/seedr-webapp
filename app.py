import os
import time
import hmac
from functools import wraps
from typing import Optional, Dict, Any
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv

from seedr_py import (
    SeedrClient,
    format_bytes,
    AuthenticationError,
    TorrentError,
    NotFoundError,
    SeedrError
)

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "seedr_webapp_super_secret_session_key_2026")

MASTER_EMAIL = os.getenv("SEEDR_EMAIL", "")
MASTER_PASSWORD = os.getenv("SEEDR_PASSWORD", "")
MASTER_PASSCODE = os.getenv("MASTER_PASSCODE", "9595")

# Global client cache
master_client: Optional[SeedrClient] = None
master_client_timestamp: float = 0
user_clients: Dict[str, SeedrClient] = {}

def get_master_client() -> Optional[SeedrClient]:
    """Retrieves or refreshes the master host SeedrClient."""
    global master_client, master_client_timestamp
    if not MASTER_EMAIL or not MASTER_PASSWORD:
        return None

    # Refresh client every 3 hours
    now = time.time()
    if master_client is None or (now - master_client_timestamp > 10800):
        master_client = SeedrClient.from_password(MASTER_EMAIL, MASTER_PASSWORD)
        master_client_timestamp = now

    return master_client

def get_current_client() -> Optional[SeedrClient]:
    """Returns the authenticated SeedrClient for the active session."""
    if not session.get("logged_in"):
        return None

    auth_type = session.get("auth_type")
    if auth_type == "guest":
        return get_master_client()

    if auth_type == "user":
        email = session.get("email")
        password = session.get("password")
        if not email or not password:
            return None
        if email not in user_clients:
            user_clients[email] = SeedrClient.from_password(email, password)
        return user_clients[email]

    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function

app.jinja_env.filters['format_bytes'] = format_bytes

# --- Brute Force Protection ---
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutes
failed_attempts: Dict[str, Dict[str, Any]] = {}

def get_client_ip() -> str:
    """Extract real client IP even behind Render / reverse proxies."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

def check_rate_limit(ip: str) -> Optional[int]:
    """Returns remaining lockout seconds if IP is locked out, else None."""
    record = failed_attempts.get(ip)
    if not record:
        return None
    lockout_until = record.get("lockout_until", 0)
    now = time.time()
    if now < lockout_until:
        return int(lockout_until - now)
    if lockout_until > 0 and now >= lockout_until:
        del failed_attempts[ip]
    return None

def record_failed_attempt(ip: str) -> int:
    """Records a failed login attempt and applies progressive delay / lockout."""
    now = time.time()
    record = failed_attempts.setdefault(ip, {"count": 0, "lockout_until": 0})
    record["count"] += 1

    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["lockout_until"] = now + LOCKOUT_SECONDS
        return 0

    # Artificial delay to choke automated script fuzzers
    time.sleep(1.0)
    return MAX_FAILED_ATTEMPTS - record["count"]

def reset_failed_attempts(ip: str):
    """Resets failed attempt counter on successful login."""
    if ip in failed_attempts:
        del failed_attempts[ip]

# --- Authentication Routes ---

@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/auth/passcode", methods=["POST"])
def auth_passcode():
    ip = get_client_ip()
    locked_for = check_rate_limit(ip)
    if locked_for:
        return jsonify({
            "success": False,
            "error": f"Too many failed attempts. Locked out for {locked_for // 60 + 1} more minute(s)."
        }), 429

    data = request.get_json(silent=True) or {}
    passcode = str(data.get("passcode", "")).strip()

    if hmac.compare_digest(passcode, MASTER_PASSCODE):
        reset_failed_attempts(ip)
        try:
            client = get_master_client()
            if not client:
                return jsonify({"success": False, "error": "Server host account not configured in .env"}), 500
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to connect host account: {e}"}), 500

        session.clear()
        session["logged_in"] = True
        session["auth_type"] = "guest"
        session["user_label"] = "Guest Passcode Access (Shared Cloud)"
        return jsonify({"success": True})

    remaining = record_failed_attempt(ip)
    if remaining == 0:
        return jsonify({
            "success": False,
            "error": "Too many failed attempts. You have been locked out for 15 minutes."
        }), 429

    return jsonify({
        "success": False,
        "error": f"Invalid passcode. ({remaining} attempt(s) remaining before 15-minute lockout)"
    }), 401

@app.route("/auth/login", methods=["POST"])
def auth_login():
    ip = get_client_ip()
    locked_for = check_rate_limit(ip)
    if locked_for:
        return jsonify({
            "success": False,
            "error": f"Too many failed attempts. Locked out for {locked_for // 60 + 1} more minute(s)."
        }), 429

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    try:
        # Validate credentials with SeedrClient
        client = SeedrClient.from_password(email, password)
        user_clients[email] = client
        reset_failed_attempts(ip)

        session.clear()
        session["logged_in"] = True
        session["auth_type"] = "user"
        session["email"] = email
        session["password"] = password
        session["user_label"] = email
        return jsonify({"success": True})
    except AuthenticationError as e:
        remaining = record_failed_attempt(ip)
        if remaining == 0:
            return jsonify({
                "success": False,
                "error": "Too many failed attempts. You have been locked out for 15 minutes."
            }), 429
        return jsonify({
            "success": False,
            "error": f"Invalid Seedr credentials ({remaining} attempt(s) remaining before 15-minute lockout)"
        }), 401
    except Exception as e:
        return jsonify({"success": False, "error": f"Login failed: {e}"}), 500

@app.route("/logout")
def logout():
    email = session.get("email")
    if email and email in user_clients:
        try:
            user_clients[email].close()
        except Exception:
            pass
        del user_clients[email]
    session.clear()
    return redirect(url_for("login_page"))

# --- Dashboard & Cloud Endpoints ---

@app.route("/")
@login_required
def index():
    return render_template("index.html", user_label=session.get("user_label", "Active User"))

@app.route("/api/status")
@login_required
def get_status():
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        quota = client.get_quota()
        return jsonify({
            "success": True,
            "user_label": session.get("user_label", "Connected"),
            "auth_type": session.get("auth_type", "guest"),
            "space_used": quota.space_used,
            "space_max": quota.space_max,
            "bandwidth_used": quota.bandwidth_used,
            "space_used_formatted": quota.space_used_formatted,
            "space_max_formatted": quota.space_max_formatted,
            "pct": quota.space_pct
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/folder/<int:folder_id>")
@login_required
def get_folder(folder_id):
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        folder = client.get_folder(folder_id)
        return jsonify({
            "success": True,
            "id": folder.id,
            "path": folder.path or "Home",
            "folders": [
                {
                    "id": f.id,
                    "name": f.name,
                    "path": f.name,
                    "size": f.size,
                    "size_formatted": f.size_formatted,
                    "last_update": f.last_update
                }
                for f in folder.folders
            ],
            "files": [
                {
                    "id": fi.id,
                    "name": fi.name,
                    "size": fi.size,
                    "size_formatted": fi.size_formatted,
                    "hash": fi.hash,
                    "is_video": fi.is_video,
                    "is_audio": fi.is_audio,
                    "thumb": fi.thumb
                }
                for fi in folder.files
            ],
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "size": t.size,
                    "size_formatted": t.size_formatted,
                    "progress": t.progress,
                    "download_rate": t.download_rate,
                    "seeders": t.seeders,
                    "leechers": t.leechers
                }
                for t in folder.tasks
            ]
        })
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/torrent/add", methods=["POST"])
@login_required
def add_torrent():
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        folder_id = int(request.form.get("folder_id", 0))

        if "torrent_file" in request.files:
            file = request.files["torrent_file"]
            if file and file.filename.endswith(".torrent"):
                content = file.read()
                res = client.add_torrent_file(content, folder_id=folder_id)
                return jsonify({"success": True, "result": res})

        magnet = request.form.get("magnet", "").strip()
        if not magnet:
            return jsonify({"success": False, "error": "No magnet link or .torrent file provided"}), 400

        res = client.add_magnet(magnet, folder_id=folder_id)
        return jsonify({"success": True, "result": res})
    except TorrentError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/file/<int:file_id>/url")
@login_required
def get_file_url(file_id):
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        link = client.get_file_url(file_id)
        return jsonify({"success": True, "url": link.url, "name": link.name})
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/file/<int:file_id>/stream")
@login_required
def get_file_stream(file_id):
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        stream = client.get_video_stream(file_id)
        return jsonify({
            "success": True,
            "name": stream.name,
            "raw_url": stream.raw_url,
            "hls_url": stream.hls_url,
            "subtitles": stream.subtitles
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/folder/<int:folder_id>/zip")
@login_required
def get_folder_zip(folder_id):
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        archive = client.get_folder_zip_url(folder_id)
        return jsonify({"success": True, "url": archive.url, "archive_id": archive.archive_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/task/<int:task_id>/cancel", methods=["POST"])
@login_required
def cancel_task(task_id):
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        res = client.cancel_task(task_id)
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/item/delete", methods=["POST"])
@login_required
def delete_item():
    client = get_current_client()
    if not client:
        return jsonify({"success": False, "error": "Session expired"}), 401
    try:
        item_type = request.form.get("type")
        item_id = int(request.form.get("id"))
        if item_type == "folder":
            res = client.delete_folder(item_id)
        else:
            res = client.delete_file(item_id)
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting Seedr WebApp on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
