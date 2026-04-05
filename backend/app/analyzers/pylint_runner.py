from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.schemas import Finding, RepositorySnapshot


class PylintRunner:
    CATEGORY_MAP = {
        "fatal": "bug",
        "error": "bug",
        "warning": "bug",
        "refactor": "code_smell",
        "convention": "code_smell",
        "info": "code_smell",
    }

    def run(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not snapshot.python_files:
            return []
        pylint_module = shutil.which("pylint")
        command = [pylint_module, "--output-format=json", snapshot.local_path] if pylint_module else [sys.executable, "-m", "pylint", "--output-format=json", snapshot.local_path]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        if not output:
            return []
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return []

        findings: list[Finding] = []
        for item in payload:
            absolute_path = item.get("path", "")
            try:
                relative_path = Path(absolute_path).relative_to(snapshot.local_path).as_posix()
            except ValueError:
                relative_path = absolute_path.replace("\\", "/")
            message_type = item.get("type", "warning")
            findings.append(
                Finding(
                    category=self.CATEGORY_MAP.get(message_type, "code_smell"),
                    title=item.get("symbol") or item.get("message-id") or "pylint issue",
                    description=item.get("message", "Pylint detected a potential issue."),
                    file_path=relative_path,
                    start_line=item.get("line") or 1,
                    end_line=item.get("endLine") or item.get("line") or 1,
                    tool_source="pylint",
                    rule_id=item.get("message-id", "pylint"),
                    raw_severity=message_type,
                    metadata={"column": item.get("column"), "message_symbol": item.get("symbol")},
                )
            )
        return findings
