#!/usr/bin/env python3
"""Find singleton palette-value seeds for flat-walk back-reference sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
    transform_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_probe import (
    DEFAULT_OUTPUT as DEFAULT_SHAPE_OUTPUT,
    value_runs,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_source_probe import (
    source_pools,
    target_op_key,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe")
DEFAULT_TARGETS = DEFAULT_SHAPE_OUTPUT / "targets.csv"
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"

BASE_TRANSFORMS = ("identity", "low7", "bit_not", "nibble_swap")
SHIFT_DELTAS = (-3, -2, -1, 0, 1, 2, 3)
SMALL_POOLS = ("control_window", "control_prefix", "fragment", "neighbor")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "candidate_rows",
    "candidate_bytes",
    "control_candidate_rows",
    "control_candidate_bytes",
    "multirow_group_rows",
    "best_group_rows",
    "best_group_bytes",
    "best_group",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_candidate_plus_unlock_bytes",
    "max_palette_size",
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
    "control_ref_mod64",
    "palette_size",
    "unique_values_hex",
    "candidate_pool",
    "candidate_transform",
    "candidate_offsets",
    "candidate_source_values_hex",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "pool",
    "transform",
    "rows",
    "bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "palette_sizes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def operation_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def transform_names() -> list[str]:
    output: list[str] = []
    for base in BASE_TRANSFORMS:
        for delta in SHIFT_DELTAS:
            output.append(base if delta == 0 else f"{base}_shift{delta:+d}")
    return output


def transformed_pool(data: bytes, transform: str) -> bytes:
    if "_shift" not in transform:
        return transform_bytes(data, transform)
    base, delta_text = transform.split("_shift", 1)
    base_data = transform_bytes(data, base)
    delta = int(delta_text)
    return bytes((value + delta) & 0xFF for value in base_data)


def first_unique(values: list[int]) -> list[int]:
    return list(OrderedDict((value, None) for value in values).keys())


def source_offsets_for_values(source: bytes, values: list[int]) -> list[int] | None:
    offsets: list[int] = []
    for value in values:
        try:
            offsets.append(source.index(value))
        except ValueError:
            return None
    return offsets


def backref_source_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("best_source_start", ""),
        row.get("best_source_end", ""),
    )


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def build_unlock_map(backref_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], Counter[str]]:
    unlocks: dict[tuple[str, str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in backref_rows:
        if row.get("best_exact") != "1":
            continue
        key = backref_source_key(row)
        unlocks[key]["rows"] += 1
        unlocks[key]["bytes"] += int_value(row, "length")
    return unlocks


def candidate_verdict(row: dict[str, str]) -> str:
    if not row.get("candidate_pool"):
        return "no_small_pool_palette"
    if int_value(row, "copy_unlock_bytes") > 0:
        return "singleton_seed_unlocks_backref"
    return "singleton_seed_review"


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
    *,
    max_palette_size: int,
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    fixtures = {fixture_key(row): row for row in fixture_rows}
    operations = {operation_key(row): row for row in operation_rows}
    unlocks = build_unlock_map(backref_rows)
    transforms = transform_names()
    rows: list[dict[str, str]] = []

    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = source_pools(target, fixtures.get(fixture_key(target), {}), operation, issues)
        run_values = [value for value, _count in value_runs(expected)]
        unique_values = first_unique(run_values)
        unlock = unlocks.get(target_key(target), Counter())
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
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "palette_size": str(len(unique_values)),
            "unique_values_hex": " ".join(f"0x{value:02x}" for value in unique_values),
            "candidate_pool": "",
            "candidate_transform": "",
            "candidate_offsets": "",
            "candidate_source_values_hex": "",
            "copy_unlock_rows": str(unlock["rows"]),
            "copy_unlock_bytes": str(unlock["bytes"]),
            "total_potential_bytes": "0",
            "verdict": "",
            "issues": "",
        }
        if len(unique_values) <= max_palette_size:
            best: tuple[int, int, str, str, list[int], bytes] | None = None
            for pool_name in SMALL_POOLS:
                pool = pools.get(pool_name, b"")
                if not pool:
                    continue
                for transform in transforms:
                    transformed = transformed_pool(pool, transform)
                    offsets = source_offsets_for_values(transformed, unique_values)
                    if offsets is None:
                        continue
                    score = (
                        1 if pool_name == "control_window" else 0,
                        -sum(offsets),
                        pool_name,
                        transform,
                        offsets,
                        transformed,
                    )
                    if best is None or score > best:
                        best = score
            if best is not None:
                _control_preference, _offset_score, pool_name, transform, offsets, transformed = best
                row["candidate_pool"] = pool_name
                row["candidate_transform"] = transform
                row["candidate_offsets"] = " ".join(str(offset) for offset in offsets)
                row["candidate_source_values_hex"] = " ".join(f"0x{transformed[offset]:02x}" for offset in offsets)
        elif len(unique_values) > max_palette_size:
            row["verdict"] = "palette_over_limit"
        row["total_potential_bytes"] = (
            str(len(expected) + int_value(row, "copy_unlock_bytes")) if row.get("candidate_pool") else "0"
        )
        if not row["verdict"]:
            row["verdict"] = candidate_verdict(row)
        row["issues"] = ";".join(issues)
        rows.append(row)
    return rows, fixture_issues


def group_label(row: dict[str, str]) -> str:
    return f"{row.get('pool')}|{row.get('transform')}"


def build_group_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    palette_sizes: dict[tuple[str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if not row.get("candidate_pool"):
            continue
        key = row.get("candidate_pool", ""), row.get("candidate_transform", "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["copy_unlock_rows"] += int_value(row, "copy_unlock_rows")
        counters[key]["copy_unlock_bytes"] += int_value(row, "copy_unlock_bytes")
        counters[key]["total_potential_bytes"] += int_value(row, "total_potential_bytes")
        fixtures[key].add(fixture_key(row))
        palette_sizes[key].add(row.get("palette_size", ""))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "pool": key[0],
                "transform": key[1],
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "copy_unlock_rows": str(counter["copy_unlock_rows"]),
                "copy_unlock_bytes": str(counter["copy_unlock_bytes"]),
                "total_potential_bytes": str(counter["total_potential_bytes"]),
                "palette_sizes": " ".join(sorted(palette_sizes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "total_potential_bytes"),
            -int_value(row, "bytes"),
            row.get("pool", ""),
            row.get("transform", ""),
        )
    )
    return output


def build_summary(
    rows: list[dict[str, str]],
    groups: list[dict[str, str]],
    fixture_issues: list[str],
    *,
    max_palette_size: int,
) -> dict[str, str]:
    candidates = [row for row in rows if row.get("candidate_pool")]
    control_candidates = [row for row in candidates if row.get("candidate_pool") == "control_window"]
    multirow_groups = [row for row in groups if int_value(row, "rows") > 1]
    best_group = max(groups, key=lambda row: int_value(row, "total_potential_bytes"), default={})
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "candidate_rows": str(len(candidates)),
        "candidate_bytes": str(sum(int_value(row, "length") for row in candidates)),
        "control_candidate_rows": str(len(control_candidates)),
        "control_candidate_bytes": str(sum(int_value(row, "length") for row in control_candidates)),
        "multirow_group_rows": str(len(multirow_groups)),
        "best_group_rows": best_group.get("rows", "0"),
        "best_group_bytes": best_group.get("bytes", "0"),
        "best_group": group_label(best_group) if best_group else "",
        "copy_unlock_rows": str(sum(int_value(row, "copy_unlock_rows") for row in candidates)),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in candidates)),
        "total_candidate_plus_unlock_bytes": str(sum(int_value(row, "total_potential_bytes") for row in candidates)),
        "max_palette_size": str(max_palette_size),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + len(fixture_issues)),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
    *,
    max_palette_size: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(
        target_rows,
        operation_rows,
        fixture_rows,
        backref_rows,
        max_palette_size=max_palette_size,
    )
    groups = build_group_rows(rows)
    summary = build_summary(rows, groups, fixture_issues, max_palette_size=max_palette_size)
    return summary, rows, groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_pool_transform.csv", output_dir / "by_pool_transform.csv"),
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
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1600px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Looks for small-pool palette seeds that can produce first flat-walk occurrences and unlock exact backrefs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{summary['candidate_rows']}</div></div>
    <div class="stat"><div class="label">Candidate bytes</div><div class="value warn">{summary['candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Control candidates</div><div class="value ok">{summary['control_candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Copy unlock bytes</div><div class="value warn">{summary['copy_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_candidate_plus_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Multirow groups</div><div class="value">{summary['multirow_group_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_SEED_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex flat-walk palette seeds.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("--max-palette-size", type=int, default=9)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Palette Seed Probe",
    )
    args = parser.parse_args()

    summary, targets, groups = build_rows(
        read_csv(args.targets),
        read_csv(args.operations),
        read_csv(args.fixtures),
        read_csv(args.backref_targets),
        max_palette_size=args.max_palette_size,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_pool_transform.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, groups, args.output, args.title))

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Control candidate bytes: {summary['control_candidate_bytes']}")
    print(f"Copy unlock bytes: {summary['copy_unlock_bytes']}")
    print(f"Total potential bytes: {summary['total_candidate_plus_unlock_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
