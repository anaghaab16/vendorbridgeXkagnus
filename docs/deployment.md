# Deployment guide

First check which hosting your programme approved. The steps below use **Neon** (database), **Render** (backend) and **Vercel** (frontend), which are free to start. Any host that runs Python and serves static files works the same way.

## 1. Database (Neon)
- Use the project you already develop against, or make a new one for production. Copy its connection string, written as `postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require`.
- Tables are created by the backend on first start. The audit-log protection triggers are installed at the same time, so the database user needs permission to create tables, functions and triggers (the default Neon owner role has it).

## 2. Backend (Render)
1. Push the repository to GitHub. Run `python scripts/check_secrets.py` first.
2. In Render choose **New, Web Service**, pick the repository, and set:
   - Root directory `backend`
   - Build command `pip install -r requirements.txt`
   - Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health check path `/health`
   (`render.yaml` in the repository root holds the same settings if you prefer a blueprint.)
3. Add these **environment variables** in the Render dashboard (never in the repository):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `SECRET_KEY` | a new random value, different from your local one |
   | `CORS_ORIGINS` | your frontend address, for example `https://vendorbridge.vercel.app` (no trailing slash) |
   | `COMPANY_NAME`, `COMPANY_ADDRESS`, `COMPANY_GSTIN` | buyer details for documents |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | mail server, only if you want invoice email |

4. Deploy. Open `https://<your-service>.onrender.com/health`. It should answer `{"status":"ok"}`. `/docs` shows the interactive API.

Notes: the free plan sleeps after inactivity, so the first request can take about a minute. Uploaded attachments live on the server's temporary disk and are lost on each redeploy; attach a persistent disk or accept this limitation and say so.

## 3. Frontend (Vercel)
1. **New Project**, pick the same repository, set the root directory to `frontend`. Vercel detects Vite (build `npm run build`, output `dist`).
2. Add one environment variable: `VITE_API_URL` = your backend address, for example `https://vendorbridge-api.onrender.com`. This value is public and is not a secret. Never put keys or passwords in a `VITE_` variable, because they are visible in the browser.
3. `frontend/vercel.json` already sends every path to `index.html`, so reloading a page such as `/rfqs/3` works. (For Netlify, `frontend/public/_redirects` does the same.)
4. Deploy, then copy the address into the backend's `CORS_ORIGINS` and redeploy the backend. If the browser console shows a CORS error, this setting is the cause.

## 4. First start in production
- Register the first account with the role **Admin** (only one admin is allowed). Register an officer and two managers, then add vendors and vendor accounts.
- Or load demo data into an empty database: `python scripts/seed_demo.py --api https://<your-backend> --password "<a strong password>"`. Do not use demo accounts with weak passwords on a public address; change or remove them afterwards.

## 5. Check the deployment
- [ ] `/health` answers ok and the frontend loads over HTTPS.
- [ ] Register, sign in, refresh the page (still signed in), sign out.
- [ ] Walk the lifecycle in `docs/TESTING.md`, including PDF download and one email.
- [ ] Browser developer tools show no request to `localhost`, and no secret appears in the page source or network responses.
- [ ] `git ls-files` shows no `.env` file and `python scripts/check_secrets.py` passes.

## Security checklist
- Secrets live only in the host's environment settings. `.env` is git-ignored; `.env.example` holds fake values.
- Use a different `SECRET_KEY` and database password in production than in development, and change any value that was ever shown in a screenshot or chat.
- HTTPS is provided by the hosts. The API only accepts browsers from `CORS_ORIGINS`.
- Known risk: the login token is kept in `localStorage`, so any script injected into the page could read it. The app does not render user input as HTML, which limits this, but a stricter design would use secure cookies.