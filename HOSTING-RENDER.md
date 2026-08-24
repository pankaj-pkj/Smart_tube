# Render par host karna — zero se

Ye guide un logon ke liye hai jinhone pehle kabhi kuch host nahi kiya. Har step ka
number hai, kahin atko to number bata dena.

Phone se kar rahe ho to browser mein **Desktop site** on kar lo (⋮ menu se), warna
Render ke kuch buttons dikhte nahi.

---

## Pehle ye padho — Render ke plans

Ye tool ek **scheduler** chalata hai (har ghante upload). Iske liye app ka **chalte
rehna** zaruri hai.

| | Free plan | Starter ($7/mo) |
|---|---|---|
| Kharcha | $0 | ~$7/mo + disk (~$1) |
| 15 min inactivity ke baad | **so jaata hai** | chalta rehta hai |
| Jaagne par saved data | **mit jaata hai** (keys, campaigns, videos) | disk lagane par bacha rehta hai |
| Hourly schedule | ❌ nahi chalega | ✅ chalega |
| Testing / demo | ✅ theek hai | — |

**Matlab saaf shabdon mein:** Free plan par tum tool **dikhaa** sakte ho, par 24 ghante
ka schedule **chala nahi** sakte. Asli use ke liye ya to Starter plan + disk lo, ya app
apne PC / Oracle Cloud free VM par chalao (dono jagah ye problem nahi hai).

---

## PART 1 — Service banana

