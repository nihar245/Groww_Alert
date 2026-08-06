# 📊 Groww Alert — Portfolio Tracker & WhatsApp Notifier

> A zero-cost, fully automated system that pulls daily Mutual Fund NAVs from the official AMFI API, calculates your portfolio P&L, and sends a clean WhatsApp summary every evening at **9:00 PM IST** — using Meta's official WhatsApp Business Cloud API. No paid APIs, no servers, no third-party relays.

---

## ✨ What You Get

Every evening your WhatsApp receives a message like this:

```
━━━━━━━━━━━━━━━━━━━━━━━
💼 GROWW PORTFOLIO ALERT
🕘 05 Aug 2026, 09:00 PM IST
━━━━━━━━━━━━━━━━━━━━━━━

Mirae Asset Large Cap Fund - Direct…
  NAV: ₹120.4530  (04 Aug 2026)
  Units: 120.456
  Current Value: ₹57,820.15

  📅 Today:   📈 +₹320.15 (+0.56%)
  📅 7-Day:   📈 +₹1,200.40 (+2.12%)
  📅 30-Day:  📈 +₹2,820.15 (+5.13%)
  📊 Overall: 📈 +₹7,820.15 (+15.64%)
  ─────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━
📈 PORTFOLIO SUMMARY
  Total Invested: ₹1,20,000.00
  Total Value:    ₹1,29,540.32
  📅 Today's Gain:  📈 +₹540.32 (+0.42%)
  📊 Net P&L:       📈 +₹9,540.32 (+7.95%)
━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🏗️ Architecture

```
portfolio.json  ──►  tracker.py  ──►  AMFI API (mfapi.in)  [free, public]
                          │
                          ▼
                   notifier.py  ──►  Meta WhatsApp Cloud API  ──►  📱 Your WhatsApp
                          │
                          ▲
               GitHub Actions (cron @ 9 PM IST)
```

| Component | Technology | Cost |
|-----------|-----------|------|
| NAV Data | [mfapi.in](https://mfapi.in) AMFI API | Free |
| WhatsApp | [Meta WhatsApp Business Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api/) | Free (≤ 1,000 msg/month) |
| Scheduler | GitHub Actions | Free (2,000 min/month) |

---

## 📁 Project Structure

```
Groww_Alert/
├── portfolio.json              ← Your holdings (edit this!)
├── tracker.py                  ← Main script
├── notifier.py                 ← WhatsApp dispatcher (Meta Cloud API)
├── config.py                   ← Env var loader
├── requirements.txt
├── .env.example                ← Template for local secrets
├── .gitignore
└── .github/
    └── workflows/
        └── daily_alert.yml     ← GitHub Actions schedule
```

---

## 🚀 Setup Guide

### Step 1 — Create a Meta App & Get API Credentials (~10 minutes)

> This uses Meta's **free test sandbox** — no credit card, no business verification required.

1. Go to [https://developers.facebook.com](https://developers.facebook.com) and log in with your Facebook account.
2. Click **My Apps → Create App**.
3. Choose **Business** as the app type → give it a name (e.g. "GrowwAlert") → click **Create App**.
4. In the app dashboard, find **WhatsApp** in the product list and click **Set up**.
5. You'll land on the **API Setup** page. Here you'll find:
   - **Phone Number ID** — copy this (it's a long number like `123456789012345`).
   - **Temporary access token** — click the copy button. *(Valid for 24h; see Step 6 for a permanent token.)*
6. Under **"To"** (Recipient phone numbers), click **Add phone number** and enter your WhatsApp number. You'll receive an OTP on WhatsApp — enter it to verify.
7. Click **Send message** to test immediately in the console (optional).

---

### Step 2 — Find Your AMFI Fund Codes

Each fund is identified by a unique AMFI scheme code. There are two ways to find it:

**Method A — mfapi.in search:**
```
https://api.mfapi.in/mf/search?q=<FUND_NAME>
```
Example:
```
https://api.mfapi.in/mf/search?q=parag+parikh+flexi
```
Copy the `schemeCode` field from the result.

**Method B — AMFI website:**
Visit [https://www.amfiindia.com/nav-history-download](https://www.amfiindia.com/nav-history-download), search for your fund, and note the scheme code.

---

### Step 3 — Edit `portfolio.json`

Replace the sample data with your actual holdings. Each entry needs:

| Field | Description | Example |
|-------|-------------|---------||
| `fund_name` | Human-readable label | `"Mirae Asset Large Cap"` |
| `amfi_code` | AMFI scheme code (string) | `"118989"` |
| `units` | Total units you own | `120.456` |
| `invested_amount` | Total capital invested (₹) | `50000.00` |

```json
[
  {
    "fund_name": "Your Fund Name Here",
    "amfi_code": "YOUR_AMFI_CODE",
    "units": 0.000,
    "invested_amount": 0.00
  }
]
```

> **Update `portfolio.json` every time you buy or sell fund units.**

---

### Step 4 — Push to GitHub

```bash
# If you haven't already initialised the remote:
git remote add origin https://github.com/YOUR_USERNAME/Groww_Alert.git

