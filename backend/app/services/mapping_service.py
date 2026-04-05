from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.schemas import Finding, RepositorySnapshot, StructureMap, SymbolInfo


class MappingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def map_findings(
        self,
        findings: list[Finding],
        snapshot: RepositorySnapshot,
        structure_map: StructureMap,
    ) -> list[Finding]:
        file_lookup = {item.path: Path(item.absolute_path) for item in snapshot.files}
        mapped_findings: list[Finding] = []

        for finding in findings:
            path = finding.file_path.replace("\\", "/")
            line = max(1, finding.start_line)
            absolute_path = file_lookup.get(path)
            symbol = self._find_symbol(line, structure_map.files.get(path))
            snippet = self._extract_snippet(absolute_path, line, finding.end_line or line)
            mapped_findings.append(
                finding.model_copy(
                    update={
                        "file_path": path,
                        "start_line": line,
                        "end_line": max(line, finding.end_line or line),
                        "symbol_name": symbol.qualified_name if symbol else None,
                        "symbol_type": symbol.symbol_type if symbol else None,
                        "snippet": snippet,
                    }
                )
            )

        return mapped_findings

    @staticmethod
    def _find_symbol(line_number: int, file_structure) -> SymbolInfo | None:
        if not file_structure:
            return None
        candidates = [
            symbol
            for symbol in file_structure.symbols
            if symbol.start_line <= line_number <= symbol.end_line
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda symbol: symbol.end_line - symbol.start_line)

    def _extract_snippet(self, absolute_path: Path | None, start_line: int, end_line: int) -> str:
        if absolute_path is None or not absolute_path.exists():
            return ""
        lines = absolute_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if not lines:
            return ""
        half_window = max(1, self.settings.max_snippet_lines // 2)
        snippet_start = max(1, start_line - half_window)
        snippet_end = min(len(lines), max(end_line, start_line) + half_window)
        return "\n".join(
            f"{line_number}: {lines[line_number - 1]}"
            for line_number in range(snippet_start, snippet_end + 1)
        )
