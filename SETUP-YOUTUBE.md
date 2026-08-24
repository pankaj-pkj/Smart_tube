# YouTube connect karna — zero se, step by step

Ye guide sirf YouTube ke liye hai. Hosting pehle ho jani chahiye —
[HOSTING-RENDER.md](HOSTING-RENDER.md) dekho.

Har jagah `<YOUR-URL>` ki jagah apni site ka URL likhna hai, jaise
`https://smart-tube-hya6.onrender.com`.

Phone se kar rahe ho to browser mein **Desktop site** on kar lo (⋮ menu se), warna
Google Console ke aadhe buttons dikhte hi nahi.

---

## Pehle 4 baatein — inhi mein log atakte hain

**1. App ko "Testing" mode mein hi rakhna hai.**
Video upload wala permission Google ke liye "sensitive" hai. App ko **Production** mein
daal doge to Google verification maangega (hafte lagte hain, privacy policy + domain
ownership chahiye) aur tab tak login block rahega.
Testing mode mein verification ki zarurat nahi — bas jo Gmail **Test users** list mein
hai wahi use kar sakta hai.

**2. Do alag Gmail ho sakte hain, aur ye bilkul theek hai.**
Cloud project kisi bhi Gmail par ban sakta hai (maan lo `owner@gmail.com`). YouTube
channel kisi aur Gmail par ho sakta hai (maan lo `channel@gmail.com`).
Bas ek niyam yaad rakho:

> **Jis Gmail se tum "Connect" ke waqt login karoge, wahi Gmail Test users list mein
> hona chahiye.**

Project kiska hai, isse koi farak nahi padta.

**3. Testing mode mein token 7 din baad expire hota hai.**
Google testing-mode apps ko 7 din wala token deta hai. Matlab har ~7 din mein `/enter`
page se **Save & Connect YouTube** dobara dabana padega. Ye Google ka rule hai, tool ka
bug nahi. Client ko pehle bata dena.

**4. Free hosting par saved data mit jaata hai.**
Render free plan 15 min inactivity ke baad instance sula deta hai, aur jaagne par app
folder reset ho jaata hai — keys, connected account aur campaigns sab chale jaate hain.

Bachne ke tareeke:
- **Keys ke liye:** hosting ke env vars mein daal do — `YT_CLIENT_ID`,
  `YT_CLIENT_SECRET`. `/enter` par field khali dikhe to bhi kaam karengi.
- **Campaigns + login token ke liye:** persistent disk chahiye
  (HOSTING-RENDER.md ka PART 4), ya app apne PC/VPS par chalao.

Sirf test kar rahe ho to itna kaafi hai: **ek hi baithak mein** keys daalo, connect karo
aur test upload chala lo — beech mein lamba gap mat do.

---

## PART A — Kaunsa Gmail use karna hai, pehle ye tay karo

**Step 1.** youtube.com kholo → upar-right profile photo par tap → jo email dikhe wo
**note kar lo**. Isi Gmail se aage "Connect" karna hai.

**Step 2.** Confusion se bachne ke liye poora kaam ek **Incognito window** mein karo
(Chrome ⋮ → New Incognito tab). Usme sirf ek account login hoga.

Channel **Brand Account** par hai (naam alag, manage kisi Gmail se hota hai)? Tab bhi
problem nahi — jis Gmail se wo manage hota hai wahi use karo. Connect ke baad Google
channel chunne ko puchhega.

---

## PART B — Google Cloud project

