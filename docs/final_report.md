# VendorBridge final completion report

**Student:** TO FILL  **Programme:** Kagnus full stack internship, Project 1  **Date:** TO FILL
**Deployed application:** TO FILL  **Repository:** TO FILL  **Demo video / screenshots:** TO FILL

## 1. What was built
| Week | Delivered |
|---|---|
| 1 | Registration and login with roles, dashboard, vendor management (add, edit, delete, search, filter) |
| 2 | RFQ creation with items, attachments and vendor assignment; vendor portal for quotations with deadline rules; quotation comparison with lowest-price highlight, sorting, filters and ratings; selection of one quotation |
| 3 | Two-level approval with remarks and timeline; purchase order and invoice generation with tax calculation; invoice PDF, print and email; role-restricted document access |
| 4 | Notifications from real events; write-once audit log and activity timeline; reports and analytics with charts and CSV export; automated test suite; deployment and documentation |

The complete lifecycle works end to end: vendor, RFQ, quotations, comparison, selection, approval L1 and L2, purchase order, invoice, PDF, email, payment, with notifications, audit entries and report figures created from those real actions.

## 2. Key design decisions
- All business rules and every money figure are enforced on the server from database records; the browser only displays.
- Purchase orders and invoices keep their own copy of prices and party details, so issued documents never change when a vendor record is edited.
- Duplicate documents are prevented twice: in the code, and by unique database columns (one PO per approval, one invoice per PO, one live approval per RFQ, one selected quotation per RFQ).
- The audit log is write-once in the application and, on PostgreSQL, refused by database triggers.
- Reports are computed from stored rows with definitions shown on screen; nothing is hard-coded.

## 3. Testing
- Automated: **TO FILL: your own pytest result** (last verified run: 104 passed, 1 skipped on SQLite; 105 passed on PostgreSQL 16). Coverage by requirement is listed in `docs/TESTING.md`.
- Manual: the 13-step checklist in `docs/TESTING.md`, run on the deployed application on **TO FILL: date**. Results and evidence: **TO FILL**.
- Invoice email delivery tested with a real mail account: **TO FILL: yes or no, and which provider**. The automated tests use a stand-in mail server only.

## 4. Verification summary (fill in after your own run)
| Check | Result |
|---|---|
| Sign in succeeds and fails correctly | TO FILL |
| Role permissions and record ownership | TO FILL |
| RFQ and quotation validation, deadline lock | TO FILL |
| Approval restrictions, duplicate PO and invoice refused | TO FILL |
| Invoice totals checked by hand | TO FILL |
| PDF opens, print preview clean, email received | TO FILL |
| Notifications and audit entries match the actions | TO FILL |
| Reports match the saved data, CSV opens | TO FILL |
| Data persists after refresh and new session | TO FILL |
| Layout at phone width | TO FILL |
| No secrets in repository or browser | TO FILL |

## 5. Known limitations and incomplete items
- Profile photo upload and forgot-password email are not implemented.
- RFQs cannot be edited after saving; approval has two fixed levels.
- Roles can be chosen at registration (one admin only); production use should restrict this to admins.
- Attachments are stored on the server disk and may be lost on redeploy on free hosting.
- The login token is stored in `localStorage` and cannot be revoked before it expires (60 minutes).
- Purchase orders have no PDF; there are no credit notes, cancellations or partial payments.
- Notifications refresh every 30 seconds instead of live push.
- The React screens have no automated tests.
- **TO FILL: anything that did not work in your deployment.**