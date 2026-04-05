from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import AnalysisReport, AnalysisStatusResponse, RepositorySummary, SummaryMetrics


class RunStore:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self._lock = threading.Lock()
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, repo_url: str) -> str:
        run_id = uuid.uuid4().hex
        now = datetime.now(UTC)
        state = {
            "run_id": run_id,
            "repo_url": repo_url,
            "status": "queued",
            "progress": "Queued for analysis",
            "error": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "repo": None,
            "summary": None,
        }
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "state.json", state)
        return run_id

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        progress: str,
        error: str | None = None,
        repo: RepositorySummary | None = None,
        summary: SummaryMetrics | None = None,
    ) -> None:
        with self._lock:
            state = self._read_json(self._run_dir(run_id) / "state.json")
            state["status"] = status
            state["progress"] = progress
            state["error"] = error
            state["updated_at"] = datetime.now(UTC).isoformat()
            if repo is not None:
                state["repo"] = repo.model_dump(mode="json")
            if summary is not None:
                state["summary"] = summary.model_dump(mode="json")
            self._write_json(self._run_dir(run_id) / "state.json", state)

    def save_report(self, run_id: str, report: AnalysisReport) -> None:
        run_dir = self._run_dir(run_id)
        self._write_json(run_dir / "report.json", report.model_dump(mode="json"))
        self.update_status(
            run_id,
            status="completed",
            progress="Analysis completed",
            repo=report.repository,
            summary=report.summary,
        )

    def get_status(self, run_id: str) -> AnalysisStatusResponse:
        state_path = self._run_dir(run_id) / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(run_id)
        return AnalysisStatusResponse.model_validate(self._read_json(state_path))

    def get_report(self, run_id: str) -> AnalysisReport:
        report_path = self._run_dir(run_id) / "report.json"
        if not report_path.exists():
            raise FileNotFoundError(run_id)
        return AnalysisReport.model_validate(self._read_json(report_path))

    def run_dir(self, run_id: str) -> Path:
        return self._run_dir(run_id)

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
