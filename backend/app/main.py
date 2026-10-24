from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import auth
from . import vendors

Base.metadata.create_all(bind=engine)

app = FastAPI(title="VendorBridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vendors.router)


@app.get("/health")
def health():
    return {"status": "ok"}
