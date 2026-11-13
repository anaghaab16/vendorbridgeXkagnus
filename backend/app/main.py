from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app import models  # noqa: F401
from app.config import settings
from app.routers import (
    activity, approvals, auth, invoices, notifications, purchase_orders, quotations, reports, rfqs, vendors,
)

Base.metadata.create_all(bind=engine)


def protect_audit_log():
    """On PostgreSQL, also refuse UPDATE and DELETE on audit_logs inside the database itself."""
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION audit_logs_write_once() RETURNS trigger AS $$ "
                "BEGIN RAISE EXCEPTION 'audit_logs records cannot be changed or deleted'; END; $$ LANGUAGE plpgsql")
            for name, action in (("audit_logs_no_update", "UPDATE"), ("audit_logs_no_delete", "DELETE")):
                conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name} ON audit_logs")
                conn.exec_driver_sql(f"CREATE TRIGGER {name} BEFORE {action} ON audit_logs "
                                     "FOR EACH ROW EXECUTE FUNCTION audit_logs_write_once()")
    except Exception as exc:  # the app still works, but say so loudly
        print(f"WARNING: could not install the audit_logs triggers: {exc}")


protect_audit_log()

app = FastAPI(title="VendorBridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vendors.router)
app.include_router(rfqs.router)
app.include_router(quotations.router)
app.include_router(approvals.router)
app.include_router(purchase_orders.router)
app.include_router(invoices.router)
app.include_router(notifications.router)
app.include_router(activity.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}