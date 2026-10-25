from __future__ import annotations

import html
import io
import json
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.storage import ReportStore
from app.schemas.contracts import ReportSummary
from app.services.cases import CaseService


class ReportService:
    """Build an evidence-linked dossier; it never produces a legal authenticity verdict."""

    report_spec_version = "0.1.0"

    def __init__(self, case_service: CaseService, report_store: ReportStore) -> None:
        self.case_service = case_service
        self.report_store = report_store

    def _payload(self, case_id: str) -> dict[str, Any]:
        case = self.case_service.get_case(case_id)
        evidence = [self.case_service.get_evidence_detail(item.id).model_dump() for item in case.evidence]
        return {
            "report_type": "Parallax Evidence Integrity Dossier",
            "report_spec_version": self.report_spec_version,
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "case": {
                "id": case.id,
                "reference": case.reference,
                "title": case.title,
                "created_at": case.created_at,
                "updated_at": case.updated_at,
            },
            "assessment": case.assessment.model_dump() if case.assessment else None,
            "evidence": evidence,
            "custody_events": [event.model_dump() for event in case.audit_events],
            "limitations": [
                "This dossier contains automated forensic indicators and processing records, not a legal authenticity determination.",
                "A finding marked for review needs examination by an authorised forensic analyst alongside the original evidence and case context.",
                "Absence of a signal does not prove that evidence is authentic, complete, or unaltered.",
            ],
        }

    @staticmethod
    def _html_dossier(payload: dict[str, Any]) -> str:
        case = payload["case"]
        rows: list[str] = []
        for evidence in payload["evidence"]:
            finding_count = sum(len(analysis["findings"]) for analysis in evidence["analyses"])
            analyses = "".join(
                f"<li><strong>{html.escape(analysis['module'])}</strong> v{html.escape(analysis['module_version'])}: {len(analysis['findings'])} findings</li>"
                for analysis in evidence["analyses"]
            ) or "<li>No analysis runs recorded.</li>"
            rows.append(
                "<section class='evidence'><h2>" + html.escape(evidence["original_filename"]) + "</h2>"
                + "<dl>"
                + f"<dt>Evidence ID</dt><dd>{html.escape(evidence['id'])}</dd>"
                + f"<dt>SHA-256</dt><dd class='hash'>{html.escape(evidence['sha256'])}</dd>"
                + f"<dt>Type</dt><dd>{html.escape(evidence['media_type'])} · {html.escape(evidence['mime_type'])}</dd>"
                + f"<dt>Recorded findings</dt><dd>{finding_count}</dd>"
                + "</dl><h3>Recorded analyses</h3><ul>" + analyses + "</ul></section>"
            )
        limitations = "".join(f"<li>{html.escape(item)}</li>" for item in payload["limitations"])
        return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><title>Parallax Dossier — {html.escape(case['reference'])}</title>
