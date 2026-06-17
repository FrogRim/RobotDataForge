from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str) -> Any:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_oracle_step_budget_stays_inside_factory_timeout_horizon() -> None:
    script = load_script("check_peg_insert_viability")
    env = SimpleNamespace(max_episode_length=150)

    budget = script.oracle_step_budget(env, requested_steps=220)

    assert budget["steps"] == 145
    assert budget["requested_steps"] == 220
    assert budget["max_episode_length"] == 150
    assert budget["horizon_limited"] is True


def test_oracle_phase_target_tracks_live_target_pose() -> None:
    script = load_script("check_peg_insert_viability")
    env = SimpleNamespace(
        fingertip_midpoint_pos=[[0.0, 0.0, 0.110]],
        held_pos=[[0.0, 0.0, 0.030]],
    )

    first = script.build_scripted_oracle_phase_target_values(
        env,
        target_held_base_pos=[0.601, 0.022, 0.064],
        phase_lift_m=0.006,
    )
    moved = script.build_scripted_oracle_phase_target_values(
        env,
        target_held_base_pos=[0.631, 0.019, 0.084],
        phase_lift_m=0.006,
    )

    assert moved[0] - first[0] == pytest.approx(0.030)
    assert moved[1] - first[1] == pytest.approx(-0.003)
    assert moved[2] - first[2] == pytest.approx(0.020)


def test_oracle_success_metrics_use_default_rdf_peg_in_hole_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script("check_peg_insert_viability")
    env = SimpleNamespace(
        held_pos=[[0.0, 0.0, 0.030]],
        held_quat=[[1.0, 0.0, 0.0, 0.0]],
        fixed_pos=[[0.0, 0.0, 0.0]],
        fixed_quat=[[1.0, 0.0, 0.0, 0.0]],
    )
    monkeypatch.setattr(
        script,
        "success_metrics",
        lambda _env: {
            "success": False,
            "xy_dist_m": 0.0,
            "z_disp_m": 0.030,
            "fixed_pos": [0.0, 0.0, 0.0],
            "held_pos": [0.0, 0.0, 0.030],
        },
    )

    metrics = script.oracle_success_metrics(env)

    assert metrics["selected_success_evaluator"] == "rdf_peg_in_hole"
    assert metrics["env_native_success"] is False
    assert metrics["success"] is True
    assert metrics["rdf_peg_in_hole"]["peg_tip_distance_to_target_max"] == 0.015
    assert metrics["rdf_peg_in_hole"]["peg_axis_alignment_error_max_rad"] == 0.25
    assert metrics["rdf_peg_in_hole"]["insertion_depth_min"] == 0.025


def test_target_jump_diagnostics_flags_reset_scale_fixed_asset_motion() -> None:
    script = load_script("check_peg_insert_viability")

    diagnostics = script.target_jump_diagnostics(
        initial_fixed_pos=[0.601, 0.022, 0.064],
        current_fixed_pos=[0.631, 0.019, 0.084],
    )

    assert diagnostics["fixed_pos_delta_m"] == pytest.approx(0.0361801, rel=1.0e-4)
    assert diagnostics["reset_or_target_jump_detected"] is True
