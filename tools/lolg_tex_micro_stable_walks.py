#!/usr/bin/env python3
"""Compare repeated non-jump micro-token walk signatures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_MICRO_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_walks")
STABLE_CLASSES = {"plateau_walk", "banded_small_signed_walk", "small_signed_walk"}

SUMMARY_FIELDNAMES = [
    "scope",
    "stable_rows",
    "stable_bytes",
    "signature_groups",
    "repeated_signature_groups",
    "repeated_signature_rows",
    "repeated_signature_bytes",
    "exact_repeat_rows",
    "exact_repeat_bytes",
    "constant_shift_rows",
    "constant_shift_bytes",
    "shape_only_rows",
    "shape_only_bytes",
    "copy_distance_320_rows",
    "copy_distance_320_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GROUP_FIELDNAMES = [
    "rank",
    "signed_shape_key",
    "micro_class",
    "rows",
    "bytes",
    "fixtures",
    "exact_repeat_rows",
    "exact_repeat_bytes",
    "constant_shift_rows",
    "constant_shift_bytes",
    "shape_only_rows",
    "shape_only_bytes",
    "shift_values",
    "start_offsets",
    "offset_deltas",
    "copy_distance_320_rows",
    "copy_distance_320_bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

TARGET_FIELDNAMES = [
    "rank",
    "group_rank",
    "signed_shape_key",
    "micro_class",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "comparison_to_seed",
    "constant_shift",
    "exact_bytes",
    "head_hex",
    "tail_hex",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except ValueError:
        return 0


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_expected_by_fixture(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        path_text = fixture.get("expected_gap_path", "")
        if not path_text:
            issues.append(f"{key}:missing_expected_path")
            expected[key] = b""
            continue
        try:
            expected[key] = Path(path_text).read_bytes()
        except OSError as exc:
            issues.append(f"{key}:read_expected_failed:{exc}")
            expected[key] = b""
    return expected, issues


def constant_shift(seed: bytes, other: bytes) -> str:
    if len(seed) != len(other) or not seed:
        return ""
    deltas = {((right - left) & 0xFF) for left, right in zip(seed, other)}
    if len(deltas) != 1:
        return ""
    return f"{next(iter(deltas)):+03d}"


def compare_to_seed(seed: bytes, other: bytes) -> tuple[str, str, int]:
    if seed == other:
        return "exact", "+00", len(other)
    shift = constant_shift(seed, other)
    if shift:
        return "constant_shift", shift, 0
    exact = sum(1 for left, right in zip(seed, other) if left == right)
    return "shape_only", "", exact


def build(
    micro_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    stable_rows = [row for row in micro_rows if row.get("micro_class") in STABLE_CLASSES]
    payloads: list[tuple[dict[str, str], bytes, list[str]]] = []
    issues: list[str] = []
    for row in stable_rows:
        local_issues = [issue for issue in row.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(row), b"")
        start = int_value(row, "start")
        end = int_value(row, "end")
        expected = expected_all[start:end]
        if not expected:
            local_issues.append("missing_expected_chunk")
        payloads.append((row, expected, local_issues))
        issues.extend(local_issues)
    issues.extend(fixture_issues)

    by_signature: dict[str, list[tuple[dict[str, str], bytes, list[str]]]] = defaultdict(list)
    for item in payloads:
        row, _expected, _issues = item
        by_signature[row.get("signed_shape_key", "")].append(item)

    group_rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    for shape_key, items in by_signature.items():
        if not shape_key:
            continue
        seed_row, seed_payload, seed_issues = items[0]
        exact_rows = 0
        exact_bytes = 0
        shift_rows = 0
        shift_bytes = 0
        shape_rows = 0
        shape_bytes = 0
        shifts: set[str] = set()
        starts = [int_value(row, "start") for row, _payload, _issues in items]
        offset_deltas = [right - left for left, right in zip(starts, starts[1:])]
        copy_distance_320_rows = 0
        copy_distance_320_bytes = 0
        for row, payload, local_issues in items:
            comparison, shift, exact = compare_to_seed(seed_payload, payload)
            if comparison == "exact":
                exact_rows += 1
                exact_bytes += len(payload)
                if row is not seed_row and int_value(row, "start") - int_value(seed_row, "start") == 320:
                    copy_distance_320_rows += 1
                    copy_distance_320_bytes += len(payload)
            elif comparison == "constant_shift":
                shift_rows += 1
                shift_bytes += len(payload)
                shifts.add(shift)
            else:
                shape_rows += 1
                shape_bytes += len(payload)
            target_rows.append(
                {
                    "rank": 0,
                    "group_rank": 0,
                    "signed_shape_key": shape_key,
                    "micro_class": row.get("micro_class", ""),
                    "archive": row.get("archive", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "frontier_id": row.get("frontier_id", ""),
                    "start": row.get("start", ""),
                    "end": row.get("end", ""),
                    "length": len(payload),
                    "comparison_to_seed": comparison,
                    "constant_shift": shift,
                    "exact_bytes": exact,
                    "head_hex": payload[:16].hex(),
                    "tail_hex": payload[-16:].hex(),
                    "issues": ";".join(local_issues),
                }
            )
        repeated = len(items) > 1
        verdict = "singleton_review"
        if repeated and shape_rows == 0 and (exact_rows + shift_rows) == len(items):
            verdict = "stable_value_relation_review"
        elif repeated:
            verdict = "shape_repeat_only"
        group_rows.append(
            {
                "rank": 0,
                "signed_shape_key": shape_key,
                "micro_class": ";".join(sorted({row.get("micro_class", "") for row, _payload, _issues in items})),
                "rows": len(items),
                "bytes": sum(len(payload) for _row, payload, _issues in items),
                "fixtures": len({fixture_key(row) for row, _payload, _issues in items}),
                "exact_repeat_rows": exact_rows if repeated else 0,
                "exact_repeat_bytes": exact_bytes if repeated else 0,
                "constant_shift_rows": shift_rows if repeated else 0,
                "constant_shift_bytes": shift_bytes if repeated else 0,
                "shape_only_rows": shape_rows if repeated else 0,
                "shape_only_bytes": shape_bytes if repeated else 0,
                "shift_values": ";".join(sorted(shifts)),
                "start_offsets": ";".join(str(value) for value in starts),
                "offset_deltas": ";".join(str(value) for value in offset_deltas),
                "copy_distance_320_rows": copy_distance_320_rows if repeated else 0,
                "copy_distance_320_bytes": copy_distance_320_bytes if repeated else 0,
                "sample_pcx": seed_row.get("pcx_name", ""),
                "sample_frontier_id": seed_row.get("frontier_id", ""),
                "verdict": "distance_320_copy_review" if copy_distance_320_bytes and not shape_rows else verdict,
            }
        )

    group_rows.sort(key=lambda row: (-int(row["rows"]), -int(row["bytes"]), str(row["signed_shape_key"])))
    group_rank = {str(row["signed_shape_key"]): index for index, row in enumerate(group_rows, start=1)}
    for index, row in enumerate(group_rows, start=1):
        row["rank"] = index
    target_rows.sort(key=lambda row: (group_rank[str(row["signed_shape_key"])], str(row["frontier_id"]), int(row["length"])))
    for index, row in enumerate(target_rows, start=1):
        row["rank"] = index
        row["group_rank"] = group_rank[str(row["signed_shape_key"])]

    repeated_groups = [row for row in group_rows if int(row["rows"]) > 1]
    summary = {
        "scope": "total",
        "stable_rows": len(stable_rows),
        "stable_bytes": sum(len(payload) for _row, payload, _issues in payloads),
        "signature_groups": len(group_rows),
        "repeated_signature_groups": len(repeated_groups),
        "repeated_signature_rows": sum(int(row["rows"]) for row in repeated_groups),
        "repeated_signature_bytes": sum(int(row["bytes"]) for row in repeated_groups),
        "exact_repeat_rows": sum(int(row["exact_repeat_rows"]) for row in repeated_groups),
        "exact_repeat_bytes": sum(int(row["exact_repeat_bytes"]) for row in repeated_groups),
        "constant_shift_rows": sum(int(row["constant_shift_rows"]) for row in repeated_groups),
        "constant_shift_bytes": sum(int(row["constant_shift_bytes"]) for row in repeated_groups),
        "shape_only_rows": sum(int(row["shape_only_rows"]) for row in repeated_groups),
        "shape_only_bytes": sum(int(row["shape_only_bytes"]) for row in repeated_groups),
        "copy_distance_320_rows": sum(int(row["copy_distance_320_rows"]) for row in repeated_groups),
        "copy_distance_320_bytes": sum(int(row["copy_distance_320_bytes"]) for row in repeated_groups),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, group_rows, target_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], groups: list[dict[str, object]], targets: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "groups": groups, "targets": targets}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['stable_rows']}</div><div class="muted">stable rows</div></div>
  <div class="box"><div class="num">{summary['repeated_signature_rows']}</div><div class="muted">repeated signature rows</div></div>
  <div class="box"><div class="num">{summary['exact_repeat_bytes']}</div><div class="muted">exact repeat bytes</div></div>
  <div class="box"><div class="num">{summary['copy_distance_320_bytes']}</div><div class="muted">distance +320 copy bytes</div></div>
  <div class="box"><div class="num">{summary['constant_shift_bytes']}</div><div class="muted">constant shift bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</div>
<script type="application/json" id="stable-walk-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare repeated stable .tex micro-token walks.")
    parser.add_argument("--micro-targets", type=Path, default=DEFAULT_MICRO_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Walks")
    args = parser.parse_args()

    summary, groups, targets = build(read_rows(args.micro_targets), read_rows(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, groups, targets, args.title))

    print(f"Stable rows: {summary['stable_rows']}")
    print(f"Repeated signature bytes: {summary['repeated_signature_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
