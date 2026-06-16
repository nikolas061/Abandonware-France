#!/usr/bin/env python3
"""Split jump-heavy noisy nonzero rows into islands and jump profiles."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "delta_count",
    "jump_delta_count",
    "jump_delta_ratio",
    "positive_jump_count",
    "negative_jump_count",
    "jump_rows_ge4",
    "jump_rows_ge8",
    "island_count",
    "single_byte_islands",
    "long_island_count",
    "long_island_bytes",
    "island_length_shape_groups",
    "island_length_repeated_groups",
    "island_length_repeated_rows",
    "island_length_repeated_bytes",
    "jump_signed_shape_groups",
    "jump_signed_repeated_groups",
    "jump_signed_repeated_rows",
    "jump_signed_repeated_bytes",
    "jump_nibble_pair_groups",
    "jump_nibble_pair_repeated_groups",
    "jump_nibble_pair_repeated_rows",
    "jump_nibble_pair_repeated_bytes",
    "jump_exact_pair_groups",
    "jump_exact_pair_repeated_groups",
    "jump_exact_pair_repeated_rows",
    "jump_exact_pair_repeated_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "control_window_signature",
    "delta_count",
    "jump_delta_count",
    "jump_delta_ratio",
    "positive_jump_count",
    "negative_jump_count",
    "first_jump_index",
    "last_jump_index",
    "island_count",
    "single_byte_islands",
    "long_island_count",
    "long_island_bytes",
    "max_island_length",
    "top_jump_nibble_pair",
    "top_jump_nibble_pair_count",
    "top_jump_nibble_pair_ratio",
    "island_length_shape_key",
    "island_length_shape_preview",
    "jump_signed_shape_key",
    "jump_signed_shape_preview",
    "jump_nibble_pair_key",
    "jump_nibble_pair_preview",
    "jump_exact_pair_key",
    "jump_exact_pair_preview",
    "jump_structure_class",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "group_preview",
    "rows",
    "bytes",
    "delta_count",
    "jump_delta_count",
    "island_count",
    "long_island_bytes",
    "jump_structure_classes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def deltas(data: bytes) -> list[int]:
    return [signed_delta(data[index - 1], data[index]) for index in range(1, len(data))]


def jump_indices(delta_values: list[int]) -> list[int]:
    return [index + 1 for index, value in enumerate(delta_values) if abs(value) > 31]


def jump_signed_label(delta: int) -> str:
    prefix = "+" if delta > 0 else "-"
    magnitude = abs(delta)
    if magnitude <= 63:
        bucket = "32_63"
    elif magnitude <= 95:
        bucket = "64_95"
    else:
        bucket = "96_128"
    return f"{prefix}{bucket}"


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 140) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def islands_for_jumps(length: int, jumps: list[int]) -> list[int]:
    if length <= 0:
        return []
    starts = [0] + jumps
    ends = jumps + [length]
    return [max(0, end - start) for start, end in zip(starts, ends)]


def run_shape(values: list[str]) -> str:
    if not values:
        return ""
    parts: list[str] = []
    current = values[0]
    count = 1
    for value in values[1:]:
        if value == current:
            count += 1
            continue
        parts.append(f"{current}x{count}")
        current = value
        count = 1
    parts.append(f"{current}x{count}")
    return ".".join(parts)


def jump_pair_values(data: bytes, jumps: list[int]) -> list[tuple[int, int, int]]:
    pairs: list[tuple[int, int, int]] = []
    for index in jumps:
        if index <= 0 or index >= len(data):
            continue
        left = data[index - 1]
        right = data[index]
        pairs.append((left, right, signed_delta(left, right)))
    return pairs


def classify_jump_structure(row: dict[str, str]) -> str:
    jump_ratio = float(row.get("jump_delta_ratio", "0") or 0)
    top_ratio = float(row.get("top_jump_nibble_pair_ratio", "0") or 0)
    long_island_count = int_value(row, "long_island_count")
    jump_count = int_value(row, "jump_delta_count")
    if jump_ratio >= 0.40:
        return "dense_jump_weave"
    if top_ratio >= 0.50 and jump_count >= 4:
        return "repeated_nibble_jump"
    if long_island_count >= 3:
        return "long_island_split"
    if jump_count <= 3:
        return "sparse_jump_split"
    return "mixed_jump_split"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("micro_class") != "jump_mixed_walk":
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue

        delta_values = deltas(expected)
        jumps = jump_indices(delta_values)
        pairs = jump_pair_values(expected, jumps)
        signed_labels = [jump_signed_label(delta) for _left, _right, delta in pairs]
        nibble_pairs = [f"{left >> 4:x}>{right >> 4:x}" for left, right, _delta in pairs]
        exact_pairs = [f"{left:02x}>{right:02x}" for left, right, _delta in pairs]
        island_lengths = islands_for_jumps(len(expected), jumps)
        long_islands = [length for length in island_lengths if length >= 8]
        top_pair, top_pair_count = Counter(nibble_pairs).most_common(1)[0] if nibble_pairs else ("", 0)
        island_shape = ".".join(str(length) for length in island_lengths)
        signed_shape = run_shape(signed_labels)
        nibble_shape = ".".join(nibble_pairs)
        exact_shape = ".".join(exact_pairs)
        positive_count = sum(1 for _left, _right, delta in pairs if delta > 0)
        negative_count = sum(1 for _left, _right, delta in pairs if delta < 0)
        row = {
            "rank": target.get("rank", ""),
            "archive": target.get("archive", ""),
            "archive_tag": target.get("archive_tag", ""),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(expected)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "start_mod64": target.get("start_mod64", ""),
            "control_ref_offset": target.get("control_ref_offset", ""),
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "control_window_signature": target.get("control_window_signature", ""),
            "delta_count": str(len(delta_values)),
            "jump_delta_count": str(len(jumps)),
            "jump_delta_ratio": ratio(len(jumps), len(delta_values)),
            "positive_jump_count": str(positive_count),
            "negative_jump_count": str(negative_count),
            "first_jump_index": str(jumps[0]) if jumps else "",
            "last_jump_index": str(jumps[-1]) if jumps else "",
            "island_count": str(len(island_lengths)),
            "single_byte_islands": str(sum(1 for length in island_lengths if length == 1)),
            "long_island_count": str(len(long_islands)),
            "long_island_bytes": str(sum(long_islands)),
            "max_island_length": str(max(island_lengths, default=0)),
            "top_jump_nibble_pair": top_pair,
            "top_jump_nibble_pair_count": str(top_pair_count),
            "top_jump_nibble_pair_ratio": ratio(top_pair_count, len(nibble_pairs)),
            "island_length_shape_key": shape_key(island_shape),
            "island_length_shape_preview": preview_text(island_shape),
            "jump_signed_shape_key": shape_key(signed_shape),
            "jump_signed_shape_preview": preview_text(signed_shape),
            "jump_nibble_pair_key": shape_key(nibble_shape),
            "jump_nibble_pair_preview": preview_text(nibble_shape),
            "jump_exact_pair_key": shape_key(exact_shape),
            "jump_exact_pair_preview": preview_text(exact_shape),
            "jump_structure_class": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["jump_structure_class"] = classify_jump_structure(row)
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], key_field: str, preview_field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    classes: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    previews: dict[str, str] = {}
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["delta_count"] += int_value(row, "delta_count")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        counters[key]["island_count"] += int_value(row, "island_count")
        counters[key]["long_island_bytes"] += int_value(row, "long_island_bytes")
        classes[key].add(row.get("jump_structure_class", ""))
        fixtures[key].add(fixture_key(row))
        previews.setdefault(key, row.get(preview_field, ""))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "group_preview": previews.get(key, ""),
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "delta_count": str(counter["delta_count"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "island_count": str(counter["island_count"]),
                "long_island_bytes": str(counter["long_island_bytes"]),
                "jump_structure_classes": ";".join(sorted(classes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("group_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    island_groups: list[dict[str, str]],
    signed_groups: list[dict[str, str]],
    nibble_groups: list[dict[str, str]],
    exact_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    delta_count = sum(int_value(row, "delta_count") for row in rows)
    jump_count = sum(int_value(row, "jump_delta_count") for row in rows)
    island_repeated = repeated_stats(island_groups)
    signed_repeated = repeated_stats(signed_groups)
    nibble_repeated = repeated_stats(nibble_groups)
    exact_repeated = repeated_stats(exact_groups)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "delta_count": str(delta_count),
        "jump_delta_count": str(jump_count),
        "jump_delta_ratio": ratio(jump_count, delta_count),
        "positive_jump_count": str(sum(int_value(row, "positive_jump_count") for row in rows)),
        "negative_jump_count": str(sum(int_value(row, "negative_jump_count") for row in rows)),
        "jump_rows_ge4": str(sum(1 for row in rows if int_value(row, "jump_delta_count") >= 4)),
        "jump_rows_ge8": str(sum(1 for row in rows if int_value(row, "jump_delta_count") >= 8)),
        "island_count": str(sum(int_value(row, "island_count") for row in rows)),
        "single_byte_islands": str(sum(int_value(row, "single_byte_islands") for row in rows)),
        "long_island_count": str(sum(int_value(row, "long_island_count") for row in rows)),
        "long_island_bytes": str(sum(int_value(row, "long_island_bytes") for row in rows)),
        "island_length_shape_groups": str(len(island_groups)),
        "island_length_repeated_groups": str(island_repeated[0]),
        "island_length_repeated_rows": str(island_repeated[1]),
        "island_length_repeated_bytes": str(island_repeated[2]),
        "jump_signed_shape_groups": str(len(signed_groups)),
        "jump_signed_repeated_groups": str(signed_repeated[0]),
        "jump_signed_repeated_rows": str(signed_repeated[1]),
        "jump_signed_repeated_bytes": str(signed_repeated[2]),
        "jump_nibble_pair_groups": str(len(nibble_groups)),
        "jump_nibble_pair_repeated_groups": str(nibble_repeated[0]),
        "jump_nibble_pair_repeated_rows": str(nibble_repeated[1]),
        "jump_nibble_pair_repeated_bytes": str(nibble_repeated[2]),
        "jump_exact_pair_groups": str(len(exact_groups)),
        "jump_exact_pair_repeated_groups": str(exact_repeated[0]),
        "jump_exact_pair_repeated_rows": str(exact_repeated[1]),
        "jump_exact_pair_repeated_bytes": str(exact_repeated[2]),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    class_groups = build_group_rows(rows, "jump_structure_class", "jump_structure_class", "jump_structure_class")
    island_groups = build_group_rows(rows, "island_length_shape_key", "island_length_shape_preview", "island_length_shape")
    signed_groups = build_group_rows(rows, "jump_signed_shape_key", "jump_signed_shape_preview", "jump_signed_shape")
    nibble_groups = build_group_rows(rows, "jump_nibble_pair_key", "jump_nibble_pair_preview", "jump_nibble_pair")
    exact_groups = build_group_rows(rows, "jump_exact_pair_key", "jump_exact_pair_preview", "jump_exact_pair")
    summary = build_summary(rows, island_groups, signed_groups, nibble_groups, exact_groups, len(fixture_issues))
    return summary, rows, class_groups, island_groups, signed_groups, nibble_groups, exact_groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    class_groups: list[dict[str, str]],
    island_groups: list[dict[str, str]],
    signed_groups: list[dict[str, str]],
    nibble_groups: list[dict[str, str]],
    exact_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "classGroups": class_groups,
        "islandGroups": island_groups,
        "signedGroups": signed_groups,
        "nibbleGroups": nibble_groups,
        "exactGroups": exact_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_jump_structure_class.csv", output_dir / "by_jump_structure_class.csv"),
            ("by_island_length_shape.csv", output_dir / "by_island_length_shape.csv"),
            ("by_jump_signed_shape.csv", output_dir / "by_jump_signed_shape.csv"),
            ("by_jump_nibble_pair.csv", output_dir / "by_jump_nibble_pair.csv"),
            ("by_jump_exact_pair.csv", output_dir / "by_jump_exact_pair.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Splits jump-heavy noisy rows into islands, signed jump buckets, and byte/nibble jump profiles.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Jump rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Jump bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Jump ratio</div><div class="value warn">{summary['jump_delta_ratio']}</div></div>
    <div class="stat"><div class="label">Long island bytes</div><div class="value ok">{summary['long_island_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Jump classes</h2>{render_table(class_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Island length shapes</h2>{render_table(island_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Signed jump shapes</h2>{render_table(signed_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Jump nibble pairs</h2>{render_table(nibble_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Jump exact pairs</h2>{render_table(exact_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_JUMP_TOKEN_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe jump-heavy noisy .tex nonzero gap rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Jump Token Probe",
    )
    args = parser.parse_args()

    summary, rows, class_groups, island_groups, signed_groups, nibble_groups, exact_groups = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_jump_structure_class.csv", GROUP_FIELDNAMES, class_groups)
    write_csv(args.output / "by_island_length_shape.csv", GROUP_FIELDNAMES, island_groups)
    write_csv(args.output / "by_jump_signed_shape.csv", GROUP_FIELDNAMES, signed_groups)
    write_csv(args.output / "by_jump_nibble_pair.csv", GROUP_FIELDNAMES, nibble_groups)
    write_csv(args.output / "by_jump_exact_pair.csv", GROUP_FIELDNAMES, exact_groups)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(
            summary,
            rows,
            class_groups,
            island_groups,
            signed_groups,
            nibble_groups,
            exact_groups,
            args.output,
            args.title,
        )
    )

    print(f"Jump-token targets: {summary['target_rows']}")
    print(f"Jump-token bytes: {summary['target_bytes']}")
    print(f"Jump delta ratio: {summary['jump_delta_ratio']}")
    print(f"Long island bytes: {summary['long_island_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
