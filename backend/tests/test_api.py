from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.core.config import get_settings
from app.main import create_app
from app.schemas import (
    AnalysisReport,
    ApplyFixRequest,
    CreatePullRequestRequest,
    Finding,
    BatchApplyFixRequest,
    RepositorySummary,
    SummaryMetrics,
)
from app.services.fix_service import FixService
from app.services.github_service import GitHubService
from app.services.run_store import RunStore

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def test_create_analysis_rejects_invalid_url():
    client = TestClient(create_app())

    response = client.post("/api/analyses", json={"repo_url": "https://example.com/not-github"})

    assert response.status_code == 400


def test_create_analysis_and_fetch_report(monkeypatch, tmp_path):
    temp_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(routes, "run_store", temp_store)

    def fake_run(run_id: str, repo_url: str) -> None:
        report = AnalysisReport(
            repository=RepositorySummary(
                repo_url=repo_url,
                repo_name="example/sample-repo",
                default_branch="main",
                languages={"Python": 2},
                total_files=2,
                total_loc=42,
            ),
            summary=SummaryMetrics(
                total_issues=0,
                severity_distribution={},
                category_distribution={},
                hotspots=[],
                overall_risk_score=0.0,
            ),
            findings=[],
            clusters=[],
        )
        temp_store.save_report(run_id, report)

    monkeypatch.setattr(routes.analysis_worker, "run", fake_run)

    client = TestClient(create_app())
    response = client.post("/api/analyses", json={"repo_url": "https://github.com/example/sample-repo"})

    assert response.status_code == 202
    run_id = response.json()["run_id"]

    status_response = client.get(f"/api/analyses/{run_id}")
    report_response = client.get(f"/api/analyses/{run_id}/report")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert report_response.status_code == 200
    assert report_response.json()["repository"]["repo_name"] == "example/sample-repo"


def test_apply_fix_endpoint_updates_cloned_file(monkeypatch, tmp_path):
    temp_store = RunStore(tmp_path / "runs")
    run_id = temp_store.create_run("https://github.com/example/sample-repo")
    repo_dir = temp_store.run_dir(run_id) / "repo"
    shutil.copytree(FIXTURE_ROOT, repo_dir)
    report = AnalysisReport(
        repository=RepositorySummary(
            repo_url="https://github.com/example/sample-repo",
            repo_name="example/sample-repo",
            default_branch="main",
            languages={"Python": 3},
            total_files=3,
            total_loc=25,
        ),
        summary=SummaryMetrics(
            total_issues=1,
            severity_distribution={"High": 1},
            category_distribution={"bug": 1},
            hotspots=[],
            overall_risk_score=10.0,
        ),
        findings=[
            Finding(
                id="ISSUE-0001",
                category="bug",
                title="misplaced-bare-raise",
                description="No active exception to reraise",
                file_path="package/service.py",
                start_line=15,
                end_line=18,
                tool_source="pylint",
                rule_id="misplaced-bare-raise",
                fix_patch="try:\n    ...\nexcept Exception as exc:\n    raise exc",
            )
        ],
        clusters=[],
    )
    temp_store.save_report(run_id, report)
    temp_fix_service = FixService(temp_store)
    monkeypatch.setattr(routes, "run_store", temp_store)
    monkeypatch.setattr(routes, "fix_service", temp_fix_service)

    client = TestClient(create_app())
    response = client.post(
        "/api/apply-fix",
        json=ApplyFixRequest(
            run_id=run_id,
            file_path="package/service.py",
            finding_id="ISSUE-0001",
            start_line=15,
            end_line=18,
            fix_patch="try:\n    ...\nexcept Exception as exc:\n    raise exc",
        ).model_dump(),
    )

    assert response.status_code == 200
    updated = (repo_dir / "package/service.py").read_text(encoding="utf-8")
    assert "raise exc" in updated
    assert (temp_store.run_dir(run_id) / "backups" / "package" / "service.py").exists()


