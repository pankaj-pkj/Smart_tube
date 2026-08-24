"""Background scheduler — due uploads uthata hai aur chalata hai.

Design jaan-bujh kar simple rakha hai: har campaign banate waqt uski saari uploads
ki rows pehle hi DB mein bana di jaati hain (scheduled_at ke saath). Scheduler har
TICK_SECONDS par due rows dhoondta hai. Iska fayda — poora schedule dashboard par
dikhta hai, user kisi bhi row ko skip/reschedule/run-now kar sakta hai, aur server
restart hone par bhi schedule zinda rehta hai (sab DB mein hai, memory mein nahi).
"""

import os
import threading
from datetime import datetime, timedelta, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler

import db
from services import instagram_service as ig
from services import media, textgen
from services import youtube_service as yt

try:  # Python 3.9+
    from zoneinfo import ZoneInfo

    PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # noqa: BLE001 - tzdata na ho to fallback
    PACIFIC = timezone(timedelta(hours=-8))

MAX_ATTEMPTS = 3
RETRY_MINUTES = 10

_tick_lock = threading.Lock()
_scheduler = None


# ------------------------------------------------------------------ helpers


def next_quota_reset():
    """YouTube ka quota midnight Pacific Time par reset hota hai."""
    now_pt = db.utcnow().astimezone(PACIFIC)
    tomorrow = (now_pt + timedelta(days=1)).replace(
        hour=0, minute=5, second=0, microsecond=0
    )
    return tomorrow.astimezone(timezone.utc)


def _campaign_tz():
    name = db.get_setting("timezone", "UTC")
    try:
        from zoneinfo import ZoneInfo as _ZI

        return _ZI(name)
    except Exception:  # noqa: BLE001
        return timezone.utc


def build_schedule(campaign_id):
    """Campaign ke liye saari upload rows banao."""
    camp = db.query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True)
    if not camp:
        return 0

    platforms = ["youtube", "instagram"] if camp["platform"] == "both" else [camp["platform"]]
    start = db.parse_iso(camp["start_at"])
    interval = timedelta(minutes=camp["interval_minutes"])
    tz = _campaign_tz()
    created = 0

    for seq in range(1, camp["total_uploads"] + 1):
        when = start + interval * (seq - 1)
        ctx = textgen.build_context(seq, camp["total_uploads"], camp["name"], when, tz)
        for platform in platforms:
            if platform == "youtube":
                title = textgen.render(camp["title_tpl"], ctx)
                comment = textgen.render(camp["comment_tpl"], ctx)
            else:
                title = textgen.render(camp["ig_caption_tpl"] or camp["title_tpl"], ctx)
                comment = textgen.render(camp["ig_comment_tpl"] or camp["comment_tpl"], ctx)
            db.execute(
                "INSERT INTO uploads (campaign_id, platform, seq, scheduled_at, status, "
                "title, comment_text) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (campaign_id, platform, seq, db.iso(when), title, comment),
            )
            created += 1

    db.log(
        f"Schedule banaya: {created} uploads, har {camp['interval_minutes']} minute",
        source="scheduler",
        campaign_id=campaign_id,
    )
    return created


def _finish(upload_id, status, **fields):
    sets = ["status = ?", "finished_at = ?"]
    args = [status, db.iso(db.utcnow())]
    for key, value in fields.items():
        sets.append(f"{key} = ?")
        args.append(value)
    args.append(upload_id)
    db.execute(f"UPDATE uploads SET {', '.join(sets)} WHERE id = ?", args)


def _defer(upload_id, when, error=None):
    db.execute(
        "UPDATE uploads SET status = 'pending', scheduled_at = ?, error = ?, "
        "started_at = NULL, progress = 0 WHERE id = ?",
        (db.iso(when), error, upload_id),
    )


def _shift_remaining(campaign_id, platform, delta, exclude_id=None):
    """Quota hit hone par baaki pending uploads ko aage khiskao, gap same rahe."""
    rows = db.query(
        "SELECT id, scheduled_at FROM uploads WHERE campaign_id = ? AND platform = ? "
        "AND status = 'pending' AND id != ?",
        (campaign_id, platform, exclude_id or -1),
    )
    for row in rows:
        db.execute(
            "UPDATE uploads SET scheduled_at = ? WHERE id = ?",
            (db.iso(db.parse_iso(row["scheduled_at"]) + delta), row["id"]),
        )
    return len(rows)


# ------------------------------------------------------------------ runners


def _progress(upload_id):
    def setter(percent):
        db.execute("UPDATE uploads SET progress = ? WHERE id = ?", (percent, upload_id))

    return setter


