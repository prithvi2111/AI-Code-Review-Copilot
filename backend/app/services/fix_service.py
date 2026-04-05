from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import AnalysisReport, ApplyFixRequest, ApplyFixResponse, BatchApplyFixRequest, BatchApplyFixResponse, Finding
from app.services.run_store import RunStore


class FixService:
    NON_INLINE_PREFIXES = ("pip install", "poetry add", "uv add", "npm install", "pnpm add", "yarn add")

    def __init__(self, run_store: RunStore) -> None:
        self.run_store = run_store

    def apply_fix(self, payload: ApplyFixRequest) -> ApplyFixResponse:
        if self._is_non_inline_fix(payload.fix_patch):
            raise ValueError("This fix is an environment command, so it cannot be applied directly to a source file.")

        report = self.run_store.get_report(payload.run_id)
        finding = self._resolve_finding(report, payload)
        repo_dir = self.run_store.run_dir(payload.run_id) / "repo"
        target_file = (repo_dir / payload.file_path).resolve()
        repo_dir_resolved = repo_dir.resolve()
        if repo_dir_resolved not in target_file.parents and target_file != repo_dir_resolved:
            raise ValueError("Requested file path is outside the cloned repository.")
        if not target_file.exists():
            raise ValueError("Requested file does not exist in the cloned repository.")

        start_line = payload.start_line or finding.start_line
        end_line = payload.end_line or finding.end_line
        self._apply_to_file(payload.run_id, target_file, payload.file_path, finding, start_line, end_line, payload.fix_patch)

        return ApplyFixResponse(
            run_id=payload.run_id,
            file_path=payload.file_path,
            applied=True,
            message="Fix patch applied to the cloned repository.",
            start_line=start_line,
            end_line=end_line,
            backup_path=str(self._backup_path(payload.run_id, payload.file_path)),
        )

    def apply_fixes(self, payload: BatchApplyFixRequest) -> BatchApplyFixResponse:
        report = self.run_store.get_report(payload.run_id)
        repo_dir = self.run_store.run_dir(payload.run_id) / "repo"
        requested_findings = [finding for finding in report.findings if finding.id in set(payload.finding_ids)]
        grouped_findings: dict[str, list[Finding]] = {}
        for finding in requested_findings:
            grouped_findings.setdefault(finding.file_path, []).append(finding)

        applied_finding_ids: list[str] = []
        skipped_finding_ids: list[str] = []
        modified_files: set[str] = set()

        for file_path, findings in grouped_findings.items():
            target_file = (repo_dir / file_path).resolve()
            if not target_file.exists():
                skipped_finding_ids.extend(item.id for item in findings)
                continue

            ordered_findings = sorted(findings, key=lambda item: (item.start_line, item.end_line), reverse=True)
            for finding in ordered_findings:
                if self._is_non_inline_fix(finding.fix_patch):
                    skipped_finding_ids.append(finding.id)
                    continue
                self._apply_to_file(
                    payload.run_id,
                    target_file,
                    file_path,
                    finding,
                    finding.start_line,
                    finding.end_line,
                    finding.fix_patch,
                )
                applied_finding_ids.append(finding.id)
                modified_files.add(file_path)

        return BatchApplyFixResponse(
            run_id=payload.run_id,
            applied_count=len(applied_finding_ids),
            skipped_count=len(skipped_finding_ids),
            modified_files=sorted(modified_files),
            applied_finding_ids=applied_finding_ids,
            skipped_finding_ids=skipped_finding_ids,
            message=f"Applied {len(applied_finding_ids)} fixes and skipped {len(skipped_finding_ids)} unsupported fixes.",
        )

    def _apply_to_file(
        self,
        run_id: str,
        target_file: Path,
        file_path: str,
        finding: Finding,
        start_line: int,
        end_line: int,
        fix_patch: str,
    ) -> None:
        if start_line < 1 or end_line < start_line:
            raise ValueError("Invalid line range supplied for fix application.")

        original_text = target_file.read_text(encoding="utf-8", errors="ignore")
        newline = "\r\n" if "\r\n" in original_text else "\n"
        trailing_newline = original_text.endswith(("\n", "\r"))
        original_lines = original_text.splitlines()
        if end_line > len(original_lines):
            raise ValueError("The requested fix range extends beyond the end of the file.")

        backup_path = self._backup_path(run_id, file_path)
        if not backup_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(original_text, encoding="utf-8")

        replacement_lines = fix_patch.rstrip("\n").splitlines() if fix_patch else []
        updated_lines = original_lines[: start_line - 1] + replacement_lines + original_lines[end_line:]
        updated_text = newline.join(updated_lines)
        if trailing_newline:
            updated_text += newline
        target_file.write_text(updated_text, encoding="utf-8")

        self._record_fix(
            run_id,
            {
                "finding_id": finding.id,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "backup_path": str(backup_path),
                "applied_at": datetime.now(UTC).isoformat(),
            },
        )

    def modified_files(self, run_id: str) -> list[str]:
        manifest = self._manifest_path(run_id)
        if not manifest.exists():
            return []
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        return sorted({item["file_path"] for item in payload.get("entries", [])})

    def build_patch_from_backups(self, run_id: str) -> str:
        import difflib

        repo_dir = self.run_store.run_dir(run_id) / "repo"
        modified_files = self.modified_files(run_id)
        if not modified_files:
            raise ValueError("No applied fixes were found for this run.")

        diff_chunks: list[str] = []
        for file_path in modified_files:
            backup_path = self._backup_path(run_id, file_path)
            current_path = repo_dir / file_path
            original = backup_path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
            updated = current_path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
            diff_chunks.extend(
                difflib.unified_diff(
                    original,
                    updated,
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                )
            )
        return "".join(diff_chunks)

    def _resolve_finding(self, report: AnalysisReport, payload: ApplyFixRequest) -> Finding:
        candidates = [finding for finding in report.findings if finding.file_path == payload.file_path]
        if payload.finding_id:
            candidates = [finding for finding in candidates if finding.id == payload.finding_id]
        if payload.start_line is not None:
            candidates = [finding for finding in candidates if finding.start_line == payload.start_line]
        if payload.end_line is not None:
            candidates = [finding for finding in candidates if finding.end_line == payload.end_line]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ValueError("No matching finding was found for the requested file and line range.")
        raise ValueError("Multiple findings match this file. Supply finding_id or exact line range to disambiguate.")

    def _backup_path(self, run_id: str, file_path: str) -> Path:
        return self.run_store.run_dir(run_id) / "backups" / Path(file_path)

    def _manifest_path(self, run_id: str) -> Path:
        return self.run_store.run_dir(run_id) / "fixes.json"

    def _record_fix(self, run_id: str, entry: dict[str, object]) -> None:
        manifest_path = self._manifest_path(run_id)
        if manifest_path.exists():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            payload = {"entries": []}
        payload["entries"].append(entry)
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _is_non_inline_fix(self, fix_patch: str) -> bool:
        normalized = fix_patch.strip().lower()
        return any(normalized.startswith(prefix) for prefix in self.NON_INLINE_PREFIXES)
