# YouTube setup — zero se, step by step

Ye guide sirf YouTube ke liye hai (Instagram alag hai, README mein hai).
Har jagah `<YOUR-URL>` ki jagah apni site ka URL likhna hai, jaise
`https://smart-tube-hya6.onrender.com`.

Phone se kar rahe ho to browser mein **Desktop site** on kar lo (⋮ menu se),
warna Google Console ke kuch buttons chhup jaate hain.

---

## Do baatein pehle jaan lo

**1. App ko "Testing" mode mein hi rakhna hai.**
Video upload wala scope Google ke liye "sensitive" hai. Agar app **Production**
mein chala gaya to Google verification maangta hai (hafte lagte hain, privacy
policy + domain ownership chahiye) aur tab tak login block ho jaata hai —
error aata hai:

> Access blocked: … has not completed the Google verification process

Testing mode mein verification ki zarurat nahi. Bas jo Gmail **Test users** list
mein hai wahi login kar sakta hai — personal use ke liye yehi sahi hai.

**2. Testing mode mein token 7 din baad expire hota hai.**
Google testing-mode apps ko 7 din wala refresh token deta hai. Matlab har
~7 din mein `/enter` page se **Connect YouTube** dobara dabana padega. Ye Google
ka rule hai, tool ka bug nahi. Client ko pehle bata dena.

---

## PART 1 — Google Cloud Console

> Naye Google UI mein OAuth settings **"Google Auth Platform"** ke andar hain.
> Purane UI mein wahi cheezein **"APIs & Services → OAuth consent screen /
> Credentials"** ke andar milti hain. Dono ek hi hain — jo dikhe wo use karo.

### Step 1 — Project banao

1. [console.cloud.google.com](https://console.cloud.google.com) kholo, Gmail se login karo.
2. Upar-left project dropdown → **NEW PROJECT**.
3. Name: `Smart Tube` → **CREATE**.
4. 10–15 second baad upar se **wahi project select karo**.
   (Ye step miss karne se log galat project mein kaam karte rehte hain.)

### Step 2 — YouTube Data API enable karo

1. Upar search bar: `YouTube Data API v3` → result par click.
2. **ENABLE** dabao, "API enabled" dikhne tak ruko.

### Step 3 — OAuth app banao

1. Search bar: `Google Auth Platform` → us par jao.
2. **GET STARTED** dabao (pehli baar par dikhta hai). Form bharo:
   - **App name**: `Smart Tube`
   - **User support email**: apna Gmail
   - **Audience**: **External**
   - **Contact email**: apna Gmail
   - Policies wala checkbox tick karo
3. **CREATE**.

### Step 4 — Testing mode + test user

1. Left menu → **Audience**.
2. **Publishing status** dekho:
   - `In production` likha ho → **BACK TO TESTING** dabao.
   - `Testing` ho → theek hai.
3. Usi page par **Test users** → **+ ADD USERS**.
4. **Apna khud ka Gmail** daalo (jisse test karoge; client ka abhi nahi chahiye).
5. **SAVE**.

### Step 5 — Scopes add karo

1. Left menu → **Data Access** (purane UI: consent screen ke andar "Scopes").
2. **ADD OR REMOVE SCOPES**.
3. Filter box mein: `youtube`
4. Ye **do** tick karo:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
5. **UPDATE** → phir page ke neeche **SAVE**.
   (Ye doosra SAVE log bhool jaate hain, isliye scopes save nahi hote.)

### Step 6 — Client ID + Secret

1. Left menu → **Clients** (purane UI: Credentials).
2. **+ CREATE CLIENT**.
3. **Application type**: **Web application**.
4. **Name**: `Smart Tube Web`.
5. **Authorized redirect URIs** → **+ ADD URI** → exactly ye:
   ```
   <YOUR-URL>/auth/youtube/callback
   ```
   Na aage space, na end mein slash. `https://` zaruri hai.
6. **CREATE**.
7. Popup mein **Client ID** aur **Client Secret** milenge — dono safe jagah copy karo.
   Secret dobara nahi dikhta (par reset kar sakte ho).

---

## PART 2 — Website par

### Step 7 — Public base URL

1. `<YOUR-URL>/enter` kholo.
2. Neeche **General** card → **Public base URL**:
   ```
   <YOUR-URL>
   ```
   (bina trailing slash)
3. **Save settings**.
4. Upar YouTube box mein redirect URI check karo — usme tumhara domain dikhna
   chahiye, `localhost` nahi. `localhost` dikhe to ye step dobara karo.

### Step 8 — Keys daalo aur connect karo

1. YouTube box mein Step 6 wali **Client ID** aur **Client Secret** paste karo.
2. **Save keys**.
3. **Connect YouTube** dabao.
4. Google login → **wahi Gmail** chuno jo Step 4 mein test user banaya tha.
5. *"Google hasn't verified this app"* warning aayegi (normal hai):
   **Advanced** → **Go to Smart Tube (unsafe)**.
6. **Continue / Allow**.
7. Wapas site par aa jaoge — green **connected** + channel ka naam dikhega. ✅

---

## PART 3 — Test

1. **New Campaign** → name `Test`, platform **YouTube only**.
2. Chhoti video chuno (10–20 sec, 5–10 MB — jaldi ho jayegi).
3. Title/comment default hi rehne do.
4. **Privacy: Private** (test hai, public nahi karna).
5. Schedule: **Gap = 2** minutes, **Total uploads = 2**.
6. "Campaign banate hi chalu kar do" checked → submit.
7. 1–2 minute mein pehli row `running` → `success` ho jayegi.
8. **Open ↗** se video kholo, uske **comments** mein auto-comment check karo.
9. Page ke neeche **logs** section mein pura detail milega.

---

## Kuch atke to

| Problem | Fix |
|---|---|
| `redirect_uri_mismatch` | Step 6 ka URI aur Step 7 ka base URL exactly same hone chahiye. https, no trailing slash. |
| `Access blocked: … verification process` | Step 4 — Publishing status **Testing** karo. |
| `Access blocked: app not configured` ya scope error | Step 5 — scopes add karke dono **UPDATE** aur **SAVE** dabao. |
| Login par "you don't have access" | Step 4 — jis Gmail se login kar rahe ho wo test users mein hai? 2–3 min wait bhi karo. |
| 7 din baad uploads fail | Token expire ho gaya (testing mode ka rule). `/enter` → **Connect YouTube** dobara. |
| `quotaExceeded` | Normal — din ke ~6 uploads ke baad aata hai. Baaki uploads khud agle din shift ho jaate hain. |
| Page 50 sec slow khula | Render free instance so gaya tha, pehli request usse jagati hai. |
| Site par `/login` maang raha hai | Render → Environment mein `APP_PIN` set hai. Wahi PIN daalo, ya variable delete karke redeploy karo. |
