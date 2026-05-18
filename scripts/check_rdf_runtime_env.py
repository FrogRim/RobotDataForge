#!/usr/bin/env python3
"""Preflight checks for the local RDF Quest/ALVR/SteamVR/Isaac runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_API_BASE = "http://127.0.0.1:8000"

XR_KIT_REQUIRED_DEPENDENCIES = [
    "isaaclab.python",
    "omni.kit.xr.system.openxr",
    "omni.kit.xr.profile.ar",
    "omni.kit.xr.core",
    "omni.kit.xr.profile.common",
    "omni.kit.xr.ui.stage",
    "omni.kit.xr.scene_view.core",
    "omni.kit.xr.scene_view.utils",
    "omni.ui.scene",
]

XR_KIT_REQUIRED_SETTINGS = [
    "app.xr.enabled = true",
    'xr.openxr.components."omni.kit.xr.openxr.ext.hand_tracking".enabled = true',
    'xr.openxr.components."isaacsim.xr.openxr.hand_tracking".enabled = true',
]

XR_LOCAL_EXTENSIONS = [
    "omni.kit.xr.system.openxr",
    "omni.kit.xr.profile.ar",
    "omni.kit.xr.core",
    "omni.kit.xr.profile.common",
    "omni.kit.xr.ui.stage",
    "omni.kit.xr.scene_view.core",
    "omni.kit.xr.scene_view.utils",
    "omni.ui.scene",
]


CheckCommand = Callable[[list[str], float], tuple[int, str, str]]
CommandExists = Callable[[str], bool]
UrlProbe = Callable[[str, float], tuple[bool, str]]


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def default_command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def default_run_command(command: list[str], timeout: float = 2.0) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def default_url_probe(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(500).decode("utf-8", errors="replace")
            return 200 <= response.status < 300, body
    except (OSError, URLError) as exc:
        return False, str(exc)


def _check(status: str, name: str, detail: str, remediation: str | None = None) -> dict[str, Any]:
    item = {"status": status, "name": name, "detail": detail}
    if remediation:
        item["remediation"] = remediation
    return item


def _path_check(name: str, path: Path, *, executable: bool = False, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        status = "FAIL" if required else "WARN"
        return _check(status, name, f"missing: {path}")
    if executable and not os.access(path, os.X_OK):
        return _check("FAIL" if required else "WARN", name, f"not executable: {path}", f"chmod +x {path}")
    return _check("PASS", name, str(path))


def _bash_syntax_check(name: str, path: Path, run_command: CheckCommand) -> dict[str, Any]:
    if not path.exists():
        return _check("FAIL", name, f"missing: {path}")
    returncode, _stdout, stderr = run_command(["bash", "-n", str(path)], 3.0)
    if returncode == 0:
        return _check("PASS", name, f"bash -n passed: {path}")
    return _check("FAIL", name, stderr.strip() or f"bash -n failed: {path}")


def _source_contains_check(name: str, path: Path, required_tokens: list[str]) -> dict[str, Any]:
    if not path.exists():
        return _check("FAIL", name, f"missing: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _check("FAIL", name, f"unreadable: {path}: {exc}")
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return _check("FAIL", name, f"missing tokens in {path}: {', '.join(missing)}")
    return _check("PASS", name, f"required RDF hooks present: {path}")


def _file_contains_check(name: str, path: Path, required_tokens: list[str], *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        status = "FAIL" if required else "WARN"
        return _check(status, name, f"missing: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        status = "FAIL" if required else "WARN"
        return _check(status, name, f"unreadable: {path}: {exc}")
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return _check("FAIL" if required else "WARN", name, f"missing tokens in {path}: {', '.join(missing)}")
    return _check("PASS", name, f"required tokens present: {path}")


def _isaac_sim_extension_roots(home: Path) -> list[Path]:
    isaac_sim = home / "IsaacLab/_isaac_sim"
    return [
        isaac_sim / "exts",
        isaac_sim / "extscore",
        isaac_sim / "extscache",
        isaac_sim / "extsPhysics",
        isaac_sim / "isaacsim/exts",
        isaac_sim / "isaacsim/extscache",
        isaac_sim / "isaacsim/extsPhysics",
    ]


def _local_extensions_check(name: str, home: Path, extension_names: list[str]) -> dict[str, Any]:
    roots = [root for root in _isaac_sim_extension_roots(home) if root.exists()]
    if not roots:
        return _check("FAIL", name, f"no Isaac Sim extension roots found under {home / 'IsaacLab/_isaac_sim'}")

    found: dict[str, str] = {}
    for root in roots:
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for extension_name in extension_names:
            if extension_name in found:
                continue
            prefix = f"{extension_name}-"
            match = next((entry for entry in entries if entry.name == extension_name or entry.name.startswith(prefix)), None)
            if match is not None and match.exists():
                found[extension_name] = str(match)

    missing = [extension_name for extension_name in extension_names if extension_name not in found]
    if missing:
        return _check(
            "FAIL",
            name,
            "missing local Isaac Sim extensions: " + ", ".join(missing),
            "Install/repair Isaac Sim or ensure IsaacLab/_isaac_sim points to the Isaac Sim release tree.",
        )
    return _check("PASS", name, f"found {len(found)}/{len(extension_names)} required XR/UI extensions")


def _known_openxr_paths(home: Path) -> list[Path]:
    return [
        home / ".config/openxr/1/active_runtime.json",
        home / ".steam/debian-installation/steamapps/common/SteamVR/steamxr_linux64.json",
        home / ".local/share/Steam/steamapps/common/SteamVR/steamxr_linux64.json",
    ]


def _read_cpu_governor() -> str | None:
    path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _process_running(name: str, run_command: CheckCommand) -> bool:
    returncode, stdout, _stderr = run_command(["pgrep", "-f", name], 1.0)
    return returncode == 0 and bool(stdout.strip())


def check_environment(
    *,
    repo_root: Path = Path("/home/kangrim/robot-data-forge"),
    home: Path = Path("/home/kangrim"),
    api_base: str = DEFAULT_API_BASE,
    require_running_xr: bool = False,
    command_exists: CommandExists = default_command_exists,
    run_command: CheckCommand = default_run_command,
    url_probe: UrlProbe = default_url_probe,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = env or dict(os.environ)
    checks: list[dict[str, Any]] = []

    alvr_dashboard = Path(
        env.get(
            "ALVR_DASHBOARD",
            str(home / ".local/share/ALVR-Launcher/installations/v20.14.1/alvr_streamer_linux/bin/alvr_dashboard"),
        )
    )
    steamvr_vrmonitor = Path(
        env.get(
            "STEAMVR_VRMONITOR",
            str(home / ".steam/debian-installation/steamapps/common/SteamVR/bin/vrmonitor.sh"),
        )
    )
    isaac_python = Path(env.get("ISAAC_PYTHON", str(home / "IsaacLab/_isaac_sim/python.sh")))
    teleop_script = Path(
        env.get(
            "ISAAC_TELEOP_SCRIPT",
            str(home / "IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py"),
        )
    )
    isaac_xr_kit = Path(
        env.get(
            "ISAAC_XR_OPENXR_KIT",
            str(home / "IsaacLab/apps/isaaclab.python.xr.openxr.kit"),
        )
    )
    live_runner = Path(env.get("RDF_LIVE_RUNNER", str(home / "run_isaac_handtracking.sh")))
    live_smoke_runner = Path(env.get("RDF_LIVE_SMOKE_RUNNER", str(repo_root / "scripts/run_live_rdf_smoke_test.sh")))
    nvidia_icd = Path(env.get("RDF_NVIDIA_ICD", "/usr/share/vulkan/icd.d/nvidia_icd.json"))

    checks.append(_path_check("repo_root", repo_root, required=True))
    checks.append(_path_check("root_pyproject", repo_root / "pyproject.toml", required=True))
    checks.append(_check("PASS" if command_exists("uv") else "FAIL", "uv", "found" if command_exists("uv") else "missing"))
    checks.append(_path_check("live_runner", live_runner, executable=True, required=True))
    checks.append(_path_check("live_smoke_runner", live_smoke_runner, executable=True, required=True))
    checks.append(_path_check("isaac_python", isaac_python, executable=True, required=True))
    checks.append(_path_check("isaac_teleop_script", teleop_script, required=True))
    checks.append(_path_check("isaac_xr_openxr_kit", isaac_xr_kit, required=True))
    checks.append(_path_check("alvr_dashboard", alvr_dashboard, executable=True, required=True))
    checks.append(_path_check("steamvr_vrmonitor", steamvr_vrmonitor, executable=True, required=True))
    checks.append(_path_check("nvidia_vulkan_icd", nvidia_icd, required=True))
    checks.append(
        _check(
            "PASS" if command_exists("bash") else "FAIL",
            "bash",
            "found" if command_exists("bash") else "missing",
        )
    )
    if command_exists("bash"):
        checks.append(_bash_syntax_check("live_runner_syntax", live_runner, run_command))
        checks.append(_bash_syntax_check("live_smoke_runner_syntax", live_smoke_runner, run_command))
    checks.append(
        _source_contains_check(
            "live_runner_rdf_env",
            live_runner,
            [
                "XR_RUNTIME_JSON",
                "RDF_ACTION_FILTER",
                "RDF_ACTION_POS_GAIN",
                "RDF_ACTION_POS_AXIS_MAP",
                "RDF_VISUAL_DEBUG",
                "RDF_TELEOP_CONTROL_MODE",
                "RDF_DIRECT_EE_POS_GAIN",
                "RDF_DIRECT_EE_MAX_STEP_M",
                "RDF_OPERATOR_FOLLOW_PRESET",
                "RDF_CARTESIAN_DELTA_POS_GAIN",
                "RDF_VISUAL_DEBUG_INPUT_SCALE",
                "RDF_XR_ANCHOR_YAW_OFFSET_DEG",
                "--rdf_record",
            ],
        )
    )
    checks.append(
        _source_contains_check(
            "teleop_rdf_hooks",
            teleop_script,
            [
                "--rdf_record",
                "--rdf_action_pos_gain",
                "--rdf_visual_debug",
                "--rdf_teleop_control_mode",
                "--rdf_direct_ee_pos_gain",
                "RdfBoundedDirectEeTargetController",
                "bounded_direct_end_effector_target_servo",
                "--rdf_operator_follow_preset",
                "RdfOperatorFollowController",
                "operator_workspace_target_following",
                "enable_cartesian_delta_control",
                "factory_cartesian_delta_control",
                "--rdf_visual_debug_input_scale",
                "--rdf_xr_anchor_yaw_offset_deg",
                "RdfUsdVisualDebugMarkers",
                "compute_rdf_visual_targets",
                "start_rdf_terminal_hotkeys",
                "request_recenter_calibration",
                "RdfTeleopActionFilter",
            ],
        )
    )
    checks.append(_file_contains_check("isaac_xr_kit_dependencies", isaac_xr_kit, XR_KIT_REQUIRED_DEPENDENCIES))
    checks.append(_file_contains_check("isaac_xr_kit_handtracking_settings", isaac_xr_kit, XR_KIT_REQUIRED_SETTINGS))
    checks.append(_local_extensions_check("isaac_xr_local_extensions", home, XR_LOCAL_EXTENSIONS))

    openxr_env = env.get("XR_RUNTIME_JSON")
    if openxr_env:
        openxr_path = Path(openxr_env)
        checks.append(_path_check("XR_RUNTIME_JSON", openxr_path, required=True))
        if openxr_path.exists() and "steamxr_linux64.json" not in str(openxr_path):
            checks.append(
                _check(
                    "WARN",
                    "XR_RUNTIME_JSON_runtime",
                    str(openxr_path),
                    "Use SteamVR OpenXR runtime for the Quest/ALVR MVP-0 path.",
                )
            )
    else:
        existing = [path for path in _known_openxr_paths(home) if path.exists()]
        if existing:
            active = home / ".config/openxr/1/active_runtime.json"
            status = "PASS" if active.exists() else "WARN"
            detail = f"found: {existing[0]}"
            if active.exists() and active.is_symlink():
                try:
                    detail = f"active: {active} -> {active.resolve()}"
                except OSError:
                    detail = f"active: {active}"
            checks.append(
                _check(
                    status,
                    "openxr_runtime",
                    detail,
                    None if status == "PASS" else "Set SteamVR as OpenXR runtime before Isaac XR launch.",
                )
            )
        else:
            checks.append(_check("FAIL", "openxr_runtime", "no SteamVR/OpenXR runtime JSON found"))

    if command_exists("nvidia-smi"):
        returncode, stdout, stderr = run_command(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], 3.0)
        if returncode == 0:
            checks.append(_check("PASS", "nvidia_smi", stdout.strip() or "nvidia-smi ok"))
        else:
            checks.append(_check("WARN", "nvidia_smi", stderr.strip() or "nvidia-smi failed"))
    else:
        checks.append(_check("WARN", "nvidia_smi", "nvidia-smi command missing"))

    governor = _read_cpu_governor()
    if governor == "powersave":
        checks.append(_check("WARN", "cpu_governor", "powersave", "Switch to performance before live validation."))
    elif governor:
        checks.append(_check("PASS", "cpu_governor", governor))
    else:
        checks.append(_check("WARN", "cpu_governor", "unavailable"))

    health_ok, health_detail = url_probe(f"{api_base.rstrip('/')}/health", 1.5)
    checks.append(
        _check(
            "PASS" if health_ok else "WARN",
            "rdf_api_health",
            health_detail if health_ok else f"not reachable: {health_detail}",
            None if health_ok else "Start ./scripts/run_local_api_sqlite.sh or let run_live_rdf_smoke_test.sh manage API.",
        )
    )

    for process_name in ("alvr_dashboard", "vrserver"):
        running = _process_running(process_name, run_command)
        if running:
            checks.append(_check("PASS", f"process_{process_name}", "running"))
        else:
            checks.append(
                _check(
                    "FAIL" if require_running_xr else "WARN",
                    f"process_{process_name}",
                    "not running",
                    "Start XR stack, or run scripts/run_live_rdf_smoke_test.sh without --no-start-xr.",
                )
            )

    fail_count = sum(1 for check in checks if check["status"] == "FAIL")
    warn_count = sum(1 for check in checks if check["status"] == "WARN")
    return {
        "schema_version": "rdf_runtime_env_preflight_v0.1.0",
        "passed": fail_count == 0,
        "api_base": api_base,
        "require_running_xr": require_running_xr,
        "summary": {"pass": sum(1 for check in checks if check["status"] == "PASS"), "warn": warn_count, "fail": fail_count},
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local RDF Quest/ALVR/SteamVR/Isaac runtime prerequisites.")
    parser.add_argument("--repo-root", type=Path, default=Path("/home/kangrim/robot-data-forge"))
    parser.add_argument("--home", type=Path, default=Path("/home/kangrim"))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--require-running-xr", action="store_true", help="Fail if ALVR/SteamVR processes are not running.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def _print_text(report: dict[str, Any]) -> None:
    print(f"RDF runtime preflight: {'PASS' if report['passed'] else 'FAIL'}")
    summary = report["summary"]
    print(f"checks: pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}")
    for check in report["checks"]:
        line = f"[{check['status']}] {check['name']}: {check['detail']}"
        print(line)
        if check.get("remediation"):
            print(f"  remediation: {check['remediation']}")


def main() -> int:
    args = parse_args()
    report = check_environment(
        repo_root=args.repo_root,
        home=args.home,
        api_base=args.api_base,
        require_running_xr=args.require_running_xr,
    )
    if args.json or args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    else:
        _print_text(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
