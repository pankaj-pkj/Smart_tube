"""YouTube Data API v3 wrapper: OAuth, video upload, thumbnail, comment.

Sab credentials SQLite ke settings table mein rehte hain, user unhe /enter page se
daalta hai. Koi credential file server par manually rakhne ki zarurat nahi.
"""

import json

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import db

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Quota cost (units) — dashboard ke estimator ke liye.
COST_UPLOAD = 1600
COST_THUMBNAIL = 50
COST_COMMENT = 50
DAILY_QUOTA = 10000


class YouTubeError(Exception):
    def __init__(self, message, reason=None):
        super().__init__(message)
        self.reason = reason

    @property
    def is_quota(self):
        return self.reason in ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded")


def _client_config(redirect_uri):
    client_id = db.get_setting("yt_client_id", "")
    client_secret = db.get_setting("yt_client_secret", "")
    if not client_id or not client_secret:
        raise YouTubeError("YouTube client ID/secret set nahi hai. /enter page par jao.")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def auth_url(redirect_uri, state=None):
    flow = Flow.from_client_config(
        _client_config(redirect_uri), scopes=SCOPES, redirect_uri=redirect_uri
    )
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # refresh_token har baar mile
        state=state,
    )
    return url, state


def exchange_code(redirect_uri, authorization_response):
    flow = Flow.from_client_config(
        _client_config(redirect_uri), scopes=SCOPES, redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    db.set_json(
        "yt_token",
        {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or SCOPES),
        },
    )
    info = channel_info()
    if info:
        db.set_json("yt_channel", info)
    db.log("YouTube account connected: %s" % (info or {}).get("title", "?"),
           source="youtube")
    return info


def is_connected():
    return bool(db.get_json("yt_token"))


def disconnect():
    db.delete_setting("yt_token")
    db.delete_setting("yt_channel")
    db.log("YouTube account disconnected", level="warn", source="youtube")


def _credentials():
    data = db.get_json("yt_token")
    if not data:
        raise YouTubeError("YouTube connected nahi hai. /enter page se connect karo.")
    creds = Credentials(**data)
    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
        data["token"] = creds.token
        db.set_json("yt_token", data)
    return creds


def _service():
    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def _wrap(err):
    """googleapiclient HttpError ko readable message mein badlo."""
    reason, message = None, str(err)
    try:
        payload = json.loads(err.content.decode("utf-8"))
        detail = payload.get("error", {})
        message = detail.get("message", message)
        errors = detail.get("errors") or []
        if errors:
            reason = errors[0].get("reason")
            message = errors[0].get("message", message)
    except Exception:  # noqa: BLE001 - kuch bhi parse fail ho to raw message hi sahi
        pass
    if reason in ("quotaExceeded", "uploadLimitExceeded"):
        message = (
            f"{message} — YouTube ka daily API quota khatam. Default quota 10,000 "
            "units/day hota hai aur ek upload 1600 units leta hai (~6 uploads/din). "
            "Baaki uploads apne aap kal ke liye reschedule ho jayenge."
        )
    return YouTubeError(message, reason)


def channel_info():
    try:
        resp = _service().channels().list(part="snippet,statistics", mine=True).execute()
    except HttpError as err:
        raise _wrap(err) from err
    items = resp.get("items") or []
    if not items:
        return None
    item = items[0]
    return {
        "id": item["id"],
        "title": item["snippet"]["title"],
        "thumbnail": item["snippet"].get("thumbnails", {}).get("default", {}).get("url"),
        "subscribers": item.get("statistics", {}).get("subscriberCount"),
        "videos": item.get("statistics", {}).get("videoCount"),
    }


def upload_video(
    video_path,
    title,
    description="",
    tags=None,
    privacy="public",
    category_id="22",
    made_for_kids=False,
    on_progress=None,
):
    body = {
        "snippet": {
            "title": title[:100],
            "description": (description or "")[:5000],
            "tags": tags or [],
            "categoryId": category_id or "22",
        },
        "status": {
            "privacyStatus": privacy or "public",
            "selfDeclaredMadeForKids": bool(made_for_kids),
        },
    }
    media = MediaFileUpload(video_path, chunksize=4 * 1024 * 1024, resumable=True)
    try:
        request = _service().videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and on_progress:
                on_progress(int(status.progress() * 100))
        if on_progress:
            on_progress(100)
        return response["id"]
    except HttpError as err:
        raise _wrap(err) from err
    finally:
        # File handle band karo warna Windows/long-running process par lock rehta hai.
        try:
            media.stream().close()
        except Exception:  # noqa: BLE001
            pass


def set_thumbnail(video_id, thumb_path):
    media = MediaFileUpload(thumb_path)
    try:
        _service().thumbnails().set(videoId=video_id, media_body=media).execute()
    except HttpError as err:
        raise _wrap(err) from err
    finally:
        try:
            media.stream().close()
        except Exception:  # noqa: BLE001
            pass


def post_comment(video_id, text):
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    try:
        resp = _service().commentThreads().insert(part="snippet", body=body).execute()
    except HttpError as err:
        raise _wrap(err) from err
    return resp["id"]


def pin_comment(comment_thread_id):
    """Apne hi channel ke comment ko pin karna.

    YouTube Data API mein pin ka koi direct field nahi hai — moderation status
    set karna hi sabse kareeb hai, aur wo har case mein pin nahi karta.
    Fail ho to upload fail nahi hona chahiye, isliye caller ise best-effort maane.
    """
    try:
        _service().comments().setModerationStatus(
            id=comment_thread_id, moderationStatus="published"
        ).execute()
        return True
    except HttpError:
        return False


def estimate_quota(uploads_per_day, with_thumbnail=True, with_comment=True):
    per_upload = COST_UPLOAD
    if with_thumbnail:
        per_upload += COST_THUMBNAIL
    if with_comment:
        per_upload += COST_COMMENT
    used = per_upload * uploads_per_day
    return {
        "per_upload": per_upload,
        "used": used,
        "limit": DAILY_QUOTA,
        "max_uploads": DAILY_QUOTA // per_upload,
        "over": used > DAILY_QUOTA,
    }
