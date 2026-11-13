# Testing

## Automated tests (backend)
```bash
cd backend
pytest
```
The suite builds its own database, wipes it between tests, and refuses to run against a hosted database. By default it uses a SQLite file; `TEST_DATABASE_URL=postgresql+psycopg2://user@localhost/testdb pytest` runs the same tests on a local PostgreSQL, which also checks the database-level audit protection (that test is skipped on SQLite).

Result of the last run: **104 passed, 1 skipped on SQLite; 105 passed on PostgreSQL 16**. Run it yourself before submitting and copy your own result into the final report.

| Requirement | Where it is tested |
|---|---|
| Authentication, successful and failing | `test_auth.py`: registration rules, duplicate email, weak passwords, wrong password and unknown user give the same answer, inactive accounts, invalid and missing tokens, single admin |
| Role permissions and record access | `test_permissions.py`: every module needs login, vendors are kept out of staff areas, managers cannot create RFQs, vendors cannot read each other's RFQs, purchase orders, invoices or PDFs |
| RFQ and quotation validation, deadlines | `test_rfq_quotation.py`: invalid RFQs, blocked vendors, price rules, missing items, other RFQ's items, deadline day, closed RFQs, edits before the deadline, selection rules, attachments |
| Approval restrictions | `test_approvals.py`: who can submit and decide, two different approvers, no self-approval, remarks required to reject, locks, rejection and resubmission, timeline |
| Duplicate prevention and invoice calculations | `test_documents.py`: one PO per approval, one invoice per PO, CGST + SGST and IGST, exact decimals, odd-paisa split, due dates, browser-supplied totals ignored |
| PDF, email, payment | `test_documents.py`: PDF content, email not configured, success and failure recorded (with a stand-in mail server), no secrets in errors, mark as paid |
| Notifications from real events | `test_notifications_audit.py`: who is told what at each step, nobody is told about their own action, unread count, read, read all, privacy |
| Audit trail | `test_notifications_audit.py`: entries with actor, record and time, newest first, filters, visibility by role, no API to edit or delete, refused by the application layer and by PostgreSQL triggers |
| Reports | `test_reports.py`: empty data, figures equal the saved records, monthly trend, categories, vendor performance, date ranges and validation, role access, four CSV exports, spreadsheet-formula safety |
| Whole lifecycle | `test_lifecycle.py`: RFQ to paid invoice in one walk, then checks notifications, audit order and reports |

Not covered by automated tests: the React screens, real email delivery, and the deployed environment. Use the checklist below for those.

## Manual end-to-end checklist (use this for the demo video)
Accounts: one officer, two managers (or manager + admin), three vendor users whose emails match three vendor records. `scripts/seed_demo.py` creates all of this.

1. **Vendors.** Officer adds a vendor with a login email; the Vendors list and dashboard counts update. A wrong GST number shows the message `gst_number: ...`.
2. **RFQ.** Officer creates an RFQ with two items, an attachment and three vendors, and sends it. The list shows its number, status and deadline. Each vendor sees a notification and finds the RFQ under My RFQ's; an unassigned vendor does not.
3. **Quotations.** Each vendor opens the RFQ, downloads the attachment, saves a draft, then submits. One vendor edits and resubmits. The officer receives "Quotation received" notifications.
4. **Compare.** Officer opens "Compare quotations": lowest price and fastest delivery are tagged, ratings show, sorting and the delivery filter work. Select a quotation, then "Submit selected quotation for approval".
5. **Approval.** A manager approves L1 with remarks; the same manager cannot do L2. A second manager approves L2. The timeline shows both people, remarks and times. Repeat on another RFQ with a rejection to show the reject path.
6. **Documents.** Officer creates the purchase order, then the invoice. Check subtotal, tax lines and grand total by hand. The vendor sees both under Purchase orders and Invoices.
7. **Invoice actions.** Download the PDF and open it; click Print and check the preview hides the menus; send the email and show the success message (and, with a wrong SMTP password, the failure message); mark as paid.
8. **Notifications.** Show the bell with an unread count, open one (it becomes read and goes to the record), "Mark all read", and the full page.
9. **Activity.** As manager or admin, open Activity: the timeline lists every step above with person and time, and the type filter works. Sign in as a vendor: no Activity link, and `/activity` redirects away.
10. **Reports.** Open Reports: the totals match the documents you created, the monthly chart shows this month, vendor performance shows the winning vendor, and "Purchase orders" CSV downloads and opens in a spreadsheet. Choose a range with no data to show the empty state.
11. **Access.** Sign in as a vendor and try `/vendors`, `/approvals`, `/reports` in the address bar (redirected), and another vendor's invoice address (not found).
12. **Responsive.** Narrow the browser to about 400 px: the sidebar becomes a scrolling row, tables scroll sideways, forms stack, and nothing is cut off.
13. **Persistence.** Refresh and sign out and in again: all records, notifications and logs are still there.

## Security checks before submission
- `python scripts/check_secrets.py` passes, and `git ls-files | grep -i "\.env"` shows only `.env.example` files.
- The deployed frontend source and network calls contain no passwords, keys or database address.