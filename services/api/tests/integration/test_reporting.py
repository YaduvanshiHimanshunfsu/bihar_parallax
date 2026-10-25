from __future__ import annotations

import json

from pypdf import PdfReader

from app.core.config import Settings
from app.schemas.contracts import CaseCreate
from app.services.cases import CaseService
from app.services.reporting import ReportService
from app.reports.storage import ReportStore


def test_report_service_generates_hashed_json_html_and_pdf(settings: Settings, case_service: CaseService) -> None:
    case = case_service.create_case(CaseCreate(reference="CYB-RPT-01", title="Dossier generation"), actor="pytest")
    service = ReportService(case_service, ReportStore(settings.reports_dir))

    reports = service.generate(case.id, actor="pytest")

    assert {report.report_format for report in reports} == {"json", "html", "pdf"}
    assert all(len(report.sha256) == 64 for report in reports)
    json_report = next(report for report in reports if report.report_format == "json")
    storage_key, report_format = case_service.get_report_storage(json_report.id)
    assert report_format == "json"
    payload = json.loads((settings.reports_dir / storage_key).read_text(encoding="utf-8"))
    assert payload["case"]["reference"] == "CYB-RPT-01"
    assert "limitations" in payload
    pdf_report = next(report for report in reports if report.report_format == "pdf")
    pdf_storage_key, pdf_format = case_service.get_report_storage(pdf_report.id)
    assert pdf_format == "pdf"
    reader = PdfReader(settings.reports_dir / pdf_storage_key)
    assert reader.pages
    assert "CYB-RPT-01" in "".join(page.extract_text() or "" for page in reader.pages)
    assert len(case_service.get_case(case.id).reports) == 3
