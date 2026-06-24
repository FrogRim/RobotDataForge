#!/usr/bin/env python3
"""Generate the RDF Public Dataset TrustPack v0 package from closed matrix evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.lerobot_public_slice import stable_json  # noqa: E402
from app.services.rdf_public_dataset_trustpack import (  # noqa: E402
    BASELINE_MATRIX_PACKAGE_DIR,
    DEFAULT_TRUSTPACK_PACKAGE_DIR,
    build_trustpack_package,
    build_non_claims,
    refresh_trustpack_matrix_indexes,
    write_trustpack_artifact_index,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_TRUSTPACK_PACKAGE_DIR)
    parser.add_argument("--baseline-package-dir", type=Path, default=BASELINE_MATRIX_PACKAGE_DIR)
    parser.add_argument("--clean", action="store_true", help="Remove an existing managed TrustPack package before rebuilding.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_trustpack_package(
        package_dir=args.package_dir,
        baseline_package_dir=args.baseline_package_dir,
        clean=args.clean,
    )
    _run_claim_scan(Path(result["package_dir"]))
    _run_regeneration_comparator(args.baseline_package_dir, Path(result["package_dir"]))
    write_trustpack_artifact_index(Path(result["package_dir"]))
    refresh_trustpack_matrix_indexes(
        Path(result["package_dir"]),
        profile_summaries=result["profiles"],
        non_claims=build_non_claims(),
    )
    if args.pretty:
        print(stable_json(result))
    else:
        print("RDF Public Dataset TrustPack v0 package generated")
        print(f"package_manifest={result['package_manifest']}")
        print(f"profile_registry={result['profile_registry']}")
        for profile in result["profiles"]:
            print(
                "profile="
                f"{profile['profile_id']} repo={profile['repo_id']} "
                f"robot_type={profile['robot_type']} dims={profile['observation_state_dim']}x{profile['action_dim']}"
            )
    return 0


def _run_claim_scan(package_dir: Path) -> None:
    scanner = ROOT / "scripts" / "scan_rdf_trustpack_html_claims.py"
    result = subprocess.run(
        [sys.executable, str(scanner), "--package-dir", str(package_dir), "--write-report"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


def _run_regeneration_comparator(baseline_package_dir: Path, generated_package_dir: Path) -> None:
    comparator = ROOT / "scripts" / "compare_rdf_public_dataset_trustpack_regeneration.py"
    result = subprocess.run(
        [
            sys.executable,
            str(comparator),
            "--baseline-package-dir",
            str(baseline_package_dir),
            "--generated-package-dir",
            str(generated_package_dir),
            "--write-report",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
