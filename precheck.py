"""
Pre-submission validator for Bug Triage OpenEnv.

Checks:
1) HF Space /reset returns HTTP 200
2) docker build succeeds
3) openenv validate succeeds
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def log(msg: str) -> None:
    print(msg)


def normalize_space_url(space_url: str) -> str:
    """Accept either hf.space or huggingface.co/spaces URLs."""
    value = space_url.strip().rstrip("/")
    match = re.match(r"^https?://huggingface\.co/spaces/([^/]+)/([^/]+)$", value)
    if match:
        owner, space = match.groups()
        slug = f"{owner}-{space}".replace("_", "-")
        return f"https://{slug}.hf.space"
    return value


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 1800) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def check_space(space_url: str, timeout_seconds: int) -> tuple[bool, str]:
    normalized_url = normalize_space_url(space_url)
    reset_url = f"{normalized_url.rstrip('/')}/reset"
    req = urllib.request.Request(reset_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            code = int(resp.getcode())
            if code == 200:
                return True, f"HF Space /reset returned HTTP {code} ({normalized_url})"
            return False, f"HF Space /reset returned HTTP {code} (expected 200) ({normalized_url})"
    except urllib.error.HTTPError as err:
        return False, f"HF Space /reset returned HTTP {err.code} (expected 200) ({normalized_url})"
    except Exception as err:
        return False, f"HF Space check failed: {err} ({normalized_url})"


def check_docker_build(repo_dir: Path, docker_timeout: int) -> tuple[bool, str]:
    if shutil.which("docker") is None:
        return False, "docker command not found"

    if (repo_dir / "Dockerfile").exists():
        context = repo_dir
    elif (repo_dir / "server" / "Dockerfile").exists():
        context = repo_dir / "server"
    else:
        return False, "No Dockerfile found in repo root or server/"

    code, out, err = run(["docker", "build", str(context)], timeout=docker_timeout)
    if code == 0:
        return True, f"Docker build succeeded ({context})"

    combined = (out + "\n" + err).strip()
    combined_lower = combined.lower()
    if (
        "failed to connect to the docker api" in combined_lower
        or "dockerdesktoplinuxengine" in combined_lower
        or ("access is denied" in combined_lower and ".docker\\buildx\\instances" in combined_lower)
    ):
        return False, "Docker daemon is not running or is not accessible to the current user"

    tail = "\n".join(combined.splitlines()[-20:])
    return False, f"Docker build failed (timeout={docker_timeout}s)\n{tail}"


def check_openenv_validate(repo_dir: Path) -> tuple[bool, str]:
    local_cli_candidates = [
        repo_dir / "venv" / "Scripts" / "openenv.exe",
        repo_dir / "venv" / "bin" / "openenv",
    ]

    cmd = None
    if shutil.which("openenv") is not None:
        cmd = ["openenv", "validate"]
    else:
        for candidate in local_cli_candidates:
            if candidate.exists():
                cmd = [str(candidate), "validate"]
                break

    if cmd is None:
        # Fallback for environments where console scripts are not on PATH.
        cmd = [sys.executable, "-m", "openenv.cli", "validate"]

    code, out, err = run(cmd, cwd=repo_dir, timeout=600)
    if code == 0:
        msg = out or "openenv validate passed"
        return True, msg

    base = "openenv validate failed"
    hint = "Install with: pip install openenv-core" if "No module named" in err else ""
    details = "\n".join(x for x in [base, hint, out, err] if x).strip()
    return False, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-submit validator")
    parser.add_argument(
        "--repo-dir",
        default=".",
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--space-url",
        default=os.getenv("HF_SPACE_URL", ""),
        help="HF Space base URL (or set HF_SPACE_URL)",
    )
    parser.add_argument(
        "--skip-space",
        action="store_true",
        help="Skip HF Space /reset check",
    )
    parser.add_argument(
        "--docker-timeout",
        type=int,
        default=1800,
        help="Docker build timeout in seconds (default: 1800)",
    )
    parser.add_argument(
        "--http-timeout",
        type=int,
        default=20,
        help="HTTP timeout for HF Space check in seconds",
    )

    args = parser.parse_args()
    repo_dir = Path(args.repo_dir).resolve()

    if not repo_dir.exists():
        log(f"FAIL: repo dir does not exist: {repo_dir}")
        return 1

    log("========================================")
    log("Pre-submission Validation")
    log("========================================")

    all_ok = True

    # Step 1: HF Space /reset
    log("Step 1/3: Checking HF Space /reset")
    if args.skip_space:
        log("SKIP: HF Space check skipped")
    else:
        if not args.space_url:
            log("FAIL: --space-url (or HF_SPACE_URL) is required unless --skip-space is used")
            all_ok = False
        else:
            ok, msg = check_space(args.space_url, args.http_timeout)
            log(("PASS: " if ok else "FAIL: ") + msg)
            all_ok = all_ok and ok

    # Step 2: docker build
    log("Step 2/3: Running docker build")
    ok, msg = check_docker_build(repo_dir, args.docker_timeout)
    log(("PASS: " if ok else "FAIL: ") + msg)
    all_ok = all_ok and ok

    # Step 3: openenv validate
    log("Step 3/3: Running openenv validate")
    ok, msg = check_openenv_validate(repo_dir)
    log(("PASS: " if ok else "FAIL: ") + msg)
    all_ok = all_ok and ok

    log("========================================")
    if all_ok:
        log("All checks passed")
        return 0

    log("One or more checks failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

