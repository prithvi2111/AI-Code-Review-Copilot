from __future__ import annotations

import ast
from pathlib import Path

from app.schemas import FileStructure, RepositorySnapshot, StructureMap, SymbolInfo


class StructureService:
    def build(self, snapshot: RepositorySnapshot) -> StructureMap:
        files: dict[str, FileStructure] = {}
        repo_root = Path(snapshot.local_path)
        for file_path in snapshot.python_files:
            absolute_path = repo_root / file_path
            source = absolute_path.read_text(encoding="utf-8", errors="ignore")
            symbols: list[SymbolInfo] = []
            imports: list[str] = []
            line_count = max(1, len(source.splitlines()))
            symbols.append(
                SymbolInfo(
                    file_path=file_path,
                    name=Path(file_path).stem,
                    qualified_name=Path(file_path).stem,
                    symbol_type="module",
                    start_line=1,
                    end_line=line_count,
                )
            )
            try:
                tree = ast.parse(source)
            except SyntaxError:
                files[file_path] = FileStructure(file_path=file_path, imports=imports, symbols=symbols)
                continue

            self._collect_imports(tree, imports)
            self._collect_symbols(tree, file_path, symbols, parent_name=None, class_name=None)
            files[file_path] = FileStructure(file_path=file_path, imports=sorted(set(imports)), symbols=symbols)

        return StructureMap(files=files)

    def _collect_imports(self, tree: ast.AST, imports: list[str]) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

    def _collect_symbols(
        self,
        node: ast.AST,
        file_path: str,
        symbols: list[SymbolInfo],
        *,
        parent_name: str | None,
        class_name: str | None,
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualified_name = child.name if not parent_name else f"{parent_name}.{child.name}"
                symbols.append(
                    SymbolInfo(
                        file_path=file_path,
                        name=child.name,
                        qualified_name=qualified_name,
                        symbol_type="class",
                        start_line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno),
                        parent_name=parent_name,
                    )
                )
                self._collect_symbols(child, file_path, symbols, parent_name=qualified_name, class_name=child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_method = class_name is not None
                symbol_type = "method" if is_method else "function"
                qualified_name = child.name if not parent_name else f"{parent_name}.{child.name}"
                symbols.append(
                    SymbolInfo(
                        file_path=file_path,
                        name=child.name,
                        qualified_name=qualified_name,
                        symbol_type=symbol_type,
                        start_line=child.lineno,
                        end_line=getattr(child, "end_lineno", child.lineno),
                        parent_name=parent_name,
                    )
                )
                self._collect_symbols(child, file_path, symbols, parent_name=qualified_name, class_name=class_name)
            else:
                self._collect_symbols(child, file_path, symbols, parent_name=parent_name, class_name=class_name)
