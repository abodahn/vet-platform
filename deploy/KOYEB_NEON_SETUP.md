# Production Deployment Guide
## Koyeb (Free Web Hosting) + Neon.tech (Free PostgreSQL)
### Premium Animal Hospital Platform

Both services are 100% free. No credit card required. Never sleep.

---

## PART 1 — Free PostgreSQL on Neon.tech (5 minutes)

### 1. Create Neon Account
Go to https://neon.tech → Sign Up (use GitHub login for speed)

### 2. Create a Project
- Click **New Project**
- Name: `vetclinic`
- Region: choose closest to Egypt → **AWS / EU-Central (Frankfurt)** or **AWS / EU-West (Ireland)**
- Click **Create Project**

### 3. Create the Database
- In your project → **Databases** tab
- Database name: `vetclinic`
- Click **Create**

### 4. Get the Connection String
- Go to **Dashboard** → **Connection Details**
- Select: **Connection string** → **psycopg2** format
- Copy the full string — it looks like:
  ```
  postgresql://neondb_owner:AbCdEf123@ep-cool-name-12345678.eu-central-1.aws.neon.tech/vetclinic?sslmode=require
  ```
- **Save this — you'll need it in Part 2**

---

## PART 2 — Push Code to GitHub (2 minutes)

Your code must be on GitHub for Koyeb to deploy it.

```bash
# In your platform folder (C:\vet\platform)
git init
git add .
git commit -m "Initial production deployment"

# Create a repo on github.com → copy the URL
git remote add origin https://github.com/YOUR_USERNAME/vet-platform.git
git push -u origin main
```

> ⚠️ The .gitignore already protects .env files — your passwords will NOT be uploaded.

---

## PART 3 — Deploy on Koyeb (5 minutes)

### 1. Create Koyeb Account
Go to https://app.koyeb.com → Sign Up (use GitHub login)

### 2. Create a New App
- Click **Create App**
- Choose **GitHub** as source
- Select your repository: `vet-platform`
- Branch: `main`

### 3. Configure the Service
| Setting | Value |
|---------|-------|
| Build method | **Buildpack** (auto-detected) |
| Run command | `gunicorn -c gunicorn.conf.py "app:create_app()"` |
| Port | `8000` |

### 4. Add Environment Variables
Click **Environment Variables** → Add each one:

| Key | Value |
|-----|-------|
| `FLASK_ENV` | `production` |
| `POSTGRES_DSN` | *(paste your Neon connection string from Part 1 Step 4)* |
| `PLATFORM_SECRET_KEY` | `5d1ba3d1364fac932c8780849f158723d31ab8c5c180d2a0a0cc3e45bfc207f639b90b48669df334e96160db566f4b45ecc29f674f19b77967eddd07fdd77fd5` |
| `SESSION_COOKIE_SECURE` | `true` |
| `PLATFORM_ADMIN_USER` | `admin` |
| `PLATFORM_ADMIN_PASS` | `Ahmed@1122` |
| `PLATFORM_PORT` | `8000` |
| `PLATFORM_DEBUG` | `0` |
| `LEGACY_APP_ENABLED` | `0` |

### 5. Deploy
- Click **Deploy**
- Wait ~3 minutes for build to complete
- Koyeb gives you a free URL like: `https://your-app-name.koyeb.app`

---

## PART 4 — First Login on Production

1. Open: `https://your-app-name.koyeb.app`
2. Login: `admin` / `Ahmed@1122`
3. Go to **Settings → Clinic Info** and fill in your clinic details
4. Go to **HR → Staff** and create real staff accounts
5. Go to **Catalog → Services** and add your services with prices

---

## PART 5 — Custom Domain (Optional, Free)

Koyeb supports custom domains for free:
1. Koyeb → Your Service → **Domains** → Add Domain
2. Enter: `platform.premiumanimalhospital.com` (or your domain)
3. Add the CNAME record Koyeb shows you to your domain DNS
4. SSL is handled automatically by Koyeb

---

## Summary — What You Get for Free

| Feature | Provider | Limit | Cost |
|---------|----------|-------|------|
| Web hosting | Koyeb | 1 service, 512MB RAM, never sleeps | FREE |
| PostgreSQL | Neon.tech | 0.5 GB storage, unlimited connections | FREE |
| SSL/HTTPS | Koyeb | Automatic, custom domain | FREE |
| CI/CD | Koyeb | Auto-deploy on every git push | FREE |
| DB backups | Neon.tech | Point-in-time restore (7 days) | FREE |

---

## Updating Production (after any code change)

```bash
git add .
git commit -m "describe your change"
git push origin main
# Koyeb automatically detects the push and redeploys in ~2 minutes
```

---

## Two Stages at a Glance

| | Development | Production |
|--|-------------|------------|
| **Start command** | `python run.py` | Auto (Koyeb git push) |
| **Config file** | `.env.development` | Environment vars on Koyeb |
| **Database** | Local PostgreSQL | Neon.tech (free) |
| **URL** | http://localhost:5100 | https://your-app.koyeb.app |
| **DEBUG** | ON | OFF |
| **HTTPS** | Not needed | Automatic |
| **Login** | admin / Ahmed@1122 | admin / Ahmed@1122 |
