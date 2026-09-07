"""
PDF Report Generator
SIH26188 - AI-Based Fake Identity & Document Screening System

Generates a downloadable, official-looking PDF summary of a single
screening result - the kind of artifact a real checkpoint would file for
records/audit purposes. This directly supports the problem statement's
stated goal of creating a "digital trail for investigations and
intelligence analysis."

Usage:
    from report_generator import build_pdf_report

    pdf_bytes = build_pdf_report(final_report, filename="passport.jpg", report_id="abc123")
    with open("report.pdf", "wb") as f:
        f.write(pdf_bytes)
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

NAVY = colors.HexColor("#0B3D5C")
SAFFRON = colors.HexColor("#FF9933")
GREEN = colors.HexColor("#138808")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")
GREY_TEXT = colors.HexColor("#444444")

VERDICT_COLORS = {
    "Likely Genuine": GREEN,
    "Needs Manual Review": AMBER,
    "Likely Fake": RED,
}


def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="OrgHeader", fontSize=9, textColor=GREY_TEXT,
        alignment=TA_CENTER, leading=12,
    ))
    styles.add(ParagraphStyle(
        name="DocTitle", fontSize=16, textColor=NAVY,
        alignment=TA_CENTER, spaceAfter=6, spaceBefore=2,
        leading=20, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", fontSize=11, textColor=NAVY,
        spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BodyTextSmall", fontSize=9.5, textColor=colors.black, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="FlagDesc", fontSize=8.5, textColor=GREY_TEXT, leading=11,
    ))
    return styles


def build_pdf_report(report: dict, filename: str, report_id: str) -> bytes:
    """
    Builds a PDF summary of a screening report and returns it as raw bytes,
    ready to send back over HTTP or write to disk.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = _get_styles()
    elements = []

    # --- Header ---
    elements.append(Paragraph("GOVERNMENT OF INDIA", styles["OrgHeader"]))
    elements.append(Paragraph("Ministry of Home Affairs &nbsp;|&nbsp; Sashastra Seema Bal (SSB), Police II Division", styles["OrgHeader"]))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.4, color=SAFFRON))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Document Screening Report", styles["DocTitle"]))
    elements.append(Paragraph("AI-Based Fake Identity &amp; Document Screening System &middot; Ref: SIH26188", styles["OrgHeader"]))
    elements.append(Spacer(1, 14))

    # --- Meta info table ---
    generated_at = datetime.now().strftime("%d %B %Y, %I:%M %p")
    meta_data = [
        ["Report ID", report_id],
        ["Document File", filename],
        ["Generated On", generated_at],
    ]
    meta_table = Table(meta_data, colWidths=[45 * mm, 120 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY_TEXT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    # --- Verdict banner ---
    verdict = report.get("verdict", "Unknown")
    verdict_color = VERDICT_COLORS.get(verdict, GREY_TEXT)
    trust_score = report.get("final_trust_score", "N/A")
    risk_score = report.get("final_risk_score", "N/A")

    verdict_table = Table(
        [[f"VERDICT: {verdict}", f"Trust Score: {trust_score}%", f"Risk Score: {risk_score}%"]],
        colWidths=[75 * mm, 45 * mm, 45 * mm],
    )
    verdict_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), verdict_color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 16))

    # --- Extracted fields ---
    ocr_module = report.get("modules", {}).get("module_1_ocr_extraction", {})
    extracted_fields = ocr_module.get("extracted_fields") or {}
    elements.append(Paragraph("Extracted Document Fields", styles["SectionHeading"]))
    if extracted_fields:
        field_rows = [[k.replace("_", " ").title(), str(v)] for k, v in extracted_fields.items()]
        field_table = Table(field_rows, colWidths=[55 * mm, 110 * mm])
        field_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(field_table)
    else:
        elements.append(Paragraph("No fields could be confidently extracted from this document.", styles["BodyTextSmall"]))

    # --- Findings / flags ---
    elements.append(Paragraph("Findings", styles["SectionHeading"]))
    all_flags = report.get("all_flags", [])
    if not all_flags:
        elements.append(Paragraph("No issues were flagged by any screening module.", styles["BodyTextSmall"]))
    else:
        for flag in all_flags:
            sev = (flag.get("severity") or "low").upper()
            sev_color = {"HIGH": RED, "MEDIUM": AMBER, "LOW": GREY_TEXT}.get(sev, GREY_TEXT)
            code = flag.get("code", "FLAG")
            source = flag.get("source_module", "unknown")
            desc = flag.get("description", "")

            row_table = Table(
                [[Paragraph(f"<b>{code}</b> &nbsp;<font color='{sev_color.hexval()}'>[{sev}]</font> "
                            f"&nbsp;<font color='#888888'>({source})</font>", styles["BodyTextSmall"])]],
                colWidths=[165 * mm],
            )
            row_table.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBEFORE", (0, 0), (0, 0), 2.5, sev_color),
            ]))
            elements.append(row_table)
            elements.append(Paragraph(desc, styles["FlagDesc"]))
            elements.append(Spacer(1, 4))

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CCCCCC")))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "This report is generated by an AI-assisted screening prototype. Findings should be "
        "verified by an authorized officer before any action is taken. This is not an "
        "automated approval or rejection decision.",
        styles["OrgHeader"],
    ))

    doc.build(elements)
    return buffer.getvalue()
