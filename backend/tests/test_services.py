from __future__ import annotations

from pathlib import Path

from app.analyzers.bandit_runner import BanditRunner
from app.analyzers.pylint_runner import PylintRunner
from app.core.config import get_settings
from app.schemas import Finding
from app.services.ingestion_service import IngestionService
from app.services.mapping_service import MappingService
from app.services.report_service import ReportService
from app.services.severity_service import SeverityService
from app.services.structure_service import StructureService


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def build_snapshot():
    service = IngestionService()
    return service.snapshot_from_local_path(
        FIXTURE_ROOT,
        repo_url="https://github.com/example/sample-repo",
        repo_name="example/sample-repo",
        default_branch="main",
    )


def test_ingestion_snapshot_filters_lockfiles_and_detects_python():
    snapshot = build_snapshot()

    assert snapshot.repo_name == "example/sample-repo"
    assert "package/service.py" in snapshot.python_files
    assert "package-lock.json" not in {item.path for item in snapshot.files}
    assert snapshot.languages["Python"] == 3


def test_structure_service_extracts_functions_and_methods():
    snapshot = build_snapshot()
    structure = StructureService().build(snapshot)

    service_symbols = structure.files["package/service.py"].symbols
    model_symbols = structure.files["package/models.py"].symbols

    assert any(symbol.qualified_name == "risky_fetch" for symbol in service_symbols)
    assert any(symbol.qualified_name == "Reviewer.score" for symbol in model_symbols)


def test_mapping_service_adds_symbol_and_snippet():
    snapshot = build_snapshot()
    structure = StructureService().build(snapshot)
    settings = get_settings()
    mapping_service = MappingService(settings)
    findings = [
        Finding(
            id="ISSUE-0001",
            category="bug",
            title="Bare except hides failures",
            description="Test issue",
            file_path="package/service.py",
            start_line=17,
            end_line=18,
            tool_source="heuristic",
            rule_id="bare-except",
            raw_severity="high",
        )
    ]

    mapped = mapping_service.map_findings(findings, snapshot, structure)

    assert mapped[0].symbol_name == "risky_fetch"
    assert "except:" in mapped[0].snippet


def test_severity_service_assigns_expected_levels():
    findings = [
        Finding(
            id="ISSUE-0001",
            category="security",
            title="eval used",
            description="Potential code execution",
            file_path="package/service.py",
            start_line=1,
            end_line=1,
            tool_source="bandit",
            rule_id="B307",
            raw_severity="high",
        ),
        Finding(
            id="ISSUE-0002",
            category="code_smell",
            title="Long function",
            description="Long function",
            file_path="package/service.py",
            start_line=1,
            end_line=10,
            tool_source="heuristic",
            rule_id="long-function",
            raw_severity="medium",
        ),
    ]

    scored = SeverityService().apply(findings)

    assert scored[0].severity == "Critical"
    assert scored[1].severity == "Medium"


def test_report_service_builds_summary():
    snapshot = build_snapshot()
    findings = [
        Finding(
            id="ISSUE-0001",
            category="bug",
            title="Bare except hides failures",
            description="Test issue",
            file_path="package/service.py",
            start_line=17,
            end_line=18,
            tool_source="heuristic",
            rule_id="bare-except",
            raw_severity="high",
            severity="High",
            suggestion="Handle explicit exceptions",
            impact="Reliability issue",
        )
    ]

    report = ReportService().build(snapshot, findings, [], [])

    assert report.summary.total_issues == 1
    assert report.summary.severity_distribution["High"] == 1
    assert report.repository.repo_name == "example/sample-repo"


def test_pylint_runner_normalizes_json(monkeypatch):
    snapshot = build_snapshot()

    class Result:
        stdout = '[{"type": "warning", "path": "C:/repo/package/service.py", "line": 9, "endLine": 9, "message-id": "W0702", "message": "No exception type(s) specified", "symbol": "bare-except"}]'

    monkeypatch.setattr("app.analyzers.pylint_runner.shutil.which", lambda _: "pylint")
    monkeypatch.setattr("app.analyzers.pylint_runner.subprocess.run", lambda *args, **kwargs: Result())

    findings = PylintRunner().run(snapshot)

    assert findings[0].tool_source == "pylint"
    assert findings[0].rule_id == "W0702"


def test_bandit_runner_normalizes_json(monkeypatch):
    snapshot = build_snapshot()

    class Result:
        stdout = '{"results": [{"filename": "C:/repo/package/service.py", "line_number": 4, "line_range": [4], "issue_severity": "HIGH", "issue_confidence": "HIGH", "issue_text": "Use of hardcoded password", "test_id": "B105", "test_name": "hardcoded_password_string"}]}'

    monkeypatch.setattr("app.analyzers.bandit_runner.shutil.which", lambda _: "bandit")
    monkeypatch.setattr("app.analyzers.bandit_runner.subprocess.run", lambda *args, **kwargs: Result())

    findings = BanditRunner().run(snapshot)

    assert findings[0].category == "security"
    assert findings[0].raw_severity == "high"
