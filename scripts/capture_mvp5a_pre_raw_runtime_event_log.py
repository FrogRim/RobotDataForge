#!/usr/bin/env python3
"""Emit MVP-5A-pre raw runtime event rows from the capture-edge path.

This script is a digital-twin rehearsal emitter. It does not run live Isaac Sim,
ROS2, HMD/OpenXR, or robot hardware, and it does not prove physical runtime
authenticity. Its role is to produce raw runtime event rows directly, before
canonical trace reconstruction, so the verifier can close L2/L3 without trusting
a canonical_trace -> event_log projection helper.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.mvp5a_file_drop_rehearsal import (  # noqa: E402
    CAPTURE_EDGE_EMITTER_CONFIG_SCHEMA_VERSION,
    MIN_CANONICAL_FRAMES,
    build_capture_edge_runtime_event_log,
    stable_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("capture-edge emitter config must be a JSON object")
    if payload.get("schema_version") != CAPTURE_EDGE_EMITTER_CONFIG_SCHEMA_VERSION:
        raise ValueError("capture-edge emitter config schema_version mismatch")
    capture_id = payload.get("capture_id")
    frame_count = payload.get("frame_count")
    if not isinstance(capture_id, str) or not capture_id:
        raise ValueError("capture-edge emitter config capture_id missing")
    if not isinstance(frame_count, int) or frame_count < MIN_CANONICAL_FRAMES:
        raise ValueError("capture-edge emitter config frame_count below minimum")
    return payload


def main() -> int:
    args = parse_args()
    config = _load_config(args.config)
    events = build_capture_edge_runtime_event_log(
        capture_id=config["capture_id"],
        frame_count=config["frame_count"],
    )
    write_jsonl(args.output, events)
    print(
        stable_json(
            {
                "schema_version": "rdf_mvp5a_pre_capture_edge_emitter_summary_v0.1.0",
                "capture_id": config["capture_id"],
                "frame_count": config["frame_count"],
                "event_count": len(events),
                "output": args.output.as_posix(),
                "external_partner_data": False,
                "real_robot_success": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
