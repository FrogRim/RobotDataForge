from __future__ import annotations

from typing import Any

from app.utils.geometry import downsample, euclidean


def trajectory_signature(trajectory: dict[str, Any], points: int = 16) -> list[list[float]]:
    frames = trajectory.get("frames") or []
    positions = [
        frame.get("object_position")
        for frame in frames
        if isinstance(frame.get("object_position"), list)
    ]
    sampled = downsample(positions, points)
    if not sampled:
        return []
    mins = [min(p[i] for p in sampled) for i in range(len(sampled[0]))]
    maxs = [max(p[i] for p in sampled) for i in range(len(sampled[0]))]
    normalized = []
    for point in sampled:
        normalized.append([
            (point[i] - mins[i]) / max(maxs[i] - mins[i], 1e-9)
            for i in range(len(point))
        ])
    return normalized


def is_duplicate(signature: list[list[float]], seen: list[list[list[float]]], threshold: float = 0.03) -> bool:
    if not signature:
        return False
    for other in seen:
        if len(other) != len(signature):
            continue
        avg = sum(euclidean(a, b) for a, b in zip(signature, other, strict=True)) / len(signature)
        if avg <= threshold:
            return True
    return False


def curate_episodes(
    episodes: list[dict[str, Any]],
    min_quality_score: float,
    fraud_threshold: float = 0.3,
) -> list[dict[str, Any]]:
    """Apply spec #10 rule and keep the legacy accepted-only return shape."""

    return curate_episodes_with_reasons(
        episodes,
        min_quality_score=min_quality_score,
        fraud_threshold=fraud_threshold,
    )["accepted"]


def curate_episodes_with_reasons(
    episodes: list[dict[str, Any]],
    min_quality_score: float,
    fraud_threshold: float = 0.3,
    min_data_usability_score: float = 0.7,
) -> dict[str, list[dict[str, Any]]]:
    """Apply curation rules and record why each trajectory was accepted or rejected."""

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_signatures: list[list[list[float]]] = []
    for episode in episodes:
        evaluation = episode.get("evaluation") or {}
        trajectory = episode.get("trajectory") or {}
        episode_meta = episode.get("episode") or {}
        summary = trajectory.get("summary") or {}
        usability = (
            episode.get("data_usability")
            or summary.get("data_usability")
            or {}
        )
        sync_metrics = summary.get("sync_metrics") or {}
        rejection_reasons: list[str] = []
        if episode_meta.get("status") not in {None, "success"}:
            rejection_reasons.append(f"EPISODE_STATUS:{episode_meta.get('status')}")
        if not evaluation.get("success"):
            rejection_reasons.append("EVALUATION_FAILED")
        if float(evaluation.get("quality_score", 0.0)) < min_quality_score:
            rejection_reasons.append("LOW_QUALITY_SCORE")
        if float(evaluation.get("fraud_risk_score", 0.0)) >= fraud_threshold:
            rejection_reasons.append("HIGH_FRAUD_RISK")
        if episode_meta.get("replayable") is False:
            rejection_reasons.append("NOT_REPLAYABLE")
        data_usability_score = usability.get("score", evaluation.get("data_usability_score"))
        if data_usability_score is not None and float(data_usability_score) < min_data_usability_score:
            rejection_reasons.append("LOW_DATA_USABILITY_SCORE")
        if usability.get("usable") is False:
            rejection_reasons.extend(str(reason) for reason in usability.get("rejection_reasons", []))
        sync_quality_score = sync_metrics.get("quality_score")
        if sync_quality_score is not None and float(sync_quality_score) < 0.7:
            rejection_reasons.append("LOW_SYNC_QUALITY")
        signature = trajectory_signature(trajectory)
        if is_duplicate(signature, seen_signatures):
            rejection_reasons.append("DUPLICATE_TRAJECTORY")

        curated = {
            **episode,
            "curation": {
                "accepted": not rejection_reasons,
                "rejection_reasons": sorted(set(rejection_reasons)),
                "min_quality_score": min_quality_score,
                "fraud_threshold": fraud_threshold,
                "min_data_usability_score": min_data_usability_score,
            },
        }
        if rejection_reasons:
            rejected.append(curated)
            continue
        seen_signatures.append(signature)
        accepted.append(curated)
    return {"accepted": accepted, "rejected": rejected}
