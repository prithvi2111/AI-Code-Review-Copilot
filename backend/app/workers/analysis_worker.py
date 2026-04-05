from __future__ import annotations

from app.analyzers.bandit_runner import BanditRunner
from app.analyzers.heuristic_analyzer import HeuristicAnalyzer
from app.analyzers.pylint_runner import PylintRunner
from app.schemas import Finding, RepositorySummary
from app.services.ai_review_service import AIReviewService
from app.services.correlation_service import CorrelationService
from app.services.ingestion_service import IngestionService
from app.services.mapping_service import MappingService
from app.services.report_service import ReportService
from app.services.run_store import RunStore
from app.services.severity_service import SeverityService
from app.services.structure_service import StructureService


def is_relevant_file(path: str) -> bool:
    ignore_paths = ["tests/", "docs/", "examples/", "__pycache__", ".venv"]
    return not any(part in path.lower() for part in ignore_paths)


def prioritize_findings(findings: list[Finding]) -> list[Finding]:
    priority = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    findings.sort(key=lambda item: (priority.get(item.severity, 0), item.file_path, item.start_line), reverse=True)
    return findings


class AnalysisWorker:
    def __init__(
        self,
        *,
        run_store: RunStore,
        ingestion_service: IngestionService,
        structure_service: StructureService,
        mapping_service: MappingService,
        severity_service: SeverityService,
        ai_review_service: AIReviewService,
        correlation_service: CorrelationService,
        report_service: ReportService,
        pylint_runner: PylintRunner,
        bandit_runner: BanditRunner,
        heuristic_analyzer: HeuristicAnalyzer,
    ) -> None:
        self.run_store = run_store
        self.ingestion_service = ingestion_service
        self.structure_service = structure_service
        self.mapping_service = mapping_service
        self.severity_service = severity_service
        self.ai_review_service = ai_review_service
        self.correlation_service = correlation_service
        self.report_service = report_service
        self.pylint_runner = pylint_runner
        self.bandit_runner = bandit_runner
        self.heuristic_analyzer = heuristic_analyzer

    def run(self, run_id: str, repo_url: str) -> None:
        try:
            self.run_store.update_status(run_id, status="running", progress="Cloning and indexing repository")
            snapshot = self.ingestion_service.ingest(repo_url, self.run_store.run_dir(run_id))

            repo_summary = RepositorySummary(
                repo_url=snapshot.repo_url,
                repo_name=snapshot.repo_name,
                default_branch=snapshot.default_branch,
                languages=snapshot.languages,
                total_files=snapshot.total_files,
                total_loc=snapshot.total_loc,
            )

            self.run_store.update_status(run_id, status="running", progress="Building code structure map", repo=repo_summary)
            structure_map = self.structure_service.build(snapshot)

            self.run_store.update_status(run_id, status="running", progress="Running static analysis", repo=repo_summary)
            raw_findings = (
                self.pylint_runner.run(snapshot)
                + self.bandit_runner.run(snapshot)
                + self.heuristic_analyzer.run(snapshot)
            )

            normalized = self._normalize(raw_findings)
            findings = [finding for finding in normalized if is_relevant_file(finding.file_path)]

            self.run_store.update_status(run_id, status="running", progress="Mapping findings to code locations", repo=repo_summary)
            mapped_findings = self.mapping_service.map_findings(findings, snapshot, structure_map)
            scored_findings = self.severity_service.apply(mapped_findings)
            prioritized_findings = prioritize_findings(scored_findings)

            self.run_store.update_status(run_id, status="running", progress="Generating AI suggestions", repo=repo_summary)
            enriched_findings = self.ai_review_service.enrich(prioritized_findings)

            self.run_store.update_status(run_id, status="running", progress="Assembling report", repo=repo_summary)
            clusters = self.correlation_service.build_clusters(enriched_findings)
            hotspots = self.correlation_service.compute_hotspots(enriched_findings)
            report = self.report_service.build(snapshot, enriched_findings, clusters, hotspots)
            self.run_store.save_report(run_id, report)
        except Exception as exc:
            self.run_store.update_status(
                run_id,
                status="failed",
                progress="Analysis failed",
                error=str(exc),
            )

    def _normalize(self, raw_findings: list[Finding]) -> list[Finding]:
        deduped: dict[tuple[str, str, int, str], Finding] = {}
        for index, finding in enumerate(raw_findings, start=1):
            normalized = finding.model_copy(update={"id": f"ISSUE-{index:04d}"})
            key = (normalized.file_path, normalized.rule_id, normalized.start_line, normalized.title)
            deduped[key] = normalized
        return list(deduped.values())
