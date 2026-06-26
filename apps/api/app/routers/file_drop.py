from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[4]
CLI = REPO_ROOT / "scripts" / "rdf_file_drop_evaluator.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "rdf_file_drop_evaluator"
COMMAND_TIMEOUT_SECONDS = 20.0
MAX_STDOUT_CHARS = 200_000
MAX_STDERR_CHARS = 20_000
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
TESTCLIENT_HOST = "testclient"


def _require_loopback_client(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host in {"localhost", TESTCLIENT_HOST}:
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="file_drop_api_loopback_only")


router = APIRouter(prefix="/api/file-drop", tags=["file-drop"], dependencies=[Depends(_require_loopback_client)])


class PreflightRequest(BaseModel):
    input_path: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)


class EvaluateRequest(BaseModel):
    input_path: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    run_id: str | None = None
    force: bool = False


class VerifyRequest(BaseModel):
    run_path: str = Field(min_length=1)
    deep_hdf5: bool = True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _clean_env() -> dict[str, str]:
    env: dict[str, str] = {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "RDF_FILE_DROP_EVALUATOR_ARTIFACT_ROOT": str(ARTIFACT_ROOT),
    }
    for key in ("HOME", "LANG", "LC_ALL", "PATH"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _cap_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _run_cli_bridge(argv: list[str], *, trust_source: str) -> dict:
    command = [sys.executable, str(CLI), *argv]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=_clean_env(),
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _cap_text(exc.stdout or "", MAX_STDOUT_CHARS)
        stderr, stderr_truncated = _cap_text(exc.stderr or "", MAX_STDERR_CHARS)
        return {
            "ok": False,
            "exit_code": None,
            "command_argv": command,
            "trust_source": trust_source,
            "bridge_error": "timeout",
            "result": None,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }

    stdout, stdout_truncated = _cap_text(completed.stdout, MAX_STDOUT_CHARS)
    stderr, stderr_truncated = _cap_text(completed.stderr, MAX_STDERR_CHARS)
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "exit_code": completed.returncode,
            "command_argv": command,
            "trust_source": trust_source,
            "bridge_error": "malformed_json",
            "result": None,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }

    result_ok = bool(isinstance(result, dict) and result.get("ok") is True and completed.returncode == 0)
    return {
        "ok": result_ok,
        "exit_code": completed.returncode,
        "command_argv": command,
        "trust_source": trust_source,
        "bridge_error": None,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def _safe_run_id(run_id: str | None) -> str:
    value = run_id or f"api-{uuid.uuid4().hex[:12]}"
    if value in {".", ".."} or "/" in value or "\\" in value or RUN_ID_RE.fullmatch(value) is None:
        raise HTTPException(status_code=400, detail="unsafe_run_id")
    return value


def _artifact_path(path_value: str) -> Path:
    path = Path(path_value)
    resolved = path.resolve()
    root = ARTIFACT_ROOT.resolve()
    if not _is_within(resolved, root):
        raise HTTPException(status_code=400, detail="unsafe_artifact_path")
    return resolved


@router.get("/profiles")
def list_profiles() -> dict:
    return _run_cli_bridge(["profiles", "list", "--json"], trust_source="cli_exit_code_and_json")


@router.get("/profiles/{profile_id}")
def inspect_profile(profile_id: str) -> dict:
    return _run_cli_bridge(["profiles", "inspect", profile_id, "--json"], trust_source="cli_exit_code_and_json")


@router.post("/preflight")
def preflight_file_drop(payload: PreflightRequest) -> dict:
    return _run_cli_bridge(
        ["preflight", payload.input_path, "--profile", payload.profile_id, "--json"],
        trust_source="cli_exit_code_and_json",
    )


@router.post("/evaluate")
def evaluate_file_drop(payload: EvaluateRequest) -> dict:
    run_id = _safe_run_id(payload.run_id)
    out_dir = ARTIFACT_ROOT / run_id
    if not _is_within(out_dir, ARTIFACT_ROOT):
        raise HTTPException(status_code=400, detail="unsafe_artifact_path")
    argv = [
        "evaluate",
        payload.input_path,
        "--profile",
        payload.profile_id,
        "--out",
        str(out_dir),
        "--json",
    ]
    if payload.force:
        argv.insert(-1, "--force")
    return _run_cli_bridge(argv, trust_source="cli_exit_code_and_json")


@router.post("/verify")
def verify_file_drop_run(payload: VerifyRequest) -> dict:
    target = _artifact_path(payload.run_path)
    argv = ["verify", str(target), "--json"]
    if payload.deep_hdf5:
        argv.insert(-1, "--deep-hdf5")
    return _run_cli_bridge(argv, trust_source="verifier_exit_code_and_json")
