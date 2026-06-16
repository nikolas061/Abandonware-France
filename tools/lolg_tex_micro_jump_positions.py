#!/usr/bin/env python3
"""Analyze jump positions inside repeated micro-jump .tex buckets."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_MICRO_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")
DEFAULT_SPLIT_BUCKETS = Path("output/tex_micro_jump_split/buckets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_jump_positions")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "bucket_rows",
    "repeated_bucket_rows",
    "repeated_bucket_bytes",
    "position_signature_groups",
    "repeated_position_signature_rows",
    "repeated_position_signature_bytes",
    "bucket_bin_repeat_rows",
    "bucket_bin_repeat_bytes",
    "largest_bucket_key",
    "largest_bucket_rows",
    "largest_bucket_repeated_bins",
    "promotion_ready_bytes",
    "issue_rows",
]

BUCKET_FIELDNAMES = [
    "rank",
    "bucket_key",
    "rows",
    "bytes",
    "jump_count",
    "positive_jump_count",
    "negative_jump_count",
    "position_signature_groups",
    "repeated_position_signature_rows",
    "repeated_position_signature_bytes",
    "repeated_bins",
    "top_bins",
    "top_sign_pattern",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

TARGET_FIELDNAMES = [
    "rank",
    "bucket_rank",
    "bucket_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "length",
    "jump_count",
    "positive_jump_count",
    "negative_jump_count",
    "jump_bins",
    "jump_signs",
    "position_signature",
    "repeated_bucket_bins",
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


def bucket_key(row: dict[str, str]) -> str:
    return f"nibble={row.get('top_nibble', '')}|control={row.get('control_window_signature', '')}"


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


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


def jump_events(data: bytes, bins: int) -> tuple[list[int], list[str]]:
    positions: list[int] = []
    signs: list[str] = []
    denominator = max(1, len(data) - 1)
    for index in range(1, len(data)):
        delta = signed_delta(data[index - 1], data[index])
        if abs(delta) <= 31:
            continue
        bucket = min(bins - 1, int(((index - 1) / denominator) * bins))
        positions.append(bucket)
        signs.append("+j" if delta > 0 else "-j")
    return positions, signs


def top_bin_text(counter: Counter[int]) -> str:
    return ";".join(f"{bin_}:{count}" for bin_, count in counter.most_common())


def build(
    micro_rows: list[dict[str, str]],
    split_buckets: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    bins: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    repeated_bucket_keys = {
        row.get("bucket_key", "")
        for row in split_buckets
        if int_value(row, "rows") > 1
    }
    source_rows = [
        row
        for row in micro_rows
        if row.get("micro_class") == "jump_mixed_walk" and bucket_key(row) in repeated_bucket_keys
    ]

    target_rows: list[dict[str, object]] = []
    by_bucket: dict[str, list[dict[str, object]]] = defaultdict(list)
    issues: list[str] = []
    for row in source_rows:
        local_issues = [issue for issue in row.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(row), b"")
        start = int_value(row, "start")
        end = int_value(row, "end")
        expected = expected_all[start:end]
        if not expected:
            local_issues.append("missing_expected_chunk")
        jump_bins, jump_signs = jump_events(expected, bins)
        signature = "|".join(f"{sign}:{bin_}" for bin_, sign in zip(jump_bins, jump_signs))
        key = bucket_key(row)
        target = {
            "rank": 0,
            "bucket_rank": 0,
            "bucket_key": key,
            "archive": row.get("archive", ""),
            "pcx_name": row.get("pcx_name", ""),
            "frontier_id": row.get("frontier_id", ""),
            "length": len(expected),
            "jump_count": len(jump_bins),
            "positive_jump_count": sum(1 for sign in jump_signs if sign == "+j"),
            "negative_jump_count": sum(1 for sign in jump_signs if sign == "-j"),
            "jump_bins": ";".join(str(value) for value in jump_bins),
            "jump_signs": ";".join(jump_signs),
            "position_signature": signature,
            "repeated_bucket_bins": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(local_issues),
        }
        target_rows.append(target)
        by_bucket[key].append(target)
        issues.extend(local_issues)
    issues.extend(fixture_issues)

    bucket_rows: list[dict[str, object]] = []
    for key, rows in by_bucket.items():
        sample = rows[0]
        bin_counter: Counter[int] = Counter()
        sign_counter: Counter[str] = Counter()
        signature_counter: Counter[str] = Counter()
        for row in rows:
            for bin_text in str(row["jump_bins"]).split(";"):
                if bin_text != "":
                    bin_counter[int(bin_text)] += 1
            sign_counter.update(str(row["jump_signs"]).split(";"))
            signature_counter[str(row["position_signature"])] += 1
        repeated_bins = sorted(bin_ for bin_, count in bin_counter.items() if count > 1)
        repeated_signature_rows = sum(
            count for signature, count in signature_counter.items() if signature and count > 1
        )
        repeated_signature_bytes = sum(
            int(row["length"])
            for row in rows
            if signature_counter[str(row["position_signature"])] > 1
        )
        for row in rows:
            row["repeated_bucket_bins"] = ";".join(str(value) for value in repeated_bins)
        bucket_rows.append(
            {
                "rank": 0,
                "bucket_key": key,
                "rows": len(rows),
                "bytes": sum(int(row["length"]) for row in rows),
                "jump_count": sum(int(row["jump_count"]) for row in rows),
                "positive_jump_count": sum(int(row["positive_jump_count"]) for row in rows),
                "negative_jump_count": sum(int(row["negative_jump_count"]) for row in rows),
                "position_signature_groups": len(signature_counter),
                "repeated_position_signature_rows": repeated_signature_rows,
                "repeated_position_signature_bytes": repeated_signature_bytes,
                "repeated_bins": ";".join(str(value) for value in repeated_bins),
                "top_bins": top_bin_text(bin_counter),
                "top_sign_pattern": ";".join(f"{sign}:{count}" for sign, count in sign_counter.most_common()),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": "position_review" if repeated_bins else "position_singletons",
            }
        )

    bucket_rows.sort(
        key=lambda row: (
            -int(row["rows"]),
            -len(str(row["repeated_bins"]).split(";")) if row["repeated_bins"] else 0,
            -int(row["bytes"]),
            str(row["bucket_key"]),
        )
    )
    bucket_rank = {str(row["bucket_key"]): index for index, row in enumerate(bucket_rows, start=1)}
    for index, row in enumerate(bucket_rows, start=1):
        row["rank"] = index
    target_rows.sort(key=lambda row: (bucket_rank[str(row["bucket_key"])], str(row["frontier_id"]), int(row["length"])))
    for index, row in enumerate(target_rows, start=1):
        row["rank"] = index
        row["bucket_rank"] = bucket_rank[str(row["bucket_key"])]

    signature_groups = Counter(str(row["position_signature"]) for row in target_rows if row["position_signature"])
    repeated_signature_rows = sum(count for count in signature_groups.values() if count > 1)
    repeated_signature_bytes = sum(
        int(row["length"])
        for row in target_rows
        if row["position_signature"] and signature_groups[str(row["position_signature"])] > 1
    )
    bucket_bin_repeat_rows = sum(1 for row in target_rows if row["repeated_bucket_bins"])
    bucket_bin_repeat_bytes = sum(int(row["length"]) for row in target_rows if row["repeated_bucket_bins"])
    largest = bucket_rows[0] if bucket_rows else {}
    summary = {
        "scope": "total",
        "target_rows": len(target_rows),
        "target_bytes": sum(int(row["length"]) for row in target_rows),
        "bucket_rows": len(bucket_rows),
        "repeated_bucket_rows": sum(1 for row in bucket_rows if int(row["rows"]) > 1),
        "repeated_bucket_bytes": sum(int(row["bytes"]) for row in bucket_rows if int(row["rows"]) > 1),
        "position_signature_groups": len(signature_groups),
        "repeated_position_signature_rows": repeated_signature_rows,
        "repeated_position_signature_bytes": repeated_signature_bytes,
        "bucket_bin_repeat_rows": bucket_bin_repeat_rows,
        "bucket_bin_repeat_bytes": bucket_bin_repeat_bytes,
        "largest_bucket_key": largest.get("bucket_key", ""),
        "largest_bucket_rows": largest.get("rows", 0),
        "largest_bucket_repeated_bins": largest.get("repeated_bins", ""),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, bucket_rows, target_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], buckets: list[dict[str, object]], targets: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "buckets": buckets, "targets": targets}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['target_rows']}</div><div class="muted">targets</div></div>
  <div class="box"><div class="num">{summary['bucket_rows']}</div><div class="muted">buckets</div></div>
  <div class="box"><div class="num">{summary['bucket_bin_repeat_rows']}</div><div class="muted">rows with repeated bins</div></div>
  <div class="box"><div class="num">{summary['bucket_bin_repeat_bytes']}</div><div class="muted">bytes with repeated bins</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Buckets</h2>{render_table(buckets, BUCKET_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</div>
<script type="application/json" id="position-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze jump positions in repeated .tex micro-jump buckets.")
    parser.add_argument("--micro-targets", type=Path, default=DEFAULT_MICRO_TARGETS)
    parser.add_argument("--split-buckets", type=Path, default=DEFAULT_SPLIT_BUCKETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--bins", type=int, default=16)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Jump Positions")
    args = parser.parse_args()

    summary, buckets, targets = build(
        read_rows(args.micro_targets),
        read_rows(args.split_buckets),
        read_rows(args.fixtures),
        args.bins,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "buckets.csv", BUCKET_FIELDNAMES, buckets)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, buckets, targets, args.title))

    print(f"Position targets: {summary['target_rows']}")
    print(f"Rows with repeated bins: {summary['bucket_bin_repeat_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
