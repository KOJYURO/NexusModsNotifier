#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


THUMBNAIL_PLACEHOLDER_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAC0AUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD56ooorzT7UKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACisqiun6v5nif2x/c/H/gGrRWVRR9X8w/tj+5+P/ANWisqij6v5h/bH9z8f+AatFZVFH1fzD+2P7n4/wDANWisqij6v5h/bH9z8f8AgGrRWVRR9X8w/tj+5+P/AADVorKoo+r+Yf2x/c/H/gGrRWVRR9X8w/tj+5+P/ANWisqij6v5h/bH9z8f+AatFZVFH1fzD+2P7n4/8A1aKyqKPq/mH9sf3Px/4Bq0VlUUfV/MP7Y/ufj/AMA1aKyqKPq/mH9sf3Px/wCAatFZVFH1fzD+2P7n4/8AANWisqij6v5h/bH9z8f+AatFZVFH1fzD+2P7n4/8A1aKyqKPq/mH9sf3Px/4Bq0VlUUfV/MP7Y/ufj/wDVorKoo+r+Yf2x/c/H/gGrRWVRR9X8w/tj+5+P8AwAooorpPFCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigD/2Q=="
)


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
    parser = argparse.ArgumentParser(description="Export Twitch VRC playlist JSON for GitHub Pages.")
    parser.add_argument(
        "--endpoint",
        default="",
        help="Twitch playlist endpoint. Default: http://127.0.0.1:${API_PORT}/twitch/vrc/playlist",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="X-Api-Key header value. Default: BOT_API_SHARED_KEY from .env or environment.",
    )
    parser.add_argument("--limit", type=int, default=20, help="Playlist item limit. Default: 20")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds. Default: 20")
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    parser.add_argument("--git-repo", default="", help="Optional git repository path for commit/push.")
    parser.add_argument(
        "--public-base-url",
        default="",
        help="Optional public base URL. Auto-detected from --git-repo when possible.",
    )
    parser.add_argument("--thumbnail-count", type=int, default=24, help="Fixed mirrored thumbnail count. Default: 24")
    parser.add_argument("--thumbnail-prefix", default="twitch_thumb_", help="Mirrored thumbnail filename prefix.")
    parser.add_argument("--commit-message", default="Update Twitch VRC playlist", help="Git commit message.")
    parser.add_argument("--push", action="store_true", help="Push to origin after commit.")
    return parser.parse_args()


def build_endpoint(endpoint: str, limit: int) -> str:
    cleaned = (endpoint or "").strip()
    if not cleaned:
        api_port = (os.getenv("API_PORT", "8787") or "8787").strip()
        cleaned = f"http://127.0.0.1:{api_port}/twitch/vrc/playlist"
    separator = "&" if "?" in cleaned else "?"
    return f"{cleaned}{separator}limit={max(1, min(limit, 100))}"


def fetch_payload(url: str, api_key: str, timeout: int) -> dict:
    request = Request(url)
    request.add_header("User-Agent", "WordPressTwitchVrcPlaylistExporter/1.0")
    if api_key:
        request.add_header("X-Api-Key", api_key)

    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")

    data = json.loads(body)
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("playlist response is invalid")
    return data


def write_payload(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_public_base_url(repo_path: Path | None, explicit_base_url: str) -> str:
    cleaned = str(explicit_base_url or "").strip().rstrip("/")
    if cleaned:
        return cleaned

    if repo_path is None:
        return ""

    remote_result = run_git(repo_path, "remote", "get-url", "origin")
    if remote_result.returncode != 0:
        return ""

    remote = (remote_result.stdout or remote_result.stderr or "").strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote)
    if not match:
        return ""

    owner = match.group("owner")
    repo = match.group("repo")
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io"

    return f"https://{owner}.github.io/{repo}"


def resolve_public_dir_url(repo_path: Path | None, output_path: Path, public_base_url: str) -> str:
    base_url = public_base_url.rstrip("/")
    if not base_url:
        return ""

    if repo_path is None:
        return base_url

    docs_root = (repo_path / "docs").resolve()
    output_dir = output_path.parent.resolve()

    try:
        relative_dir = output_dir.relative_to(docs_root)
    except ValueError:
        try:
            relative_dir = output_dir.relative_to(repo_path.resolve())
        except ValueError:
            return base_url

    relative_dir_text = relative_dir.as_posix().strip(".").strip("/")
    if not relative_dir_text:
        return base_url

    return f"{base_url}/{relative_dir_text}"


