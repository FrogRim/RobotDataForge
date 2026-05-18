from __future__ import annotations


class MockSimAdapter:
    """Fallback/debug adapter only. It must not replace the primary path."""

    simulator = "mock_sim"
    input_device = "mock"
    runtime = "none"
    robot = "franka"

    def trajectory_source(self, task_name: str) -> dict[str, str]:
        return {
            "input_device": self.input_device,
            "runtime": self.runtime,
            "simulator": self.simulator,
            "robot": self.robot,
            "task_name": task_name,
        }

    def sample_success_trajectory(self, task_id: str, episode_id: str) -> dict:
        return {
            "id": "mock_traj",
            "episode_id": episode_id,
            "task_id": task_id,
            "schema_version": "0.1.0",
            "source": self.trajectory_source("mock-peg-in-hole"),
            "frames": [
                {
                    "t": 0.0,
                    "step": 0,
                    "end_effector_position": [0.15, 0.5],
                    "object_position": [0.15, 0.5],
                    "action": {"delta_position": [0.0, 0.0], "gripper": 1.0},
                    "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
                },
                {
                    "t": 5.0,
                    "step": 1,
                    "end_effector_position": [0.75, 0.5],
                    "object_position": [0.75, 0.5],
                    "action": {"delta_position": [0.6, 0.0], "gripper": 1.0},
                    "metadata": {"right_hand_tracked": True, "xr_frame_valid": True},
                },
            ],
            "summary": {"duration_sec": 5.0, "collision_count": 0},
        }