<style>body{{font:15px system-ui,sans-serif;color:#182234;max-width:900px;margin:40px auto;padding:0 24px;line-height:1.55}}h1{{color:#0b4d66}}h2{{border-bottom:1px solid #ced9e1;padding-bottom:8px;margin-top:34px}}.eyebrow{{color:#46677f;text-transform:uppercase;letter-spacing:.1em;font-size:12px}}.evidence{{padding:4px 0 18px}}dl{{display:grid;grid-template-columns:170px 1fr;gap:5px 16px}}dt{{font-weight:700}}dd{{margin:0}}.hash{{font-family:ui-monospace,monospace;overflow-wrap:anywhere}}.notice{{background:#fff7dc;border-left:4px solid #d4a72c;padding:14px 16px}}@media print{{body{{margin:0;max-width:none}}}}</style></head>
<body><p class='eyebrow'>Evidence integrity dossier · version {html.escape(payload['report_spec_version'])}</p>
<h1>{html.escape(case['reference'])} — {html.escape(case['title'])}</h1>
<p>Generated {html.escape(payload['generated_at'])}</p><p class='notice'>Human forensic review required. This dossier is an investigation aid, not a legal authenticity verdict.</p>
<h2>Evidence record</h2>{''.join(rows) or '<p>No evidence is recorded for this case.</p>'}
<h2>Limitations and reviewer notice</h2><ul>{limitations}</ul></body></html>"""

    @staticmethod
    def _pdf_text(value: Any) -> str:
        """Use ASCII-safe report text so rendering is predictable across platforms."""
        return str(value).encode("ascii", "replace").decode("ascii")

    @classmethod
    def _pdf_dossier(cls, payload: dict[str, Any]) -> bytes:
        """Create a readable, fixed-format dossier with no authenticity verdict."""
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=17 * mm,
            title=f"Parallax Dossier - {cls._pdf_text(payload['case']['reference'])}",
            author="Parallax Evidence Integrity Workbench",
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "ParallaxTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19,
            leading=24, textColor=colors.HexColor("#0B4D66"), spaceAfter=5,
        )
        eyebrow = ParagraphStyle(
            "ParallaxEyebrow", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=colors.HexColor("#46677F"), spaceAfter=6,
        )
        section = ParagraphStyle(
            "ParallaxSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12,
            leading=15, textColor=colors.HexColor("#12344D"), spaceBefore=13, spaceAfter=7,
        )
        body = ParagraphStyle(
            "ParallaxBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.7,
            leading=12, textColor=colors.HexColor("#1E2A35"), spaceAfter=5,
        )
        small = ParagraphStyle(
            "ParallaxSmall", parent=body, fontSize=7.4, leading=9.5, textColor=colors.HexColor("#465968"),
        )
        table_label = ParagraphStyle(
            "ParallaxTableLabel", parent=small, fontName="Helvetica-Bold", textColor=colors.HexColor("#173B54"),
        )
        right = ParagraphStyle("ParallaxRight", parent=small, alignment=TA_RIGHT)
        case = payload["case"]
        story: list[Any] = [
            Paragraph("EVIDENCE INTEGRITY DOSSIER", eyebrow),
            Paragraph(
                f"{xml_escape(cls._pdf_text(case['reference']))} - {xml_escape(cls._pdf_text(case['title']))}",
                title,
            ),
            Paragraph(f"Generated: {xml_escape(cls._pdf_text(payload['generated_at']))}", small),
        ]
        notice = Table(
            [[Paragraph(
                "<b>Human forensic review required.</b> This dossier is an investigation aid. It records automated forensic indicators and does not determine legal authenticity, manipulation, or admissibility.",
                body,
            )]],
            colWidths=[178 * mm],
        )
        notice.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7DC")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#D4A72C")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E8D9AA")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.extend([Spacer(1, 5 * mm), notice, Paragraph("Case assessment", section)])
        assessment = payload["assessment"]
        if assessment:
            story.append(Paragraph(
                f"Recommendation: <b>{xml_escape(cls._pdf_text(assessment['outcome'].replace('_', ' ')))}.</b> "
                + " ".join(xml_escape(cls._pdf_text(reason)) for reason in assessment["reasons"]),
                body,
            ))
        else:
            story.append(Paragraph("No automated case recommendation was recorded when this dossier was generated.", body))

        story.append(Paragraph("Evidence record", section))
        if not payload["evidence"]:
            story.append(Paragraph("No evidence items are recorded for this case.", body))
        for evidence in payload["evidence"]:
            analyses = evidence["analyses"]
            findings = [finding for analysis in analyses for finding in analysis["findings"]]
            data = [
                [Paragraph("File", table_label), Paragraph(xml_escape(cls._pdf_text(evidence["original_filename"])), body)],
                [Paragraph("Evidence ID", table_label), Paragraph(xml_escape(cls._pdf_text(evidence["id"])), small)],
                [Paragraph("SHA-256", table_label), Paragraph(xml_escape(cls._pdf_text(evidence["sha256"])), small)],
                [Paragraph("Type", table_label), Paragraph(xml_escape(cls._pdf_text(f"{evidence['media_type']} - {evidence['mime_type']}")), body)],
                [Paragraph("Recorded analysis", table_label), Paragraph(xml_escape(cls._pdf_text(f"{len(analyses)} run(s), {len(findings)} finding(s)")), body)],
            ]
            record = Table(data, colWidths=[35 * mm, 143 * mm], hAlign="LEFT")
            record.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF5F8")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CBD5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E2E7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            finding_lines = [
                Paragraph(
                    f"<b>{xml_escape(cls._pdf_text(finding['title']))}</b> - {xml_escape(cls._pdf_text(finding['detail']))}",
                    small,
                )
                for finding in findings
            ] or [Paragraph("No stored findings for this evidence item.", small)]
            story.extend([KeepTogether([record, Spacer(1, 3 * mm)]), *finding_lines, Spacer(1, 5 * mm)])

        story.append(Paragraph("Custody record", section))
        custody_events = payload["custody_events"]
        custody_table = [[Paragraph("Time", table_label), Paragraph("Event", table_label), Paragraph("Actor", table_label)]]
        for event in custody_events[:80]:
            custody_table.append([
                Paragraph(xml_escape(cls._pdf_text(event["created_at"])), small),
                Paragraph(xml_escape(cls._pdf_text(event["event_type"])), small),
                Paragraph(xml_escape(cls._pdf_text(event["actor"])), small),
            ])
        if len(custody_table) == 1:
            custody_table.append([Paragraph("No events", small), Paragraph("-", small), Paragraph("-", small)])
        custody = Table(custody_table, colWidths=[57 * mm, 83 * mm, 38 * mm], repeatRows=1)
        custody.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B54")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CBD5")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E2E7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([custody, Paragraph("Limitations and reviewer notice", section)])
        for limitation in payload["limitations"]:
            story.append(Paragraph(f"- {xml_escape(cls._pdf_text(limitation))}", body))

        def page_footer(canvas, document) -> None:
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#B9CBD5"))
            canvas.line(document.leftMargin, 12 * mm, A4[0] - document.rightMargin, 12 * mm)
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#46677F"))
            canvas.drawString(document.leftMargin, 7.5 * mm, "Parallax Evidence Integrity Workbench - human review required")
            canvas.drawRightString(A4[0] - document.rightMargin, 7.5 * mm, f"Page {document.page}")
            canvas.restoreState()

        document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
        return output.getvalue()

    def generate(
        self, case_id: str, actor: str, formats: tuple[str, ...] = ("json", "html", "pdf")
    ) -> list[ReportSummary]:
        payload = self._payload(case_id)
        generated = {
            "json": json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
            "html": self._html_dossier(payload).encode("utf-8"),
            "pdf": self._pdf_dossier(payload),
        }
        unsupported = set(formats) - set(generated)
        if unsupported:
            raise ValueError(f"Unsupported report formats: {', '.join(sorted(unsupported))}.")
        stored = [self.report_store.persist(case_id, report_format, generated[report_format]) for report_format in formats]
        return self.case_service.record_reports(case_id, stored, actor)
