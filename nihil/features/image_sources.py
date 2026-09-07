#!/usr/bin/env python3
"""Manage GitHub sources used to build Nihil images."""

from __future__ import annotations

import os
import subprocess
import shutil
import json
import time
from datetime import datetime, timedelta, timezone
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

    @staticmethod
    def _noninteractive_env() -> dict[str, str]:
        """Make git and gh fail loudly instead of waiting on a prompt nobody can see."""
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new")
        env["GH_PROMPT_DISABLED"] = "1"
        env.pop("SSH_ASKPASS", None)
        env.pop("SSH_ASKPASS_REQUIRE", None)
        return env

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        capture: bool = True,
        timeout: float | None = 300,
    ) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                check=True,
                text=True,
                env=self._noninteractive_env(),
                stdin=subprocess.DEVNULL if capture else None,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise ImageSourceError(f"Command not found: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ImageSourceError(
                f"Command timed out after {timeout:.0f}s: {' '.join(command)}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip()
            detail = f": {output}" if output else ""
            raise ImageSourceError(f"Command failed: {' '.join(command)}{detail}") from exc
        return (result.stdout or "").strip() if capture else ""

    def _gh_user(self) -> str:
        return self._run(["gh", "api", "user", "--jq", ".login"])

    def _default_git_protocol(self) -> str:
        """Use the protocol configured in gh, falling back to HTTPS."""
        try:
            protocol = self._run(["gh", "config", "get", "git_protocol", "--host", "github.com"])
        except ImageSourceError:
            protocol = ""
        if protocol == "ssh" and self._has_ssh_key():
            return "ssh"
        return "https"

    @staticmethod
    def _has_ssh_key() -> bool:
        """Report whether an SSH key is loaded in an agent or present on disk."""
        try:
            agent = subprocess.run(
                ["ssh-add", "-l"],
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            if agent.returncode == 0 and agent.stdout.strip():
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        ssh_dir = Path.home() / ".ssh"
        return ssh_dir.is_dir() and any(ssh_dir.glob("id_*"))

    def _default_branch(self, repo: str) -> str:
        return self._run([
            "gh", "repo", "view", repo,
            "--json", "defaultBranchRef",
            "--jq", ".defaultBranchRef.name",
        ]) or "main"

    def _enable_actions(self, repo: str) -> None:
        """Enable GitHub Actions for the fork so workflow dispatches work."""
        self._run([
            "gh", "api", "--method", "PUT",
            f"repos/{repo}/actions/permissions",
            "-F", "enabled=true",
            "-f", "allowed_actions=all",
        ])

    def _delete_remote_customization(self, fork_repo: str, branch: str) -> None:
        """Delete the customization branch and its variant packages if present."""
        try:
            self._run(["gh", "api", "--method", "DELETE", f"repos/{fork_repo}/git/refs/heads/{branch}"])
        except ImageSourceError as exc:
            message = str(exc)
            if not any(marker in message for marker in ("404", "Not Found", "Reference does not exist")):
                raise
        owner = fork_repo.split("/", 1)[0]
        for package in ("full", "ad", "web", "blueteam"):
            try:
                self._run(["gh", "api", "--method", "DELETE", f"users/{owner}/packages/container/{package}"])
            except ImageSourceError as exc:
                if "404" not in str(exc) and "Not Found" not in str(exc):
                    if "delete:packages" in str(exc) or "read:packages" in str(exc):
                        raise ImageSourceError(
                            f"{exc}\nRefresh GitHub CLI package scopes with:\n"
                            "  gh auth refresh -h github.com -s read:packages,delete:packages"
                        ) from exc
                    raise

    def _ensure_git_remote(self, path: Path, name: str, url: str) -> None:
        remotes = self._run(["git", "remote"], cwd=path).splitlines()
        if name in remotes:
            current = self._run(["git", "remote", "get-url", name], cwd=path)
            if current != url:
                self._run(["git", "remote", "set-url", name, url], cwd=path)
        else:
            self._run(["git", "remote", "add", name, url], cwd=path)

    def ensure_personal_fork(
        self,
        *,
        variant: str,
        git_protocol: str | None = None,
        delete_existing: bool | str = False,
    ) -> tuple[Path, str, str]:
        """Create or reuse the fork and prepare a customization branch."""
        if git_protocol in (None, "auto"):
            git_protocol = self._default_git_protocol()
        if git_protocol not in {"ssh", "https"}:
            raise ImageSourceError("Git protocol must be 'ssh', 'https' or 'auto'.")
        login = self._gh_user()
        repo_name = self.upstream_repo.rsplit("/", 1)[1]
        fork_repo = f"{login}/{repo_name}"
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            self._run(["gh", "repo", "view", fork_repo, "--json", "name"])
        except ImageSourceError:
            # Fork from outside any git repository: inside one, gh offers to rewrite
            # the local remotes through a prompt the caller never sees.
            self._run(
                ["gh", "repo", "fork", self.upstream_repo, "--clone=false"],
                cwd=self.home,
            )
        self._enable_actions(fork_repo)

        branch = f"nihil/{variant}-custom"
        path = self.home / login / repo_name
        path.parent.mkdir(parents=True, exist_ok=True)
        if git_protocol == "ssh":
            fork_url = f"git@github.com:{fork_repo}.git"
            upstream_url = f"git@github.com:{self.upstream_repo}.git"
        else:
            fork_url = f"https://github.com/{fork_repo}.git"
            upstream_url = f"https://github.com/{self.upstream_repo}.git"

        delete_mode = "local" if delete_existing is True else delete_existing
        if delete_mode in {"distant", "all"}:
            self._delete_remote_customization(fork_repo, branch)
        if delete_mode in {"local", "all"} and path.exists():
            shutil.rmtree(path)

        if not (path / ".git").is_dir():
            try:
                self._run(["git", "clone", fork_url, str(path)])
            except ImageSourceError as exc:
                if git_protocol == "ssh":
                    raise ImageSourceError(
                        f"{exc}\nSSH clone failed. Retry with: nihil image customize "
                        f"{variant} --git-protocol https"
                    ) from exc
                raise
        self._ensure_git_remote(path, "origin", fork_url)
        self._ensure_git_remote(path, "upstream", upstream_url)
        self._run(["git", "fetch", "upstream"], cwd=path)

        default_branch = self._default_branch(self.upstream_repo)
        self._run(["git", "fetch", "origin"], cwd=path)
        branches = self._run(["git", "branch", "--format=%(refname:short)"], cwd=path).splitlines()
        remote_branches = self._run(
            ["git", "branch", "--remotes", "--format=%(refname:short)"], cwd=path
        ).splitlines()
        if branch in branches:
            self._run(["git", "switch", branch], cwd=path)
        elif f"origin/{branch}" in remote_branches:
            self._run(["git", "switch", "-c", branch, "--track", f"origin/{branch}"], cwd=path)
        else:
            self._run(["git", "switch", "-c", branch, f"upstream/{default_branch}"], cwd=path)

        return path, fork_repo, branch

    def activate_personal(self, path: Path, fork_repo: str, branch: str) -> None:
        """Activate a personal source after customization completes successfully."""
        self.config.set_image_source(
            active="personal",
            path=path,
            personal_repo=fork_repo,
            personal_branch=branch,
            upstream_path=self.config.image_sources_upstream_path,
            upstream_repo=self.upstream_repo,
        )

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

    def trigger_build(self, *, variant: str = "all", wait: bool = False) -> None:
        """Trigger the Docker workflow on the active personal branch."""
        if variant not in {"all", "full", "ad", "web", "blueteam"}:
            raise ImageSourceError("Unknown image variant. Choose all, full, ad, web, or blueteam.")
        repo = self.config.personal_image_repo
        branch = self.config.personal_image_branch
        if not repo or not branch:
            raise ImageSourceError("No personal fork is configured.")
        self._enable_actions(repo)
        dispatch_started = datetime.now(timezone.utc)
        self._run([
            "gh", "workflow", "run", "docker-build.yml",
            "--repo", repo, "--ref", branch,
            "-f", f"variant={variant}",
        ])
        if wait:
            run_id = ""
            deadline = time.monotonic() + 30
            earliest_run = dispatch_started - timedelta(seconds=2)
            while time.monotonic() < deadline:
                raw_runs = self._run([
                    "gh", "run", "list", "--workflow", "docker-build.yml",
                    "--repo", repo, "--branch", branch, "--limit", "10",
                    "--json", "databaseId,createdAt",
                ])
                try:
                    runs = json.loads(raw_runs or "[]")
                except json.JSONDecodeError:
                    runs = []
                for run in runs:
                    try:
                        created_at = datetime.fromisoformat(
                            run["createdAt"].replace("Z", "+00:00")
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
                    if created_at >= earliest_run:
                        run_id = str(run.get("databaseId", ""))
                        break
                if run_id:
                    break
                time.sleep(1)
            if not run_id:
                raise ImageSourceError(
                    "The workflow was dispatched, but its new run ID could not be found."
                )
            self._run(
                ["gh", "run", "watch", run_id, "--repo", repo, "--exit-status"],
                capture=False,
                timeout=None,
            )

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
