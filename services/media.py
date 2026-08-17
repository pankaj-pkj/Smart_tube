"""Uploaded files ke liye chhota helper.

Instagram apne server se hamari video **download** karta hai, isliye video ka ek
public URL chahiye. Hum app se hi serve karte hain, ek HMAC signature ke saath
taaki URL guess na kiya ja sake (poora storage folder public na ho jaye).
"""

import hashlib
import hmac
import os
import re
import uuid

import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_DIR = os.path.join(BASE_DIR, "storage", "videos")
THUMB_DIR = os.path.join(BASE_DIR, "storage", "thumbs")

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_dirs():
    os.makedirs(VIDEO_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)


def _secret():
    return (os.environ.get("SECRET_KEY") or "smart-tube-dev-secret").encode()


def safe_name(filename):
    name = _SAFE.sub("_", os.path.basename(filename or "file")).strip("._") or "file"
    return f"{uuid.uuid4().hex[:10]}_{name[:60]}"


def save_upload(file_storage, kind="video"):
    """Flask FileStorage ko disk par likho, relative path return karo."""
    ensure_dirs()
    ext = os.path.splitext(file_storage.filename or "")[1].lower()
    allowed = VIDEO_EXT if kind == "video" else IMAGE_EXT
    if ext not in allowed:
        raise ValueError(
            f"'{ext or 'unknown'}' file type allowed nahi hai. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )
    target_dir = VIDEO_DIR if kind == "video" else THUMB_DIR
    name = safe_name(file_storage.filename)
    path = os.path.join(target_dir, name)
    file_storage.save(path)
    return os.path.relpath(path, BASE_DIR)


def abs_path(rel_path):
    return os.path.join(BASE_DIR, rel_path) if rel_path else None


def exists(rel_path):
    path = abs_path(rel_path)
    return bool(path and os.path.isfile(path))


def size_mb(rel_path):
    path = abs_path(rel_path)
    if not path or not os.path.isfile(path):
        return 0
    return round(os.path.getsize(path) / (1024 * 1024), 1)


def delete(rel_path):
    path = abs_path(rel_path)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def sign(rel_path):
    return hmac.new(_secret(), rel_path.encode(), hashlib.sha256).hexdigest()[:20]


def verify(rel_path, signature):
    return hmac.compare_digest(sign(rel_path), signature or "")


def base_url():
    url = db.get_setting("public_base_url") or os.environ.get(
        "PUBLIC_BASE_URL", "http://localhost:8000"
    )
    return url.rstrip("/")


def public_url(rel_path):
    """Instagram ke liye publicly reachable signed URL."""
    return f"{base_url()}/media/{sign(rel_path)}/{rel_path.replace(os.sep, '/')}"
