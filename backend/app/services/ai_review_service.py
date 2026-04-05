from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.schemas import Finding


@dataclass(frozen=True)
class Guidance:
    explanation: str
    root_cause: str
    impact: str
    impact_level: str
    confidence: int
    fix_effort: str
    suggestion: str
    fix_patch: str


class AIReviewService:
    RULE_PACKAGE_PATTERN = re.compile(r"'([^']+)'")
    NO_NAME_PATTERN = re.compile(r"No name '([^']+)' in module '([^']+)'", re.IGNORECASE)
    NOT_CALLABLE_PATTERN = re.compile(r"'?([A-Za-z_][\w.]*)'?\s+is not callable", re.IGNORECASE)
    UNUSED_VARIABLE_PATTERN = re.compile(r"Unused variable '([^']+)'", re.IGNORECASE)
    IMPORT_ERROR_RULES = {"import-error", "e0401"}
    NO_NAME_RULES = {"no-name-in-module", "e0611"}
    MISPLACED_BARE_RAISE_RULES = {"misplaced-bare-raise", "e0704"}
    NOT_CALLABLE_RULES = {"not-callable", "e1102"}
    UNUSED_VARIABLE_RULES = {"unused-variable", "w0612"}
    BROAD_EXCEPTION_RULES = {"broad-exception-caught", "w0718", "broad-except", "w0703"}
    TOO_MANY_BRANCHES_RULES = {"too-many-branches", "r0912"}
    MISSING_DOCSTRING_RULES = {"missing-module-docstring", "missing-class-docstring", "missing-function-docstring", "c0114", "c0115", "c0116"}
    BARE_EXCEPT_RULES = {"bare-except", "w0702"}
    OPEN_WITHOUT_CONTEXT_RULES = {"open-without-context-manager"}
    BLOCKING_CALL_RULES = {"blocking-call-in-loop"}
    NESTED_LOOP_RULES = {"nested-loops"}
    LONG_FUNCTION_RULES = {"long-function"}
    DEEP_NESTING_RULES = {"deep-nesting"}
    COMPLEX_CONDITIONAL_RULES = {"complex-conditional"}
    DUPLICATE_CODE_RULES = {"duplicate-code-pattern"}
    HARDCODED_SECRET_RULES = {"hardcoded-secret", "b105"}
    EVAL_RULES = {"b307"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enrich(self, findings: list[Finding]) -> list[Finding]:
        if not findings:
            return findings

        enriched_findings = []
        for finding in findings:
            guidance = self._build_guidance(finding)
            enriched_findings.append(
                finding.model_copy(
                    update={
                        "explanation": guidance.explanation,
                        "root_cause": guidance.root_cause,
                        "impact": guidance.impact,
                        "impact_level": guidance.impact_level,
                        "confidence": guidance.confidence,
                        "fix_effort": guidance.fix_effort,
                        "suggestion": guidance.suggestion,
                        "fix_patch": guidance.fix_patch,
                    }
                )
            )

        if self.settings.openai_api_key and self.settings.openai_model:
            refined = self._try_openai_enrichment(enriched_findings)
            if refined is not None:
                return refined

        return enriched_findings

    def generate_fix_patch(self, finding: Finding) -> str:
        return self._build_guidance(finding).fix_patch

    def _build_guidance(self, finding: Finding) -> Guidance:
        title = (finding.title or "").lower()
        rule = (finding.rule_id or "").lower()
        description = finding.description or ""
        text = " ".join([title, rule, description.lower()])
        impact_level = self._impact_level_for_finding(finding)
        confidence = self._confidence_for_finding(finding)

        if rule in self.IMPORT_ERROR_RULES or "import-error" in text:
            package = self._extract_missing_package(finding) or "missing_package"
            package_root = package.split(".")[0]
            return Guidance(
                explanation=f"The import for `{package_root}` cannot be resolved in the scanned environment.",
                root_cause=f"Module `{package_root}` is referenced in the codebase but is not installed or the import path does not match the package that is available at runtime.",
                impact="The file cannot import successfully, so startup paths, CLI commands, or request handlers that depend on it can fail before any business logic runs.",
                impact_level=impact_level,
                confidence=max(confidence, 92),
                fix_effort="low",
                suggestion=f"Install `{package_root}` in the runtime environment and keep the import statement aligned with the installed package name.",
                fix_patch=f"pip install {package_root}",
            )

        if rule in self.NO_NAME_RULES or "no-name-in-module" in text:
            imported_name, module_name = self._extract_missing_symbol(description)
            imported_name = imported_name or "correct_name"
            module_name = module_name or "module"
            return Guidance(
                explanation=f"`{imported_name}` is imported from `{module_name}`, but that symbol is not exposed by the installed module.",
                root_cause=f"The code expects `{module_name}` to export `{imported_name}`, but the symbol either moved, was renamed, or is only available in a different package version.",
                impact="This raises an import failure at module load time, which can block the entire feature path that depends on the file.",
                impact_level=impact_level,
                confidence=max(confidence, 88),
                fix_effort="medium",
                suggestion=f"Verify the installed package version and import `{imported_name}` from the module that actually defines it.",
                fix_patch=f"from {module_name} import {imported_name}",
            )

        if rule in self.MISPLACED_BARE_RAISE_RULES or "misplaced bare raise" in text:
            return Guidance(
                explanation="A bare `raise` is being used where Python does not have an active exception to re-raise.",
                root_cause="The statement sits outside a matching `except` block, so the interpreter has no captured exception object available.",
                impact="That path fails with a new runtime error and hides the original failure the code was trying to propagate.",
                impact_level=impact_level,
                confidence=max(confidence, 90),
                fix_effort="low",
                suggestion="Re-raise from inside an `except` block and keep the exception bound to a local name when you need explicit access to it.",
                fix_patch="except Exception as exc:\n    raise exc",
            )

        if rule in self.NOT_CALLABLE_RULES or "not-callable" in text:
            object_name = self._extract_not_callable_name(description) or "value"
            return Guidance(
                explanation=f"`{object_name}` is being invoked like a function even though the inferred object is not callable.",
                root_cause=f"`{object_name}` was assigned a value or object instance instead of a function, but later code still treats it as if it can be called with `()`.",
                impact="This path can raise `TypeError` at runtime and usually indicates an incorrect variable assignment or an API misuse bug.",
                impact_level=impact_level,
                confidence=max(confidence, 86),
                fix_effort="medium",
                suggestion=f"Use `{object_name}` directly if it is a value, or replace it with the callable attribute or function you intended to execute.",
                fix_patch=self._build_not_callable_fix(finding, object_name),
            )

        if rule in self.UNUSED_VARIABLE_RULES or "unused variable" in text:
            variable_name = self._extract_unused_variable(description) or "unused_value"
            return Guidance(
                explanation=f"`{variable_name}` is assigned but never read anywhere in the flagged scope.",
                root_cause=f"The assignment to `{variable_name}` survived a refactor or an unfinished implementation, so the value now serves no purpose.",
                impact="Unused assignments add noise to reviews, make control flow harder to read, and often hide code that is no longer doing what the author intended.",
                impact_level=impact_level,
                confidence=max(confidence, 95),
                fix_effort="low",
                suggestion=f"Delete the assignment if the value is unnecessary, or rename it to `_{variable_name}` only when the unused value is intentional.",
                fix_patch=self._build_unused_variable_fix(finding, variable_name),
            )

        if rule in self.BROAD_EXCEPTION_RULES or "broad exception" in text:
            return Guidance(
                explanation="The handler catches a generic `Exception`, so it also swallows unexpected programming errors.",
                root_cause="The exception clause is broader than the narrow set of failures that the guarded operation is expected to raise.",
                impact="Unexpected defects are hidden behind the catch-all handler, which makes failures harder to debug and can leave bad state undiscovered in production.",
                impact_level=impact_level,
                confidence=max(confidence, 84),
                fix_effort="medium",
                suggestion="Catch the most specific exception raised by the guarded call so real defects still bubble up and only expected failures are handled.",
                fix_patch="except ValueError as exc:\n    raise exc",
            )

        if rule in self.TOO_MANY_BRANCHES_RULES or "too-many-branches" in text:
            return Guidance(
                explanation="The function contains more branch paths than one block of logic can comfortably communicate or test.",
                root_cause="Multiple conditional responsibilities were accumulated inside a single function instead of being split into smaller helpers or a dispatch structure.",
                impact="Complex branching increases regression risk, reduces testability, and makes future changes expensive because every new path interacts with several old ones.",
                impact_level=impact_level,
                confidence=max(confidence, 80),
                fix_effort="high",
                suggestion="Extract branch-specific behavior into helper functions or dispatch tables so each path becomes smaller, isolated, and easier to verify.",
                fix_patch="handler = handlers.get(action, default_handler)\nreturn handler(payload)",
            )

        if rule in self.MISSING_DOCSTRING_RULES or "missing-docstring" in text:
            docstring = self._build_docstring_template(finding)
            return Guidance(
                explanation="The symbol has no docstring describing its purpose or contract.",
                root_cause="The module, class, or callable was added without documenting what it does, what it expects, or what it returns.",
                impact="Missing interface documentation slows onboarding and increases the chance that future changes misuse the symbol or duplicate existing behavior.",
                impact_level=impact_level,
                confidence=max(confidence, 93),
                fix_effort="low",
                suggestion="Add a concise docstring that states the symbol's responsibility in the same vocabulary the rest of the codebase uses.",
                fix_patch=docstring,
            )

        if rule in self.BARE_EXCEPT_RULES or "bare except" in text:
            return Guidance(
                explanation="The exception block catches every failure without specifying which errors are actually expected.",
                root_cause="The handler uses a bare `except:` clause, so both ordinary operational failures and programming bugs are collapsed into the same branch.",
                impact="Hidden exceptions make production debugging difficult and can suppress failures that should stop execution immediately.",
                impact_level=impact_level,
                confidence=max(confidence, 90),
                fix_effort="medium",
                suggestion="Replace the bare clause with a specific exception type or with `Exception as exc` if the fallback must stay broad for now.",
                fix_patch="except Exception as exc:\n    return []",
            )

        if rule in self.OPEN_WITHOUT_CONTEXT_RULES or "context manager" in text:
            file_target = self._extract_open_target(finding) or '"debug.log"'
            return Guidance(
                explanation="A file handle is opened without a context manager, so the close lifecycle depends on every code path behaving perfectly.",
                root_cause="The file is created with `open()` directly instead of being wrapped in `with`, which means exceptions can bypass explicit cleanup.",
                impact="Leaked file descriptors can accumulate under failure conditions and produce subtle bugs in long-running processes.",
                impact_level=impact_level,
                confidence=max(confidence, 82),
                fix_effort="medium",
                suggestion="Wrap the file operation in a `with` block so Python always closes the file handle when the block exits.",
                fix_patch=f'with open({file_target}, "w", encoding="utf-8") as handle:\n    handle.write(data)',
            )

        if rule in self.BLOCKING_CALL_RULES or "blocking call" in text:
            return Guidance(
                explanation="A blocking operation is running inside a loop, so every iteration waits on I/O before the next one can start.",
                root_cause="Network or sleep calls are embedded directly in the loop body instead of being batched, cached, or moved outside the repeated path.",
                impact="Latency compounds with every iteration, making throughput worse and causing performance to degrade sharply as the input size grows.",
                impact_level=impact_level,
                confidence=max(confidence, 80),
                fix_effort="medium",
                suggestion="Precompute or batch the blocking work before the loop, then iterate over the prepared results instead of waiting on I/O every iteration.",
                fix_patch="responses = [fetch_url(url) for url in urls]\nfor response in responses:\n    process_response(response)",
            )

        if rule in self.NESTED_LOOP_RULES or "nested loops" in text:
            return Guidance(
                explanation="The flagged logic uses nested iteration, which grows work multiplicatively as the input size increases.",
                root_cause="The code repeatedly scans one collection from inside another loop instead of indexing or precomputing a lookup structure.",
                impact="Quadratic work can turn routine inputs into slow requests or long-running jobs as the repository or dataset grows.",
                impact_level=impact_level,
                confidence=max(confidence, 78),
                fix_effort="medium",
                suggestion="Build a dictionary or set once, then use O(1) lookups inside the outer loop instead of scanning the inner collection repeatedly.",
                fix_patch="lookup = {item.id: item for item in items}\nfor candidate in candidates:\n    match = lookup.get(candidate.id)",
            )

        if rule in self.LONG_FUNCTION_RULES or "unusually long" in text:
            return Guidance(
                explanation="The function spans too many lines for one reader to quickly reason about its responsibilities.",
                root_cause="Multiple logical steps, side effects, and conditional branches accumulated in a single callable instead of being extracted into focused helpers.",
                impact="Large functions are harder to test, harder to review, and more likely to break when one sub-step changes.",
                impact_level=impact_level,
                confidence=max(confidence, 76),
                fix_effort="high",
                suggestion="Split setup, validation, and execution into separate helpers so the main function reads as a short orchestration layer.",
                fix_patch="validated_input = validate_input(payload)\nprepared_data = prepare_data(validated_input)\nreturn execute_flow(prepared_data)",
            )

        if rule in self.DEEP_NESTING_RULES or "deeply nested" in text:
            return Guidance(
                explanation="The control flow is nested deeply enough that the success and failure paths are hard to follow.",
                root_cause="Guard clauses were not used early, so conditions keep wrapping later logic instead of returning as soon as a prerequisite fails.",
                impact="Nested control flow increases cognitive load and makes small logic changes risky because the true execution path is difficult to see at a glance.",
                impact_level=impact_level,
                confidence=max(confidence, 79),
                fix_effort="high",
                suggestion="Use early returns or extracted helpers to flatten the nesting and make each branch terminate sooner.",
                fix_patch="if not is_valid(payload):\n    return fallback_response()\nreturn handle_valid_payload(payload)",
            )

        if rule in self.COMPLEX_CONDITIONAL_RULES or "overly complex" in text:
            return Guidance(
                explanation="The conditional mixes several boolean decisions into one expression that is hard to reason about.",
                root_cause="Distinct business rules were compressed into a single condition instead of being named and evaluated separately.",
                impact="Dense conditional logic is easy to misread, difficult to test exhaustively, and prone to accidental behavior changes.",
                impact_level=impact_level,
                confidence=max(confidence, 77),
                fix_effort="medium",
                suggestion="Split the compound expression into named boolean checks so each rule is visible and testable on its own.",
                fix_patch="is_ready = response.status == 200\nhas_url = bool(url)\ncan_retry = attempt >= 0\nif is_ready and has_url and can_retry:\n    return handle_response(response)",
            )

        if rule in self.DUPLICATE_CODE_RULES or "repeated code pattern" in text:
            return Guidance(
                explanation="The same logic appears multiple times in the same file or flow.",
                root_cause="Common behavior was copied instead of being lifted into a shared helper, so changes must now be made in several places.",
                impact="Duplicated logic increases maintenance effort and raises the chance that one copy is fixed while another copy drifts out of sync.",
                impact_level=impact_level,
                confidence=max(confidence, 74),
                fix_effort="high",
                suggestion="Extract the repeated block into a helper and call it from each site so future fixes are made once.",
                fix_patch="def shared_step(value):\n    return normalize_value(value)\n\nresult = shared_step(raw_value)",
            )

        if rule in self.HARDCODED_SECRET_RULES or "hardcoded secret" in text or "password" in text:
            secret_name = self._extract_assignment_name(finding) or "API_TOKEN"
            return Guidance(
                explanation=f"`{secret_name}` appears to be a hardcoded credential in source control.",
                root_cause="A secret was embedded directly in the file instead of being loaded from environment-backed configuration or a secret manager.",
                impact="Leaked credentials increase the blast radius of repository access and often require credential rotation across dependent systems.",
                impact_level="critical",
                confidence=max(confidence, 96),
                fix_effort="low",
                suggestion=f"Load `{secret_name}` from the environment or a secret store so the credential never ships in the repository.",
                fix_patch=f'{secret_name} = os.getenv("{secret_name}", "")',
            )

        if rule in self.EVAL_RULES or "eval" in text:
            return Guidance(
                explanation="The code executes dynamically evaluated input.",
                root_cause="User-controlled or variable data is being executed directly instead of being parsed or mapped through a safe dispatcher.",
                impact="Dynamic evaluation can become arbitrary code execution when untrusted input reaches the call site.",
                impact_level="critical",
                confidence=max(confidence, 94),
                fix_effort="medium",
                suggestion="Replace dynamic evaluation with a whitelist-based lookup or a parser that treats the input as data instead of executable code.",
                fix_patch='allowed_values = {"sum": sum, "max": max}\nresult = allowed_values[user_choice](values)',
            )

        if finding.category == "security":
            replacement = self._clean_snippet(finding.snippet) or 'token = os.getenv("TOKEN", "")'
            return Guidance(
                explanation=f"The analyzer flagged a security-sensitive pattern in `{finding.file_path}`.",
                root_cause=self._first_sentence(description) or "The code performs an operation that should be constrained, validated, or isolated more carefully.",
                impact="Security weaknesses can expose data, widen the attack surface, or let unsafe input reach critical parts of the system.",
                impact_level=impact_level,
                confidence=confidence,
                fix_effort="medium",
                suggestion="Reduce privilege, validate untrusted input before it reaches the dangerous call, and move secrets or dynamic behavior behind safer abstractions.",
                fix_patch=replacement,
            )

        if finding.category == "performance":
            replacement = self._clean_snippet(finding.snippet) or "cached_result = cache.get(key)\nif cached_result is None:\n    cached_result = compute_value(key)"
            return Guidance(
                explanation=f"The analyzer found a performance hotspot in `{finding.file_path}`.",
                root_cause=self._first_sentence(description) or "Repeated work, blocking I/O, or expensive loops are being executed in a path that runs often.",
                impact="As the input grows, this path can become slower and reduce throughput for the whole feature.",
                impact_level=impact_level,
                confidence=confidence,
                fix_effort="medium",
                suggestion="Move expensive work out of the hot path, cache repeated lookups, and make sure repeated loops only touch precomputed data.",
                fix_patch=replacement,
            )

        if finding.category == "code_smell":
            replacement = self._clean_snippet(finding.snippet) or self._fallback_docstring(finding)
            return Guidance(
                explanation=f"The flagged code in `{finding.file_path}` is harder to maintain than it needs to be.",
                root_cause=self._first_sentence(description) or "The implementation mixes too many responsibilities or uses a structure that obscures intent.",
                impact="Maintainability issues slow down reviews, increase regression risk, and make the repository harder to extend with confidence.",
                impact_level=impact_level,
                confidence=confidence,
                fix_effort="medium",
                suggestion="Make the implementation smaller, better named, and more explicit so the next change only touches one clear responsibility.",
                fix_patch=replacement,
            )

        replacement = self._clean_snippet(finding.snippet) or "return safe_result"
        return Guidance(
            explanation=f"The analyzer found a correctness issue in `{finding.file_path}`.",
            root_cause=self._first_sentence(description) or "The current code path uses control flow or an API contract in a way that can fail at runtime.",
            impact="If the flagged branch executes in production, it can return the wrong result or raise an avoidable runtime error.",
            impact_level=impact_level,
            confidence=confidence,
            fix_effort="medium",
            suggestion="Adjust the exact flagged block so the code follows the expected control flow or API contract and behaves safely under failure conditions.",
            fix_patch=replacement,
        )

    def _try_openai_enrichment(self, findings: list[Finding]) -> list[Finding] | None:
        prompt_payload = [
            {
                "id": finding.id,
                "title": finding.title,
                "rule_id": finding.rule_id,
                "description": finding.description,
                "severity": finding.severity,
                "explanation": finding.explanation,
                "root_cause": finding.root_cause,
                "impact": finding.impact,
                "impact_level": finding.impact_level,
                "confidence": finding.confidence,
                "fix_effort": finding.fix_effort,
                "snippet": finding.snippet,
                "suggestion": finding.suggestion,
                "fix_patch": finding.fix_patch,
            }
            for finding in findings[:40]
        ]
        body = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You improve code review findings. Respond with JSON only. "
                        "Return an object with an 'items' array. Each item must include id, explanation, root_cause, impact, "
                        "impact_level, confidence, fix_effort, suggestion, and fix_patch. Avoid generic advice and return code-only fix_patch values."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_payload)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=30.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            payload = json.loads(content)
            items = payload.get("items", []) if isinstance(payload, dict) else payload
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return None

        refined_lookup = {item["id"]: item for item in items if isinstance(item, dict) and item.get("id")}
        refined: list[Finding] = []
        for finding in findings:
            item = refined_lookup.get(finding.id)
            if not item:
                refined.append(finding)
                continue
            refined.append(
                finding.model_copy(
                    update={
                        "explanation": item.get("explanation") or finding.explanation,
                        "root_cause": item.get("root_cause") or finding.root_cause,
                        "impact": item.get("impact") or finding.impact,
                        "impact_level": item.get("impact_level") or finding.impact_level,
                        "confidence": int(item.get("confidence") or finding.confidence),
                        "fix_effort": item.get("fix_effort") or finding.fix_effort,
                        "suggestion": item.get("suggestion") or finding.suggestion,
                        "fix_patch": item.get("fix_patch") or finding.fix_patch,
                    }
                )
            )
        return refined

    def _impact_level_for_finding(self, finding: Finding) -> str:
        severity_map = {
            "Critical": "critical",
            "High": "high",
            "Medium": "medium",
            "Low": "low",
        }
        return severity_map.get(finding.severity, "medium")

    def _confidence_for_finding(self, finding: Finding) -> int:
        if finding.tool_source == "bandit":
            mapping = {"HIGH": 94, "MEDIUM": 82, "LOW": 68}
            raw_confidence = str(finding.metadata.get("confidence", "")).upper()
            return mapping.get(raw_confidence, 80)
        if finding.tool_source == "pylint":
            mapping = {"fatal": 92, "error": 88, "warning": 80, "refactor": 72, "convention": 70, "info": 66}
            return mapping.get((finding.raw_severity or "").lower(), 76)
        heuristic_map = {
            "long-function": 74,
            "deep-nesting": 78,
            "duplicate-code-pattern": 72,
            "bare-except": 88,
            "nested-loops": 76,
            "blocking-call-in-loop": 80,
            "open-without-context-manager": 82,
            "complex-conditional": 77,
        }
        return heuristic_map.get((finding.rule_id or "").lower(), 75)

    def _extract_missing_package(self, finding: Finding) -> str | None:
        description = finding.description or ""
        match = self.RULE_PACKAGE_PATTERN.search(description)
        if match:
            return match.group(1)
        snippet_match = re.search(r"^\d+:\s*(?:from|import)\s+([A-Za-z_][\w.]*)", finding.snippet or "", re.MULTILINE)
        if snippet_match:
            return snippet_match.group(1)
        return None

    def _extract_missing_symbol(self, description: str) -> tuple[str | None, str | None]:
        match = self.NO_NAME_PATTERN.search(description or "")
        if not match:
            return None, None
        return match.group(1), match.group(2)

    def _extract_not_callable_name(self, description: str) -> str | None:
        match = self.NOT_CALLABLE_PATTERN.search(description or "")
        return match.group(1) if match else None

    def _extract_unused_variable(self, description: str) -> str | None:
        match = self.UNUSED_VARIABLE_PATTERN.search(description or "")
        return match.group(1) if match else None

    def _extract_open_target(self, finding: Finding) -> str | None:
        snippet = self._clean_snippet(finding.snippet)
        match = re.search(r'open\(([^,]+),', snippet)
        return match.group(1).strip() if match else None

    def _extract_assignment_name(self, finding: Finding) -> str | None:
        snippet = self._clean_snippet(finding.snippet)
        match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", snippet)
        return match.group(1) if match else None

    def _build_docstring_template(self, finding: Finding) -> str:
        symbol_name = (finding.symbol_name or finding.title or "symbol").split(".")[-1]
        if finding.symbol_type == "class":
            return f'"""Represent {symbol_name}. """'
        if finding.symbol_type in {"function", "method"}:
            return f'"""Return the result for {symbol_name}. """'
        return f'"""Define the responsibilities for {symbol_name}. """'

    def _build_not_callable_fix(self, finding: Finding, object_name: str) -> str:
        source_line = self._extract_source_line(finding)
        if source_line:
            zero_arg_call = f"{object_name}()"
            if zero_arg_call in source_line:
                return source_line.replace(zero_arg_call, object_name, 1)
        return object_name

    def _build_unused_variable_fix(self, finding: Finding, variable_name: str) -> str:
        source_line = self._extract_source_line(finding)
        if source_line:
            assignment_pattern = re.compile(rf"^(\s*){re.escape(variable_name)}(\s*=.*)$")
            match = assignment_pattern.match(source_line)
            if match:
                return f"{match.group(1)}_{variable_name}{match.group(2)}"
            return source_line
        return f"_{variable_name} = value"

    def _fallback_docstring(self, finding: Finding) -> str:
        return self._build_docstring_template(finding)

    def _extract_source_line(self, finding: Finding) -> str:
        if not finding.snippet:
            return ""
        pattern = re.compile(rf"^\s*{finding.start_line}:\s?(.*)$")
        for line in finding.snippet.splitlines():
            match = pattern.match(line)
            if match:
                return match.group(1)
        return ""

    def _clean_snippet(self, snippet: str) -> str:
        if not snippet:
            return ""
        cleaned_lines = []
        for line in snippet.splitlines():
            cleaned_lines.append(re.sub(r"^\s*\d+:\s?", "", line))
        return "\n".join(cleaned_lines).strip()

    def _first_sentence(self, text: str) -> str:
        if not text:
            return ""
        sentence = text.strip().split(".")[0].strip()
        return sentence + "." if sentence else ""
