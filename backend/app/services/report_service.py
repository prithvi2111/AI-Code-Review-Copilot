from __future__ import annotations

from collections import defaultdict

from app.schemas import AnalysisReport, Finding, Hotspot, IssueCluster, RepositorySnapshot, RepositorySummary, SummaryMetrics


class ReportService:
    SEVERITY_WEIGHTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

    def build(
        self,
        snapshot: RepositorySnapshot,
        findings: list[Finding],
        clusters: list[IssueCluster],
        hotspots: list[Hotspot],
    ) -> AnalysisReport:
        severity_distribution: dict[str, int] = defaultdict(int)
        impact_distribution: dict[str, int] = defaultdict(int)
        category_distribution: dict[str, int] = defaultdict(int)
        for finding in findings:
            severity_distribution[finding.severity] += 1
            impact_distribution[finding.impact_level] += 1
            category_distribution[finding.category] += 1

        overall_risk_score = self._compute_risk_score(snapshot.total_files, findings)
        summary = SummaryMetrics(
            total_issues=len(findings),
            severity_distribution=dict(sorted(severity_distribution.items())),
            impact_distribution=dict(sorted(impact_distribution.items())),
            category_distribution=dict(sorted(category_distribution.items())),
            hotspots=hotspots,
            overall_risk_score=overall_risk_score,
            repository_health_score=round(max(0.0, 100.0 - overall_risk_score), 1),
            total_groups=len(clusters),
        )
        repository = RepositorySummary(
            repo_url=snapshot.repo_url,
            repo_name=snapshot.repo_name,
            default_branch=snapshot.default_branch,
            languages=snapshot.languages,
            total_files=snapshot.total_files,
            total_loc=snapshot.total_loc,
        )
        return AnalysisReport(
            repository=repository,
            summary=summary,
            findings=findings,
            clusters=clusters,
        )

    def _compute_risk_score(self, total_files: int, findings: list[Finding]) -> float:
        if not findings:
            return 0.0
        weighted_total = 0
        for item in findings:
            category_weight = 1.0
            if item.category == "security":
                category_weight = 1.25
            elif item.category == "bug":
                category_weight = 1.15
            weighted_total += self.SEVERITY_WEIGHTS[item.severity] * category_weight

        normalized = (weighted_total / max(1, total_files)) * 7
        return round(min(100.0, normalized), 1)
