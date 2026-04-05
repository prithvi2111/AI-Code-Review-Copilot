from __future__ import annotations

from pathlib import Path

from app.analyzers.bandit_runner import BanditRunner
from app.analyzers.heuristic_analyzer import HeuristicAnalyzer
from app.analyzers.pylint_runner import PylintRunner
from app.core.config import get_settings
from app.schemas import Finding
from app.services.ai_review_service import AIReviewService
from app.services.correlation_service import CorrelationService
from app.services.ingestion_service import IngestionService
from app.services.mapping_service import MappingService
from app.services.report_service import ReportService
from app.services.run_store import RunStore
from app.services.severity_service import SeverityService
from app.services.structure_service import StructureService
from app.workers.analysis_worker import AnalysisWorker


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


class FixtureIngestionService(IngestionService):
    def ingest(self, repo_url: str, destination_dir: Path):
        return self.snapshot_from_local_path(
            FIXTURE_ROOT,
            repo_url=repo_url,
            repo_name="example/sample-repo",
            default_branch="main",
        )


class StubPylintRunner(PylintRunner):
    def run(self, snapshot):
        return [
            Finding(
                category="bug",
                title="bare-except",
                description="No exception type(s) specified",
                file_path="package/service.py",
                start_line=18,
                end_line=18,
                tool_source="pylint",
                rule_id="W0702",
                raw_severity="warning",
            )
        ]


class StubBanditRunner(BanditRunner):
    def run(self, snapshot):
        return [
            Finding(
                category="security",
                title="hardcoded_password_string",
                description="Possible hardcoded secret",
                file_path="package/service.py",
                start_line=4,
                end_line=4,
                tool_source="bandit",
                rule_id="hardcoded-secret",
                raw_severity="high",
            )
        ]


class NoOpAIReviewService:
    def enrich(self, findings):
        return findings


class EmptyBanditRunner(BanditRunner):
    def run(self, snapshot):
        return []


class EmptyHeuristicAnalyzer(HeuristicAnalyzer):
    def run(self, snapshot):
        return []


class MassPylintRunner(PylintRunner):
    def run(self, snapshot):
        return [
            Finding(
                category="bug",
                title=f"unused-variable-{index}",
                description="Unused variable 'value'",
                file_path="package/service.py",
                start_line=index + 1,
                end_line=index + 1,
                tool_source="pylint",
                rule_id="W0612",
                raw_severity="warning",
            )
            for index in range(1001)
        ]


def test_analysis_worker_creates_report(tmp_path):
    settings = get_settings()
    run_store = RunStore(tmp_path / "runs")
    worker = AnalysisWorker(
        run_store=run_store,
        ingestion_service=FixtureIngestionService(),
        structure_service=StructureService(),
        mapping_service=MappingService(settings),
        severity_service=SeverityService(),
        ai_review_service=AIReviewService(settings),
        correlation_service=CorrelationService(),
        report_service=ReportService(),
        pylint_runner=StubPylintRunner(),
        bandit_runner=StubBanditRunner(),
        heuristic_analyzer=HeuristicAnalyzer(),
    )

    run_id = run_store.create_run("https://github.com/example/sample-repo")
    worker.run(run_id, "https://github.com/example/sample-repo")

    status = run_store.get_status(run_id)
    report = run_store.get_report(run_id)

    assert status.status == "completed"
    assert report.summary.total_issues >= 2
    assert any(item.severity == "Critical" for item in report.findings)
    assert any(item.symbol_name == "risky_fetch" for item in report.findings)
    assert any(item.fix_patch for item in report.findings)


def test_analysis_worker_preserves_all_findings(tmp_path):
    settings = get_settings()
    run_store = RunStore(tmp_path / "runs")
    worker = AnalysisWorker(
        run_store=run_store,
        ingestion_service=FixtureIngestionService(),
        structure_service=StructureService(),
        mapping_service=MappingService(settings),
        severity_service=SeverityService(),
        ai_review_service=NoOpAIReviewService(),
        correlation_service=CorrelationService(),
        report_service=ReportService(),
        pylint_runner=MassPylintRunner(),
        bandit_runner=EmptyBanditRunner(),
        heuristic_analyzer=EmptyHeuristicAnalyzer(),
    )

    run_id = run_store.create_run("https://github.com/example/sample-repo")
    worker.run(run_id, "https://github.com/example/sample-repo")

    report = run_store.get_report(run_id)

    assert report.summary.total_issues == 1001
    assert len(report.findings) == 1001
