#!/usr/bin/env python3
"""Profile direct payload/source/spatial evidence for jump-token .tex rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_jump_mixed_payload_probe import (
    DISTANCE_FIELDNAMES,
    GROUP_FIELDNAMES,
    best_peer_score,
    best_source_match,
    best_source_profile,
    best_spatial_match,
    exact_count,
    fixture_key,
    float_value,
    int_value,
    load_sources,
    payload_signature,
    repeated_row_stats,
    signed_profile_key,
    value_histogram_key,
    write_csv,
)


DEFAULT_JUMP_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_jump_token_payload_profile")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "structure_classes",
    "dense_jump_bytes",
    "mixed_jump_bytes",
    "repeated_nibble_bytes",
    "long_island_bytes",
    "repeated_payload_signature_rows",
    "repeated_payload_signature_bytes",
    "repeated_value_histogram_rows",
    "repeated_value_histogram_bytes",
    "repeated_signed_profile_rows",
    "repeated_signed_profile_bytes",
    "class_pair_ge50_rows",
    "class_pair_ge50_bytes",
    "source_profile_ge50_rows",
    "source_profile_ge50_bytes",
    "source_profile_ge75_rows",
    "source_profile_ge75_bytes",
    "external_best_exact_bytes",
    "external_best_prefix_bytes",
    "spatial_best_distance",
    "spatial_best_rows",
    "spatial_best_bytes",
    "spatial_best_correct_bytes",
    "spatial_best_false_bytes",
    "spatial_exact_copy_rows",
    "spatial_exact_copy_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "jump_structure_class",
    "length",
    "start",
    "end",
    "jump_delta_count",
    "jump_delta_ratio",
    "long_island_bytes",
    "top_jump_nibble_pair",
    "top_jump_nibble_pair_ratio",
    "payload_signature",
    "value_histogram_key",
    "signed_profile_key",
    "best_class_peer_exact",
    "best_class_peer_ratio",
    "best_source_pool",
    "best_source_offset",
    "best_source_transform",
    "best_source_exact",
    "best_source_prefix",
    "best_source_known_bytes",
    "best_source_profile_pool",
    "best_source_profile_offset",
    "best_source_profile_overlap",
    "best_source_profile_ratio",
    "best_spatial_distance",
    "best_spatial_correct",
    "best_spatial_false",
    "verdict",
    "head_hex",
    "source_head_hex",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def build_groups(rows: list[dict[str, object]], fields: list[tuple[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for kind, field in fields:
        by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            key = str(row.get(field, ""))
            if key:
                by_key[key].append(row)
        for key, members in by_key.items():
            sample = members[0]
            output.append(
                {
                    "rank": 0,
                    "group_kind": kind,
                    "group_key": key,
                    "rows": len(members),
                    "bytes": sum(int_value(row, "length") for row in members),
                    "sample_pcx": sample.get("pcx_name", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                    "verdict": "repeated_group" if len(members) > 1 else "singleton_group",
                }
            )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), str(row["group_kind"])))
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def bytes_for_classes(rows: list[dict[str, object]], classes: set[str]) -> int:
    return sum(int_value(row, "length") for row in rows if row.get("jump_structure_class") in classes)


def build(
    jump_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    source_by_fixture, fixture_issues = load_sources(fixture_rows, replay_rows)
    prepared: list[tuple[dict[str, str], bytes, dict[str, bytes], list[str]]] = []
    by_class_payloads: dict[str, list[bytes]] = defaultdict(list)
    issues: list[str] = []
    for row in jump_rows:
        row_issues = [issue for issue in row.get("issues", "").split(";") if issue]
        sources = source_by_fixture.get(fixture_key(row), {})
        expected_all = sources.get("expected", b"")
        start = int_value(row, "start")
        end = int_value(row, "end")
        target = expected_all[start:end]
        if not target:
            row_issues.append("missing_expected_payload")
        if row.get("length") and int_value(row, "length") != len(target):
            row_issues.append(f"length_mismatch:{row.get('length')}:{len(target)}")
        prepared.append((row, target, sources, row_issues))
        by_class_payloads[row.get("jump_structure_class", "")].append(target)
        issues.extend(row_issues)
    issues.extend(fixture_issues)

    row_outputs: list[dict[str, object]] = []
    distance_counters: dict[int, Counter[str]] = defaultdict(Counter)
    distance_samples: dict[int, dict[str, str]] = {}
    for row, target, sources, row_issues in prepared:
        start = int_value(row, "start")
        end = int_value(row, "end")
        expected_all = sources.get("expected", b"")
        class_peer_exact, class_peer_ratio = best_peer_score(target, by_class_payloads[row.get("jump_structure_class", "")])
        source_match = best_source_match(target, sources, sources.get("known_mask", b""))
        source_profile = best_source_profile(target, sources)
        spatial = best_spatial_match(expected_all, start, end, max_distance)
        for distance in range(1, min(max_distance, start) + 1):
            source = expected_all[start - distance : end - distance]
            if len(source) != len(target):
                continue
            correct = exact_count(target, source)
            counter = distance_counters[distance]
            counter["rows"] += 1
            counter["bytes"] += len(target)
            counter["correct"] += correct
            counter["false"] += len(target) - correct
            counter["exact_rows"] += 1 if correct == len(target) else 0
            distance_samples.setdefault(distance, row)
        if int(source_match["exact"]) == len(target) and int(source_match["known"]) == len(target):
            verdict = "known_source_exact_review"
        elif int(source_match["exact"]) == len(target):
            verdict = "oracle_source_exact_review"
        elif int(spatial["correct"]) == len(target):
            verdict = "oracle_spatial_exact_review"
        elif float(class_peer_ratio) >= 0.5:
            verdict = "class_peer_overlap_review"
        elif float_value(source_profile, "ratio") >= 0.75:
            verdict = "source_profile_review"
        else:
            verdict = "jump_payload_blocked"
        row_outputs.append(
            {
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "jump_structure_class": row.get("jump_structure_class", ""),
                "length": len(target),
                "start": start,
                "end": end,
                "jump_delta_count": row.get("jump_delta_count", ""),
                "jump_delta_ratio": row.get("jump_delta_ratio", ""),
                "long_island_bytes": row.get("long_island_bytes", ""),
                "top_jump_nibble_pair": row.get("top_jump_nibble_pair", ""),
                "top_jump_nibble_pair_ratio": row.get("top_jump_nibble_pair_ratio", ""),
                "payload_signature": payload_signature(target),
                "value_histogram_key": value_histogram_key(target),
                "signed_profile_key": signed_profile_key(target),
                "best_class_peer_exact": class_peer_exact,
                "best_class_peer_ratio": class_peer_ratio,
                "best_source_pool": source_match["pool"],
                "best_source_offset": source_match["offset"],
                "best_source_transform": source_match["transform"],
                "best_source_exact": source_match["exact"],
                "best_source_prefix": source_match["prefix"],
                "best_source_known_bytes": source_match["known"],
                "best_source_profile_pool": source_profile["pool"],
                "best_source_profile_offset": source_profile["offset"],
                "best_source_profile_overlap": source_profile["overlap"],
                "best_source_profile_ratio": source_profile["ratio"],
                "best_spatial_distance": spatial["distance"],
                "best_spatial_correct": spatial["correct"],
                "best_spatial_false": spatial["false"],
                "verdict": verdict,
                "head_hex": target[:16].hex(),
                "source_head_hex": source_match["source_head_hex"],
                "issues": ";".join(row_issues),
            }
        )

    distance_rows: list[dict[str, object]] = []
    for distance, counter in distance_counters.items():
        sample = distance_samples[distance]
        if counter["exact_rows"]:
            verdict = "oracle_spatial_exact_review"
        elif counter["correct"] >= counter["false"]:
            verdict = "partial_spatial_review"
        else:
            verdict = "spatial_reject"
        distance_rows.append(
            {
                "distance": distance,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "correct_bytes": counter["correct"],
                "false_bytes": counter["false"],
                "exact_rows": counter["exact_rows"],
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    distance_rows.sort(
        key=lambda row: (-int_value(row, "correct_bytes"), int_value(row, "false_bytes"), int_value(row, "distance"))
    )
    groups = build_groups(
        row_outputs,
        [
            ("jump_structure_class", "jump_structure_class"),
            ("payload_signature", "payload_signature"),
            ("value_histogram", "value_histogram_key"),
            ("signed_profile", "signed_profile_key"),
            ("source_profile_pool", "best_source_profile_pool"),
            ("verdict", "verdict"),
        ],
    )
    _payload_groups, repeated_payload_rows, repeated_payload_bytes = repeated_row_stats(row_outputs, "payload_signature")
    _value_groups, repeated_value_rows, repeated_value_bytes = repeated_row_stats(row_outputs, "value_histogram_key")
    _signed_groups, repeated_signed_rows, repeated_signed_bytes = repeated_row_stats(row_outputs, "signed_profile_key")
    class_pair_rows = [row for row in row_outputs if float_value(row, "best_class_peer_ratio") >= 0.5]
    profile_ge50_rows = [row for row in row_outputs if float_value(row, "best_source_profile_ratio") >= 0.5]
    profile_ge75_rows = [row for row in row_outputs if float_value(row, "best_source_profile_ratio") >= 0.75]
    best_distance = distance_rows[0] if distance_rows else {}
    spatial_exact_rows = [row for row in row_outputs if int_value(row, "best_spatial_correct") == int_value(row, "length")]
    summary = {
        "scope": "total",
        "target_rows": len(row_outputs),
        "target_bytes": sum(int_value(row, "length") for row in row_outputs),
        "structure_classes": len({row.get("jump_structure_class", "") for row in row_outputs}),
        "dense_jump_bytes": bytes_for_classes(row_outputs, {"dense_jump_weave"}),
        "mixed_jump_bytes": bytes_for_classes(row_outputs, {"mixed_jump_split"}),
        "repeated_nibble_bytes": bytes_for_classes(row_outputs, {"repeated_nibble_jump"}),
        "long_island_bytes": bytes_for_classes(row_outputs, {"long_island_split"}),
        "repeated_payload_signature_rows": repeated_payload_rows,
        "repeated_payload_signature_bytes": repeated_payload_bytes,
        "repeated_value_histogram_rows": repeated_value_rows,
        "repeated_value_histogram_bytes": repeated_value_bytes,
        "repeated_signed_profile_rows": repeated_signed_rows,
        "repeated_signed_profile_bytes": repeated_signed_bytes,
        "class_pair_ge50_rows": len(class_pair_rows),
        "class_pair_ge50_bytes": sum(int_value(row, "length") for row in class_pair_rows),
        "source_profile_ge50_rows": len(profile_ge50_rows),
        "source_profile_ge50_bytes": sum(int_value(row, "length") for row in profile_ge50_rows),
        "source_profile_ge75_rows": len(profile_ge75_rows),
        "source_profile_ge75_bytes": sum(int_value(row, "length") for row in profile_ge75_rows),
        "external_best_exact_bytes": sum(int_value(row, "best_source_exact") for row in row_outputs),
        "external_best_prefix_bytes": sum(int_value(row, "best_source_prefix") for row in row_outputs),
        "spatial_best_distance": best_distance.get("distance", ""),
        "spatial_best_rows": best_distance.get("rows", 0),
        "spatial_best_bytes": best_distance.get("bytes", 0),
        "spatial_best_correct_bytes": best_distance.get("correct_bytes", 0),
        "spatial_best_false_bytes": best_distance.get("false_bytes", 0),
        "spatial_exact_copy_rows": len(spatial_exact_rows),
        "spatial_exact_copy_bytes": sum(int_value(row, "length") for row in spatial_exact_rows),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, row_outputs, groups, distance_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    groups: list[dict[str, object]],
    distances: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "groups": groups, "distances": distances},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_payload_signature_bytes']}</div><div class="muted">repeated payload bytes</div></div>
  <div class="box"><div class="num">{summary['class_pair_ge50_bytes']}</div><div class="muted">class peer >= 50%</div></div>
  <div class="box"><div class="num">{summary['source_profile_ge75_bytes']}</div><div class="muted">source profile >= 75%</div></div>
  <div class="box"><div class="num">{summary['spatial_exact_copy_bytes']}</div><div class="muted">spatial exact copy bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Distances</h2>{render_table(distances, DISTANCE_FIELDNAMES)}</div>
<script type="application/json" id="jump-token-payload-profile-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile direct evidence for .tex jump-token payloads.")
    parser.add_argument("--jump-targets", type=Path, default=DEFAULT_JUMP_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=700)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Jump-Token Payload Profile")
    args = parser.parse_args()

    summary, rows, groups, distances = build(
        read_csv(args.jump_targets),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    write_csv(args.output / "distances.csv", DISTANCE_FIELDNAMES, distances)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, distances, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Repeated payload signature bytes: {summary['repeated_payload_signature_bytes']}")
    print(f"Class peer >=50 bytes: {summary['class_pair_ge50_bytes']}")
    print(f"Source profile >=75 bytes: {summary['source_profile_ge75_bytes']}")
    print(f"Spatial exact copy bytes: {summary['spatial_exact_copy_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