**Step 1.** [render.com](https://render.com) kholo → **Get Started** → **GitHub** se sign up karo.

**Step 2.** GitHub permission maange to **Smart_tube** repo ka access de do.
(Chaho to "All repositories" bhi de sakte ho.)

**Step 3.** Render dashboard par upar-right **"+ New"** → **"Web Service"** chuno.

**Step 4.** Repo list mein se **`Smart_tube`** chuno → **Connect**.

> ⚠️ Dhyan se — agar tumhare paas kai repos hain to naam milte-julte ho sakte hain.
> Galat repo chuna to build fail hoga: *"Could not open requirements file"*.

**Step 5.** Ab settings ka form aayega. Ye bharo:

| Field | Value |
|---|---|
| **Name** | `smart-tube` (ya jo mann kare) |
| **Region** | Singapore (India ke sabse paas) |
| **Branch** | `main` |
| **Root Directory** | khali chhod do |
| **Runtime / Language** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app -w 1 --threads 8 -b 0.0.0.0:$PORT --timeout 1800` |
| **Instance Type** | `Free` (ya `Starter`) |

> ⚠️ **Start command mein `-w 1` kabhi mat badalna.** Scheduler app ke andar chalta
> hai — 2 workers matlab 2 scheduler matlab **har video do baar upload**.

**Step 6.** Neeche **"Advanced"** kholo → **"Add Environment Variable"** se ye daalo:

| Key | Value |
|---|---|
| `SECRET_KEY` | koi bhi lamba random string, jaise `kjh34kjh5k3j4h5kjh34k5jh` |
| `PUBLIC_BASE_URL` | abhi khali chhod do — Step 9 mein bharenge |

Chaho to ye bhi:

| Key | Value | Kaam |
|---|---|---|
| `APP_PIN` | koi 4-6 digit PIN | site kholne se pehle PIN maangega |
| `MAX_UPLOAD_MB` | `512` | ek video ki max size |

**Step 7.** **"Create Web Service"** dabao. Build shuru ho jayega (2-4 minute).

Logs mein `==> Build successful` aur phir `==> Your service is live` dikhna chahiye.

---

## PART 2 — URL set karna (ye step chhodna mat)

**Step 8.** Page ke upar tumhari site ka URL dikhega, jaise:
```
https://smart-tube-hya6.onrender.com
```
Use copy kar lo.

**Step 9.** Left menu se **"Environment"** par jao → `PUBLIC_BASE_URL` ko edit karo
(ya naya banao) aur wahi URL daalo:
```
https://smart-tube-hya6.onrender.com
```

⚠️ **Sirf domain** — end mein slash nahi, aur `/auth/youtube/callback` jaisa koi path
**bilkul nahi**. Wo app khud jodta hai.

**Step 10.** **Save Changes** dabao. Render apne aap redeploy karega.

> Ye step isliye zaruri hai kyunki free plan par database mit jaati hai. Env var mein
> URL rakhoge to restart ke baad bhi sahi rahega, aur Google `redirect_uri_mismatch`
> nahi dega.

**Step 11.** Left menu → **Settings** → **Build & Deploy** → **Auto-Deploy** ko **Yes**
kar do. Ab GitHub par naya code aate hi apne aap deploy ho jayega.

---

## PART 3 — Chal raha hai ya nahi, check karo

**Step 12.** Apna URL browser mein kholo.

Pehli baar 50 second tak lag sakta hai — free instance so raha tha, request usse jagati
hai. Ye normal hai.

**Step 13.** `APP_PIN` set kiya tha to PIN maangega — daal do.

**Step 14.** **API & Settings** page kholo. Ye dikhna chahiye:

- YouTube box mein **"Save & Connect YouTube"** aur **"Sirf save karo"** — do buttons
- Neeche **General** card mein Public base URL tumhara asli URL
- Sabse neeche ek **peela box** — *"Free hosting par data mit sakta hai"*

Sab dikh gaya? Hosting ho gayi ✅

**Step 15.** Ab **[SETUP-YOUTUBE.md](SETUP-YOUTUBE.md)** follow karo — YouTube connect
karne ke liye.

---

## PART 4 — Asli use ke liye (paid, optional)

Free plan par campaigns nahi bachte. 24-ghante ka schedule chalana ho to:

**Step 16.** Render → Settings → **Instance Type** → **Starter** ($7/mo) chuno.

**Step 17.** Left menu → **Disks** → **Add Disk**:

| Field | Value |
|---|---|
| Name | `smart-tube-data` |
| Mount Path | `/opt/render/project/src/storage` |
| Size | `5` GB |

**Step 18.** **Environment** mein ek aur var daalo:

| Key | Value |
|---|---|
| `DB_PATH` | `/opt/render/project/src/storage/smarttube.db` |

**Step 19.** Save karo. Ab database aur videos dono disk par rahenge — restart aur
redeploy dono ke baad bache rahenge.

> Repo mein `render.yaml` file already ye sab set karke rakhti hai, agar tum Render ka
> "Blueprint" option use karo to.

---

## Kuch atke to

| Problem | Wajah | Fix |
|---|---|---|
| `Could not open requirements file: requirements.txt` | galat repo ya galat branch | Settings → Build & Deploy → Repository `Smart_tube`, Branch `main` |
| Site 50 second baad khuli | free instance so gaya tha | normal hai, kuch nahi karna |
| `/login` PIN maang raha hai | `APP_PIN` set hai | wahi PIN daalo, ya Environment se wo var delete karke redeploy karo |
| Keys/campaigns apne aap gayab | free plan ka data wipe | `PUBLIC_BASE_URL`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET` env vars mein daalo; poora bachana ho to PART 4 |
| Ek hi video **do baar** upload hui | start command mein `-w 1` nahi hai | Settings → Start Command theek karo |
| Naya code deploy nahi ho raha | Auto-Deploy off hai | Manual Deploy → Deploy latest commit; ya Step 11 |
| Deploy ke baad purana page dikh raha | browser cache | page ko hard refresh karo (ya incognito mein kholo) |

---

## Backup

Sab kuch do jagah rehta hai:

- `smarttube.db` — settings, campaigns, schedule, logs
- `storage/` — uploaded videos aur thumbnails

Disk wale setup par dono `storage/` ke andar honge. Backup lena ho to bas ye copy kar lo.
