#!/usr/bin/env python3
"""Scan RDF TrustPack buyer HTML for unnegated forbidden claims."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
from typing import Any


FORBIDDEN_TEXT_CLAIM_PHRASES = (
    "generic lerobot parser support",
    "full lerobot parser support",
    "full dataset evaluation",
    "real robot success",
    "physical robot readiness",
    "live hardware support",
    "live aloha support",
    "live ur rtde support",
    "live franka hardware support",
    "live ros2 dds bridge readiness",
    "visual policy performance",
    "policy uplift",
    "learning proven value",
    "deployable policy readiness",
    "marketplace readiness",
    "production certification",
    "sim to real",
    "sim-to-real",
    "general robot intelligence",
)
NEGATION_MARKERS = (
    "does not claim",
    "do not claim",
    "not claim",
    "no claim",
    "does not prove",
    "do not prove",
    "not prove",
    "not supported",
    "does not support",
    "do not support",
    "not a ",
    "without ",
    "no ",
)
CLAUSE_DELIMITERS = ".!?;:\n"


@dataclass(frozen=True)
class HtmlScanResult:
    passed: bool
    issue_count: int
    scanned_paths: tuple[str, ...]
    canonical_and_top_level_byte_match: bool
    issues: tuple[str, ...]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self.chunks.append(data)

    @property
    def visible_text(self) -> str:
        return " ".join(self.chunks)


def scan_package(package_dir: Path) -> HtmlScanResult:
    top_level = package_dir / "buyer_report.html"
    canonical = package_dir / "data" / "reports" / "buyer_report.html"
    scanned = (top_level, canonical)
    issues: list[str] = []
    for path in scanned:
        if not path.is_file():
            issues.append(f"{path.relative_to(package_dir).as_posix()}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        _scan_text(text, f"{path.relative_to(package_dir).as_posix()}:raw", issues)
        _scan_text(_visible_text(text), f"{path.relative_to(package_dir).as_posix()}:visible", issues)
    byte_match = top_level.is_file() and canonical.is_file() and top_level.read_bytes() == canonical.read_bytes()
    if not byte_match:
        issues.append("html copies differ")
    return HtmlScanResult(
        passed=not issues,
        issue_count=len(issues),
        scanned_paths=tuple(path.relative_to(package_dir).as_posix() for path in scanned),
        canonical_and_top_level_byte_match=byte_match,
        issues=tuple(issues),
    )


def report_payload(result: HtmlScanResult) -> dict[str, Any]:
    return {
        "schema_version": "rdf_trustpack_html_claim_scan_report_v0.1.0",
        "scanner": "rdf_trustpack_html_claim_scan_v0.1.0",
        "passed": result.passed,
        "issue_count": result.issue_count,
        "scanned_paths": list(result.scanned_paths),
        "canonical_and_top_level_byte_match": result.canonical_and_top_level_byte_match,
        "raw_html_scanned": True,
        "visible_text_scanned": True,
        "entity_unescape_applied": True,
        "script_style_handling": "ignored_for_visible_text",
        "forbidden_phrase_rule_count": len(FORBIDDEN_TEXT_CLAIM_PHRASES),
        "negation_rule_count": len(NEGATION_MARKERS),
    }


def write_report(package_dir: Path, result: HtmlScanResult) -> Path:
    report_path = package_dir / "data" / "claim_scan_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload(result), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report_path


def _visible_text(html_text: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html_text)
    parser.close()
    return parser.visible_text


def _scan_text(text: str, label: str, issues: list[str]) -> None:
    lowered = " ".join(unescape(text).lower().replace("_", " ").replace("-", " ").split())
    for phrase in FORBIDDEN_TEXT_CLAIM_PHRASES:
        normalized = " ".join(phrase.replace("-", " ").split())
        index = lowered.find(normalized)
        while index != -1:
            if not _forbidden_phrase_is_directly_negated(lowered, index):
                issues.append(f"{label}: unnegated forbidden phrase")
                break
            index = lowered.find(normalized, index + 1)


def _forbidden_phrase_is_directly_negated(lowered_text: str, phrase_index: int) -> bool:
    clause_start = max(lowered_text.rfind(delimiter, 0, phrase_index) for delimiter in CLAUSE_DELIMITERS) + 1
    prefix = lowered_text[clause_start:phrase_index].strip()
    direct_markers = tuple(marker.strip() for marker in NEGATION_MARKERS)
    return any(prefix.endswith(marker) for marker in direct_markers)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = scan_package(args.package_dir)
    report = report_payload(result)
    if args.write_report:
        report["report_path"] = str(write_report(args.package_dir, result))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("buyer_report_html_claim_scan=PASS" if result.passed else "buyer_report_html_claim_scan=FAIL")
        if result.issues:
            for issue in result.issues[:8]:
                print(issue)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
