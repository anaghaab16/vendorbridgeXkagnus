from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth

app = FastAPI()

# 1. Enable CORS so your React frontend (localhost:5173) can talk to FastAPI (127.0.0.1:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Include your auth router (since auth.py already has prefix="/auth")
app.include_router(auth.router, tags=["auth"])
