from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.analyzers.bandit_runner import BanditRunner
from app.analyzers.heuristic_analyzer import HeuristicAnalyzer
from app.analyzers.pylint_runner import PylintRunner
from app.core.config import get_settings
from app.schemas import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
    AnalysisReport,
    AnalysisStatusResponse,
    ApplyFixRequest,
    ApplyFixResponse,
    BatchApplyFixRequest,
    BatchApplyFixResponse,
    CreatePullRequestRequest,
    CreatePullRequestResponse,
)
from app.services.ai_review_service import AIReviewService
from app.services.correlation_service import CorrelationService
from app.services.fix_service import FixService
from app.services.github_service import GitHubService
from app.services.ingestion_service import IngestionService
from app.services.mapping_service import MappingService
from app.services.report_service import ReportService
from app.services.run_store import RunStore
from app.services.severity_service import SeverityService
from app.services.structure_service import StructureService
from app.workers.analysis_worker import AnalysisWorker

router = APIRouter(prefix="/api")
settings = get_settings()
run_store = RunStore(settings.runs_dir)
fix_service = FixService(run_store)
github_service = GitHubService(settings, run_store, fix_service)
analysis_worker = AnalysisWorker(
    run_store=run_store,
    ingestion_service=IngestionService(),
    structure_service=StructureService(),
    mapping_service=MappingService(settings),
    severity_service=SeverityService(),
    ai_review_service=AIReviewService(settings),
    correlation_service=CorrelationService(),
    report_service=ReportService(),
    pylint_runner=PylintRunner(),
    bandit_runner=BanditRunner(),
    heuristic_analyzer=HeuristicAnalyzer(),
)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyses", response_model=AnalysisCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_analysis(payload: AnalysisCreateRequest, background_tasks: BackgroundTasks) -> AnalysisCreateResponse:
    try:
        IngestionService().validate_repo_url(payload.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    run_id = run_store.create_run(payload.repo_url)
    background_tasks.add_task(analysis_worker.run, run_id, payload.repo_url)
    return AnalysisCreateResponse(run_id=run_id, status="queued")


@router.get("/analyses/{run_id}", response_model=AnalysisStatusResponse)
def get_analysis_status(run_id: str) -> AnalysisStatusResponse:
    try:
        return run_store.get_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.") from exc


@router.get("/analyses/{run_id}/report", response_model=AnalysisReport)
def get_analysis_report(run_id: str) -> AnalysisReport:
    try:
        return run_store.get_report(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not available for this run.") from exc


@router.post("/apply-fix", response_model=ApplyFixResponse)
def apply_fix(payload: ApplyFixRequest) -> ApplyFixResponse:
    try:
        return fix_service.apply_fix(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/apply-fixes/batch", response_model=BatchApplyFixResponse)
def apply_fixes_batch(payload: BatchApplyFixRequest) -> BatchApplyFixResponse:
    try:
        return fix_service.apply_fixes(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/create-pr", response_model=CreatePullRequestResponse)
def create_pull_request(payload: CreatePullRequestRequest) -> CreatePullRequestResponse:
    try:
        return github_service.create_pull_request(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run or report not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
