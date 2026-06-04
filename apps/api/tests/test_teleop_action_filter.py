from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


FILTER_PATH = Path(__file__).resolve().parents[3] / "scripts" / "rdf_teleop_action_filter.py"
SPEC = importlib.util.spec_from_file_location("rdf_teleop_action_filter", FILTER_PATH)
assert SPEC is not None
filter_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = filter_module
SPEC.loader.exec_module(filter_module)


def test_axis_map_supports_signed_coordinate_remap():
    axis_map = filter_module.parse_signed_axis_map("x,-z,y")

    config = filter_module.RdfTeleopActionFilterConfig(
        position_gain=1.0,
        rotation_gain=1.0,
        position_deadzone=0.0,
        rotation_deadzone=0.0,
        smoothing_alpha=1.0,
        position_axis_map=axis_map,
    )
    action_filter = filter_module.RdfTeleopActionFilter(config)

    result = action_filter.apply([1.0, 2.0, 3.0, 0.1, 0.2, 0.3, 1.0])

    assert result.applied_action[:3] == [1.0, -3.0, 2.0]
    assert result.applied_action[3:] == [0.1, 0.2, 0.3, 1.0]
    assert result.metadata["config"]["position_axis_map"] == "x,-z,y"


def test_position_yaw_offset_rotates_openxr_horizontal_plane_before_axis_map():
    config = filter_module.RdfTeleopActionFilterConfig(
        position_gain=1.0,
        position_deadzone=0.0,
        smoothing_alpha=1.0,
        position_yaw_offset_deg=90.0,
        position_axis_map=filter_module.parse_signed_axis_map("x,z,y"),
    )
    action_filter = filter_module.RdfTeleopActionFilter(config)

    result = action_filter.apply([0.0, 0.0, 1.0])

    assert result.applied_action[:3] == pytest.approx([1.0, 0.0, 0.0])
    assert result.metadata["config"]["position_yaw_offset_deg"] == 90.0


def test_filter_applies_gain_deadzone_and_smoothing():
    config = filter_module.RdfTeleopActionFilterConfig(
        position_gain=0.5,
        rotation_gain=0.25,
        position_deadzone=0.01,
        rotation_deadzone=0.01,
        smoothing_alpha=0.5,
    )
    action_filter = filter_module.RdfTeleopActionFilter(config)

    first = action_filter.apply([0.02, 0.004, -0.02, 0.0, 0.02, 0.0, 1.0])
    second = action_filter.apply([0.02, 0.004, -0.02, 0.0, 0.02, 0.0, 1.0])

    assert first.raw_action == [0.02, 0.004, -0.02, 0.0, 0.02, 0.0, 1.0]
    assert first.applied_action == pytest.approx([0.005, 0.0, -0.005, 0.0, 0.0025, 0.0, 1.0])
    assert second.applied_action == pytest.approx([0.0075, 0.0, -0.0075, 0.0, 0.00375, 0.0, 1.0])


def test_recenter_suppresses_next_motion_frame():
    config = filter_module.RdfTeleopActionFilterConfig(
        position_gain=1.0,
        rotation_gain=1.0,
        position_deadzone=0.0,
        rotation_deadzone=0.0,
        smoothing_alpha=1.0,
    )
    action_filter = filter_module.RdfTeleopActionFilter(config)

    action_filter.recenter("operator_command")
    result = action_filter.apply([0.1, 0.2, 0.3, 0.4])

    assert result.applied_action == [0.0, 0.0, 0.0, 0.4]
    assert result.metadata["last_recenter_reason"] == "operator_command"
    assert result.metadata["suppressed_after_recenter"] is True


def test_from_env_parses_filter_config():
    config = filter_module.RdfTeleopActionFilterConfig.from_env(
        {
            "RDF_ACTION_FILTER": "1",
            "RDF_ACTION_POS_GAIN": "0.3",
            "RDF_ACTION_ROT_GAIN": "0.2",
            "RDF_ACTION_POS_DEADZONE": "0.01",
            "RDF_ACTION_ROT_DEADZONE": "0.02",
            "RDF_ACTION_SMOOTHING_ALPHA": "0.7",
            "RDF_ACTION_POS_YAW_OFFSET_DEG": "-90",
            "RDF_ACTION_POS_AXIS_MAP": "x,-z,y",
            "RDF_ACTION_ROT_AXIS_MAP": "-x,y,z",
        }
    )

    assert config.enabled is True
    assert config.position_gain == 0.3
    assert config.rotation_gain == 0.2
    assert config.position_deadzone == 0.01
    assert config.rotation_deadzone == 0.02
    assert config.smoothing_alpha == 0.7
    assert config.position_yaw_offset_deg == -90.0
    assert config.to_dict()["position_axis_map"] == "x,-z,y"
    assert config.to_dict()["rotation_axis_map"] == "-x,y,z"


def test_from_env_defaults_position_axis_to_openxr_y_up_mapping():
    config = filter_module.RdfTeleopActionFilterConfig.from_env({})

    assert config.to_dict()["position_axis_map"] == "x,z,y"
    assert config.to_dict()["rotation_axis_map"] == "x,y,z"
    assert config.to_dict()["position_yaw_offset_deg"] == 0.0
