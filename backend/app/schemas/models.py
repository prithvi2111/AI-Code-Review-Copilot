from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["Critical", "High", "Medium", "Low"]
Category = Literal["bug", "security", "code_smell", "performance"]
RunStatus = Literal["queued", "running", "completed", "failed"]
SymbolType = Literal["module", "class", "function", "method"]
ImpactLevel = Literal["critical", "high", "medium", "low"]
FixEffort = Literal["low", "medium", "high"]


class AnalysisCreateRequest(BaseModel):
    repo_url: str = Field(..., examples=["https://github.com/owner/repository"])


class AnalysisCreateResponse(BaseModel):
    run_id: str
    status: RunStatus


class ApplyFixRequest(BaseModel):
    run_id: str
    file_path: str
    fix_patch: str
    finding_id: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class ApplyFixResponse(BaseModel):
    run_id: str
    file_path: str
    applied: bool
    message: str
    start_line: int | None = None
    end_line: int | None = None
    backup_path: str | None = None


class BatchApplyFixRequest(BaseModel):
    run_id: str
    finding_ids: list[str] = Field(default_factory=list)


class BatchApplyFixResponse(BaseModel):
    run_id: str
    applied_count: int
    skipped_count: int
    modified_files: list[str] = Field(default_factory=list)
    applied_finding_ids: list[str] = Field(default_factory=list)
    skipped_finding_ids: list[str] = Field(default_factory=list)
    message: str


class CreatePullRequestRequest(BaseModel):
    run_id: str
    title: str | None = None
    body: str | None = None


class CreatePullRequestResponse(BaseModel):
    run_id: str
    mode: Literal["pull_request", "patch"]
    message: str
    branch_name: str | None = None
    pr_url: str | None = None
    patch_path: str | None = None
    modified_files: list[str] = Field(default_factory=list)


class SourceFileInfo(BaseModel):
    path: str
    absolute_path: str
    language: str
    is_python: bool = False
    loc: int = 0


class RepositorySummary(BaseModel):
    repo_url: str
    repo_name: str
    default_branch: str
    languages: dict[str, int] = Field(default_factory=dict)
    total_files: int = 0
    total_loc: int = 0


class RepositorySnapshot(RepositorySummary):
    local_path: str
    files: list[SourceFileInfo] = Field(default_factory=list)
    python_files: list[str] = Field(default_factory=list)


class SymbolInfo(BaseModel):
    file_path: str
    name: str
    qualified_name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    parent_name: str | None = None


class FileStructure(BaseModel):
    file_path: str
    imports: list[str] = Field(default_factory=list)
    symbols: list[SymbolInfo] = Field(default_factory=list)


class StructureMap(BaseModel):
    files: dict[str, FileStructure] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str = ""
    category: Category
    title: str
    description: str
    file_path: str
    start_line: int = 1
    end_line: int = 1
    tool_source: str
    rule_id: str
    raw_severity: str = "medium"
    severity: Severity = "Low"
    symbol_name: str | None = None
    symbol_type: str | None = None
    snippet: str = ""
    explanation: str = ""
    root_cause: str = ""
    suggestion: str = ""
    impact: str = ""
    impact_level: ImpactLevel = "medium"
    confidence: int = 75
    fix_effort: FixEffort = "medium"
    fix_patch: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Hotspot(BaseModel):
    file_path: str
    issue_count: int
    severity_distribution: dict[str, int] = Field(default_factory=dict)


class IssueCluster(BaseModel):
    cluster_id: str
    type: str
    count: int = 0
    reason: str
    common_fix: str = ""
    impact_level: ImpactLevel = "medium"
    issue_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    affected_symbols: list[str] = Field(default_factory=list)


class SummaryMetrics(BaseModel):
    total_issues: int
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    impact_distribution: dict[str, int] = Field(default_factory=dict)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    hotspots: list[Hotspot] = Field(default_factory=list)
    overall_risk_score: float = 0.0
    repository_health_score: float = 100.0
    total_groups: int = 0


class AnalysisReport(BaseModel):
    repository: RepositorySummary
    summary: SummaryMetrics
    findings: list[Finding] = Field(default_factory=list)
    clusters: list[IssueCluster] = Field(default_factory=list)


class AnalysisStatusResponse(BaseModel):
    run_id: str
    status: RunStatus
    progress: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    repo: RepositorySummary | None = None
    summary: SummaryMetrics | None = None
