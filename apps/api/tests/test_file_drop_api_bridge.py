from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.routers import file_drop
from app.services.mvp5a_file_drop_rehearsal import build_fixture_canonical_trace, write_golden_profile_drop


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(file_drop, "ARTIFACT_ROOT", tmp_path / "artifacts")
    file_drop.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return TestClient(app)


def _golden_drop(tmp_path: Path, profile_id: str = "ur_rtde_csv_v0") -> Path:
    drop_dir = tmp_path / "drops" / profile_id
    write_golden_profile_drop(profile_id, build_fixture_canonical_trace(), drop_dir)
    return drop_dir


def _write_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_profiles_endpoint_returns_cli_profile_list(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/file-drop/profiles")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["exit_code"] == 0
    assert body["result"]["ok"] is True
    assert "ur_rtde_csv_v0" in body["result"]["profile_ids"]
    assert body["trust_source"] == "cli_exit_code_and_json"


def test_file_drop_api_allows_local_web_cors_preflight(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.options(
        "/api/file-drop/profiles",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_file_drop_api_rejects_remote_web_cors_preflight(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.options(
        "/api/file-drop/profiles",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_preflight_endpoint_returns_non_ok_when_cli_rejects(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    drop_dir = _golden_drop(tmp_path)

    response = client.post(
        "/api/file-drop/preflight",
        json={"input_path": str(drop_dir), "profile_id": "unknown_profile"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["exit_code"] != 0
    assert body["result"]["ok"] is False
    assert "unsupported_profile" in body["result"]["rejection_reasons"]


def test_file_drop_api_rejects_non_loopback_clients(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(file_drop, "ARTIFACT_ROOT", tmp_path / "artifacts")
    file_drop.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    client = TestClient(app, client=("203.0.113.10", 49152))
    drop_dir = _golden_drop(tmp_path)

    response = client.post(
        "/api/file-drop/preflight",
        json={"input_path": str(drop_dir), "profile_id": "ur_rtde_csv_v0"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "file_drop_api_loopback_only"


def test_evaluate_endpoint_writes_under_confined_artifact_root_and_verify_preserves_verdict(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    drop_dir = _golden_drop(tmp_path, "franka_state_jsonl_v0")

    evaluate_response = client.post(
        "/api/file-drop/evaluate",
        json={"input_path": str(drop_dir), "profile_id": "franka_state_jsonl_v0", "run_id": "franka-golden"},
    )

    assert evaluate_response.status_code == 200
    evaluate_body = evaluate_response.json()
    assert evaluate_body["ok"] is True
    assert evaluate_body["result"]["passed"] is True
    run_dir = Path(evaluate_body["result"]["run_dir"])
    assert run_dir.resolve().relative_to(file_drop.ARTIFACT_ROOT.resolve())
    assert run_dir == file_drop.ARTIFACT_ROOT / "franka-golden"

    verify_response = client.post("/api/file-drop/verify", json={"run_path": str(run_dir), "deep_hdf5": True})

    assert verify_response.status_code == 200
    verify_body = verify_response.json()
    assert verify_body["ok"] is True
    assert verify_body["exit_code"] == 0
    assert verify_body["result"]["verdict"] == "VERIFIED"
    assert verify_body["result"]["ok"] is True
    assert verify_body["trust_source"] == "verifier_exit_code_and_json"


def test_evaluate_rejects_path_traversal_run_id(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    drop_dir = _golden_drop(tmp_path)

    response = client.post(
        "/api/file-drop/evaluate",
        json={"input_path": str(drop_dir), "profile_id": "ur_rtde_csv_v0", "run_id": "../escape"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsafe_run_id"


def test_verify_rejects_paths_outside_artifact_root(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside" / "package_manifest.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("{}", encoding="utf-8")

    response = client.post("/api/file-drop/verify", json={"run_path": str(outside), "deep_hdf5": True})

    assert response.status_code == 400
    assert response.json()["detail"] == "unsafe_artifact_path"


def test_bridge_uses_argv_with_shell_false(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        captured["shell"] = kwargs.get("shell")
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='{"ok": true}\n', stderr="")

    monkeypatch.setattr(file_drop.subprocess, "run", fake_run)

    result = file_drop._run_cli_bridge(["profiles", "list", "--json"], trust_source="cli_exit_code_and_json")

    assert result["ok"] is True
    assert isinstance(captured["args"], list)
    assert captured["args"][0] == sys.executable
    assert captured["shell"] is False
    assert captured["cwd"] == file_drop.REPO_ROOT
    assert set(captured["env"]) <= {
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "RDF_FILE_DROP_EVALUATOR_ARTIFACT_ROOT",
    }
    assert captured["env"]["RDF_FILE_DROP_EVALUATOR_ARTIFACT_ROOT"] == str(file_drop.ARTIFACT_ROOT)


def test_bridge_fails_closed_on_malformed_json(tmp_path: Path, monkeypatch) -> None:
    bad_script = _write_script(
        tmp_path / "bad_cli.py",
        "import sys\nprint('not-json')\n",
    )
    monkeypatch.setattr(file_drop, "CLI", bad_script)

    result = file_drop._run_cli_bridge(["profiles", "list", "--json"], trust_source="cli_exit_code_and_json")

    assert result["ok"] is False
    assert result["bridge_error"] == "malformed_json"
    assert result["result"] is None


def test_bridge_fails_closed_on_timeout(tmp_path: Path, monkeypatch) -> None:
    slow_script = _write_script(
        tmp_path / "slow_cli.py",
        "import time\ntime.sleep(1)\nprint('{\"ok\": true}')\n",
    )
    monkeypatch.setattr(file_drop, "CLI", slow_script)
    monkeypatch.setattr(file_drop, "COMMAND_TIMEOUT_SECONDS", 0.01)

    start = time.monotonic()
    result = file_drop._run_cli_bridge(["profiles", "list", "--json"], trust_source="cli_exit_code_and_json")

    assert time.monotonic() - start < 0.5
    assert result["ok"] is False
    assert result["bridge_error"] == "timeout"


def test_bridge_caps_stdout_and_stderr(tmp_path: Path, monkeypatch) -> None:
    noisy_script = _write_script(
        tmp_path / "noisy_cli.py",
        "import sys\nprint('x' * 500)\nprint('e' * 500, file=sys.stderr)\n",
    )
    monkeypatch.setattr(file_drop, "CLI", noisy_script)
    monkeypatch.setattr(file_drop, "MAX_STDOUT_CHARS", 64)
    monkeypatch.setattr(file_drop, "MAX_STDERR_CHARS", 32)

    result = file_drop._run_cli_bridge(["profiles", "list", "--json"], trust_source="cli_exit_code_and_json")

    assert result["ok"] is False
    assert result["stdout_truncated"] is True
    assert result["stderr_truncated"] is True
    assert len(result["stdout"]) == 64
    assert len(result["stderr"]) == 32


def test_api_fails_closed_when_cli_outputs_malformed_json(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    bad_script = _write_script(tmp_path / "bad_cli.py", "print('not-json')\n")
    monkeypatch.setattr(file_drop, "CLI", bad_script)

    response = client.get("/api/file-drop/profiles")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["bridge_error"] == "malformed_json"
    assert body["result"] is None


def test_verify_endpoint_does_not_rewrite_failed_verifier_result(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    drop_dir = _golden_drop(tmp_path, "generic_command_state_jsonl_v0")
    evaluate_response = client.post(
        "/api/file-drop/evaluate",
        json={"input_path": str(drop_dir), "profile_id": "generic_command_state_jsonl_v0", "run_id": "tampered"},
    )
    run_dir = Path(evaluate_response.json()["result"]["run_dir"])
    buyer_report = run_dir / "reports" / "buyer_report.html"
    buyer_report.write_text(
        buyer_report.read_text(encoding="utf-8") + "\n<p>real robot success and hardware readiness</p>\n",
        encoding="utf-8",
    )
    manifest = json.loads((run_dir / "package_manifest.json").read_text(encoding="utf-8"))
    for artifact in manifest["artifact_index"]:
        if artifact["path"] == "reports/buyer_report.html":
            artifact["sha256"] = file_drop._sha256_file(buyer_report)
            artifact["byte_size"] = buyer_report.stat().st_size
    (run_dir / "package_manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    verify_response = client.post("/api/file-drop/verify", json={"run_path": str(run_dir), "deep_hdf5": True})

    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["ok"] is False
    assert body["exit_code"] != 0
    assert body["result"]["ok"] is False
    assert "forbidden_claim_leakage" in body["result"]["failed_checks"]
