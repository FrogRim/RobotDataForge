from __future__ import annotations

from app.services.curator import curate_episodes
from tests.test_evaluator import make_trajectory


def test_curator_filters_failed_and_duplicates() -> None:
    trajectory = make_trajectory()
    episodes = [
        {"trajectory": trajectory, "evaluation": {"success": True, "quality_score": 0.9, "fraud_risk_score": 0.0}},
        {"trajectory": trajectory, "evaluation": {"success": True, "quality_score": 0.9, "fraud_risk_score": 0.0}},
        {"trajectory": trajectory, "evaluation": {"success": False, "quality_score": 1.0, "fraud_risk_score": 0.0}},
    ]
    accepted = curate_episodes(episodes, min_quality_score=0.7)
    assert len(accepted) == 1


if __name__ == "__main__":
    test_curator_filters_failed_and_duplicates()
