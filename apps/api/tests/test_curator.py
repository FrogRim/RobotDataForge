from __future__ import annotations

from app.services.curator import curate_episodes, curate_episodes_with_reasons
from tests.test_evaluator import make_trajectory


def test_curator_filters_failed_and_duplicates() -> None:
    trajectory = make_trajectory()
    episodes = [
        {
            "trajectory": trajectory,
            "evaluation": {
                "success": True,
                "quality_score": 0.9,
                "fraud_risk_score": 0.0,
            },
        },
        {
            "trajectory": trajectory,
            "evaluation": {
                "success": True,
                "quality_score": 0.9,
                "fraud_risk_score": 0.0,
            },
        },
        {
            "trajectory": trajectory,
            "evaluation": {
                "success": False,
                "quality_score": 1.0,
                "fraud_risk_score": 0.0,
            },
        },
    ]
    accepted = curate_episodes(episodes, min_quality_score=0.7)
    assert len(accepted) == 1


def test_curator_preserves_evaluator_scene_state_discontinuity_reason() -> None:
    trajectory = make_trajectory()
    episodes = [
        {
            "trajectory": trajectory,
            "evaluation": {
                "success": True,
                "quality_score": 0.95,
                "fraud_risk_score": 0.0,
                "metrics": {
                    "data_quality": {
                        "quality_failure_reasons": ["SCENE_STATE_DISCONTINUITY"]
                    },
                    "curation": {
                        "training_eligible": False,
                        "rejection_reasons": ["SCENE_STATE_DISCONTINUITY"],
                    },
                },
            },
        }
    ]

    result = curate_episodes_with_reasons(episodes, min_quality_score=0.7)

    assert result["accepted"] == []
    assert len(result["rejected"]) == 1
    reasons = result["rejected"][0]["curation"]["rejection_reasons"]
    assert "SCENE_STATE_DISCONTINUITY" in reasons


if __name__ == "__main__":
    test_curator_filters_failed_and_duplicates()
