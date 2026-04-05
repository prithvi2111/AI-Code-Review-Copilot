from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from app.schemas import Finding, RepositorySnapshot


class HeuristicAnalyzer:
    LONG_FUNCTION_THRESHOLD = 50
    DEEP_NESTING_THRESHOLD = 4
    COMPLEX_CONDITIONAL_THRESHOLD = 3

    def run(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        repo_root = Path(snapshot.local_path)
        for file_path in snapshot.python_files:
            absolute_path = repo_root / file_path
            source = absolute_path.read_text(encoding="utf-8", errors="ignore")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            findings.extend(self._analyze_functions(file_path, tree))
            findings.extend(self._analyze_file_patterns(file_path, source))
        return findings

    def _analyze_functions(self, file_path: str, tree: ast.AST) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno)
                function_length = end_line - node.lineno + 1
                if function_length >= self.LONG_FUNCTION_THRESHOLD:
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "code_smell",
                            "Function is unusually long",
                            "This function likely does too much, making it harder to test and maintain.",
                            "long-function",
                            "medium",
                        )
                    )
                nesting_depth = self._max_nesting_depth(node)
                if nesting_depth >= self.DEEP_NESTING_THRESHOLD:
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "code_smell",
                            "Control flow is deeply nested",
                            "Deep nesting makes the execution path hard to understand and increases maintenance cost.",
                            "deep-nesting",
                            "medium",
                        )
                    )
                if self._has_nested_loops(node):
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "performance",
                            "Nested loops detected",
                            "Nested loops can create avoidable quadratic work in hot code paths.",
                            "nested-loops",
                            "medium",
                        )
                    )
                if self._contains_blocking_call_inside_loop(node):
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "performance",
                            "Blocking call detected inside loop",
                            "Blocking I/O or sleeps inside loops can degrade throughput and increase response times.",
                            "blocking-call-in-loop",
                            "high",
                        )
                    )
                if self._has_bare_except(node):
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "bug",
                            "Bare except hides failures",
                            "Catching every exception without handling specific failures can mask bugs and operational issues.",
                            "bare-except",
                            "high",
                        )
                    )
                if self._opens_file_without_context_manager(node):
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "bug",
                            "File opened without context manager",
                            "Using open() without a context manager risks leaking file descriptors on error paths.",
                            "open-without-context-manager",
                            "medium",
                        )
                    )
                if self._complex_conditionals(node):
                    findings.append(
                        self._finding(
                            file_path,
                            node.lineno,
                            end_line,
                            "code_smell",
                            "Conditional logic is overly complex",
                            "High conditional branching in a single function is a sign the logic should be decomposed.",
                            "complex-conditional",
                            "medium",
                        )
                    )
        return findings

    def _analyze_file_patterns(self, file_path: str, source: str) -> list[Finding]:
        findings: list[Finding] = []
        source_lines = source.splitlines()
        lines = [line.strip() for line in source_lines if line.strip()]
        repeated_lines = Counter(lines)
        for content, count in repeated_lines.items():
            if count >= 4 and len(content) > 24:
                line_number = next(index for index, value in enumerate(source_lines, start=1) if value.strip() == content)
                findings.append(
                    self._finding(
                        file_path,
                        line_number,
                        line_number,
                        "code_smell",
                        "Repeated code pattern detected",
                        "Repeated logic often indicates a shared helper or abstraction is missing.",
                        "duplicate-code-pattern",
                        "low",
                    )
                )
                break
        return findings

    def _max_nesting_depth(self, node: ast.AST) -> int:
        def depth(current: ast.AST, level: int = 0) -> int:
            max_depth = level
            for child in ast.iter_child_nodes(current):
                next_level = level + 1 if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.Match)) else level
                max_depth = max(max_depth, depth(child, next_level))
            return max_depth

        return depth(node)

    def _has_nested_loops(self, node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for nested in ast.walk(child):
                    if nested is not child and isinstance(nested, (ast.For, ast.While)):
                        return True
        return False

    def _contains_blocking_call_inside_loop(self, node: ast.AST) -> bool:
        blocking_terms = {"sleep", "urlopen", "requests.get", "requests.post", "requests.put"}
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for nested in ast.walk(child):
                    if isinstance(nested, ast.Call):
                        call_name = self._call_name(nested.func)
                        if call_name in blocking_terms:
                            return True
        return False

    def _has_bare_except(self, node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.ExceptHandler) and child.type is None:
                return True
        return False

    def _opens_file_without_context_manager(self, node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.With):
                with_calls = {self._call_name(item.context_expr.func) for item in child.items if isinstance(item.context_expr, ast.Call)}
                if "open" in with_calls:
                    return False
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and self._call_name(child.func) == "open":
                return True
        return False

    def _complex_conditionals(self, node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                bool_ops = sum(1 for nested in ast.walk(child.test) if isinstance(nested, ast.BoolOp))
                comparators = sum(1 for nested in ast.walk(child.test) if isinstance(nested, ast.Compare))
                if bool_ops + comparators >= self.COMPLEX_CONDITIONAL_THRESHOLD:
                    return True
        return False

    def _call_name(self, func: ast.AST) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            prefix = self._call_name(func.value)
            return f"{prefix}.{func.attr}" if prefix else func.attr
        return ""

    def _finding(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        category: str,
        title: str,
        description: str,
        rule_id: str,
        severity: str,
    ) -> Finding:
        return Finding(
            category=category,
            title=title,
            description=description,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            tool_source="heuristic",
            rule_id=rule_id,
            raw_severity=severity,
        )
