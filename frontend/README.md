# VendorBridge Frontend

React (Vite) frontend. Place this folder as `frontend/` in the repo.

```bash
npm install
cp .env.example .env     # Windows: copy .env.example .env
npm run dev              # http://localhost:5173
```

## Backend endpoints this UI expects
- POST /auth/register, POST /auth/login (returns access_token), GET /auth/me, POST /auth/forgot-password
- GET /vendors?search=&status=, POST /vendors, PUT /vendors/{id}, DELETE /vendors/{id}
- Vendor fields: name, category, gst_number, contact_name, email, phone, status (active|pending|inactive)
- The backend needs CORS enabled for http://localhost:5173

## Known limitations
- Token is kept in localStorage (readable by scripts if the site has an XSS bug).
- Role checks in the UI only hide buttons; real enforcement is in the backend.
