"""Instagram Graph API wrapper — Reels publish + auto comment.

Zaruri baat: Instagram ka publishing API sirf **Business ya Creator** account par
kaam karta hai jo ek Facebook Page se linked ho. Purely personal account par
Instagram khud API se posting allow nahi karta (paisa ya code ka masla nahi hai,
Meta ki policy hai). Account ko Creator mein switch karna free hai.

Flow (Meta ka official 3-step resumable flow):
    1. POST /{ig_user_id}/media          -> container id
    2. GET  /{container_id}?fields=status_code  (FINISHED hone tak poll)
    3. POST /{ig_user_id}/media_publish  -> media id
"""

import time

import requests

import db

GRAPH = "https://graph.facebook.com/v21.0"
TIMEOUT = 60


class InstagramError(Exception):
    pass


def _token():
    token = db.get_setting("ig_access_token", "")
    if not token:
        raise InstagramError("Instagram access token set nahi hai. /enter page par jao.")
    return token


def _user_id():
    uid = db.get_setting("ig_user_id", "")
    if not uid:
        raise InstagramError("Instagram user ID set nahi hai. /enter page par jao.")
    return uid


def is_connected():
    return bool(db.get_setting("ig_access_token") and db.get_setting("ig_user_id"))


def disconnect():
    db.delete_setting("ig_access_token")
    db.delete_setting("ig_user_id")
    db.delete_setting("ig_account")
    db.log("Instagram account disconnected", level="warn", source="instagram")


def _call(method, path, **params):
    params["access_token"] = _token()
    url = f"{GRAPH}/{path.lstrip('/')}"
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=TIMEOUT)
        else:
            resp = requests.post(url, data=params, timeout=TIMEOUT)
    except requests.RequestException as err:
        raise InstagramError(f"Instagram network error: {err}") from err

    try:
        payload = resp.json()
    except ValueError:
        raise InstagramError(f"Instagram ne unexpected response diya (HTTP {resp.status_code})")

    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        raise InstagramError(
            f"{err.get('message', 'Unknown error')} "
            f"(type={err.get('type')}, code={err.get('code')})"
        )
    if resp.status_code >= 400:
        raise InstagramError(f"Instagram HTTP {resp.status_code}: {resp.text[:300]}")
    return payload


def account_info():
    data = _call(
        "GET",
        _user_id(),
        fields="id,username,name,profile_picture_url,followers_count,media_count",
    )
    return {
        "id": data.get("id"),
        "username": data.get("username"),
        "name": data.get("name"),
        "picture": data.get("profile_picture_url"),
        "followers": data.get("followers_count"),
        "media": data.get("media_count"),
    }


def verify_and_save():
    """Token check karke account info settings mein cache kar do."""
    info = account_info()
    db.set_json("ig_account", info)
    db.log("Instagram account connected: @%s" % info.get("username"), source="instagram")
    return info


def upload_reel(video_url, caption="", share_to_feed=True, cover_url=None,
                on_progress=None, poll_seconds=5, max_wait=900):
    """Public video URL se Reel publish karo. Media ID return karta hai."""
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": (caption or "")[:2200],
        "share_to_feed": "true" if share_to_feed else "false",
    }
    if cover_url:
        params["thumb_offset"] = 0
        params["cover_url"] = cover_url

    container = _call("POST", f"{_user_id()}/media", **params)
    container_id = container.get("id")
    if not container_id:
        raise InstagramError("Instagram ne container ID nahi diya.")
    if on_progress:
        on_progress(20)

    # Instagram khud hamare URL se video download karta hai, isliye poll karna padta hai.
    waited = 0
    while waited < max_wait:
        status = _call("GET", container_id, fields="status_code,status")
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise InstagramError(
                "Instagram video process nahi kar paya: %s" % status.get("status", "ERROR")
            )
        if on_progress:
            on_progress(min(20 + waited * 60 // max_wait, 80))
        time.sleep(poll_seconds)
        waited += poll_seconds
    else:
        raise InstagramError(
            f"Instagram ne {max_wait}s mein video process nahi kiya (container {container_id})."
        )

    published = _call("POST", f"{_user_id()}/media_publish", creation_id=container_id)
    media_id = published.get("id")
    if not media_id:
        raise InstagramError("Instagram ne publish ke baad media ID nahi diya.")
    if on_progress:
        on_progress(100)
    return media_id


def permalink(media_id):
    try:
        return _call("GET", media_id, fields="permalink").get("permalink")
    except InstagramError:
        return None


def post_comment(media_id, text):
    resp = _call("POST", f"{media_id}/comments", message=text)
    return resp.get("id")


def publishing_limit():
    """Instagram 24 ghante mein 50 posts allow karta hai — bacha hua quota."""
    try:
        data = _call(
            "GET", f"{_user_id()}/content_publishing_limit", fields="config,quota_usage"
        )
        item = (data.get("data") or [{}])[0]
        return {
            "used": item.get("quota_usage", 0),
            "limit": (item.get("config") or {}).get("quota_total", 50),
        }
    except InstagramError:
        return None
