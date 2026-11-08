# ⚡ Seedr Minimal Cloud WebApp

[![Powered by seedr-py](https://img.shields.io/badge/Powered%20by-seedr--py-blue.svg)](https://pypi.org/project/seedr-py/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)

A clean, lightning-fast, minimalist personal cloud torrent downloader powered by **[seedr-py](https://pypi.org/project/seedr-py/)**.

Bypasses Seedr's web bloat, eliminates login CAPTCHAs, enables **one-click direct ZIP downloads of entire folders without mCaptcha**, and provides an in-browser HLS video player with AAC stereo audio conversion.

---

## ✨ Features

- 🔑 **Dual Authentication Modes:**
  - **Access Passcode (e.g. `0001`):** Allows friends or guests to access your cloud storage without seeing your Seedr username or password.
  - **Personal Seedr Login:** Allows users to log in with their own Seedr accounts directly with zero CAPTCHA.
- 📦 **One-Click Folder ZIP Download:** Downloads entire subfolder structures as a single ZIP archive directly from Seedr's high-speed CDN with zero interaction.
- 🎬 **Universal HLS Video Streaming:** Transcodes Dolby EAC3 5.1 audio tracks into AAC stereo on-the-fly, fixing browser silence on Chrome/Firefox/Edge while preserving access to raw 1080p/4K streams.
- 🧲 **Magnet & `.torrent` Support:** Paste any magnet link, torrent URL, or upload local `.torrent` files.
- ⚡ **Active Task Monitor:** Real-time progress bars, download rates, and seeder counts with task cancellation.
- 📂 **Full File Management:** Instant signed CDN download URLs, folder exploration, and batch or single item deletion.
- 🎨 **Light Neutral Aesthetic:** Designed with soft `#F4F5F7` background tones, clean card elevations, and minimal color highlights.

---

## 🚀 Quickstart (Local)

### 1. Activate Environment
```powershell
cd seedr-webapp
.\.venv\Scripts\activate      # Windows
# or: source .venv/bin/activate  # macOS / Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Edit the `.env` file with your credentials:
```env
SEEDR_EMAIL=your_email@example.com
SEEDR_PASSWORD=your_password
MASTER_PASSCODE=0001
SECRET_KEY=super_secret_session_key
PORT=5000
```

### 4. Run the App
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 🌐 Deploy to Render (100% Free)

1. Push this folder to a GitHub repository.
2. Sign in to [Render.com](https://render.com) and create a **New Web Service**.
3. Select your repository:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. In the **Environment Variables** section, add:
   - `SEEDR_EMAIL` = `your_email@example.com`
   - `SEEDR_PASSWORD` = `your_password`
   - `MASTER_PASSCODE` = `0001`
   - `SECRET_KEY` = `some_random_secret_key`
5. Click **Create Web Service**. Your app is live at `https://your-app.onrender.com`.

### Connecting a Free Custom Domain:
1. In Render, go to **Settings &rarr; Custom Domains**.
2. Add your domain (e.g., `cloud.yourdomain.com`).
3. Add a CNAME record in your DNS provider pointing to your Render subdomain. Free SSL certificate is issued automatically.