def _run_youtube(up, camp):
    video = media.abs_path(camp["video_path"])
    video_id = yt.upload_video(
        video_path=video,
        title=up["title"] or camp["name"],
        description=camp["description"] or "",
        tags=[t.strip() for t in (camp["tags"] or "").split(",") if t.strip()],
        privacy=camp["privacy"],
        category_id=camp["category_id"],
        made_for_kids=bool(camp["made_for_kids"]),
        on_progress=_progress(up["id"]),
    )
    url = f"https://www.youtube.com/watch?v={video_id}"
    db.execute(
        "UPDATE uploads SET remote_id = ?, remote_url = ? WHERE id = ?",
        (video_id, url, up["id"]),
    )
    db.log(f"YouTube upload #{up['seq']} done: {url}", source="youtube",
           campaign_id=camp["id"], upload_id=up["id"])

    # Thumbnail aur comment fail ho jayein to upload ko fail mat karo — video to chadh gaya.
    if camp["thumb_path"] and media.exists(camp["thumb_path"]):
        try:
            yt.set_thumbnail(video_id, media.abs_path(camp["thumb_path"]))
        except yt.YouTubeError as err:
            db.log(f"Thumbnail set nahi hua: {err}", level="warn", source="youtube",
                   campaign_id=camp["id"], upload_id=up["id"])

    comment_id = None
    if up["comment_text"]:
        try:
            comment_id = yt.post_comment(video_id, up["comment_text"])
            if camp["pin_comment"]:
                yt.pin_comment(comment_id)
            db.log(f"Comment post hua: {up['comment_text'][:80]}", source="youtube",
                   campaign_id=camp["id"], upload_id=up["id"])
        except yt.YouTubeError as err:
            db.log(f"Comment post nahi hua: {err}", level="warn", source="youtube",
                   campaign_id=camp["id"], upload_id=up["id"])

    _finish(up["id"], "success", remote_id=video_id, remote_url=url,
            comment_id=comment_id, progress=100, error=None)


def _run_instagram(up, camp):
    video_url = media.public_url(camp["video_path"])
    media_id = ig.upload_reel(
        video_url=video_url,
        caption=up["title"] or "",
        share_to_feed=bool(camp["ig_share_to_feed"]),
        on_progress=_progress(up["id"]),
    )
    link = ig.permalink(media_id) or f"https://www.instagram.com/reel/{media_id}"
    db.execute(
        "UPDATE uploads SET remote_id = ?, remote_url = ? WHERE id = ?",
        (media_id, link, up["id"]),
    )
    db.log(f"Instagram reel #{up['seq']} publish hua: {link}", source="instagram",
           campaign_id=camp["id"], upload_id=up["id"])

    comment_id = None
    if up["comment_text"]:
        try:
            comment_id = ig.post_comment(media_id, up["comment_text"])
            db.log(f"IG comment post hua: {up['comment_text'][:80]}", source="instagram",
                   campaign_id=camp["id"], upload_id=up["id"])
        except ig.InstagramError as err:
            db.log(f"IG comment post nahi hua: {err}", level="warn", source="instagram",
                   campaign_id=camp["id"], upload_id=up["id"])

    _finish(up["id"], "success", remote_id=media_id, remote_url=link,
            comment_id=comment_id, progress=100, error=None)


def run_upload(upload_id):
    """Ek upload chalao. Ye function hi retry/quota policy sambhalta hai."""
    up = db.query("SELECT * FROM uploads WHERE id = ?", (upload_id,), one=True)
    if not up or up["status"] == "running":
        return
    camp = db.query("SELECT * FROM campaigns WHERE id = ?", (up["campaign_id"],), one=True)
    if not camp:
        _finish(upload_id, "failed", error="Campaign delete ho chuka hai")
        return

    db.execute(
        "UPDATE uploads SET status = 'running', started_at = ?, attempts = attempts + 1, "
        "progress = 0, error = NULL WHERE id = ?",
        (db.iso(db.utcnow()), upload_id),
    )
    up = db.query("SELECT * FROM uploads WHERE id = ?", (upload_id,), one=True)

    try:
        if not media.exists(camp["video_path"]):
            raise RuntimeError(f"Video file storage mein nahi mili: {camp['video_path']}")
        if up["platform"] == "youtube":
            _run_youtube(up, camp)
        else:
            _run_instagram(up, camp)

    except yt.YouTubeError as err:
        if err.is_quota:
            reset = next_quota_reset()
            delta = reset - db.utcnow()
            shifted = _shift_remaining(camp["id"], "youtube", delta, exclude_id=upload_id)
            # Quota fail user ki galti nahi hai, isliye attempt count wapas kam kar do
            # warna 3 quota errors ke baad upload permanently failed ho jayega.
            db.execute(
                "UPDATE uploads SET attempts = MAX(attempts - 1, 0) WHERE id = ?", (upload_id,)
            )
            _defer(upload_id, reset, error=str(err))
            db.log(
                f"Quota khatam. Upload #{up['seq']} aur {shifted} baaki uploads "
                f"{db.iso(reset)} par shift kar diye.",
                level="warn", source="youtube", campaign_id=camp["id"], upload_id=upload_id,
            )
        else:
            _fail_or_retry(up, camp, str(err), "youtube")

    except ig.InstagramError as err:
        _fail_or_retry(up, camp, str(err), "instagram")

    except Exception as err:  # noqa: BLE001 - koi bhi crash campaign ko na rok de
        _fail_or_retry(up, camp, str(err), up["platform"])


