from __future__ import annotations

from app.schemas import Finding


class SeverityService:
    PYLINT_MAP = {
        "fatal": "High",
        "error": "High",
        "warning": "Medium",
        "refactor": "Low",
        "convention": "Low",
        "info": "Low",
    }
    HEURISTIC_MAP = {
        "long-function": "Medium",
        "deep-nesting": "Medium",
        "duplicate-code-pattern": "Low",
        "bare-except": "High",
        "nested-loops": "Medium",
        "blocking-call-in-loop": "High",
        "open-without-context-manager": "Medium",
        "complex-conditional": "Medium",
    }
    CRITICAL_RULES = {"B307", "hardcoded-secret"}

    def apply(self, findings: list[Finding]) -> list[Finding]:
        return [finding.model_copy(update={"severity": self._severity_for_finding(finding)}) for finding in findings]

    def _severity_for_finding(self, finding: Finding) -> str:
        raw = finding.raw_severity.lower()
        if finding.rule_id in self.CRITICAL_RULES:
            return "Critical"
        if finding.category == "security":
            if raw in {"high", "medium", "low"}:
                return raw.capitalize()
            if "secret" in finding.title.lower() or "credential" in finding.description.lower():
                return "Critical"
            return "High"
        if finding.tool_source == "pylint":
            return self.PYLINT_MAP.get(raw, "Medium")
        if finding.tool_source == "heuristic":
            return self.HEURISTIC_MAP.get(finding.rule_id, "Medium")
        if finding.category == "performance":
            return "High" if "blocking" in finding.rule_id else "Medium"
        if finding.category == "bug":
            return "High" if raw in {"error", "fatal"} else "Medium"
        return "Low"
