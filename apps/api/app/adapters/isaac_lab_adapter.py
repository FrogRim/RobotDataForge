from __future__ import annotations

from pathlib import Path

from app.config import settings


class IsaacLabAdapter:
    """Primary collection adapter for Quest/OpenXR/Isaac Lab.

    This adapter does not control a real robot. It standardizes the local Isaac
    Lab handtracking command and exposes the boundary used by the recorder.
    """

    simulator = "isaac_lab"
    input_device = "quest3_handtracking"
    runtime = "steamvr_openxr"
    robot = "franka"

    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path or settings.isaac_handtracking_script

    def is_available(self) -> bool:
        return self.script_path.exists()

    def build_command(self, task_name: str) -> list[str]:
        if not self.is_available():
            raise FileNotFoundError(f"Isaac handtracking script not found: {self.script_path}")
        return [str(self.script_path)]

    def trajectory_source(self, task_name: str) -> dict[str, str]:
        return {
            "input_device": self.input_device,
            "runtime": self.runtime,
            "simulator": self.simulator,
            "robot": self.robot,
            "task_name": task_name,
        }
