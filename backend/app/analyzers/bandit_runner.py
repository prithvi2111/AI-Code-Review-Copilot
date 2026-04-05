from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.schemas import Finding, RepositorySnapshot


class BanditRunner:
    def run(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not snapshot.python_files:
            return []
        bandit_module = shutil.which("bandit")
        command = [bandit_module, "-r", snapshot.local_path, "-f", "json"] if bandit_module else [sys.executable, "-m", "bandit", "-r", snapshot.local_path, "-f", "json"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        if not output:
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return []

        findings: list[Finding] = []
        for item in payload.get("results", []):
            absolute_path = item.get("filename", "")
            try:
                relative_path = Path(absolute_path).relative_to(snapshot.local_path).as_posix()
            except ValueError:
                relative_path = absolute_path.replace("\\", "/")
            findings.append(
                Finding(
                    category="security",
                    title=item.get("test_name", "bandit issue"),
                    description=item.get("issue_text", "Bandit identified a potential security issue."),
                    file_path=relative_path,
                    start_line=item.get("line_number") or 1,
                    end_line=item.get("line_range", [item.get("line_number") or 1])[-1],
                    tool_source="bandit",
                    rule_id=item.get("test_id", "bandit"),
                    raw_severity=(item.get("issue_severity") or "medium").lower(),
                    metadata={"confidence": item.get("issue_confidence"), "more_info": item.get("more_info")},
                )
            )
        return findings