git add .
git commit -m "Initial setup"
git push -u origin main
```

---

### Step 5 — Add GitHub Repository Secrets

1. Go to your repository on GitHub.
2. Click **Settings → Secrets and variables → Actions → New repository secret**.
3. Add the following **three** secrets:

| Secret Name | Where to find it |
|-------------|-----------------|
| `WHATSAPP_PHONE` | Your number in E.164 format, e.g. `+919876543210` |
| `WA_PHONE_NUMBER_ID` | The **Phone Number ID** from Step 1 (Meta API Setup page) |
| `WA_ACCESS_TOKEN` | The **access token** from Step 1 (or a permanent System User token) |

---

### Step 6 (Optional) — Generate a Permanent Access Token

The temporary token from the console expires in **24 hours**. For automated daily use, create a permanent one:

1. In your Meta App, go to **Settings → Business settings → System Users**.
2. Create a System User → assign it to your app → generate a token.
3. Grant the `whatsapp_business_messaging` permission.
4. Copy the token and update your `WA_ACCESS_TOKEN` GitHub Secret.

---

### Step 7 — Test It Immediately

Go to **Actions → Daily Portfolio Alert → Run workflow** to trigger a manual run. Check your WhatsApp within 30 seconds.

---

## 💻 Running Locally

```bash
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your secrets
copy .env.example .env           # Windows
# cp .env.example .env           # macOS / Linux
# Then edit .env with your real values

# 4. Run (preview only — no WhatsApp sent)
python tracker.py --dry-run

# 5. Run for real
python tracker.py
```

---

## 🔧 Configuration Reference

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `WHATSAPP_PHONE` | ✅ | Recipient WhatsApp number (E.164 format, e.g. `+919876543210`) |
| `WA_PHONE_NUMBER_ID` | ✅ | Phone Number ID from Meta Developer Console |
| `WA_ACCESS_TOKEN` | ✅ | Meta access token (temporary or permanent System User token) |

### Changing the Schedule

Edit `.github/workflows/daily_alert.yml`:
```yaml
- cron: '30 15 * * *'   # 15:30 UTC = 9:00 PM IST
```
Use [crontab.guru](https://crontab.guru) to convert any IST time to UTC.

---

## 🔄 Updating Your Portfolio

Edit `portfolio.json` directly and commit the change:

```bash
# After buying/selling units, update portfolio.json then:
git add portfolio.json
git commit -m "Update holdings after SIP"
git push
```

---

## 🛠️ Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Required environment variable … is not set` | Check GitHub Secrets or your local `.env` file |
| `Failed to fetch NAV for AMFI code …` | Verify the `amfi_code` at `https://api.mfapi.in/mf/<code>/latest` |
| `Meta API error [code 190]` | Your `WA_ACCESS_TOKEN` is expired — regenerate it or use a permanent System User token |
| `Meta API error [code 131030]` | Recipient number not in sandbox allowlist — add it in the Meta Developer Console |
| `Meta API error [code 100]` | `WA_PHONE_NUMBER_ID` is incorrect — copy it again from API Setup page |
| WhatsApp message not arriving | Ensure your number is verified in the Meta sandbox recipient list |
| GitHub Action not running | Ensure the repo has at least one recent commit (GitHub disables cron on inactive repos) |

---

## 📜 License

MIT — free to use, fork, and modify.


---

## ✨ What You Get

Every evening your WhatsApp receives a message like this:

```
━━━━━━━━━━━━━━━━━━━━━━━
💼 GROWW PORTFOLIO ALERT
🕘 05 Aug 2026, 09:00 PM IST
━━━━━━━━━━━━━━━━━━━━━━━

Mirae Asset Large Cap Fund - Direct…
  NAV (as of 04-08-2026): ₹120.4530
  Units: 120.456
  Invested:     ₹   50,000.00
  Current Val:  ₹   57,820.15
  P&L: 📈 +₹7,820.15 (+15.64%)

Parag Parikh Flexi Cap Fund - Direct…
  NAV (as of 04-08-2026): ₹85.2310
  Units: 85.231
  Invested:     ₹   40,000.00
  Current Val:  ₹   38,962.11
  P&L: 📉 -₹1,037.89 (-2.59%)

━━━━━━━━━━━━━━━━━━━━━━━
📈 PORTFOLIO SUMMARY
  Total Invested:  ₹  120,000.00
  Total Value:     ₹  129,540.32
  Net P&L: +₹9,540.32 (+7.95%)
━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🏗️ Architecture

```
portfolio.json  ──►  tracker.py  ──►  AMFI API (mfapi.in)  [free, public]
                          │
                          ▼
                   notifier.py  ──►  CallMeBot  ──►  📱 Your WhatsApp
                          │
                          ▲
               GitHub Actions (cron @ 9 PM IST)
