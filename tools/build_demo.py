"""Static demo builder — asli app se hi HTML nikaal kar `docs/` mein rakhta hai.

Kyun: GitHub Pages Python nahi chalata, sirf static files serve karta hai. Isliye
client ko UI dikhane ke liye hum app ko locally chalate hain, demo data seed karte
hain, har page ka HTML capture karte hain aur links ko .html files par point kara
dete hain. Fayda ye ki demo aur asli UI kabhi alag nahi hote — demo asli code se
hi banta hai.

Chalane ke liye:   python tools/build_demo.py
Output:            docs/  (GitHub Pages isi folder se serve kar sakta hai)
"""

import os
import re
import shutil
import sys
import tempfile
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("SECRET_KEY", "demo-build-key")
os.environ.setdefault("TICK_SECONDS", "3600")
os.environ.pop("APP_PIN", None)

import db  # noqa: E402

# Demo build asli database ko haath na lagaye.
db.DB_PATH = os.path.join(tempfile.mkdtemp(prefix="smarttube-demo-"), "demo.db")

import app as flask_app  # noqa: E402

DOCS = os.path.join(BASE_DIR, "docs")

# App ke route se demo file ka naam.
PAGES = {
    "/dashboard": "index.html",
    "/enter": "enter.html",
    "/campaigns/new": "new.html",
    "/campaigns/1": "campaign.html",
    "/logs": "logs.html",
}

BANNER = """
<div class="demo-banner">
  <b>🎬 DEMO</b> — ye sirf UI preview hai (GitHub Pages par static chal raha hai).
  Asli tool Python se chalta hai: video upload, scheduling aur auto-comment tabhi hote
  hain jab app kisi server ya PC par chal raha ho.
  <a href="https://github.com/pankaj-pkj/Smart_tube" target="_blank" rel="noopener">Source ↗</a>
</div>
"""

BANNER_CSS = """
<style>
  .demo-banner {
    position: sticky; top: 0; z-index: 50;
    background: linear-gradient(90deg, rgba(255,61,84,.22), rgba(124,92,255,.18));
    border-bottom: 1px solid var(--line);
    padding: 9px 16px; font-size: 12.5px; color: var(--text);
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  }
  .demo-banner a { color: #b9a6ff; text-decoration: underline; }
</style>
"""

# Demo mein koi backend nahi hai, isliye /api/* calls ko yahin fake kar dete hain.
# Isse live title preview aur quota estimator demo mein bhi kaam karte hain.
DEMO_JS = """
<script>
(function () {
  const EMOJIS = ["🔥","✨","🚀","💯","🎬","😍","👌","⚡","🌟","🎯"];
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  function renderTemplate(tpl, n, total) {
    const now = new Date();
    const pad = (x) => String(x).padStart(2, "0");
    const vars = {
      n: String(n), nn: pad(n), total: String(total),
      date: `${pad(now.getDate())}-${pad(now.getMonth() + 1)}-${now.getFullYear()}`,
      time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
      day: now.toLocaleDateString("en", { weekday: "long" }),
      campaign: "Demo Campaign",
      rand: String(1000 + Math.floor(Math.random() * 9000)),
      emoji: pick(EMOJIS),
    };
    let out = tpl;
    for (const [k, v] of Object.entries(vars)) out = out.split("{" + k + "}").join(v);
    for (let i = 0; i < 20; i++) {
      const m = out.match(/\\{([^{}]*\\|[^{}]*)\\}/);
      if (!m) break;
      out = out.slice(0, m.index) + pick(m[1].split("|")) + out.slice(m.index + m[0].length);
    }
    return out.trim();
  }

  const realFetch = window.fetch.bind(window);
  const json = (data) => Promise.resolve(new Response(JSON.stringify(data), {
    status: 200, headers: { "Content-Type": "application/json" },
  }));

  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;

    if (url.includes("/api/preview")) {
      const body = JSON.parse((init && init.body) || "{}");
      const total = parseInt(body.total || 24, 10);
      return json({ samples: [1, 2, 3].map((i) => renderTemplate(body.template || "", i, total)) });
    }

    if (url.includes("/api/quota")) {
      const params = new URLSearchParams(url.split("?")[1] || "");
      const interval = Math.max(parseInt(params.get("interval") || "60", 10), 1);
      const perUpload = 1600 + (params.get("thumb") === "1" ? 50 : 0)
                             + (params.get("comment") === "1" ? 50 : 0);
      const perDay = Math.max(Math.floor(1440 / interval), 1);
      const used = perUpload * perDay;
      return json({
        per_upload: perUpload, per_day: perDay, used: used, limit: 10000,
        max_uploads: Math.floor(10000 / perUpload), over: used > 10000,
      });
    }

    if (url.includes("/api/stats")) {
      return json({ totals: {}, running: [], next: null, server_time: new Date().toISOString() });
    }

    return realFetch(input, init);
  };

  // Demo mein koi form submit nahi hona chahiye.
  document.addEventListener("submit", function (e) {
    e.preventDefault();
    alert("Ye demo hai — asli upload ke liye tool ko server ya PC par chalana padega.");
  }, true);
})();
</script>
"""


