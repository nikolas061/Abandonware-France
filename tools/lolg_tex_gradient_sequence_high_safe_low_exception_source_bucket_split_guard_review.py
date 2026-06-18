#!/usr/bin/env python3
"""Review bucket-split guards for remaining known-source high-safe chains."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay/slots.csv")
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard")

PREDICTOR = "bucket_split_prediction"
FEATURE_SETS = [
    ("source_slot_frontier_id", "source_slot_start", "bucket_split_context"),
    ("source_slot_frontier_id", "bucket_split_context"),
    ("source_slot_start", "bucket_split_context"),
    ("frontier_id", "start", "bucket_split_context"),
    ("frontier_id", "bucket_split_context"),
    ("low_bucket", "gradient_class", "bucket_split_context"),
    ("target_y_band8", "source_slot_frontier_id", "bucket_split_context"),
    ("target_y_band8", "source_slot_start", "bucket_split_context"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slot_rows",
    "unknown_highsafe_rows",
    "guard_rows",
    "best_predictor",
    "best_guard_family",
    "best_guard_key",
    "best_unknown_exact_rows",
    "best_unknown_false_rows",
    "best_known_exact_rows",
    "best_known_false_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GUARD_FIELDNAMES = [
    "rank",
    "predictor",
    "guard_family",
    "guard_key",
    "unknown_exact_rows",
    "unknown_false_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
]

TARGET_FIELDNAMES = [
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "target_offset",
    "relative_offset",
    "expected_byte",
    "predicted_byte",
    "target_high",
    "predicted_low",
    "best_predictor",
    "best_guard_family",
    "best_guard_key",
    "source_slot_rank",
    "source_slot_frontier_id",
    "source_slot_start",
    "source_dependency_edge",
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def archive_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def predicted_byte(row: dict[str, str]) -> str:
    low_or_byte = row.get(PREDICTOR, "")
    if not low_or_byte or low_or_byte in {"NA", "unknown"}:
        return ""
    if len(low_or_byte) == 2:
        return low_or_byte.lower()
    high = row.get("target_high", "")
    if len(high) != 1:
        return ""
    return f"{high}{low_or_byte}".lower()


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def annotate_slots(
    slot_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    fixtures = {archive_key(row): row for row in fixture_rows}
    manifests = {archive_key(row): row for row in manifest_rows}
    cache: dict[tuple[str, str, str], tuple[bytes, bytes, list[str]]] = {}
    issue_rows = 0
    annotated: list[dict[str, str]] = []
    for row in slot_rows:
        key = archive_key(row)
        if key not in cache:
            issues: list[str] = []
            fixture = fixtures.get(key, {})
            manifest = manifests.get(key, {})
            expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
            known_mask = load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask")
            if len(known_mask) != len(expected):
                issues.append("known_mask_size_mismatch")
                known_mask = known_mask[: len(expected)] + (b"\x00" * max(0, len(expected) - len(known_mask)))
            if issues:
                issue_rows += 1
            cache[key] = expected, known_mask, issues
        expected, known_mask, _issues = cache[key]
        offset = int_value(row, "target_offset", -1)
        expected_byte = f"{expected[offset]:02x}" if 0 <= offset < len(expected) else ""
        known = "1" if 0 <= offset < len(known_mask) and known_mask[offset] else "0"
        promoted = dict(row)
        promoted["_expected_byte"] = expected_byte
        promoted["_known"] = known
        promoted["_predicted_byte"] = predicted_byte(row)
        promoted["_source_dependency_edge"] = source_dependency_edge(row)
        annotated.append(promoted)
    return annotated, issue_rows


def guard_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "+".join(f"{field}={row.get(field, '')}" for field in fields)


def guard_family(fields: tuple[str, ...]) -> str:
    return "+".join(fields)


def target_scope(row: dict[str, str]) -> bool:
    return (
        row.get("_known") == "0"
        and row.get("source_availability") == "unknown_source"
        and row.get("source_location") == "in_highsafe"
        and bool(row.get("_predicted_byte"))
    )


def known_scope(row: dict[str, str]) -> bool:
    return row.get("_known") == "1" and bool(row.get("_predicted_byte"))


def build_guard_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    guard_rows: list[dict[str, str]] = []
    for fields in FEATURE_SETS:
        groups: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            if not row.get("_predicted_byte"):
                continue
            key = guard_key(row, fields)
            exact = row.get("_predicted_byte") == row.get("_expected_byte")
            if target_scope(row):
                groups[key]["unknown_exact_rows" if exact else "unknown_false_rows"] += 1
            elif known_scope(row):
                groups[key]["known_exact_rows" if exact else "known_false_rows"] += 1
        for key, counts in groups.items():
            if not counts:
                continue
            verdict = "rejected_guard"
            if counts["unknown_exact_rows"] > 0 and counts["unknown_false_rows"] == 0 and counts["known_false_rows"] == 0:
                verdict = "false_free_target_only_guard"
                if counts["known_exact_rows"] > 0:
                    verdict = "promotion_ready_guard"
            guard_rows.append(
                {
                    "rank": "",
                    "predictor": PREDICTOR,
                    "guard_family": guard_family(fields),
                    "guard_key": key,
                    "unknown_exact_rows": str(counts["unknown_exact_rows"]),
                    "unknown_false_rows": str(counts["unknown_false_rows"]),
                    "known_exact_rows": str(counts["known_exact_rows"]),
                    "known_false_rows": str(counts["known_false_rows"]),
                    "verdict": verdict,
                }
            )
    guard_rows.sort(
        key=lambda row: (
            row.get("verdict") != "promotion_ready_guard",
            -int_value(row, "unknown_exact_rows"),
            -int_value(row, "known_exact_rows"),
            len(row.get("guard_family", "").split("+")),
            row.get("guard_key", ""),
        )
    )
    for index, row in enumerate(guard_rows, start=1):
        row["rank"] = str(index)
    return guard_rows


def select_guard(guard_rows: list[dict[str, str]]) -> dict[str, str]:
    for row in guard_rows:
        if row.get("verdict") == "promotion_ready_guard":
            return row
    return {}


def matches_guard(row: dict[str, str], guard: dict[str, str]) -> bool:
    fields = tuple(guard.get("guard_family", "").split("+"))
    return guard_key(row, fields) == guard.get("guard_key", "")


def review_verdict(guard: dict[str, str]) -> str:
    if not guard:
        return "missing_bucket_split_guard"
    if int_value(guard, "known_exact_rows") <= 0:
        return "bucket_split_guard_missing_known_support"
    if int_value(guard, "known_false_rows") > 0:
        return "bucket_split_guard_known_false"
    if int_value(guard, "unknown_false_rows") > 0:
        return "bucket_split_guard_unknown_false"
    if int_value(guard, "unknown_exact_rows") <= 0:
        return "bucket_split_guard_no_targets"
    return "bucket_split_guard_promotion_ready"


def next_probe_for(verdict: str) -> str:
    if verdict == "bucket_split_guard_promotion_ready":
        return "promote final known-source bucket-split guard bytes"
    if verdict == "bucket_split_guard_missing_known_support":
        return "seek known support for final known-source bucket-split guard"
    return "derive safer final known-source bucket-split guard"


def build(
    slot_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    rows, issue_rows = annotate_slots(slot_rows, fixture_rows, manifest_rows)
    guard_rows = build_guard_rows(rows)
    guard = select_guard(guard_rows)
    verdict = review_verdict(guard)
    target_rows: list[dict[str, str]] = []
    if guard:
        for row in rows:
            if not target_scope(row) or not matches_guard(row, guard):
                continue
            issues: list[str] = []
            if row.get("_predicted_byte") != row.get("_expected_byte"):
                issues.append("prediction_false")
            target_rows.append(
                {
                    "rank": str(len(target_rows) + 1),
                    "slot_rank": row.get("rank", ""),
                    "archive": row.get("archive", ""),
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "span_index": row.get("span_index", ""),
                    "op_index": row.get("op_index", ""),
                    "target_offset": row.get("target_offset", ""),
                    "relative_offset": row.get("relative_offset", ""),
                    "expected_byte": row.get("_expected_byte", ""),
                    "predicted_byte": row.get("_predicted_byte", ""),
                    "target_high": row.get("target_high", ""),
                    "predicted_low": row.get(PREDICTOR, ""),
                    "best_predictor": PREDICTOR,
                    "best_guard_family": guard.get("guard_family", ""),
                    "best_guard_key": guard.get("guard_key", ""),
                    "source_slot_rank": row.get("source_slot_rank", ""),
                    "source_slot_frontier_id": row.get("source_slot_frontier_id", ""),
                    "source_slot_start": row.get("source_slot_start", ""),
                    "source_dependency_edge": row.get("_source_dependency_edge", ""),
                    "promotion_ready": "1" if verdict == "bucket_split_guard_promotion_ready" and not issues else "0",
                    "issues": ";".join(issues),
                }
            )
    promotion_ready = (
        len(target_rows)
        if verdict == "bucket_split_guard_promotion_ready" and not any(row.get("issues") for row in target_rows)
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_bucket_split_guard_review",
        "slot_rows": str(len(slot_rows)),
        "unknown_highsafe_rows": str(sum(1 for row in rows if target_scope(row))),
        "guard_rows": str(len(guard_rows)),
        "best_predictor": guard.get("predictor", ""),
        "best_guard_family": guard.get("guard_family", ""),
        "best_guard_key": guard.get("guard_key", ""),
        "best_unknown_exact_rows": guard.get("unknown_exact_rows", "0"),
        "best_unknown_false_rows": guard.get("unknown_false_rows", "0"),
        "best_known_exact_rows": guard.get("known_exact_rows", "0"),
        "best_known_false_rows": guard.get("known_false_rows", "0"),
        "review_verdict": verdict,
        "next_probe": next_probe_for(verdict),
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(issue_rows + sum(1 for row in target_rows if row.get("issues"))),
    }
    return summary, guard_rows, target_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    guard_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "guards": guard_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guards.csv", output_dir / "guards.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1200px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
code {{ color: #77d3b1; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">candidate bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
  <div class="box"><div class="num">{summary['best_known_exact_rows']}/{summary['best_known_false_rows']}</div><div class="muted">known exact/false</div></div>
  <div class="box"><div class="num">{summary['best_unknown_exact_rows']}/{summary['best_unknown_false_rows']}</div><div class="muted">unknown exact/false</div></div>
</div>
<p>{links}</p>
<p>Best guard: <code>{html.escape(summary['best_guard_key'])}</code>. Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Guards</h2>{render_table(guard_rows, GUARD_FIELDNAMES)}</div>
<script type="application/json" id="source-bucket-split-guard-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Source Bucket-Split Guard Review")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, guard_rows, target_rows = build(
        read_csv(args.slots),
        read_csv(args.base_fixtures),
        read_csv(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "guards.csv", GUARD_FIELDNAMES, guard_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, guard_rows, target_rows, args.output, args.title), encoding="utf-8")

    print(
        "Source bucket-split guard review: "
        f"verdict={summary['review_verdict']} "
        f"guard={summary['best_guard_key']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"unknown={summary['best_unknown_exact_rows']}/{summary['best_unknown_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
