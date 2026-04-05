from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from app.schemas import RepositorySnapshot, SourceFileInfo

GITHUB_REPO_PATTERN = re.compile(r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$")


class IngestionService:
    IGNORED_DIRECTORIES = {
        ".git",
        ".idea",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "vendor",
        ".next",
        ".turbo",
    }
    IGNORED_SUFFIXES = {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".zip",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".ico",
        ".pdf",
        ".jar",
        ".lock",
    }
    LANGUAGE_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".go": "Go",
        ".rb": "Ruby",
        ".rs": "Rust",
        ".php": "PHP",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".json": "JSON",
        ".toml": "TOML",
        ".md": "Markdown",
    }

    def validate_repo_url(self, repo_url: str) -> tuple[str, str]:
        match = GITHUB_REPO_PATTERN.match(repo_url.strip())
        if not match:
            raise ValueError("Only public GitHub repository URLs in the format https://github.com/owner/repo are supported.")
        return match.group("owner"), match.group("repo")

    def ingest(self, repo_url: str, destination_dir: Path) -> RepositorySnapshot:
        owner, repo = self.validate_repo_url(repo_url)
        destination_dir.mkdir(parents=True, exist_ok=True)
        clone_dir = destination_dir / "repo"
        metadata = self._fetch_repo_metadata(owner, repo)
        clone_success = self._clone_with_git(repo_url, clone_dir)
        if not clone_success:
            self._download_archive(owner, repo, metadata["default_branch"], clone_dir)
        return self.snapshot_from_local_path(
            clone_dir,
            repo_url=repo_url,
            repo_name=metadata["full_name"],
            default_branch=metadata["default_branch"],
        )

    def snapshot_from_local_path(
        self,
        local_path: Path,
        *,
        repo_url: str,
        repo_name: str,
        default_branch: str,
    ) -> RepositorySnapshot:
        files: list[SourceFileInfo] = []
        python_files: list[str] = []
        languages: dict[str, int] = {}
        total_loc = 0

        for root, dirs, filenames in os.walk(local_path):
            dirs[:] = [name for name in dirs if name not in self.IGNORED_DIRECTORIES]
            for filename in filenames:
                absolute_path = Path(root) / filename
                relative_path = absolute_path.relative_to(local_path).as_posix()
                if self._should_skip_file(absolute_path, filename):
                    continue
                if self._is_binary_file(absolute_path):
                    continue
                language = self._detect_language(absolute_path)
                loc = self._count_loc(absolute_path)
                total_loc += loc
                is_python = absolute_path.suffix == ".py"
                files.append(
                    SourceFileInfo(
                        path=relative_path,
                        absolute_path=str(absolute_path),
                        language=language,
                        is_python=is_python,
                        loc=loc,
                    )
                )
                languages[language] = languages.get(language, 0) + 1
                if is_python:
                    python_files.append(relative_path)

        return RepositorySnapshot(
            repo_url=repo_url,
            repo_name=repo_name,
            default_branch=default_branch,
            languages=dict(sorted(languages.items(), key=lambda item: item[0])),
            total_files=len(files),
            total_loc=total_loc,
            local_path=str(local_path),
            files=sorted(files, key=lambda item: item.path),
            python_files=sorted(python_files),
        )

    def _clone_with_git(self, repo_url: str, clone_dir: Path) -> bool:
        git_executable = shutil.which("git")
        if not git_executable:
            return False
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
        command = [git_executable, "clone", "--depth", "1", repo_url, str(clone_dir)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode == 0

    def _fetch_repo_metadata(self, owner: str, repo: str) -> dict[str, str]:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"User-Agent": "ai-code-review-copilot"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ValueError(f"Unable to access GitHub repository metadata: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Unable to contact GitHub: {exc.reason}") from exc

        default_branch = payload.get("default_branch") or "main"
        full_name = payload.get("full_name") or f"{owner}/{repo}"
        return {"default_branch": default_branch, "full_name": full_name}

    def _download_archive(self, owner: str, repo: str, branch: str, clone_dir: Path) -> None:
        clone_dir.mkdir(parents=True, exist_ok=True)
        archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
        request = urllib.request.Request(archive_url, headers={"User-Agent": "ai-code-review-copilot"})
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            archive_path = temp_dir / "repo.zip"
            with urllib.request.urlopen(request, timeout=20) as response:
                archive_path.write_bytes(response.read())
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(temp_dir)
            extracted_root = next(path for path in temp_dir.iterdir() if path.is_dir())
            for child in extracted_root.iterdir():
                destination = clone_dir / child.name
                if child.is_dir():
                    shutil.copytree(child, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, destination)

    def _should_skip_file(self, absolute_path: Path, filename: str) -> bool:
        suffix = absolute_path.suffix.lower()
        if suffix in self.IGNORED_SUFFIXES:
            return True
        if suffix == ".js" and absolute_path.name.endswith(".min.js"):
            return True
        if filename in {"poetry.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
            return True
        return False

    @staticmethod
    def _is_binary_file(path: Path) -> bool:
        try:
            chunk = path.read_bytes()[:1024]
        except OSError:
            return True
        return b"\0" in chunk

    def _detect_language(self, path: Path) -> str:
        return self.LANGUAGE_MAP.get(path.suffix.lower(), "Other")

    @staticmethod
    def _count_loc(path: Path) -> int:
        try:
            return len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