def _fail_or_retry(up, camp, message, source):
    if up["attempts"] < MAX_ATTEMPTS:
        when = db.utcnow() + timedelta(minutes=RETRY_MINUTES)
        _defer(up["id"], when, error=message)
        db.log(
            f"Upload #{up['seq']} fail hua (attempt {up['attempts']}/{MAX_ATTEMPTS}), "
            f"{RETRY_MINUTES} min baad retry: {message}",
            level="warn", source=source, campaign_id=camp["id"], upload_id=up["id"],
        )
    else:
        _finish(up["id"], "failed", error=message)
        db.log(
            f"Upload #{up['seq']} {MAX_ATTEMPTS} attempts ke baad fail: {message}",
            level="error", source=source, campaign_id=camp["id"], upload_id=up["id"],
        )


# ------------------------------------------------------------------ tick


def tick():
    """Har TICK_SECONDS par chalta hai: due uploads dhoondo aur ek-ek karke chalao."""
    if not _tick_lock.acquire(blocking=False):
        return  # pichhla tick abhi chal raha hai
    try:
        now = db.iso(db.utcnow())
        due = db.query(
            "SELECT u.id FROM uploads u JOIN campaigns c ON c.id = u.campaign_id "
            "WHERE u.status = 'pending' AND u.scheduled_at <= ? AND c.status = 'running' "
            "ORDER BY u.scheduled_at LIMIT 5",
            (now,),
        )
        for row in due:
            run_upload(row["id"])

        # Jo campaigns poore ho gaye unhe done mark karo.
        db.execute(
            "UPDATE campaigns SET status = 'done' WHERE status = 'running' AND id NOT IN "
            "(SELECT campaign_id FROM uploads WHERE status IN ('pending','running'))"
        )
    except Exception as err:  # noqa: BLE001 - scheduler thread kabhi mare nahi
        db.log(f"Scheduler tick error: {err}", level="error", source="scheduler")
    finally:
        _tick_lock.release()


# ------------------------------------------------------------ keep alive


_ping_fail_streak = 0


def keep_alive_ping():
    """App khud ko HTTP request bhejta hai taaki free hosting use sula na de.

    Render/Koyeb jaise free plans instance ko tab sulate hain jab kuch der koi
    **inbound HTTP request** na aaye. Andar chal rahe timers se koi farak nahi
    padta — isliye bahar se aati hui ek asli request chahiye. Jab instance sota
    nahi to uska folder bhi reset nahi hota, yaani keys aur campaigns bhi bache
    rehte hain.

    Ek baat saaf rahe: jo cheez ise nahi bacha sakti wo hai deploy ya platform ka
    apna restart — us waqt free plan par data phir bhi jaata hai (disk nahi hoti).
    """
    global _ping_fail_streak
    base = media.base_url()
    if not base or base.startswith("http://localhost") or "127.0.0.1" in base:
        return  # local development — ping ka koi matlab nahi
    try:
        resp = requests.get(f"{base}/healthz", timeout=20)
        if resp.status_code >= 400:
            raise requests.RequestException(f"HTTP {resp.status_code}")
        if _ping_fail_streak:
            db.log(f"Keep-alive dobara chalu ({_ping_fail_streak} fail ke baad)",
                   source="keepalive")
        _ping_fail_streak = 0
    except requests.RequestException as err:
        # Har fail log karoge to logs bhar jayenge; sirf pehla aur phir har 6th.
        _ping_fail_streak += 1
        if _ping_fail_streak == 1 or _ping_fail_streak % 6 == 0:
            db.log(f"Keep-alive ping fail ({_ping_fail_streak}): {err}",
                   level="warn", source="keepalive")


def start():
    global _scheduler
    if _scheduler:
        return _scheduler
    seconds = int(os.environ.get("TICK_SECONDS", "30"))
    _scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
    _scheduler.add_job(
        tick, "interval", seconds=seconds, id="tick",
        max_instances=1, coalesce=True, misfire_grace_time=3600,
    )

    if os.environ.get("KEEP_ALIVE", "1").strip().lower() not in ("0", "false", "no", "off"):
        minutes = max(int(os.environ.get("KEEP_ALIVE_MINUTES", "10")), 1)
        _scheduler.add_job(
            keep_alive_ping, "interval", minutes=minutes, id="keepalive",
            max_instances=1, coalesce=True, misfire_grace_time=600,
        )
        db.log(f"Keep-alive on: har {minutes} minute par self-ping", source="keepalive")

    _scheduler.start()
    db.log(f"Scheduler start hua (har {seconds}s par check)", source="scheduler")
    return _scheduler


def run_now(upload_id):
    """Dashboard ka 'Run now' button — background thread mein chalao."""
    db.execute(
        "UPDATE uploads SET scheduled_at = ?, status = 'pending' WHERE id = ?",
        (db.iso(db.utcnow()), upload_id),
    )
    threading.Thread(target=run_upload, args=(upload_id,), daemon=True).start()
