from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402


MVP3B_REGISTRY_IDS = {
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm",
    "universal_robots_ur_external_style",
}
MVP3C_SOURCE_INGRESS_IDS = {
    "franka_panda_isaac_sim",
    "universal_robots_ur10e_isaac_sim",
}
XR_LEAK_VALUES = {
    "quest3_handtracking",
    "steamvr_openxr",
    "alvr",
}


def _lower_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()


def test_mvp3c_source_ingress_profiles_are_separate_from_mvp3b_registry() -> None:
    default_ids = {
        profile.adapter_id for profile in RobotEmbodimentAdapterRegistry.list_profiles()
    }
    mvp3c_ids = {
        profile.adapter_id
        for profile in RobotEmbodimentAdapterRegistry.list_mvp3c_source_ingress_profiles()
    }

    assert default_ids == MVP3B_REGISTRY_IDS
    assert mvp3c_ids == MVP3C_SOURCE_INGRESS_IDS
    assert default_ids.isdisjoint(mvp3c_ids)


def test_mvp3c_source_ingress_profiles_encode_isaac_sim_runtime_contract() -> None:
    profiles = {
        profile.adapter_id: profile
        for profile in RobotEmbodimentAdapterRegistry.list_mvp3c_source_ingress_profiles()
    }

    for embodiment_id, profile in profiles.items():
        artifact = profile.to_artifact()

        assert artifact["adapter_id"] == embodiment_id
        assert artifact["source_runtime"] == "isaac_sim"
        assert artifact["source_simulator"] == "isaac_sim"
        assert artifact["source_kind"] == "isaac_sim_runtime_backed_command_state_log"
        assert artifact["source_ingress_role"] == "mvp3c_isaac_sim_embodiment_source"
        assert artifact["evidence_level"] == "isaac_sim_runtime_backed_command_state_log"
        assert artifact["claim_boundary"]["real_robot_success_claimed"] is False
        assert artifact["claim_boundary"]["physical_robot_readiness_claimed"] is False
        assert artifact["claim_boundary"]["live_runtime_support_claimed"] is False
        assert artifact["claim_boundary"]["live_ur_hardware_support_claimed"] is False
        assert artifact["claim_boundary"]["live_franka_hardware_support_claimed"] is False
        assert artifact["claim_boundary"]["live_ros2_dds_runtime_support_claimed"] is False
        assert artifact["claim_boundary"]["hmd_openxr_collection_readiness_claimed"] is False
        assert artifact["claim_boundary"]["policy_uplift_claimed"] is False


def test_mvp3c_source_ingress_profiles_do_not_leak_xr_or_static_recorder_defaults() -> None:
    for profile in RobotEmbodimentAdapterRegistry.list_mvp3c_source_ingress_profiles():
        artifact_text = _lower_json(profile.to_artifact())

        for leak in XR_LEAK_VALUES:
            assert leak not in artifact_text
        assert "recorded_log_fixture" not in artifact_text
        assert "generated_or_file_backed_recorded_log_fixture" not in artifact_text


def test_mvp3c_source_ingress_adapter_creation_uses_separate_profile_set() -> None:
    for embodiment_id in MVP3C_SOURCE_INGRESS_IDS:
        adapter = RobotEmbodimentAdapterRegistry.create_mvp3c_source_ingress_adapter(
            embodiment_id
        )

        assert adapter.profile.adapter_id == embodiment_id
        assert adapter.profile.source_runtime == "isaac_sim"
        assert adapter.profile.source_simulator == "isaac_sim"
        assert (
            adapter.profile.source_kind
            == "isaac_sim_runtime_backed_command_state_log"
        )

