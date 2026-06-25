#!/usr/bin/env python3
"""Generate the MVP-5A-pre digital-twin file-drop chaos rehearsal package.

This runner does not run Isaac Sim, ROS2, HMD/OpenXR, or robot hardware. It
materializes deterministic recorded-log rehearsal drops. If a runtime-shaped
capture is supplied, v0 copies and structurally checks it for diagnostics only:
the package still emits `file_drop_rehearsal_contract_ready` with
`file_drop_rehearsal_ready=false` until a future verifier-owned raw runtime
evidence contract exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.mvp5a_file_drop_rehearsal import (  # noqa: E402
    DEFAULT_PACKAGE_DIR,
    build_rehearsal_package,
    stable_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--runtime-capture", type=Path)
    parser.add_argument("--fixture-only", action="store_true", help="Force deterministic fixture-only contract-ready mode.")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_rehearsal_package(
        package_dir=args.package_dir,
        runtime_capture=args.runtime_capture,
        fixture_only=args.fixture_only or args.runtime_capture is None,
        clean=args.clean,
    )
    if args.pretty:
        print(stable_json(result))
    else:
        print("MVP-5A-pre file-drop chaos rehearsal package generated")
        print(f"package_manifest={result['package_manifest']}")
        print(f"status={result['status']}")
        print(f"file_drop_rehearsal_ready={str(result['file_drop_rehearsal_ready']).lower()}")
        print(f"golden_profile_count={result['golden_profile_count']}")
        print(f"corrupt_case_count={result['corrupt_case_count']}")
        if result["blocked_reason"]:
            print(f"blocked_reason={result['blocked_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
