from __future__ import annotations

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.evidence.storage import EvidenceStorageError
from app.evidence.validation import EvidenceValidationError
from app.schemas.contracts import AnalysisSummary, AssessmentSummary, AuditChainVerification, CaseCreate, CaseDetail, CaseSummary, EvidenceDetail, EvidenceSummary, IntegrityVerification, ReportSummary
from app.services.cases import CaseNotFoundError, CaseService, DuplicateCaseError

router = APIRouter(prefix="/cases", tags=["cases"])


def case_service(request: Request) -> CaseService:
    return request.app.state.case_service


@router.post("", response_model=CaseSummary, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> CaseSummary:
    try:
        return case_service(request).create_case(payload, actor=actor)
    except DuplicateCaseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[CaseSummary])
def list_cases(request: Request) -> list[CaseSummary]:
    return case_service(request).list_cases()


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, request: Request) -> CaseDetail:
    try:
        return case_service(request).get_case(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.") from exc


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(evidence_id: str, request: Request) -> EvidenceDetail:
    try:
        return case_service(request).get_evidence_detail(evidence_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.") from exc


@router.post("/{case_id}/evidence", response_model=EvidenceSummary, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> EvidenceSummary:
    try:
        # Check before writing bytes so unknown cases cannot leave orphaned originals.
        case_service(request).get_case_summary(case_id)
        stored = request.app.state.evidence_store.persist(file)
        return case_service(request).add_evidence(case_id, stored, actor=actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.") from exc
    except EvidenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except EvidenceStorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Evidence storage failed safely.") from exc


@router.post("/evidence/{evidence_id}/analysis/image", response_model=AnalysisSummary, status_code=status.HTTP_201_CREATED)
def analyse_image(
    evidence_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> AnalysisSummary:
    try:
        evidence = case_service(request).get_evidence_detail(evidence_id)
        if evidence.media_type != "image":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Image analysis requires image evidence.")
        return request.app.state.image_analysis_service.analyse(evidence_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/evidence/{evidence_id}/analysis/video", response_model=AnalysisSummary, status_code=status.HTTP_201_CREATED)
def analyse_video(
    evidence_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> AnalysisSummary:
    try:
        evidence = case_service(request).get_evidence_detail(evidence_id)
        if evidence.media_type != "video":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Video analysis requires video evidence.")
        return request.app.state.video_analysis_service.analyse(evidence_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/evidence/{evidence_id}/analysis/audio", response_model=AnalysisSummary, status_code=status.HTTP_201_CREATED)
def analyse_audio(
    evidence_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> AnalysisSummary:
    try:
        evidence = case_service(request).get_evidence_detail(evidence_id)
        if evidence.media_type != "audio":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Audio analysis requires audio evidence.")
        return request.app.state.audio_analysis_service.analyse(evidence_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/evidence/{evidence_id}/verify-integrity", response_model=IntegrityVerification)
def verify_integrity(
    evidence_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> IntegrityVerification:
    try:
        return request.app.state.integrity_verification_service.verify(evidence_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.") from exc
    except EvidenceStorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original evidence is unavailable for verification.") from exc


@router.get("/{case_id}/verify-audit-chain", response_model=AuditChainVerification)
def verify_audit_chain(case_id: str, request: Request) -> AuditChainVerification:
    try:
        return case_service(request).verify_audit_chain(case_id)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.") from exc


@router.post("/{case_id}/assessment", response_model=AssessmentSummary, status_code=status.HTTP_201_CREATED)
def assess_case(
    case_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> AssessmentSummary:
    try:
        return request.app.state.assessment_service.assess(case_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.") from exc


@router.post("/{case_id}/reports", response_model=list[ReportSummary], status_code=status.HTTP_201_CREATED)
def create_report(
    case_id: str,
    request: Request,
    actor: str = Header(default="demo-analyst", alias="X-Analyst-ID"),
) -> list[ReportSummary]:
    try:
        return request.app.state.report_service.generate(case_id, actor)
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.") from exc


@router.get("/reports/{report_id}", response_class=FileResponse)
def download_report(report_id: str, request: Request) -> FileResponse:
    try:
        storage_key, report_format = case_service(request).get_report_storage(report_id)
        path = (request.app.state.report_store.reports_dir / storage_key).resolve()
        path.relative_to(request.app.state.report_store.reports_dir)
        if not path.is_file():
            raise FileNotFoundError
        media_type = {"json": "application/json", "html": "text/html", "pdf": "application/pdf"}[report_format]
        return FileResponse(path, filename=path.name, media_type=media_type)
    except (CaseNotFoundError, FileNotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated report not found.") from exc


@router.get("/evidence/{evidence_id}/original", response_class=FileResponse)
def download_original(evidence_id: str, request: Request) -> FileResponse:
    try:
        storage_key, filename = case_service(request).get_evidence_storage_key(evidence_id)
        path = request.app.state.evidence_store.original_path(storage_key)
        return FileResponse(path, filename=filename, media_type="application/octet-stream")
    except (CaseNotFoundError, EvidenceStorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original evidence not found.") from exc


@router.get("/artifacts/{artifact_id}", response_class=FileResponse)
def download_artifact(artifact_id: str, request: Request) -> FileResponse:
    try:
        storage_key = case_service(request).get_artifact_storage_key(artifact_id)
        path = (request.app.state.artifact_store.derived_dir / storage_key).resolve()
        path.relative_to(request.app.state.artifact_store.derived_dir)
        if not path.is_file():
            raise FileNotFoundError
        return FileResponse(path, filename=path.name, media_type="image/png")
    except (CaseNotFoundError, FileNotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Derived artifact not found.")
