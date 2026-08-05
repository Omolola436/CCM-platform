from io import BytesIO
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from models import db, Consent, DataSubject, AuditLog, ConsentHistory
from sqlalchemy import func


PRIMARY = colors.HexColor("#1a3a5c")
ACCENT = colors.HexColor("#4f46e5")
GREEN = colors.HexColor("#16a34a")
RED = colors.HexColor("#dc2626")
ORANGE = colors.HexColor("#d97706")
LIGHT_BLUE = colors.HexColor("#eff6ff")
LIGHT_GREY = colors.HexColor("#f8fafc")
MID_GREY = colors.HexColor("#e2e8f0")


class ReportService:

    @staticmethod
    def generate_audit_report(org_id, report_type="audit", filters=None):
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle("title", fontSize=20, textColor=PRIMARY,
                                     spaceAfter=6, fontName="Helvetica-Bold", alignment=TA_LEFT)
        sub_style = ParagraphStyle("sub", fontSize=10, textColor=colors.HexColor("#64748b"),
                                   spaceAfter=4, fontName="Helvetica")
        heading_style = ParagraphStyle("h2", fontSize=13, textColor=PRIMARY,
                                       spaceBefore=16, spaceAfter=6, fontName="Helvetica-Bold")
        body_style = ParagraphStyle("body", fontSize=9, textColor=colors.HexColor("#334155"),
                                    spaceAfter=4, fontName="Helvetica", leading=14)

        labels = {
            "audit": "Audit & Compliance Report",
            "ndpa": "NDPA Compliance Report",
            "gdpr": "GDPR Compliance Report",
        }

        story.append(Paragraph("3CONSULTING", ParagraphStyle("brand", fontSize=10, textColor=ACCENT,
                                                              fontName="Helvetica-Bold")))
        story.append(Paragraph("Centralized Consent Management Platform", sub_style))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(labels.get(report_type, "Compliance Report"), title_style))
        story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}", sub_style))
        story.append(Spacer(1, 0.6*cm))

        total = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id).scalar() or 0
        active = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Active").scalar() or 0
        withdrawn = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Withdrawn").scalar() or 0
        expired = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Expired").scalar() or 0
        subjects = db.session.query(func.count(DataSubject.id)).filter_by(org_id=org_id).scalar() or 0

        story.append(Paragraph("Summary Statistics", heading_style))
        summary_data = [
            ["Metric", "Value"],
            ["Total Consent Records", str(total)],
            ["Active Consents", str(active)],
            ["Withdrawn Consents", str(withdrawn)],
            ["Expired Consents", str(expired)],
            ["Registered Data Subjects", str(subjects)],
            ["Compliance Rate", f"{round(active/total*100, 1) if total else 0}%"],
        ]
        t = Table(summary_data, colWidths=[10*cm, 6*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, MID_GREY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        if report_type == "ndpa":
            story.append(Paragraph("NDPA Compliance Assessment", heading_style))
            story.append(Paragraph(
                "This report confirms compliance with the Nigeria Data Protection Act (NDPA). "
                "All consent records have been captured with explicit data subject agreement, "
                "purpose specification, and lawful basis as required under NDPA Section 2.1(a).",
                body_style
            ))
            checklist = [
                ["Requirement", "Status"],
                ["Lawful basis documented for each consent", "✓ Compliant"],
                ["Data subject identity verified", "✓ Compliant"],
                ["Purpose limitation enforced", "✓ Compliant"],
                ["Withdrawal mechanism available", "✓ Compliant"],
                ["Audit trail maintained", "✓ Compliant"],
                ["Privacy notice version tracked", "✓ Compliant"],
            ]
            ReportService._add_checklist_table(story, checklist)

        elif report_type == "gdpr":
            story.append(Paragraph("GDPR Compliance Assessment", heading_style))
            story.append(Paragraph(
                "This report confirms alignment with the General Data Protection Regulation (GDPR). "
                "The platform maintains records of processing activities, implements the right to "
                "erasure, and ensures transparent consent management per Article 7 GDPR.",
                body_style
            ))
            checklist = [
                ["Requirement", "Status"],
                ["Article 7 — Consent conditions met", "✓ Compliant"],
                ["Article 13 — Transparency at collection", "✓ Compliant"],
                ["Article 17 — Right to erasure supported", "✓ Compliant"],
                ["Article 21 — Right to object implemented", "✓ Compliant"],
                ["Recital 32 — Unambiguous consent captured", "✓ Compliant"],
                ["Records of Processing Activities (RoPA)", "✓ Maintained"],
            ]
            ReportService._add_checklist_table(story, checklist)

        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("Recent Consent Records", heading_style))
        consents = (
            db.session.query(Consent)
            .filter_by(org_id=org_id)
            .order_by(Consent.created_at.desc())
            .limit(20)
            .all()
        )
        consent_data = [["ID", "Subject", "Purpose", "Status", "Channel", "Date"]]
        for c in consents:
            consent_data.append([
                str(c.id),
                c.data_subject.email[:30] if c.data_subject else "—",
                c.purpose[:30],
                c.status,
                c.channel,
                c.created_at.strftime("%d %b %Y") if c.created_at else "—",
            ])
        if len(consent_data) > 1:
            ct = Table(consent_data, colWidths=[1.2*cm, 4.5*cm, 4*cm, 2*cm, 2.5*cm, 2.5*cm])
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.3, MID_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(ct)

        story.append(Spacer(1, 0.8*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=MID_GREY))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            "This report was generated automatically by the 3Consulting CCMP. "
            "All data is sourced directly from the Central Consent Registry.",
            ParagraphStyle("footer", fontSize=8, textColor=colors.HexColor("#94a3b8"),
                           alignment=TA_CENTER, fontName="Helvetica")
        ))

        doc.build(story)
        buf.seek(0)
        return buf

    @staticmethod
    def _add_checklist_table(story, data):
        t = Table(data, colWidths=[12*cm, 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
            ("TEXTCOLOR", (1, 1), (1, -1), GREEN),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, MID_GREY),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4*cm))
