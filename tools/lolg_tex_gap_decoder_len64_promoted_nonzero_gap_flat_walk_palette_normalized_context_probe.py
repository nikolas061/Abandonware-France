#!/usr/bin/env python3
"""Probe normalized palette contexts for repeated flat-walk signatures."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_MIX_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe/targets.csv"
)
DEFAULT_SIGNATURES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe/by_signature.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_normalized_context_probe"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "repeated_signature_groups",
    "repeated_signature_rows",
    "repeated_signature_bytes",
    "palette_value_count",
    "source_candidate_groups",
    "same_candidate_pool_groups",
    "same_transform_set_groups",
    "uniform_transform_delta_groups",
    "uniform_offset_delta_groups",
    "full_normalized_groups",
    "best_transform_delta_value_hits",
    "best_offset_delta_value_hits",
    "promotion_ready_bytes",
    "issue_rows",
]

GROUP_FIELDNAMES = [
    "signature_id",
    "palette_size",
    "unique_values_hex",
    "rows",
    "bytes",
    "source_start",
    "copy_start",
    "copy_distance",
    "source_pool",
    "copy_pool",
    "source_transform_set",
    "copy_transform_set",
    "same_candidate_pool",
    "same_transform_set",
    "matched_values",
    "uniform_transform_delta",
    "transform_delta_mode",
    "transform_delta_mode_values",
    "transform_delta_values",
    "uniform_offset_delta",
    "offset_delta_mode",
    "offset_delta_mode_values",
    "offset_delta_values",
    "verdict",
]


PLAN_PATTERN = re.compile(r"(0x[0-9a-fA-F]+)=([^@\s]+)@(-?\d+)")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, object], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw) if raw != "" else 0
    except (TypeError, ValueError):
        return 0


def transform_shift(transform: str) -> int | None:
    if transform == "identity":
        return 0
    prefix = "identity_shift"
    if not transform.startswith(prefix):
        return None
    raw = transform[len(prefix) :]
    try:
        return int(raw)
    except ValueError:
        return None


def parse_plan(plan: str) -> dict[str, tuple[int, int]]:
    values: dict[str, tuple[int, int]] = {}
    for value, transform, offset in PLAN_PATTERN.findall(plan):
        shift = transform_shift(transform)
        if shift is None:
            continue
        values[value.lower()] = (shift, int(offset))
    return values


def signature_rows(signatures: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in signatures
        if row.get("verdict") == "copy_backed_repeated_signature_review"
        and int_value(row, "rows") >= 2
    ]


def build_group_rows(
    mix_targets: list[dict[str, str]],
    signatures: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    targets_by_signature: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mix_targets:
        key = row.get("unique_values_hex", "")
        if key:
            targets_by_signature[key].append(row)

    groups: list[dict[str, object]] = []
    issues: list[str] = []
    for signature in signature_rows(signatures):
        key = signature.get("unique_values_hex", "")
        rows = sorted(targets_by_signature.get(key, []), key=lambda row: int_value(row, "start"))
        candidates = [row for row in rows if row.get("candidate_plan")]
        if len(candidates) < 2:
            issues.append(f"{signature.get('signature_id', '')}:missing_candidate_pair")
            continue

        source = next((row for row in candidates if int_value(row, "copy_unlock_rows") > 0), candidates[0])
        copies = [row for row in candidates if row is not source]
        copy = next((row for row in copies if int_value(row, "start") > int_value(source, "start")), copies[0])
        source_plan = parse_plan(source.get("candidate_plan", ""))
        copy_plan = parse_plan(copy.get("candidate_plan", ""))
        shared_values = sorted(set(source_plan) & set(copy_plan))
        transform_deltas: list[int] = []
        offset_deltas: list[int] = []
        for value in shared_values:
            source_shift, source_offset = source_plan[value]
            copy_shift, copy_offset = copy_plan[value]
            transform_deltas.append(copy_shift - source_shift)
            offset_deltas.append(copy_offset - source_offset)

        transform_counter = Counter(transform_deltas)
        offset_counter = Counter(offset_deltas)
        transform_mode, transform_mode_count = transform_counter.most_common(1)[0] if transform_counter else ("", 0)
        offset_mode, offset_mode_count = offset_counter.most_common(1)[0] if offset_counter else ("", 0)
        uniform_transform = bool(transform_counter) and len(transform_counter) == 1
        uniform_offset = bool(offset_counter) and len(offset_counter) == 1
        same_pool = source.get("candidate_pool", "") == copy.get("candidate_pool", "")
        same_transform_set = source.get("candidate_transform_set", "") == copy.get("candidate_transform_set", "")
        verdict = (
            "normalized_palette_candidate"
            if uniform_transform and uniform_offset and same_pool
            else "partial_transform_delta_review"
            if transform_mode_count >= max(2, len(shared_values) // 2)
            else "normalized_context_reject"
        )
        groups.append(
            {
                "signature_id": signature.get("signature_id", ""),
                "palette_size": signature.get("palette_size", ""),
                "unique_values_hex": key,
                "rows": signature.get("rows", ""),
                "bytes": signature.get("bytes", ""),
                "source_start": source.get("start", ""),
                "copy_start": copy.get("start", ""),
                "copy_distance": int_value(copy, "start") - int_value(source, "start"),
                "source_pool": source.get("candidate_pool", ""),
                "copy_pool": copy.get("candidate_pool", ""),
                "source_transform_set": source.get("candidate_transform_set", ""),
                "copy_transform_set": copy.get("candidate_transform_set", ""),
                "same_candidate_pool": 1 if same_pool else 0,
                "same_transform_set": 1 if same_transform_set else 0,
                "matched_values": len(shared_values),
                "uniform_transform_delta": 1 if uniform_transform else 0,
                "transform_delta_mode": transform_mode,
                "transform_delta_mode_values": transform_mode_count,
                "transform_delta_values": json.dumps(dict(sorted(transform_counter.items())), sort_keys=True),
                "uniform_offset_delta": 1 if uniform_offset else 0,
                "offset_delta_mode": offset_mode,
                "offset_delta_mode_values": offset_mode_count,
                "offset_delta_values": json.dumps(dict(sorted(offset_counter.items())), sort_keys=True),
                "verdict": verdict,
            }
        )

    summary = {
        "scope": "total",
        "repeated_signature_groups": len(groups),
        "repeated_signature_rows": sum(int_value(row, "rows") for row in groups),
        "repeated_signature_bytes": sum(int_value(row, "bytes") for row in groups),
        "palette_value_count": sum(int_value(row, "matched_values") for row in groups),
        "source_candidate_groups": sum(1 for row in groups if int_value(row, "matched_values") > 0),
        "same_candidate_pool_groups": sum(1 for row in groups if int_value(row, "same_candidate_pool")),
        "same_transform_set_groups": sum(1 for row in groups if int_value(row, "same_transform_set")),
        "uniform_transform_delta_groups": sum(1 for row in groups if int_value(row, "uniform_transform_delta")),
        "uniform_offset_delta_groups": sum(1 for row in groups if int_value(row, "uniform_offset_delta")),
        "full_normalized_groups": sum(
            1 for row in groups if row.get("verdict") == "normalized_palette_candidate"
        ),
        "best_transform_delta_value_hits": max(
            (int_value(row, "transform_delta_mode_values") for row in groups), default=0
        ),
        "best_offset_delta_value_hits": max(
            (int_value(row, "offset_delta_mode_values") for row in groups), default=0
        ),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, groups


def render_table(rows: list[dict[str, object]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], groups: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "groups": groups}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
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
  <div class="box"><div class="num">{summary['repeated_signature_groups']}</div><div class="muted">signature groups</div></div>
  <div class="box"><div class="num">{summary['palette_value_count']}</div><div class="muted">matched palette values</div></div>
  <div class="box"><div class="num">{summary['same_candidate_pool_groups']}</div><div class="muted">same pool groups</div></div>
  <div class="box"><div class="num">{summary['uniform_transform_delta_groups']}</div><div class="muted">uniform transform delta groups</div></div>
  <div class="box"><div class="num">{summary['uniform_offset_delta_groups']}</div><div class="muted">uniform offset delta groups</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="flat-walk-palette-normalized-context-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe normalized flat-walk palette contexts.")
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--signatures", type=Path, default=DEFAULT_SIGNATURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Flat Walk Palette Normalized Context Probe",
    )
    args = parser.parse_args()

    summary, groups = build_group_rows(read_csv(args.mix_targets), read_csv(args.signatures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, groups, args.title))

    print(f"Repeated signature groups: {summary['repeated_signature_groups']}")
    print(f"Matched palette values: {summary['palette_value_count']}")
    print(f"Uniform transform delta groups: {summary['uniform_transform_delta_groups']}")
    print(f"Uniform offset delta groups: {summary['uniform_offset_delta_groups']}")
    print(f"Best transform delta value hits: {summary['best_transform_delta_value_hits']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