def test_create_pr_endpoint_generates_patch_for_non_git_run(monkeypatch, tmp_path):
    temp_store = RunStore(tmp_path / "runs")
    run_id = temp_store.create_run("https://github.com/example/sample-repo")
    repo_dir = temp_store.run_dir(run_id) / "repo"
    shutil.copytree(FIXTURE_ROOT, repo_dir)
    report = AnalysisReport(
        repository=RepositorySummary(
            repo_url="https://github.com/example/sample-repo",
            repo_name="example/sample-repo",
            default_branch="main",
            languages={"Python": 3},
            total_files=3,
            total_loc=25,
        ),
        summary=SummaryMetrics(
            total_issues=1,
            severity_distribution={"High": 1},
            category_distribution={"bug": 1},
            hotspots=[],
            overall_risk_score=10.0,
        ),
        findings=[
            Finding(
                id="ISSUE-0001",
                category="bug",
                title="misplaced-bare-raise",
                description="No active exception to reraise",
                file_path="package/service.py",
                start_line=15,
                end_line=18,
                tool_source="pylint",
                rule_id="misplaced-bare-raise",
                fix_patch="try:\n    ...\nexcept Exception as exc:\n    raise exc",
            )
        ],
        clusters=[],
    )
    temp_store.save_report(run_id, report)
    temp_fix_service = FixService(temp_store)
    temp_fix_service.apply_fix(
        ApplyFixRequest(
            run_id=run_id,
            file_path="package/service.py",
            finding_id="ISSUE-0001",
            start_line=15,
            end_line=18,
            fix_patch="try:\n    ...\nexcept Exception as exc:\n    raise exc",
        )
    )
    temp_github_service = GitHubService(get_settings(), temp_store, temp_fix_service)
    monkeypatch.setattr(routes, "run_store", temp_store)
    monkeypatch.setattr(routes, "fix_service", temp_fix_service)
    monkeypatch.setattr(routes, "github_service", temp_github_service)

    client = TestClient(create_app())
    response = client.post(
        "/api/create-pr",
        json=CreatePullRequestRequest(run_id=run_id).model_dump(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "patch"
    assert Path(payload["patch_path"]).exists()


def test_apply_fixes_batch_endpoint_updates_multiple_findings(monkeypatch, tmp_path):
    temp_store = RunStore(tmp_path / "runs")
    run_id = temp_store.create_run("https://github.com/example/sample-repo")
    repo_dir = temp_store.run_dir(run_id) / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    target_file = repo_dir / "package" / "module.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("value = 1\nprint(value)\nunused = 3\n", encoding="utf-8")

    report = AnalysisReport(
        repository=RepositorySummary(
            repo_url="https://github.com/example/sample-repo",
            repo_name="example/sample-repo",
            default_branch="main",
            languages={"Python": 1},
            total_files=1,
            total_loc=3,
        ),
        summary=SummaryMetrics(
            total_issues=2,
            severity_distribution={"High": 1, "Low": 1},
            category_distribution={"bug": 2},
            hotspots=[],
            overall_risk_score=12.0,
        ),
        findings=[
            Finding(
                id="ISSUE-0001",
                category="bug",
                title="not-callable",
                description="Value is reused incorrectly",
                file_path="package/module.py",
                start_line=1,
                end_line=1,
                tool_source="pylint",
                rule_id="not-callable",
                fix_patch="value = 2",
            ),
            Finding(
                id="ISSUE-0002",
                category="bug",
                title="unused-variable",
                description="Unused variable 'unused'",
                file_path="package/module.py",
                start_line=3,
                end_line=3,
                tool_source="pylint",
                rule_id="unused-variable",
                fix_patch="",
            ),
        ],
        clusters=[],
    )
    temp_store.save_report(run_id, report)
    temp_fix_service = FixService(temp_store)
    monkeypatch.setattr(routes, "run_store", temp_store)
    monkeypatch.setattr(routes, "fix_service", temp_fix_service)

    client = TestClient(create_app())
    response = client.post(
        "/api/apply-fixes/batch",
        json=BatchApplyFixRequest(run_id=run_id, finding_ids=["ISSUE-0001", "ISSUE-0002"]).model_dump(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_count"] == 2
    assert payload["modified_files"] == ["package/module.py"]
    updated = target_file.read_text(encoding="utf-8")
    assert updated == "value = 2\nprint(value)\n"