def build_thumbnail_file_name(prefix: str, index: int) -> str:
    return f"{prefix}{index:02d}.jpg"


def build_public_file_url(public_dir_url: str, file_name: str) -> str:
    return f"{public_dir_url.rstrip('/')}/{file_name}"


def fetch_binary(url: str, timeout: int) -> bytes:
    request = Request(url)
    request.add_header("User-Agent", "WordPressTwitchVrcPlaylistExporter/1.0")
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def write_placeholder_thumbnail(output_path: Path) -> None:
    output_path.write_bytes(base64.b64decode(THUMBNAIL_PLACEHOLDER_JPEG_BASE64))


def write_thumbnail_file(source_url: str, output_path: Path, timeout: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_url:
        write_placeholder_thumbnail(output_path)
        return

    try:
        output_path.write_bytes(fetch_binary(source_url, timeout))
    except Exception as exc:
        print(f"thumbnail download failed for {source_url}: {exc}", file=sys.stderr)
        write_placeholder_thumbnail(output_path)


def mirror_playlist_thumbnails(
    payload: dict,
    output_path: Path,
    public_dir_url: str,
    thumbnail_prefix: str,
    thumbnail_count: int,
    timeout: int,
) -> list[Path]:
    items = payload.get("items")
    if not isinstance(items, list) or not public_dir_url:
        return []

    written_files: list[Path] = []
    fixed_count = max(0, thumbnail_count)
    for index in range(fixed_count):
        file_name = build_thumbnail_file_name(thumbnail_prefix, index)
        local_path = output_path.parent / file_name
        public_url = build_public_file_url(public_dir_url, file_name)

        source_url = ""
        if index < len(items) and isinstance(items[index], dict):
            source_url = str(items[index].get("thumbnail_url", "") or "").strip()

        write_thumbnail_file(source_url, local_path, timeout)
        written_files.append(local_path)

        if index < len(items) and isinstance(items[index], dict):
            if source_url and source_url != public_url:
                items[index]["thumbnail_source_url"] = source_url
                items[index]["image_source_url"] = source_url
            items[index]["thumbnail_url"] = public_url
            items[index]["image_url"] = public_url

    return written_files


def run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=False,
        text=True,
        capture_output=True,
    )


def commit_and_push(repo_path: Path, output_paths: list[Path], commit_message: str, push: bool) -> None:
    relative_outputs: list[str] = []
    for output_path in output_paths:
        try:
            relative_output = output_path.resolve().relative_to(repo_path.resolve())
        except ValueError as exc:
            raise RuntimeError("output path must be inside git repo") from exc
        relative_outputs.append(str(relative_output))

    # GitHub Pages 側へ置くファイルだけを stage する。
    add_result = run_git(repo_path, "add", "--", *relative_outputs)
    if add_result.returncode != 0:
        raise RuntimeError(add_result.stderr.strip() or add_result.stdout.strip() or "git add failed")

    diff_result = run_git(repo_path, "diff", "--cached", "--quiet", "--", *relative_outputs)
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
    api_key = (args.api_key or os.getenv("BOT_API_SHARED_KEY", "") or "").strip()
    output_path = Path(args.output).expanduser().resolve()
    repo_path = Path(args.git_repo).expanduser().resolve() if args.git_repo else None

    payload = fetch_payload(endpoint, api_key, args.timeout)
    public_base_url = detect_public_base_url(repo_path, args.public_base_url)
    public_dir_url = resolve_public_dir_url(repo_path, output_path, public_base_url)
    mirrored_thumbnail_paths = mirror_playlist_thumbnails(
        payload,
        output_path,
        public_dir_url,
        args.thumbnail_prefix,
        args.thumbnail_count,
        args.timeout,
    )
    write_payload(output_path, payload)
    print(f"Wrote playlist JSON to {output_path}")
    if mirrored_thumbnail_paths:
        print(f"Wrote {len(mirrored_thumbnail_paths)} mirrored thumbnails to {output_path.parent}")
    elif public_base_url:
        print("Skipped thumbnail mirroring because no playlist items were available.")
    else:
        print("Skipped thumbnail mirroring because public base URL could not be resolved.")

    if repo_path is not None:
        commit_and_push(repo_path, [output_path, *mirrored_thumbnail_paths], args.commit_message, args.push)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)