def seed():
    """Demo data — screenshot-worthy, saare statuses dikhne chahiye."""
    db.init_db()
    now = db.utcnow()

    db.set_json("yt_channel", {
        "id": "UCdemo", "title": "My Shorts Channel",
        "subscribers": "12400", "videos": "318",
    })
    db.set_json("yt_token", {"token": "demo"})
    db.set_setting("yt_client_id", "1234567890-democlient.apps.googleusercontent.com")
    db.set_setting("yt_client_secret", "GOCSPX-demo-secret-value")
    db.set_setting("ig_access_token", "EAAG-demo-token")
    db.set_setting("ig_user_id", "17841400000000000")
    db.set_json("ig_account", {
        "id": "17841400000000000", "username": "my.reels.page",
        "followers": 8420, "media": 96,
    })
    db.set_setting("timezone", "Asia/Kolkata")
    db.set_setting("public_base_url", "https://smarttube.example.com")

    campaign_id = db.execute(
        "INSERT INTO campaigns (id, name, platform, video_path, video_name, thumb_path, "
        "title_tpl, description, tags, privacy, category_id, made_for_kids, comment_tpl, "
        "pin_comment, ig_caption_tpl, ig_comment_tpl, ig_share_to_feed, interval_minutes, "
        "total_uploads, start_at, status, created_at) "
        "VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "Motivation Reel — August", "both",
            "storage/videos/demo_clip.mp4", "motivation_clip.mp4",
            "storage/thumbs/demo_thumb.jpg",
            "{Amazing|Superb|Best} clip {emoji} — part {n}/{total}",
            "Upload #{n} · {date} {time}\n\n#shorts #viral #motivation",
            "shorts, viral, motivation", "public", "22", 0,
            "{Nice|Superb|Mast} video {emoji} — {Subscribe|Follow} kar do! #{n}",
            1, "{Reel|Clip} #{n} {emoji} #reels #viral", "Follow for more {emoji}", 1,
            60, 24, db.iso(now - timedelta(hours=5)), "running", db.iso(now - timedelta(hours=6)),
        ),
    )

    titles = [
        "Superb clip 🔥 — part {}/24", "Best clip ✨ — part {}/24",
        "Amazing clip 🚀 — part {}/24", "Superb clip 💯 — part {}/24",
    ]
    comments = ["Nice video 🔥 — Subscribe kar do! #{}", "Mast video ✨ — Follow kar do! #{}"]

    for seq in range(1, 13):
        when = now - timedelta(hours=5) + timedelta(hours=seq - 1)
        for platform in ("youtube", "instagram"):
            if seq <= 5:
                status, progress = "success", 100
            elif seq == 6 and platform == "youtube":
                status, progress = "running", 62
            elif seq == 6:
                status, progress = "failed", 0
            else:
                status, progress = "pending", 0

            remote_id = f"dQw4w9Wg{seq}" if status == "success" else None
            remote_url = None
            if status == "success":
                remote_url = (
                    f"https://www.youtube.com/watch?v={remote_id}"
                    if platform == "youtube"
                    else f"https://www.instagram.com/reel/C{seq}xyzDemo/"
                )

            db.execute(
                "INSERT INTO uploads (campaign_id, platform, seq, scheduled_at, status, title, "
                "remote_id, remote_url, comment_id, comment_text, progress, attempts, error, "
                "started_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    campaign_id, platform, seq, db.iso(when), status,
                    titles[seq % len(titles)].format(seq),
                    remote_id, remote_url,
                    "UgxDemoComment" if status == "success" else None,
                    comments[seq % 2].format(seq), progress,
                    2 if status == "failed" else (1 if status != "pending" else 0),
                    "Instagram ne video process nahi kiya: video format supported nahi hai"
                    if status == "failed" else None,
                    db.iso(when) if status != "pending" else None,
                    db.iso(when + timedelta(minutes=2)) if status == "success" else None,
                ),
            )

    entries = [
        ("info", "scheduler", "Scheduler start hua (har 30s par check)"),
        ("info", "app", "Campaign 'Motivation Reel — August' banaya"),
        ("info", "scheduler", "Schedule banaya: 24 uploads, har 60 minute"),
        ("info", "youtube", "YouTube upload #1 done: https://www.youtube.com/watch?v=dQw4w9Wg1"),
        ("info", "youtube", "Comment post hua: Nice video 🔥 — Subscribe kar do! #1"),
        ("info", "instagram", "Instagram reel #1 publish hua: https://www.instagram.com/reel/C1xyzDemo/"),
        ("warn", "youtube", "Thumbnail set nahi hua: The thumbnail image is too large."),
        ("info", "youtube", "YouTube upload #4 done: https://www.youtube.com/watch?v=dQw4w9Wg4"),
        ("warn", "instagram", "Upload #6 fail hua (attempt 2/3), 10 min baad retry: video format supported nahi hai"),
        ("error", "youtube", "Quota khatam. Upload #7 aur 11 baaki uploads kal shift kar diye."),
    ]
    for level, source, message in entries:
        db.execute(
            "INSERT INTO logs (ts, level, source, message, campaign_id) VALUES (?,?,?,?,?)",
            (db.iso(now - timedelta(minutes=len(entries) * 7)), level, source, message, campaign_id),
        )


