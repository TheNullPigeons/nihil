#!/usr/bin/env python3
"""Manage GitHub sources used to build Nihil images."""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


UPSTREAM_REPO = "TheNullPigeons/nihil-images"


class ImageSourceError(RuntimeError):
    """Error related to a local image source or GitHub repository."""


class ImageSourceManager:
    """Prepare the upstream repository and a personal nihil-images fork."""

    def __init__(self, config, formatter=None, upstream_repo: str | None = None):
        self.config = config
        self.formatter = formatter
        self.home = config.image_sources_home
        configured_repo = config._get("image_sources", "upstream_repo") if hasattr(config, "_get") else None
        self.upstream_repo = self._normalize_repo(upstream_repo or configured_repo or UPSTREAM_REPO)

    @staticmethod
    def _normalize_repo(value: str) -> str:
        raw = value.strip().rstrip("/")
        if raw.startswith(("https://", "http://")):
            raw = urlparse(raw).path.strip("/")
        if raw.endswith(".git"):
            raw = raw[:-4]
        if raw.count("/") != 1 or any(not part for part in raw.split("/")):
            raise ImageSourceError("The repository must use the owner/repo format or a GitHub URL.")
        return raw

    def _run(self, command: list[str], *, cwd: Path | None = None, capture: bool = True) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                check=True,
                text=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
            )
        except FileNotFoundError as exc:
            raise ImageSourceError(f"Command not found: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip()
            detail = f": {output}" if output else ""
            raise ImageSourceError(f"Command failed: {' '.join(command)}{detail}") from exc
        return (result.stdout or "").strip() if capture else ""

    def _gh_user(self) -> str:
        return self._run(["gh", "api", "user", "--jq", ".login"])

    def _default_branch(self, repo: str) -> str:
        return self._run([
            "gh", "repo", "view", repo,
            "--json", "defaultBranchRef",
            "--jq", ".defaultBranchRef.name",
        ]) or "main"

    def _ensure_git_remote(self, path: Path, name: str, url: str) -> None:
        remotes = self._run(["git", "remote"], cwd=path).splitlines()
        if name in remotes:
            current = self._run(["git", "remote", "get-url", name], cwd=path)
            if current != url:
                self._run(["git", "remote", "set-url", name, url], cwd=path)
        else:
            self._run(["git", "remote", "add", name, url], cwd=path)

    def ensure_personal_fork(self, *, variant: str) -> tuple[Path, str, str]:
        """Create or reuse the fork and prepare a customization branch."""
        self._run(["gh", "auth", "status"])
        login = self._gh_user()
        repo_name = self.upstream_repo.rsplit("/", 1)[1]
        fork_repo = f"{login}/{repo_name}"
        try:
            self._run(["gh", "repo", "view", fork_repo, "--json", "name"])
        except ImageSourceError:
            self._run(["gh", "repo", "fork", self.upstream_repo, "--clone=false"])

        branch = f"nihil/{variant}-custom"
        path = self.home / login / repo_name
        path.parent.mkdir(parents=True, exist_ok=True)
        fork_url = f"https://github.com/{fork_repo}.git"
        upstream_url = f"https://github.com/{self.upstream_repo}.git"

        if not (path / ".git").is_dir():
            self._run(["git", "clone", fork_url, str(path)])
        self._ensure_git_remote(path, "origin", fork_url)
        self._ensure_git_remote(path, "upstream", upstream_url)
        self._run(["git", "fetch", "upstream"], cwd=path)

        default_branch = self._default_branch(self.upstream_repo)
        self._run(["git", "fetch", "origin"], cwd=path)
        branches = self._run(["git", "branch", "--format=%(refname:short)"], cwd=path).splitlines()
        if branch in branches:
            self._run(["git", "switch", branch], cwd=path)
        else:
            self._run(["git", "switch", "-c", branch, f"upstream/{default_branch}"], cwd=path)

        self.config.set_image_source(
            active="personal",
            path=path,
            personal_repo=fork_repo,
            personal_branch=branch,
            upstream_path=self.config.image_sources_upstream_path,
            upstream_repo=self.upstream_repo,
        )
        return path, fork_repo, branch

    def ensure_upstream(self) -> Path:
        path = self.config.image_sources_upstream_path
        path.parent.mkdir(parents=True, exist_ok=True)
        upstream_url = f"https://github.com/{self.upstream_repo}.git"
        if not (path / ".git").is_dir():
            self._run(["git", "clone", upstream_url, str(path)])
        else:
            self._run(["git", "pull", "--ff-only"], cwd=path)
        self.config.set_image_source(
            active="upstream",
            path=path,
            personal_repo=self.config.personal_image_repo,
            personal_branch=self.config.personal_image_branch,
            upstream_path=path,
            upstream_repo=self.upstream_repo,
        )
        return path

    def trigger_build(self, *, wait: bool = False) -> None:
        """Trigger the Docker workflow on the active personal branch."""
        repo = self.config.personal_image_repo
        branch = self.config.personal_image_branch
        if not repo or not branch:
            raise ImageSourceError("No personal fork is configured.")
        self._run([
            "gh", "workflow", "run", "docker-build.yml",
            "--repo", repo, "--ref", branch,
        ])
        if wait:
            run_id = self._run([
                "gh", "run", "list", "--workflow", "docker-build.yml",
                "--repo", repo, "--branch", branch, "--limit", "1",
                "--json", "databaseId", "--jq", ".[0].databaseId",
            ])
            if not run_id:
                raise ImageSourceError("The workflow was dispatched, but its run ID could not be found.")
            self._run(["gh", "run", "watch", run_id, "--repo", repo, "--exit-status"], capture=False)

    def switch(self, source: str) -> Path:
        if source == "personal":
            path = self.config.personal_image_path
            if not path or not (path / ".git").is_dir():
                raise ImageSourceError("No personal fork is configured. Run 'nihil image customize' first.")
            branch = self.config.personal_image_branch
            if not branch:
                raise ImageSourceError("The personal fork branch is not configured.")
            self._run(["git", "switch", branch], cwd=path)
            self.config.set_image_source(
                active="personal", path=path,
                personal_repo=self.config.personal_image_repo,
                personal_branch=branch,
                upstream_path=self.config.image_sources_upstream_path,
                upstream_repo=self.upstream_repo,
            )
            return path
        if source == "upstream":
            return self.ensure_upstream()
        raise ImageSourceError("Unknown source. Choose 'upstream' or 'personal'.")