```

| Component | Technology | Cost |
|-----------|-----------|------|
| NAV Data | [mfapi.in](https://mfapi.in) AMFI API | Free |
| WhatsApp | [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/) | Free |
| Scheduler | GitHub Actions | Free (2,000 min/month) |

---

## 📁 Project Structure

```
Groww_Alert/
├── portfolio.json              ← Your holdings (edit this!)
├── tracker.py                  ← Main script
├── notifier.py                 ← WhatsApp dispatcher
├── config.py                   ← Env var loader
├── requirements.txt
├── .env.example                ← Template for local secrets
├── .gitignore
└── .github/
    └── workflows/
        └── daily_alert.yml     ← GitHub Actions schedule
```

---

## 🚀 Setup Guide

### Step 1 — Get Your Free CallMeBot API Key

> CallMeBot is completely free — no account, no credit card. It takes ~2 minutes.

1. Save the number **+34 644 60 49 14** as a contact (name it "CallMeBot").
2. Open WhatsApp and send this exact message to that contact:
   ```
   I allow callmebot to send me messages
   ```
3. Within a minute you'll receive a reply with your **API key** (an 8-digit number). Save it.

---

### Step 2 — Find Your AMFI Fund Codes

Each fund is identified by a unique AMFI scheme code. There are two ways to find it:

**Method A — mfapi.in search:**
Open your browser and go to:
```
https://api.mfapi.in/mf/search?q=<FUND_NAME>
```
Example:
```
https://api.mfapi.in/mf/search?q=parag+parikh+flexi
```
Copy the `schemeCode` field from the result.

**Method B — AMFI website:**
Visit [https://www.amfiindia.com/nav-history-download](https://www.amfiindia.com/nav-history-download), search for your fund, and note the scheme code.

---

### Step 3 — Edit `portfolio.json`

Replace the sample data with your actual holdings. Each entry needs:

| Field | Description | Example |
|-------|-------------|---------|
| `fund_name` | Human-readable label | `"Mirae Asset Large Cap"` |
| `amfi_code` | AMFI scheme code (string) | `"118989"` |
| `units` | Total units you own | `120.456` |
| `invested_amount` | Total capital invested (₹) | `50000.00` |

```json
[
  {
    "fund_name": "Your Fund Name Here",
    "amfi_code": "YOUR_AMFI_CODE",
    "units": 0.000,
    "invested_amount": 0.00
  }
]
```

> **Update `portfolio.json` every time you buy or sell fund units.**

---

### Step 4 — Push to GitHub

```bash
# If you haven't already initialised the remote:
git remote add origin https://github.com/YOUR_USERNAME/Groww_Alert.git

git add .
git commit -m "Initial setup"
git push -u origin main
```

---

### Step 5 — Add GitHub Repository Secrets

1. Go to your repository on GitHub.
2. Click **Settings → Secrets and variables → Actions → New repository secret**.
3. Add the following two secrets:

| Secret Name | Value |
|-------------|-------|
| `WHATSAPP_PHONE` | Your number in international format, e.g. `+919876543210` |
| `CALLMEBOT_API_KEY` | The 8-digit key you got from CallMeBot in Step 1 |

---

### Step 6 — Test It Immediately

Go to **Actions → Daily Portfolio Alert → Run workflow** to trigger a manual run without waiting for 9 PM. Check your WhatsApp within 30 seconds.

---

## 💻 Running Locally

```bash
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your secrets
copy .env.example .env           # Windows
# cp .env.example .env           # macOS / Linux
# Then edit .env with your real values

# 4. Run
python tracker.py
```

---

## 🔧 Configuration Reference

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `WHATSAPP_PHONE` | ✅ | Your WhatsApp number (+91XXXXXXXXXX) |
| `CALLMEBOT_API_KEY` | ✅ | Your CallMeBot API key |

### Changing the Schedule

Edit `.github/workflows/daily_alert.yml`:
```yaml
- cron: '30 15 * * *'   # 15:30 UTC = 9:00 PM IST
```
Use [crontab.guru](https://crontab.guru) to convert any IST time to UTC.

---

## 🔄 Updating Your Portfolio

Edit `portfolio.json` directly and commit the change:

```bash
# After buying/selling units, update portfolio.json then:
git add portfolio.json
git commit -m "Update holdings after SIP"
git push
```

---

## 🛠️ Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Required environment variable … is not set` | Check GitHub Secrets or your local `.env` file |
| `Failed to fetch NAV for AMFI code …` | Verify the `amfi_code` at `https://api.mfapi.in/mf/<code>/latest` |
| WhatsApp message not arriving | Re-activate CallMeBot by sending the activation message again |
| GitHub Action not running | Ensure the repo has at least one recent commit (GitHub disables cron on inactive repos) |

---

## 📜 License

MIT — free to use, fork, and modify.