def rewrite(html):
    """App ke URLs ko static demo files par point karo."""
    replacements = [
        ('href="/static/css/style.css"', 'href="assets/style.css"'),
        ('src="/static/js/app.js"', 'src="assets/app.js"'),
        ('href="/dashboard"', 'href="index.html"'),
        ('href="/enter"', 'href="enter.html"'),
        ('href="/campaigns/new"', 'href="new.html"'),
        ('href="/logs"', 'href="logs.html"'),
        ('href="/auth/youtube"', 'href="#"'),
    ]
    for old, new in replacements:
        html = html.replace(old, new)

    # Campaign links (/campaigns/1, /campaigns/1?x=…) → campaign.html
    html = re.sub(r'href="/campaigns/\d+[^"]*"', 'href="campaign.html"', html)
    # Logs filters (/logs?level=warn) → logs.html
    html = re.sub(r'href="/logs\?[^"]*"', 'href="logs.html"', html)
    # Forms demo mein submit nahi hone chahiye.
    html = re.sub(r'action="/[^"]*"', 'action="#"', html)

    html = html.replace("</head>", BANNER_CSS + "</head>")
    html = html.replace("<body>", "<body>" + BANNER)
    # DEMO_JS ko app.js se PEHLE daalna zaruri hai — app.js load hote hi preview aur
    # quota ke liye fetch() maar deta hai, isliye stub usse pehle taiyaar hona chahiye.
    html = html.replace(
        '<script src="assets/app.js"></script>',
        DEMO_JS + '<script src="assets/app.js"></script>',
    )
    return html


def dummy_video():
    """Campaign page 'X MB' dikhata hai, isliye build ke waqt ek sparse file bana dete hain."""
    path = os.path.join(BASE_DIR, "storage", "videos", "demo_clip.mp4")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.truncate(8 * 1024 * 1024)
    return path


def build():
    seed()
    demo_file = dummy_video()
    shutil.rmtree(DOCS, ignore_errors=True)
    os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)

    shutil.copy(os.path.join(BASE_DIR, "static", "css", "style.css"),
                os.path.join(DOCS, "assets", "style.css"))
    shutil.copy(os.path.join(BASE_DIR, "static", "js", "app.js"),
                os.path.join(DOCS, "assets", "app.js"))
    # GitHub Pages Jekyll ko band karo warna kuch files skip ho sakti hain.
    open(os.path.join(DOCS, ".nojekyll"), "w").close()

    client = flask_app.app.test_client()
    for route, filename in PAGES.items():
        response = client.get(route)
        if response.status_code != 200:
            raise SystemExit(f"{route} ne {response.status_code} diya, demo build ruk gaya")
        html = rewrite(response.data.decode("utf-8"))
        with open(os.path.join(DOCS, filename), "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"  {route:22} -> docs/{filename}  ({len(html) // 1024} KB)")

    os.remove(demo_file)
    print(f"\nDemo taiyaar: {DOCS}")
    print("Local par dekhne ke liye: python -m http.server -d docs 3000")


if __name__ == "__main__":
    build()
