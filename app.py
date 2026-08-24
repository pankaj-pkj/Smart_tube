"""Smart Tube — web dashboard se YouTube + Instagram par automatic uploads.

Sab kuch ek hi Flask app mein hai: UI, API keys ka form (/enter), dashboard,
scheduler aur upload worker. Alag se koi backend host karne ki zarurat nahi —
ek jagah deploy karo, URL client ko de do, baaki sab wo website se hi karega.
"""

import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

import db
import scheduler
from services import instagram_service as ig
from services import media, textgen
from services import youtube_service as yt

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "512"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smart-tube-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.jinja_env.globals["now"] = db.utcnow

CATEGORIES = [
    ("22", "People & Blogs"), ("24", "Entertainment"), ("10", "Music"),
    ("20", "Gaming"), ("23", "Comedy"), ("27", "Education"),
    ("28", "Science & Technology"), ("17", "Sports"), ("26", "Howto & Style"),
    ("25", "News & Politics"), ("19", "Travel & Events"), ("15", "Pets & Animals"),
    ("1", "Film & Animation"), ("2", "Autos & Vehicles"),
]

COMMON_TIMEZONES = [
    "Asia/Kolkata", "UTC", "Asia/Dubai", "Asia/Karachi", "Europe/London",
    "America/New_York", "America/Los_Angeles", "Asia/Singapore", "Australia/Sydney",
]


# ------------------------------------------------------------------ helpers


def user_tz():
    name = db.get_setting("timezone", "Asia/Kolkata")
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return timezone.utc


@app.template_filter("localtime")
def localtime_filter(value, fmt="%d %b, %I:%M %p"):
    dt = db.parse_iso(value) if isinstance(value, str) else value
    if not dt:
        return "—"
    return dt.astimezone(user_tz()).strftime(fmt)


@app.template_filter("ago")
def ago_filter(value):
    dt = db.parse_iso(value) if isinstance(value, str) else value
    if not dt:
        return "—"
    delta = (db.utcnow() - dt).total_seconds()
    future = delta < 0
    delta = abs(delta)
    if delta < 60:
        text = "abhi"
    elif delta < 3600:
        text = f"{int(delta // 60)} min"
    elif delta < 86400:
        text = f"{int(delta // 3600)} ghante"
    else:
        text = f"{int(delta // 86400)} din"
    if text == "abhi":
        return text
    return f"{text} baad" if future else f"{text} pehle"


