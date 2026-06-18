#!/usr/bin/env python3
"""Deterministically build the out-of-band Level C trace tarball for the MVP-2
package, and print its sha256.

The tarball bundles the 100 per-step Isaac held-out traces. It is too large for
git, so it lives out-of-band; the manifest records only its sha256. For that hash
to mean anything, the build must be byte-reproducible: an auditor who holds the
same trace files runs this script and must get the identical sha256.

Determinism: entries sorted by name; per-entry mtime/uid/gid/uname/gname/mode
normalized; gzip mtime pinned to 0. stdlib-only.

Usage:
    python3 scripts/build_mvp2_trace_tarball.py <traces_dir> <output.tar.gz>
"""

from __future__ import annotations

import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path

NORMALIZED_MODE = 0o644


def build_tarball_bytes(traces_dir: Path) -> bytes:
    names = sorted(p.name for p in traces_dir.glob("*.json"))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for name in names:
            fpath = traces_dir / name
            info = tarfile.TarInfo(name=name)
            data = fpath.read_bytes()
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = NORMALIZED_MODE
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    # gzip with mtime=0 so the compressed stream is reproducible.
    return gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        sys.stderr.write(
            "Usage: python3 scripts/build_mvp2_trace_tarball.py <traces_dir> <output.tar.gz>\n"
        )
        return 1
    traces_dir = Path(args[0])
    out_path = Path(args[1])
    if not traces_dir.is_dir():
        sys.stderr.write(f"traces_dir not found: {traces_dir}\n")
        return 1
    blob = build_tarball_bytes(traces_dir)
    out_path.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    count = len(sorted(traces_dir.glob("*.json")))
    print(f"traces: {count}")
    print(f"tarball: {out_path} ({len(blob)} bytes)")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
