#!/usr/bin/env python3
"""Split micro-token jump-mixed rows into narrower review buckets."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_jump_split")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "jump_mixed_rows",
    "jump_mixed_bytes",
    "top_nibble_groups",
    "control_signature_groups",
    "transition_profile_groups",
    "review_bucket_rows",
    "repeated_bucket_rows",
    "repeated_bucket_bytes",
    "largest_bucket_rows",
    "largest_bucket_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

BUCKET_FIELDNAMES = [
    "rank",
    "bucket_key",
    "rows",
    "bytes",
    "top_nibble",
    "control_window_signature",
    "transition_profile_key",
    "coarse_shape_keys",
    "signed_shape_keys",
    "jump_delta_count",
    "small_delta_count",
    "zero_delta_count",
    "avg_jump_ratio",
    "avg_small_ratio",
    "sample_pcx",
    "sample_frontier_id",
    "next_action",
]

TARGET_FIELDNAMES = [
    "rank",
    "bucket_rank",
    "bucket_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "length",
    "top_nibble",
    "top_nibble_ratio",
    "control_window_signature",
    "transition_profile_key",
    "transition_profile_preview",
    "jump_delta_count",
    "jump_delta_ratio",
    "small_delta_count",
    "small_delta_ratio",
    "coarse_shape_key",
    "signed_shape_key",
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


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or 0)
    except ValueError:
        return 0.0


def ratio(numerator: float, denominator: float) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def bucket_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            f"nibble={row.get('top_nibble', '')}",
            f"control={row.get('control_window_signature', '')}",
        ]
    )


def next_action_for_bucket(rows: int, bytes_: int) -> str:
    if rows >= 3 and bytes_ >= 128:
        return "inspect shared control payload and transition profile"
    if rows >= 2:
        return "compare pair for repeated jump placement"
    return "singleton review only"


def build(target_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    jump_rows = [row for row in target_rows if row.get("micro_class") == "jump_mixed_walk"]
    by_bucket: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in jump_rows:
        by_bucket[bucket_key(row)].append(row)

    bucket_rows: list[dict[str, object]] = []
    for key, rows in by_bucket.items():
        sample = rows[0]
        bytes_ = sum(int_value(row, "length") for row in rows)
        jump_count = sum(int_value(row, "jump_delta_count") for row in rows)
        small_count = sum(int_value(row, "small_delta_count") for row in rows)
        zero_count = sum(int_value(row, "zero_delta_count") for row in rows)
        bucket_rows.append(
            {
                "rank": 0,
                "bucket_key": key,
                "rows": len(rows),
                "bytes": bytes_,
                "top_nibble": sample.get("top_nibble", ""),
                "control_window_signature": sample.get("control_window_signature", ""),
                "transition_profile_key": len({row.get("transition_profile_key", "") for row in rows}),
                "coarse_shape_keys": len({row.get("coarse_shape_key", "") for row in rows}),
                "signed_shape_keys": len({row.get("signed_shape_key", "") for row in rows}),
                "jump_delta_count": jump_count,
                "small_delta_count": small_count,
                "zero_delta_count": zero_count,
                "avg_jump_ratio": ratio(sum(float_value(row, "jump_delta_ratio") for row in rows), len(rows)),
                "avg_small_ratio": ratio(sum(float_value(row, "small_delta_ratio") for row in rows), len(rows)),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "next_action": next_action_for_bucket(len(rows), bytes_),
            }
        )

    bucket_rows.sort(key=lambda row: (-int(row["rows"]), -int(row["bytes"]), str(row["bucket_key"])))
    bucket_rank = {str(row["bucket_key"]): index for index, row in enumerate(bucket_rows, start=1)}
    for index, row in enumerate(bucket_rows, start=1):
        row["rank"] = index

    target_output: list[dict[str, object]] = []
    for index, row in enumerate(
        sorted(jump_rows, key=lambda item: (bucket_rank[bucket_key(item)], int_value(item, "rank"))),
        start=1,
    ):
        key = bucket_key(row)
        target_output.append(
            {
                "rank": index,
                "bucket_rank": bucket_rank[key],
                "bucket_key": key,
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "length": row.get("length", ""),
                "top_nibble": row.get("top_nibble", ""),
                "top_nibble_ratio": row.get("top_nibble_ratio", ""),
                "control_window_signature": row.get("control_window_signature", ""),
                "transition_profile_key": row.get("transition_profile_key", ""),
                "transition_profile_preview": row.get("transition_profile_preview", ""),
                "jump_delta_count": row.get("jump_delta_count", ""),
                "jump_delta_ratio": row.get("jump_delta_ratio", ""),
                "small_delta_count": row.get("small_delta_count", ""),
                "small_delta_ratio": row.get("small_delta_ratio", ""),
                "coarse_shape_key": row.get("coarse_shape_key", ""),
                "signed_shape_key": row.get("signed_shape_key", ""),
                "head_hex": row.get("head_hex", ""),
                "tail_hex": row.get("tail_hex", ""),
                "issues": row.get("issues", ""),
            }
        )

    repeated = [row for row in bucket_rows if int(row["rows"]) > 1]
    largest = bucket_rows[0] if bucket_rows else {}
    summary = {
        "scope": "total",
        "source_rows": len(target_rows),
        "jump_mixed_rows": len(jump_rows),
        "jump_mixed_bytes": sum(int_value(row, "length") for row in jump_rows),
        "top_nibble_groups": len({row.get("top_nibble", "") for row in jump_rows}),
        "control_signature_groups": len({row.get("control_window_signature", "") for row in jump_rows}),
        "transition_profile_groups": len({row.get("transition_profile_key", "") for row in jump_rows}),
        "review_bucket_rows": len(bucket_rows),
        "repeated_bucket_rows": len(repeated),
        "repeated_bucket_bytes": sum(int(row["bytes"]) for row in repeated),
        "largest_bucket_rows": largest.get("rows", 0),
        "largest_bucket_bytes": largest.get("bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in jump_rows if row.get("issues")),
    }
    return summary, bucket_rows, target_output


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 120) -> str:
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
table {{ border-collapse: collapse; width: 100%; min-width: 1400px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; text-align: left; background: #172023; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['jump_mixed_rows']}</div><div class="muted">jump mixed rows</div></div>
  <div class="box"><div class="num">{summary['jump_mixed_bytes']}</div><div class="muted">bytes</div></div>
  <div class="box"><div class="num">{summary['review_bucket_rows']}</div><div class="muted">buckets</div></div>
  <div class="box"><div class="num">{summary['repeated_bucket_rows']}</div><div class="muted">repeated buckets</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Buckets</h2>{render_table(buckets, BUCKET_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</div>
<script type="application/json" id="split-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split .tex micro-token jump-mixed rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Jump Split")
    args = parser.parse_args()

    summary, buckets, targets = build(read_rows(args.targets))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "buckets.csv", BUCKET_FIELDNAMES, buckets)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, buckets, targets, args.title))

    print(f"Jump-mixed rows: {summary['jump_mixed_rows']}")
    print(f"Review buckets: {summary['review_bucket_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
