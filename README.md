# 📺 Smart Tube — web-based auto uploader (YouTube + Instagram)

Ek hi website se video upload schedule karo. Video, title, description, thumbnail
aur custom comment set karo, gap batao (jaise **har 1 ghante = 24 ghante mein 24 uploads**),
aur tool apne aap upload karta rahega — **har upload ke baad customised comment bhi post
karega**.

Sab kuch ek hi Flask app mein hai: UI, API keys ka page, scheduler aur upload worker.
Alag se koi backend/server host karne ki zarurat nahi — ek jagah deploy karo, URL client
ko de do, wo `URL/enter` par apni API keys daalega aur dashboard se sab chalayega.

---

## Demo (bina hosting ke UI dikhane ke liye)

GitHub Pages Python nahi chala sakta — wo sirf static files serve karta hai. Isliye
`docs/` folder mein UI ka **static demo** rakha hai, jo asli app se hi generate hota hai
(dummy data ke saath). Client ko UI dikhana ho to bas ye link bhej do — hosting ka
paisa lagne se pehle.

**GitHub Pages on karo:** repo → Settings → Pages → Source: *Deploy from a branch* →
branch `main`, folder `/docs` → Save. 1 minute mein link mil jayega:
`https://<username>.github.io/Smart_tube/`

Demo mein live title-preview, spintax aur quota estimator sach mein kaam karte hain
(inko fake kar diya gaya hai). Upload/schedule nahi chalega — uske liye Python app
chahiye.

Demo dobara banana ho (UI badalne ke baad):

```bash
python tools/build_demo.py          # docs/ regenerate ho jayega
python -m http.server -d docs 3000  # local par dekhne ke liye
```

### Sirf HTML/JS se ye tool kyun nahi ban sakta

| Cheez | Static HTML page | Python app |
|---|---|---|
| YouTube upload | Ho sakta hai (OAuth PKCE), **par sirf tab khuli ho tab** | ✅ |
| 24 ghante ka schedule | ❌ tab band = schedule khatam | ✅ SQLite mein hai, restart ke baad bhi chalta hai |
| Instagram Reels | ❌ Graph API browser se CORS block karta hai | ✅ |
| Instagram ke liye video ka public URL | ❌ static site file host nahi kar sakti | ✅ signed URL se serve hota hai |
| Client secret / token chhupana | ❌ JS mein sab kuch public hota hai | ✅ server par rehta hai |

Chhota sa matlab: static page se 24 ghante ka auto-upload aur Instagram — dono possible
hi nahi hain. Python zaruri hai, par uski hosting **$0 mein** ho sakti hai (upar table dekho).

---

## Screens

| Page | Kya hai |
|---|---|
| `/enter` | Saari API keys + timezone + public URL. Ek baar bharo, bas. |
| `/dashboard` | Sab campaigns, live stats, agle uploads, recent activity. |
| `/campaigns/new` | Video + title + description + thumbnail + comment + schedule. |
| `/campaigns/<id>` | Poora upload schedule — har row run / skip / reschedule ho sakti hai. |
| `/logs` | Har upload, comment aur error ka record. |

---

## 1. Local par chalao (2 minute)

```bash
git clone <repo-url> && cd Smart_tube
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # SECRET_KEY set karo
.venv/bin/python app.py
```

Browser mein `http://localhost:8000` kholo → `/enter` par settings bharo.

---

## 2. Kahan chalayein (free options bhi hain)

Scheduler tabhi chalega jab app **on** rahe. Jo hosting inactivity par so jaati hai
(Render Free, PythonAnywhere free) wo hourly uploads ke liye theek nahi.