def setup_done():
    return yt.is_connected() or ig.is_connected()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        pin = os.environ.get("APP_PIN", "").strip()
        if pin and not session.get("unlocked"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    return {
        "yt_connected": yt.is_connected(),
        "ig_connected": ig.is_connected(),
        "yt_channel": db.get_json("yt_channel"),
        "ig_account": db.get_json("ig_account"),
        "tz_name": db.get_setting("timezone", "Asia/Kolkata"),
    }


# ------------------------------------------------------------------ auth lock


@app.route("/login", methods=["GET", "POST"])
def login():
    pin = os.environ.get("APP_PIN", "").strip()
    if not pin:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if request.form.get("pin", "") == pin:
            session["unlocked"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Galat PIN", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ pages


@app.route("/")
@login_required
def index():
    return redirect(url_for("dashboard") if setup_done() else url_for("enter"))


@app.route("/enter", methods=["GET", "POST"])
@login_required
def enter():
    """Saari API keys aur global settings yahin se — client ko sirf ye URL chahiye."""
    if request.method == "POST":
        form = request.form
        section = form.get("section", "all")

        if section in ("youtube", "all"):
            db.set_setting("yt_client_id", form.get("yt_client_id", "").strip())
            db.set_setting("yt_client_secret", form.get("yt_client_secret", "").strip())
        if section in ("instagram", "all"):
            token = form.get("ig_access_token", "").strip()
            if token:
                db.set_setting("ig_access_token", token)
            db.set_setting("ig_user_id", form.get("ig_user_id", "").strip())
        if section in ("general", "all"):
            db.set_setting("public_base_url", form.get("public_base_url", "").strip())
            db.set_setting("timezone", form.get("timezone", "Asia/Kolkata"))

        flash("Settings save ho gayi", "success")

        if section == "instagram" and db.get_setting("ig_access_token"):
            try:
                info = ig.verify_and_save()
                flash(f"Instagram connected: @{info.get('username')}", "success")
            except ig.InstagramError as err:
                flash(f"Instagram verify fail: {err}", "error")
        return redirect(url_for("enter"))

    return render_template(
        "enter.html",
        yt_client_id=db.get_config("yt_client_id", "YT_CLIENT_ID"),
        yt_client_secret=db.get_config("yt_client_secret", "YT_CLIENT_SECRET"),
        ig_user_id=db.get_config("ig_user_id", "IG_USER_ID"),
        ig_token_set=bool(db.get_config("ig_access_token", "IG_ACCESS_TOKEN")),
        public_base_url=media.base_url(),
        redirect_uri=media.base_url() + "/auth/youtube/callback",
        timezones=COMMON_TIMEZONES,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    campaigns = db.query("SELECT * FROM campaigns ORDER BY id DESC")
    rows = []
    for camp in campaigns:
        stats = db.query(
            "SELECT status, COUNT(*) AS c FROM uploads WHERE campaign_id = ? GROUP BY status",
            (camp["id"],),
        )
        counts = {r["status"]: r["c"] for r in stats}
        nxt = db.query(
            "SELECT scheduled_at FROM uploads WHERE campaign_id = ? AND status = 'pending' "
            "ORDER BY scheduled_at LIMIT 1",
            (camp["id"],), one=True,
        )
        total = sum(counts.values()) or 1
        rows.append({
            "c": camp,
            "counts": counts,
            "total": sum(counts.values()),
            "done": counts.get("success", 0),
            "percent": round(counts.get("success", 0) * 100 / total),
            "next_at": nxt["scheduled_at"] if nxt else None,
        })

    recent = db.query(
        "SELECT u.*, c.name AS campaign_name FROM uploads u "
        "JOIN campaigns c ON c.id = u.campaign_id "
        "WHERE u.status IN ('success','failed','running') "
        "ORDER BY COALESCE(u.finished_at, u.started_at) DESC LIMIT 10"
    )
    upcoming = db.query(
        "SELECT u.*, c.name AS campaign_name FROM uploads u "
        "JOIN campaigns c ON c.id = u.campaign_id "
        "WHERE u.status = 'pending' AND c.status = 'running' "
        "ORDER BY u.scheduled_at LIMIT 10"
    )
    totals = db.query(
        "SELECT status, COUNT(*) AS c FROM uploads GROUP BY status"
    )
    return render_template(
        "dashboard.html",
        rows=rows,
        recent=recent,
        upcoming=upcoming,
        totals={r["status"]: r["c"] for r in totals},
    )


@app.route("/campaigns/new", methods=["GET", "POST"])
@login_required
def campaign_new():
    if request.method == "POST":
        try:
            campaign_id = _create_campaign(request)
        except ValueError as err:
            flash(str(err), "error")
            return redirect(url_for("campaign_new"))
        count = scheduler.build_schedule(campaign_id)
        flash(f"Campaign ban gaya — {count} uploads schedule ho gaye", "success")
        return redirect(url_for("campaign_detail", campaign_id=campaign_id))

    default_start = (db.utcnow() + timedelta(minutes=5)).astimezone(user_tz())
    return render_template(
        "campaign_new.html",
        categories=CATEGORIES,
        default_start=default_start.strftime("%Y-%m-%dT%H:%M"),
        max_mb=MAX_UPLOAD_MB,
    )


def _create_campaign(req):
    form = req.form
    name = (form.get("name") or "").strip()
    title_tpl = (form.get("title_tpl") or "").strip()
    if not name:
        raise ValueError("Campaign ka naam daalo")
    if not title_tpl:
        raise ValueError("Video title daalo")

    video = req.files.get("video")
    if not video or not video.filename:
        raise ValueError("Video file select karo")
    try:
        video_path = media.save_upload(video, "video")
    except ValueError as err:
        raise ValueError(str(err)) from err

    thumb_path = None
    thumb = req.files.get("thumbnail")
    if thumb and thumb.filename:
        try:
            thumb_path = media.save_upload(thumb, "image")
        except ValueError as err:
            media.delete(video_path)
            raise ValueError(str(err)) from err

    interval = max(int(form.get("interval_minutes") or 60), 1)
    total = max(min(int(form.get("total_uploads") or 24), 500), 1)

    start_raw = form.get("start_at") or ""
    try:
        start_local = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
        start_at = start_local.replace(tzinfo=user_tz()).astimezone(timezone.utc)
    except ValueError:
        start_at = db.utcnow() + timedelta(minutes=2)

    campaign_id = db.execute(
        "INSERT INTO campaigns (name, platform, video_path, video_name, thumb_path, "
        "title_tpl, description, tags, privacy, category_id, made_for_kids, comment_tpl, "
        "pin_comment, ig_caption_tpl, ig_comment_tpl, ig_share_to_feed, interval_minutes, "
        "total_uploads, start_at, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            name,
            form.get("platform", "youtube"),
            video_path,
            video.filename,
            thumb_path,
            title_tpl,
            form.get("description", ""),
            form.get("tags", ""),
            form.get("privacy", "public"),
            form.get("category_id", "22"),
            1 if form.get("made_for_kids") else 0,
            form.get("comment_tpl", ""),
            1 if form.get("pin_comment") else 0,
            form.get("ig_caption_tpl", ""),
            form.get("ig_comment_tpl", ""),
            1 if form.get("ig_share_to_feed") else 0,
            interval,
            total,
            db.iso(start_at),
            "running" if form.get("start_now") else "paused",
            db.iso(db.utcnow()),
        ),
    )
    db.log(f"Campaign '{name}' banaya", source="app", campaign_id=campaign_id)
    return campaign_id


@app.route("/campaigns/<int:campaign_id>")
@login_required
def campaign_detail(campaign_id):
    camp = db.query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True)
    if not camp:
        abort(404)
    uploads = db.query(
        "SELECT * FROM uploads WHERE campaign_id = ? ORDER BY scheduled_at, platform",
        (campaign_id,),
    )
    logs = db.query(
        "SELECT * FROM logs WHERE campaign_id = ? ORDER BY id DESC LIMIT 50", (campaign_id,)
    )
    per_day = round(1440 / camp["interval_minutes"], 1)
    quota = yt.estimate_quota(
        min(int(per_day) or 1, camp["total_uploads"]),
        with_thumbnail=bool(camp["thumb_path"]),
        with_comment=bool(camp["comment_tpl"]),
    )
    return render_template(
        "campaign_detail.html",
        c=camp,
        uploads=uploads,
        logs=logs,
        per_day=per_day,
        quota=quota,
        video_mb=media.size_mb(camp["video_path"]),
    )


@app.route("/campaigns/<int:campaign_id>/<action>", methods=["POST"])
@login_required
def campaign_action(campaign_id, action):
    camp = db.query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), one=True)
    if not camp:
        abort(404)

    if action == "pause":
        db.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (campaign_id,))
        flash("Campaign pause ho gaya", "success")
    elif action == "resume":
        db.execute("UPDATE campaigns SET status = 'running' WHERE id = ?", (campaign_id,))
        flash("Campaign chalu ho gaya", "success")
    elif action == "shift":
        # Sab pending uploads ko aage/peeche khiskao (minutes mein).
        minutes = int(request.form.get("minutes") or 0)
        rows = db.query(
            "SELECT id, scheduled_at FROM uploads WHERE campaign_id = ? AND status = 'pending'",
            (campaign_id,),
        )
        for row in rows:
            when = db.parse_iso(row["scheduled_at"]) + timedelta(minutes=minutes)
            db.execute("UPDATE uploads SET scheduled_at = ? WHERE id = ?",
                       (db.iso(when), row["id"]))
        flash(f"{len(rows)} pending uploads {minutes} minute shift ho gaye", "success")
    elif action == "delete":
        db.execute("DELETE FROM uploads WHERE campaign_id = ?", (campaign_id,))
        db.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        media.delete(camp["video_path"])
        media.delete(camp["thumb_path"])
        flash("Campaign delete ho gaya", "success")
        return redirect(url_for("dashboard"))
    else:
        abort(404)
    return redirect(url_for("campaign_detail", campaign_id=campaign_id))


