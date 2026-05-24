#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export server-hub VRC feed JSON for GitHub Pages.")
    parser.add_argument(
        "--endpoint",
        default="https://7daystodie.jp/wp-json/sevendtd/v1/server-hub/vrc",
        help="Server hub VRC endpoint. Default: https://7daystodie.jp/wp-json/sevendtd/v1/server-hub/vrc",
    )
    parser.add_argument(
        "--host-header",
        default="",
        help="Optional Host header for local vhost access, e.g. 7daystodie.jp",
    )
    parser.add_argument("--limit", type=int, default=8, help="Feed item limit. Default: 8")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds. Default: 20")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--git-repo", default="", help="Optional git repository path for commit/push.")
    parser.add_argument("--commit-message", default="Update Server Hub VRC feed", help="Git commit message.")
    parser.add_argument("--push", action="store_true", help="Push to origin after commit.")
    return parser.parse_args()


def build_endpoint(endpoint: str, limit: int) -> str:
    cleaned = (endpoint or "").strip()
    separator = "&" if "?" in cleaned else "?"
    return f"{cleaned}{separator}limit={max(1, min(limit, 24))}"


def fetch_payload(url: str, timeout: int, host_header: str) -> dict:
    request = Request(url)
    request.add_header("User-Agent", "WordPressServerHubVrcExporter/1.0")
    if host_header:
        request.add_header("Host", host_header)

    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")

    data = json.loads(body)
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("server hub VRC response is invalid")
    return data


def write_payload(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def commit_and_push(repo_path: Path, output_path: Path, commit_message: str, push: bool) -> None:
    try:
        relative_output = output_path.resolve().relative_to(repo_path.resolve())
    except ValueError as exc:
        raise RuntimeError("output path must be inside git repo") from exc

    add_result = run_git(repo_path, "add", "--", str(relative_output))
    if add_result.returncode != 0:
        raise RuntimeError(add_result.stderr.strip() or add_result.stdout.strip() or "git add failed")

    diff_result = run_git(repo_path, "diff", "--cached", "--quiet", "--", str(relative_output))
    if diff_result.returncode == 0:
        print("No git changes to commit.")
        return
    if diff_result.returncode not in (0, 1):
        raise RuntimeError(diff_result.stderr.strip() or diff_result.stdout.strip() or "git diff failed")

    commit_result = run_git(repo_path, "commit", "-m", commit_message)
    if commit_result.returncode != 0:
        raise RuntimeError(commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed")
    print(commit_result.stdout.strip() or commit_result.stderr.strip())

    if not push:
        return

    push_result = run_git(repo_path, "push", "origin", "HEAD")
    if push_result.returncode != 0:
        raise RuntimeError(push_result.stderr.strip() or push_result.stdout.strip() or "git push failed")
    print(push_result.stdout.strip() or push_result.stderr.strip())


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_env_file(repo_root / ".env")
    args = parse_args()

    endpoint = build_endpoint(args.endpoint, args.limit)
    output_path = Path(args.output).expanduser().resolve()
    repo_path = Path(args.git_repo).expanduser().resolve() if args.git_repo else None

    payload = fetch_payload(endpoint, args.timeout, args.host_header.strip())
    write_payload(output_path, payload)
    print(f"Wrote server hub VRC feed to {output_path}")

    if repo_path is not None:
        commit_and_push(repo_path, output_path, args.commit_message, args.push)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)