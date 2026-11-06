"""Invoice PDF, drawn with ReportLab from the stored invoice record."""
from io import BytesIO

import reportlab.lib  # type: ignore[reportMissingModuleSource]
from reportlab.lib.pagesizes import A4  # cspell:ignore pagesizes  # type: ignore[reportMissingModuleSource]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[reportMissingModuleSource]
from reportlab.lib.units import mm  # type: ignore[reportMissingModuleSource]
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore[reportMissingModuleSource]

ORANGE = reportlab.lib.colors.HexColor("#C8460C")
INK = reportlab.lib.colors.HexColor("#2B2520")
GRAY = reportlab.lib.colors.HexColor("#6B6258")
PAPER = reportlab.lib.colors.HexColor("#FBF6EE")
LINE = reportlab.lib.colors.HexColor("#E3D8C8")


def inr(value) -> str:
    """Indian digit grouping, for example 169500 becomes 1,69,500.00."""
    whole, _, frac = f"{float(value):.2f}".partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}{whole}.{frac}"


def _d(value) -> str:
    return value.strftime("%d %b %Y") if value else "-"


def invoice_pdf(inv: dict) -> bytes:
    ss = getSampleStyleSheet()
    body = ParagraphStyle(
        "b", parent=ss["Normal"], fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, textColor=GRAY)
    right = ParagraphStyle("r", parent=body, alignment=2)
    head = ParagraphStyle(
        "h", parent=ss["Title"], fontSize=22, textColor=INK, alignment=0, spaceAfter=2)
    label = ParagraphStyle(
        "l", parent=small, textTransform="uppercase", fontSize=7.5)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=inv["invoice_number"] or "Invoice", author=inv["buyer"]["name"])
    width = A4[0] - 36 * mm
    t = inv["totals"]
    story = [Paragraph("TAX INVOICE", head),
             Paragraph(
                 f"<b>{inv['invoice_number']}</b> &nbsp;&middot;&nbsp; PO {inv['po_number']} &nbsp;&middot;&nbsp; RFQ {inv['rfq_number'] or '-'}", small),
             Spacer(1, 8)]

    def party(title, p):
        lines = [f"<b>{p['name']}</b>"]
        if p.get("address"):
            lines.append(p["address"])
        if p.get("gstin"):
            lines.append(f"GSTIN: {p['gstin']}")
        if p.get("contact"):
            lines.append(f"Phone: {p['contact']}")
        if p.get("email"):
            lines.append(p["email"])
        return [Paragraph(title, label), Paragraph("<br/>".join(lines), body)]

    meta = [[Paragraph("Invoice date", label), Paragraph(_d(inv["invoice_date"]), body)],
            [Paragraph("Due date", label), Paragraph(
                _d(inv["due_date"]), body)],
            [Paragraph("Payment terms", label), Paragraph(
                inv["payment_terms"] or "-", body)],
            [Paragraph("Status", label), Paragraph(inv["status"].value.replace("_", " ").title(), body)]]
    top = Table([[party("Bill to", inv["buyer"]), party("Vendor", inv["vendor"]), Table(meta, colWidths=[28 * mm, 32 * mm])]],
                colWidths=[width * 0.36, width * 0.36, width * 0.28])
    top.setStyle(TableStyle(
        [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [top, Spacer(1, 12)]

    rows = [["Item", "Qty", "Unit price (INR)", "Total (INR)"]]
    for i in inv["items"]:
        rows.append([Paragraph(i["item_name"], body), f"{i['quantity']:g} {i['unit']}", inr(
            i["unit_price"]), inr(i["line_total"])])
    items = Table(rows, colWidths=[
                  width * 0.46, width * 0.16, width * 0.19, width * 0.19], repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE), ("TEXTCOLOR",
                                                  (0, 0), (-1, 0), reportlab.lib.colors.white),
        ("FONTNAME", (0, 0), (-1, 0),
         "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [reportlab.lib.colors.white, PAPER]), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [items, Spacer(1, 8)]

    tax_rows = [["Subtotal", inr(t["subtotal"])]]
    half = t["gst_percent"] / 2
    if t["igst"]:
        tax_rows.append([f"IGST ({t['gst_percent']:g}%)", inr(t["igst"])])
    else:
        tax_rows += [[f"CGST ({half:g}%)", inr(t["cgst"])],
                     [f"SGST ({half:g}%)", inr(t["sgst"])]]
    tax_rows.append(["Grand total (INR)", inr(t["grand_total"])])
    tot = Table(tax_rows, colWidths=[40 * mm, 34 * mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, -1), (-1, -1),
         "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [tot, Spacer(1, 18)]
    if inv["paid_at"]:
        story.append(Paragraph(f"Paid on {_d(inv['paid_at'])}.", body))
    story.append(Paragraph(
        "This is a computer generated invoice and does not need a signature.", small))
    doc.build(story)
    return buf.getvalue()