**Step 3.** [console.cloud.google.com](https://console.cloud.google.com) kholo, login karo.

**Step 4.** Pehli baar hai to Country chuno + Terms wala checkbox tick karo →
**AGREE AND CONTINUE**.

**Step 5.** Upar-left project dropdown ("Select a project") par tap → **NEW PROJECT**.

**Step 6.** Name: `Smart Tube` → **CREATE**.

**Step 7.** 10-20 second baad **upar-left dropdown se wahi project select karo**.

> ⚠️ Project banane ke baad wo apne aap select nahi hota. Upar-left mein "Smart Tube"
> likha dikhna chahiye. Ye step sabse zyada log bhoolte hain, aur phir galat project
> mein kaam karte rehte hain.

---

## PART C — YouTube API on karna

**Step 8.** Upar search bar mein type karo: `YouTube Data API v3` → result par tap.

**Step 9.** Bada blue **ENABLE** button dabao → "API enabled" dikhne tak ruko.

---

## PART D — OAuth app banana

> Naye Google UI mein ye sab **"Google Auth Platform"** ke andar hai. Purane UI mein
> **"APIs & Services → OAuth consent screen / Credentials"** ke andar. Dono ek hi hain.

**Step 10.** Search bar: `Google Auth Platform` → us par jao.
(Na mile to search karo `OAuth consent screen`.)

**Step 11.** **GET STARTED** dabao. 4 chhote steps aayenge:

- **App Information** — App name: `Smart Tube`, User support email: apna Gmail → **NEXT**
- **Audience** — **External** chuno (Internal nahi) → **NEXT**
- **Contact Information** — apna Gmail → **NEXT**
- **Finish** — policy wala checkbox tick → **CONTINUE** → **CREATE**

**Step 12.** Ab left menu aa jayega:
**Overview · Branding · Audience · Clients · Data Access · Verification Center**
(na dikhe to upar-left **☰** dabao)

---

## PART E — Test user add karna

**Step 13.** Left menu → **Audience**.

**Step 14.** **Publishing status** dekho:
- `Testing` → sahi hai
- `In production` → **BACK TO TESTING** dabao

**Step 15.** Neeche **Test users** → **+ ADD USERS**.

**Step 16.** **Step 1 wala Gmail** type karo (jis par YouTube channel hai) → **SAVE**.

**Step 17.** List mein wo email dikhna chahiye. Aage chalke koi doosra Gmail bhi use
karna ho to usse bhi yahin add karna padega.

---

## PART F — Permissions (scopes)

**Step 18.** Left menu → **Data Access**.

**Step 19.** **ADD OR REMOVE SCOPES** dabao — right se panel khulega.

**Step 20.** Filter box mein type karo: `youtube`

**Step 21.** Ye **do** tick karo:
- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube.force-ssl`

**Step 22.** Panel ke neeche **UPDATE** dabao.

**Step 23.** Ab page ke **sabse neeche** **SAVE** bhi dabao.

> ⚠️ Ye doosra SAVE 90% log bhool jaate hain, aur phir scopes save hi nahi hote.

---

## PART G — Client ID aur Secret

**Step 24.** Left menu → **Clients** → **+ CREATE CLIENT**.

**Step 25.** **Application type**: **Web application**.

**Step 26.** **Name**: `Smart Tube Web`.

**Step 27.** Neeche **Authorized redirect URIs** → **+ ADD URI** → exactly ye daalo:
```
<YOUR-URL>/auth/youtube/callback
```

Check karo:
- `https://` hai (`http://` nahi)
- end mein koi slash nahi
- aage-peeche koi space nahi

**Step 28.** **CREATE** dabao.

**Step 29.** Popup mein **Client ID** aur **Client Secret** milenge — **dono safe jagah
copy kar lo** (Notes app mein, ya khud ko WhatsApp kar do). Secret dobara nahi dikhta
(reset kar sakte ho).

---

## PART H — Website par keys daalna

**Step 30.** `<YOUR-URL>/enter` kholo.

**Step 31.** Sabse neeche **⚙️ General** card → **Public base URL** field mein **sirf
domain** daalo:
```
<YOUR-URL>
```

> ⚠️ **Yahan poori redirect URI mat paste karna.** Sirf `https://...onrender.com`.
> `/auth/youtube/callback` app khud jodta hai. Poori URI paste kar doge to wo **do baar**
> lag jayegi aur Google `redirect_uri_mismatch` dega.
> (Naya code ise apne aap saaf kar deta hai, par sahi daalna hi behtar hai.)

**Step 32.** **Save settings** dabao.

**Step 33.** Upar **YouTube** box mein jo redirect URI likhi hai use padho. Aisi honi
chahiye — `/auth/youtube/callback` **sirf ek baar**:
```
<YOUR-URL>/auth/youtube/callback
```
`localhost` dikhe ya do baar `/callback` dikhe → Step 31 dobara karo.

**Step 34.** YouTube box mein Step 29 wali **Client ID** aur **Client Secret** paste karo.

**Step 35.** ⚠️ Ab **"Save & Connect YouTube"** (pink wala) dabao.

> Ye button pehle keys save karta hai, phir Google par le jaata hai. "Sirf save karo"
> sirf save karta hai, connect nahi.

---

## PART I — Google par allow karna

**Step 36.** Google ka account chooser khulega. **Step 1 wala Gmail** chuno.
List mein na ho to **"Use another account"** se login karo.

**Step 37.** **"Google hasn't verified this app"** screen aayegi — ye normal hai:
- neeche-left **"Advanced"** par tap karo
- phir **"Go to Smart Tube (unsafe)"** par tap karo

> Sirf "Back to safety" dabaoge to connect nahi hoga.

**Step 38.** Ek se zyada channel hain to Google puchhega — apna channel chuno.

**Step 39.** ⚠️ **Permissions wali screen — checkboxes tick karna zaruri hai.**
Google inhe by default khali chhodta hai. "Select all" ho to wahi dabao, warna dono
ek-ek karke tick karo.

> Bina tick kiye Continue dabaoge to connect to ho jayega, **par upload ke waqt
> "insufficient permissions" error aayega** aur wajah samajh nahi aayegi.

**Step 40.** **Continue** / **Allow** dabao.

**Step 41.** Wapas site par pahunch jaoge. Ab ye dikhna chahiye:
- green flash: *"YouTube channel connect ho gaya: [channel ka naam]"*
- YouTube box par green **connected** tag
- channel ka naam, subscribers, videos ki count
- left sidebar mein YouTube ke aage **hari batti** ✅

---

## PART J — Test upload

Connect hote hi **turant** ye kar lo (free hosting par 15 min baad sab mit jayega).

**Step 42.** **New Campaign** → bharo:
- **Campaign name**: `Test`
- **Platform**: `YouTube only`
- **Video file**: chhoti video (10-20 sec, 5-10 MB)
- **Title** / **Auto comment**: default hi rehne do
- **Privacy**: **Private** ⬅️ test hai, public mat karna

**Step 43.** Schedule section:
- **Gap (minutes)**: `2`
- **Total uploads**: `2`
- "Campaign banate hi chalu kar do" **checked**

**Step 44.** **Campaign banao aur schedule karo** dabao.

**Step 45.** 2-4 minute wait karke page **refresh** karo. Rows ka status
`pending` → `running` (progress bar) → `success` hona chahiye.

**Step 46.** **Open ↗** se video kholo (private hai, sirf tumhe dikhegi).

**Step 47.** Video ke **comments** check karo — auto-comment gaya hoga.

**Step 48.** Page ke neeche **logs** mein pura detail milega.

Sab chal gaya? Ab asli campaign bana lo — **Gap 60**, **Total 24**.

---

## Errors ki poori list

| Screen par kya likha hai | Matlab | Fix |
|---|---|---|
| `YouTube Client ID / Secret save nahi hain` | keys type ki thi par save nahi hui | **Save & Connect YouTube** button dabao (sirf type karne se save nahi hota) |
| `Error 400: redirect_uri_mismatch` | app jo URI bhej raha hai wo Console mein registered nahi hai | Error page par **"error details"** dabao, `redirect_uri=` padho. `localhost` ho → Step 31. Do baar `/callback` ho → Step 31. Alag domain ho → Console mein wahi URI add karo |
| `Error 403: access_denied` + *"can only be accessed by developer-approved testers"* | jis Gmail se login kiya wo Test users mein nahi hai | Step 13-16, **usi Gmail** ko add karo. Console mein project ke owner Gmail se jaana padega |
| `has not completed the Google verification process` (testers wali line ke bina) | app Production mode mein hai | Step 14 — **BACK TO TESTING** |
| `Error 401: invalid_client` | Client ID/Secret galat ya adhoora paste hua | Step 34 dobara, aage-peeche space na ho |
| `Access blocked: app not configured` | scopes save nahi hue | Step 18-23, **UPDATE ke baad SAVE bhi** |
| Upload par `insufficient permissions` | consent screen par checkboxes tick nahi kiye | Disconnect karo, dobara connect karo, Step 39 par sab tick karo |
| Upload par `quotaExceeded` | din ke ~6 uploads ho gaye | Normal hai. Baaki uploads apne aap agle din shift ho jaate hain |
| 7 din baad sab uploads fail | testing-mode token expire ho gaya | `/enter` → **Save & Connect YouTube** dobara |
| Keys apne aap gayab ho gayin | free hosting ka data wipe | Upar wali baat #4 |

Ab bhi atko to error page ka **"error details"** wala screenshot lo — usme exact wajah
likhi hoti hai.