| Option | Kharcha | Note |
|---|---|---|
| **Client ka apna PC/laptop** | **$0** | Personal use ke liye bilkul sahi. `python app.py` chalao, bas PC on rehna chahiye. |
| **Oracle Cloud Always Free VM** | **$0** | Hamesha on. Card verify karna padta hai, setup thoda lamba. |
| **Raspberry Pi / purana laptop** | $0 | Ghar par 24x7 chal jaata hai, bijli ke alawa kuch nahi. |
| **Hetzner CX22 VPS** | ~$4.5/mo | Best paid value, full control. |
| **RackNerd VPS** | ~$12–15/**saal** | Sasta paid option. |
| **Render Starter** | $7/mo + disk | Sabse aasan (`render.yaml` ready hai), disk alag se lagta hai. |

**PC band ho jaye to kya hota hai?** Kuch nahi bigadta — poora schedule SQLite mein hai.
App dobara chalu karte hi jo uploads miss hue the wo turant chal jaate hain (ek saath,
back-to-back). Nahi chahiye to campaign page se un rows ko **Skip** kar do. Browser-only
tool mein ye possible hi nahi hota — tab band, schedule khatam.

### VPS par (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone <repo-url> && cd Smart_tube
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # SECRET_KEY, PUBLIC_BASE_URL, APP_PIN

sudo cp deploy/smarttube.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now smarttube
```

Phir Caddy/Nginx se HTTPS laga do (Google OAuth ke liye https zaruri hai):

```bash
sudo apt install -y caddy
echo "mytool.example.com { reverse_proxy 127.0.0.1:8000 }" | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

### Docker se

```bash
docker build -t smarttube .
docker run -d --restart always -p 8000:8000 \
  -e SECRET_KEY=... -e PUBLIC_BASE_URL=https://mytool.example.com \
  -v $PWD/storage:/app/storage -v $PWD/smarttube.db:/app/smarttube.db \
  smarttube
```

> ⚠️ **Worker hamesha 1 rakhna** (`-w 1`). Scheduler app ke andar chalta hai — 2 workers
> matlab 2 scheduler matlab har video **do baar** upload.

### ⚠️ Free hosting par data mit jaata hai

Render free plan jaise hosts 15 min inactivity par instance sula dete hain, aur jaagne
par app folder reset ho jaata hai. `smarttube.db` wahin banti hai, isliye **keys,
connected account aur saare campaigns chale jaate hain**. Hourly schedule aisi jagah
chal hi nahi sakta.

Isse nipatne ke do hisse hain:

| Kya bachana hai | Kaise |
|---|---|
| API keys | Hosting ke env vars mein daalo: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `IG_ACCESS_TOKEN`, `IG_USER_ID`. `/enter` par field khali dikhegi par kaam karegi. |
| Campaigns, schedule, OAuth token, videos | Persistent disk chahiye. `DB_PATH` ko disk ke andar point karo (`render.yaml` mein already set hai) aur `storage/` bhi usi disk par rakho. |

Sabse saaf raasta: app apne PC / VPS / Oracle free VM par chalao — wahan ye problem hai
hi nahi.

---

## 3. YouTube connect (`/enter` page par)

👉 **Poora step-by-step (screenshots wale button naam ke saath): [SETUP-YOUTUBE.md](SETUP-YOUTUBE.md)**

Chhota version:

1. [console.cloud.google.com](https://console.cloud.google.com) par project banao (free).
2. **YouTube Data API v3** enable karo.
3. **OAuth consent screen / Google Auth Platform** → Audience type *External*,
   **Publishing status = Testing**, apni Gmail ko **Test user** mein add karo.
4. **Data Access** mein ye scopes add karo: `youtube.upload` aur `youtube.force-ssl`.
5. **Credentials/Clients → Create → OAuth client ID → Web application**.
   Authorized redirect URI mein exactly ye daalo:
   `https://<tumhara-domain>/auth/youtube/callback`
6. `/enter` ke **General** section mein Public base URL set karo (warna redirect URI
   `localhost` wala banega aur `redirect_uri_mismatch` aayega).
7. Client ID + Secret `/enter` par paste karo → **Connect YouTube** → Google par Allow.
   ("Google hasn't verified this app" warning normal hai: *Advanced → Go to … (unsafe)*.)

Token DB mein save hota hai aur apne aap refresh hota rehta hai. **Par dhyan do:** Google
testing-mode apps ko **7 din** wala refresh token deta hai, isliye har ~7 din mein
`/enter` se **Connect YouTube** dobara dabana padega. Isse bachne ka ek hi tareeka hai —
app ko Google se verify karana (hafte lagte hain, privacy policy + domain ownership
chahiye). App ko bina verification ke *Production* mein daal doge to login hi block ho
jayega: *"has not completed the Google verification process"*.

---

## 4. Instagram connect

> Instagram apni API se posting **sirf Business/Creator account** par deta hai jo ek
> Facebook Page se linked ho. Purely personal account par Meta khud allow nahi karta —
> ye code ki limitation nahi, Meta ki policy hai. Switch karna free hai:
> Instagram app → Settings → Account type → **Switch to Creator**.

1. IG account ko Creator/Business banao + Facebook Page se link karo.
2. [developers.facebook.com](https://developers.facebook.com) par app banao → **Instagram Graph API** add karo.
3. Graph API Explorer se permissions lo:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.
4. Short-lived token ko **60-din wale long-lived token** mein exchange karo.
5. `/me/accounts` → Page ID → `GET /<page-id>?fields=instagram_business_account` → IG user ID.
6. Dono cheezein `/enter` par daalo → **Save & verify**.

Token 60 din baad expire hota hai — tab `/enter` se naya paste kar dena.

---

## 5. Title / comment templates

Har upload ka text alag ho isliye variables aur spintax dono chalte hain:

| Variable | Output |
|---|---|
| `{n}` / `{nn}` | 1, 2, 3… / 01, 02, 03… |
| `{total}` | campaign ka total uploads |
| `{date}` `{time}` `{datetime}` `{day}` | 17-08-2026 · 14:30 · Monday |
| `{rand}` | 4 digit random number |
| `{emoji}` | random emoji |

Spintax: `{Best|Top|Superb} clip` → har baar inme se ek chunta hai.

Example title:
```
{Amazing|Superb|Best} clip {emoji} — part {n}/{total}
```
Example comment:
```
{Nice|Mast|Superb} video {emoji} — {Subscribe|Follow} kar do! #{n}
```

Form par live preview dikhta hai, isliye guess nahi karna padta.

---

## 6. Zaruri limits (client ko pehle bata dena)

**YouTube API quota — 24 uploads/din default project par possible nahi hai.**
Google har project ko roz 10,000 units deta hai:

| Kaam | Cost |
|---|---|
| video upload | 1,600 units |
| thumbnail set | 50 units |
| comment post | 50 units |
| **kul per upload** | **~1,700 units** |

Yaani **~5–6 uploads/din**. Tool 24 schedule kar sakta hai, par 6 ke baad Google
quota error dega. Tab tool khud:

- upload ko **fail nahi** karta,
- baaki saare uploads **agle din** (midnight Pacific ke baad) shift kar deta hai, gap same rakhte hue,
- dashboard par warning + log dikha deta hai.

Sach mein 24/din chahiye to Google se **quota increase** form bharna padega (free hai, par
review hota hai aur commercial justification maangta hai).

Instagram ki limit alag hai: **50 posts / 24 ghante** — 24 uploads uske andar aa jaate hain.

**Policy warning:** ek hi video baar-baar upload karna YouTube ki duplicate/spam policy
mein aata hai. Channel par strike ya suspension ka risk account owner ka hai. Tool ye
decide nahi karta ki content repeat karna theek hai ya nahi.

---

## 7. Security ke baare mein saaf baat

Client ne bola tha security nahi chahiye, isliye jaan-bujh kar simple rakha hai —
lekin do cheezein phir bhi daali hain, kyunki inke bina koi bhi tumhara URL kholkar
tumhare API keys se upload kar sakta hai:

- **`APP_PIN`** — `.env` mein PIN daal do to har page se pehle PIN maangega.
  Khali chhod doge to bilkul open rahega (jo client ne maanga tha).
- **Signed media URLs** — video ka public link HMAC signature ke saath banta hai
  (Instagram ko video download karne ke liye chahiye), isliye poora storage folder
  public nahi hota.

Iske alawa kuch nahi hai: koi user accounts nahi, koi rate limiting nahi, HTTPS tumhare
reverse proxy ke bharose. Personal use ke liye theek hai. Kabhi doosre logon ko dena ho
to pehle proper auth lagwa lena.

---

## Env variables

| Var | Default | Kaam |
|---|---|---|
| `SECRET_KEY` | dev value | Session + media URL signing. Production mein zaroor badlo. |
| `APP_PIN` | *(khali)* | Set karoge to poori site PIN se lock ho jayegi. |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | OAuth redirect + Instagram video URL isi se bante hain. |
| `PORT` | `8000` | Server port. |
| `TICK_SECONDS` | `30` | Scheduler kitni der mein due uploads check kare. |
| `MAX_UPLOAD_MB` | `512` | Ek video ki max size. |

---

## Files

```
app.py                      Flask routes — /enter, dashboard, campaigns, logs, media
scheduler.py                schedule banana + upload worker + retry/quota handling
db.py                       SQLite schema aur helpers
services/youtube_service.py OAuth, video upload, thumbnail, comment
services/instagram_service.py Reels publish (3-step) + comment
services/textgen.py         {n}, {date}, spintax wala template engine
services/media.py           file save + signed public URLs
templates/ static/          UI
deploy/ Dockerfile Procfile render.yaml   hosting
```

Data `smarttube.db` (SQLite) aur `storage/` folder mein rehta hai — backup lena ho to
bas ye dono copy kar lo.
