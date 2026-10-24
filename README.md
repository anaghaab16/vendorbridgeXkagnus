# VendorBridge X Kagnus

Procurement & Vendor Management ERP (Week 1: Foundation).

## Stack
- Frontend: React (Vite) - added later
- Backend: FastAPI
- Database: PostgreSQL via SQLAlchemy

## Backend setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # then fill in real values
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs and http://127.0.0.1:8000/health

## Environment variables
| Name | Purpose |
|------|---------|
| DATABASE_URL | PostgreSQL connection string |
| SECRET_KEY | Long random string used to sign tokens |