@app.route("/uploads/<int:upload_id>/<action>", methods=["POST"])
@login_required
def upload_action(upload_id, action):
    up = db.query("SELECT * FROM uploads WHERE id = ?", (upload_id,), one=True)
    if not up:
        abort(404)

    if action == "run":
        scheduler.run_now(upload_id)
        flash(f"Upload #{up['seq']} abhi chalu kar diya", "success")
    elif action == "retry":
        db.execute(
            "UPDATE uploads SET status = 'pending', attempts = 0, error = NULL, "
            "scheduled_at = ? WHERE id = ?",
            (db.iso(db.utcnow()), upload_id),
        )
        flash("Retry queue mein daal diya", "success")
    elif action == "skip":
        db.execute("UPDATE uploads SET status = 'skipped' WHERE id = ?", (upload_id,))
        flash("Upload skip kar diya", "success")
    elif action == "reschedule":
        raw = request.form.get("scheduled_at", "")
        try:
            when = datetime.strptime(raw, "%Y-%m-%dT%H:%M").replace(tzinfo=user_tz())
        except ValueError:
            flash("Time galat format mein hai", "error")
            return redirect(url_for("campaign_detail", campaign_id=up["campaign_id"]))
        db.execute(
            "UPDATE uploads SET scheduled_at = ?, status = 'pending' WHERE id = ?",
            (db.iso(when.astimezone(timezone.utc)), upload_id),
        )
        flash("Time badal diya", "success")
    else:
        abort(404)
    return redirect(url_for("campaign_detail", campaign_id=up["campaign_id"]))


