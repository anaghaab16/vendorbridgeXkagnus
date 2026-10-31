# VendorBridge ERP

VendorBridge procurement and vendor management ERP, built for the Kagnus full stack internship (Project 1) from the provided problem statement and Excalidraw mockup.

- **Week 1:** authentication, dashboard, vendor management
- **Week 2:** RFQs, vendor quotations, quotation comparison

## Run

Requirements: Python 3.12, Node.js 18 or newer, a PostgreSQL database (a free Neon project works).

### 1. Backend configuration

Copy `backend/.env.example` to `backend/.env` and set:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string (`postgresql+psycopg2://...`) |
| `SECRET_KEY` | yes | Signs login tokens. Make one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_MINUTES` | no | Token lifetime, default 60 |

`.env` is git-ignored. Do not commit it.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Tables are created on first start. Uploaded RFQ attachments are stored in `backend/uploads/` (git-ignored).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Optional: set `VITE_API_URL` in `frontend/.env` if the API is not at `http://127.0.0.1:8000`.

- App: http://localhost:5173
- API docs: http://127.0.0.1:8000/docs

## Implemented Screens

- Login and registration (screens 1 and 2) with role selection, validation, JWT session that survives a refresh.
- Dashboard (screen 3) with vendor counts and the sidebar layout.
- Vendor management (screen 4): name, category, GST number, contact number, login email, rating, status; search, status filters, add, edit, delete.
- RFQ creation and list (screen 5): title, category, deadline, description, line items with quantity and unit, vendor assignment, up to 5 attachments. Each RFQ gets a unique number such as `RFQ-2026-0001`. Save as draft or send to vendors. List shows status, deadline and quotes received.
- RFQ detail: requirements, assigned vendors with quotation status, attachments, and actions to send, close, cancel or delete a draft.
- Vendor RFQ view and quotation submission (screen 6): vendors see only RFQs assigned to them, enter unit prices, GST, delivery days, payment terms and notes, save a draft or submit, and edit until the deadline.
- Quotation comparison (screen 7): submitted quotations side by side with the lowest total highlighted, fastest delivery, vendor ratings, sorting by price, delivery or rating, filters for minimum rating and maximum delivery days, and an empty state. An officer can select one quotation, which is stored for the Week 3 approval workflow.

## Roles

| Action | Admin | Manager | Procurement Officer | Vendor |
|---|---|---|---|---|
| Dashboard | yes | yes | yes | yes |
| View and manage vendors | yes | yes | yes | no |
| Delete vendors | yes | yes | no | no |
| View RFQs and compare quotations | yes | yes | yes | no |
| Create, send, cancel RFQs, select a quotation | yes | no | yes | no |
| See assigned RFQs and submit quotations | no | no | no | yes |

A vendor user is linked to a vendor record by email: the vendor record's login email must match the vendor user's login email. Only one Admin can be created from the register form.

## Architecture Notes

- `frontend/` is a React (Vite) single-page app. `auth.jsx` holds the logged-in user, `api.js` sends JSON requests with the token, `files.js` handles uploads and downloads, and a route guard in `App.jsx` blocks pages by login state and role.
- `backend/` is a FastAPI app. Routes live in `routers/` (`auth`, `vendors`, `rfqs`, `quotations`). `deps.py` checks the token and role on every protected route, and `services.py` holds shared RFQ and quotation logic.
- Rules are enforced on the server: vendors can only read RFQs assigned to them, quotations are refused after the deadline, prices must match the RFQ's own items, and a submitted quotation cannot be changed once it is selected.
- Database relationships: `rfqs` has line items, assigned vendors, attachments and quotations. A quotation must belong to an assigned vendor of the same RFQ, enforced by a composite foreign key. At most one quotation per RFQ can be selected.
- Passwords are hashed with bcrypt. Tokens are JWTs.

## Not Implemented Yet

- Profile photo upload (the photo icon is a preview only)
- Forgot-password emails
- Editing an RFQ after it is saved (delete the draft and create it again)
- Approvals, purchase orders, invoices, reports and the activity log (Weeks 3 and 4)
- Database migrations: tables are created by SQLAlchemy, which does not alter existing tables