@app.route("/logs")
@login_required
def logs():
    level = request.args.get("level", "")
    if level:
        rows = db.query(
            "SELECT * FROM logs WHERE level = ? ORDER BY id DESC LIMIT 300", (level,)
        )
    else:
        rows = db.query("SELECT * FROM logs ORDER BY id DESC LIMIT 300")
    return render_template("logs.html", rows=rows, level=level)


# ------------------------------------------------------------------ oauth


@app.route("/auth/youtube")
@login_required
def auth_youtube():
    redirect_uri = media.base_url() + "/auth/youtube/callback"
    if redirect_uri.startswith("http://"):
        # Localhost testing ke liye — production https par ye set nahi hoga.
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    try:
        url, state = yt.auth_url(redirect_uri)
    except yt.YouTubeError as err:
        flash(str(err), "error")
        return redirect(url_for("enter"))
    session["oauth_state"] = state
    return redirect(url)


@app.route("/auth/youtube/callback")
@login_required
def auth_youtube_callback():
    redirect_uri = media.base_url() + "/auth/youtube/callback"
    if redirect_uri.startswith("http://"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    if request.args.get("error"):
        flash("Google ne permission deny kar di: %s" % request.args["error"], "error")
        return redirect(url_for("enter"))
    try:
        # request.url proxy ke peeche http dikha sakta hai, isliye configured base use karo.
        authorization_response = redirect_uri + "?" + request.query_string.decode()
        info = yt.exchange_code(redirect_uri, authorization_response)
        flash("YouTube channel connect ho gaya: %s" % (info or {}).get("title", ""), "success")
    except Exception as err:  # noqa: BLE001 - OAuth ki har error user ko dikhani hai
        flash(f"YouTube connect fail: {err}", "error")
    return redirect(url_for("enter"))


@app.route("/disconnect/<platform>", methods=["POST"])
@login_required
def disconnect(platform):
    if platform == "youtube":
        yt.disconnect()
    elif platform == "instagram":
        ig.disconnect()
    else:
        abort(404)
    flash(f"{platform.title()} disconnect ho gaya", "success")
    return redirect(url_for("enter"))


@app.route("/verify/instagram", methods=["POST"])
@login_required
def verify_instagram():
    try:
        info = ig.verify_and_save()
        flash(f"Instagram OK: @{info.get('username')} ({info.get('followers')} followers)",
              "success")
    except ig.InstagramError as err:
        flash(f"Instagram verify fail: {err}", "error")
    return redirect(url_for("enter"))


# ------------------------------------------------------------------ media + api


@app.route("/media/<signature>/<path:rel_path>")
def serve_media(signature, rel_path):
    """Signed public URL — Instagram isi se video download karta hai."""
    if not rel_path.startswith(("storage/videos/", "storage/thumbs/")):
        abort(404)
    if not media.verify(rel_path, signature):
        abort(403)
    directory = os.path.join(BASE_DIR, os.path.dirname(rel_path))
    return send_from_directory(directory, os.path.basename(rel_path), conditional=True)


@app.route("/api/stats")
@login_required
def api_stats():
    """Dashboard auto-refresh ke liye."""
    totals = {
        r["status"]: r["c"]
        for r in db.query("SELECT status, COUNT(*) AS c FROM uploads GROUP BY status")
    }
    running = db.query(
        "SELECT id, campaign_id, seq, platform, progress, title FROM uploads "
        "WHERE status = 'running'"
    )
    nxt = db.query(
        "SELECT u.scheduled_at, u.platform, u.title, c.name FROM uploads u "
        "JOIN campaigns c ON c.id = u.campaign_id "
        "WHERE u.status = 'pending' AND c.status = 'running' "
        "ORDER BY u.scheduled_at LIMIT 1",
        one=True,
    )
    return jsonify({
        "totals": totals,
        "running": [dict(r) for r in running],
        "next": dict(nxt) if nxt else None,
        "server_time": db.iso(db.utcnow()),
    })


@app.route("/api/preview", methods=["POST"])
@login_required
def api_preview():
    data = request.get_json(silent=True) or {}
    return jsonify({
        "samples": textgen.preview(
            data.get("template", ""),
            campaign_name=data.get("name") or "Campaign",
            total=int(data.get("total") or 24),
            count=3,
        )
    })


@app.route("/api/quota")
@login_required
def api_quota():
    interval = max(int(request.args.get("interval", 60)), 1)
    per_day = max(int(1440 // interval), 1)
    est = yt.estimate_quota(
        per_day,
        with_thumbnail=request.args.get("thumb") == "1",
        with_comment=request.args.get("comment") == "1",
    )
    est["per_day"] = per_day
    return jsonify(est)


@app.errorhandler(413)
def too_large(_err):
    flash(f"File bahut badi hai. Limit {MAX_UPLOAD_MB} MB hai "
          "(MAX_UPLOAD_MB env se badla ja sakta hai).", "error")
    return redirect(url_for("campaign_new")), 302


# ------------------------------------------------------------------ boot


def bootstrap():
    db.init_db()
    media.ensure_dirs()
    scheduler.start()


bootstrap()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # use_reloader=False — warna scheduler do baar start hota hai.
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
