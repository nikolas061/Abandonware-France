#!/usr/bin/env python3
"""Probe mixed-transform palette seeds for flat-walk source rows."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_seed_probe import (
    DEFAULT_TARGETS,
    SMALL_POOLS,
    build_unlock_map,
    first_unique,
    operation_key,
    target_key,
    transform_names,
    transformed_pool,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_probe import value_runs
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_source_probe import (
    source_pools,
    target_op_key,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe")
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "candidate_rows",
    "candidate_bytes",
    "control_candidate_rows",
    "control_candidate_bytes",
    "mixed_candidate_rows",
    "mixed_candidate_bytes",
    "single_transform_rows",
    "single_transform_bytes",
    "multirow_group_rows",
    "best_group_rows",
    "best_group_bytes",
    "best_group",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_candidate_plus_unlock_bytes",
    "max_palette_size",
    "max_mix_transforms",
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
    "transform_count",
    "candidate_transform_set",
    "candidate_plan",
    "candidate_kind",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "pool",
    "transform_set",
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

POOL_RANK = {
    "control_window": 0,
    "control_prefix": 1,
    "fragment": 2,
    "neighbor": 3,
    "segment_gap": 4,
}


def transform_complexity(transform: str) -> tuple[int, int]:
    base = transform
    delta = 0
    if "_shift" in transform:
        base, delta_text = transform.split("_shift", 1)
        delta = abs(int(delta_text))
    base_rank = {
        "identity": 0,
        "low7": 1,
        "nibble_swap": 2,
        "bit_not": 3,
    }.get(base, 9)
    return base_rank, delta


def transform_sort_key(transform: str) -> tuple[int, int, str]:
    base_rank, delta = transform_complexity(transform)
    return base_rank, delta, transform


def cover_map(pool: bytes, values: list[int], transforms: list[str]) -> dict[str, set[int]]:
    wanted = set(values)
    output: dict[str, set[int]] = {}
    for transform in transforms:
        covered = set(transformed_pool(pool, transform)) & wanted
        if covered:
            output[transform] = covered
    return output


def best_transform_cover(
    pool: bytes,
    values: list[int],
    transforms: list[str],
    *,
    max_mix_transforms: int,
) -> list[str]:
    wanted = set(values)
    if not wanted or not pool:
        return []
    covers = cover_map(pool, values, transforms)
    if not covers:
        return []
    cover_items = sorted(covers.items(), key=lambda item: transform_sort_key(item[0]))
    for size in range(1, max_mix_transforms + 1):
        best_score: tuple[int, int, int, tuple[str, ...]] | None = None
        best_names: tuple[str, ...] = ()
        for combo in itertools.combinations(cover_items, size):
            names = tuple(name for name, _covered in combo)
            union: set[int] = set()
            for _name, covered in combo:
                union.update(covered)
            if not wanted.issubset(union):
                continue
            complexity = sum(sum(transform_complexity(name)) for name in names)
            identity_count = sum(1 for name in names if name == "identity")
            total_coverage = sum(len(covers[name]) for name in names)
            score = (complexity, -identity_count, -total_coverage, names)
            if best_score is None or score < best_score:
                best_score = score
                best_names = names
        if best_names:
            return list(best_names)
    return []


def source_choice(pool: bytes, value: int, transforms: list[str]) -> tuple[str, int] | None:
    choices: list[tuple[tuple[int, int, str, int], str, int]] = []
    for transform in transforms:
        transformed = transformed_pool(pool, transform)
        try:
            offset = transformed.index(value)
        except ValueError:
            continue
        choices.append(((*transform_sort_key(transform), offset), transform, offset))
    if not choices:
        return None
    _score, transform, offset = min(choices, key=lambda item: item[0])
    return transform, offset


def candidate_plan(pool: bytes, values: list[int], transforms: list[str]) -> str:
    parts: list[str] = []
    for value in values:
        choice = source_choice(pool, value, transforms)
        if choice is None:
            parts.append(f"0x{value:02x}=missing")
            continue
        transform, offset = choice
        parts.append(f"0x{value:02x}={transform}@{offset}")
    return " ".join(parts)


def candidate_verdict(row: dict[str, str]) -> str:
    if not row.get("candidate_pool"):
        return "no_mixed_palette"
    prefix = "single_transform" if row.get("candidate_kind") == "single_transform" else "mixed_transform"
    if int_value(row, "copy_unlock_bytes") > 0:
        return f"{prefix}_seed_unlocks_backref"
    return f"{prefix}_seed_review"


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
    *,
    max_palette_size: int,
    max_mix_transforms: int,
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
            "transform_count": "0",
            "candidate_transform_set": "",
            "candidate_plan": "",
            "candidate_kind": "",
            "copy_unlock_rows": str(unlock["rows"]),
            "copy_unlock_bytes": str(unlock["bytes"]),
            "total_potential_bytes": "0",
            "verdict": "",
            "issues": "",
        }
        if len(unique_values) <= max_palette_size:
            best: tuple[int, int, int, tuple[str, ...], str, bytes, list[str]] | None = None
            for pool_name in SMALL_POOLS:
                pool = pools.get(pool_name, b"")
                transform_set = best_transform_cover(
                    pool,
                    unique_values,
                    transforms,
                    max_mix_transforms=max_mix_transforms,
                )
                if not transform_set:
                    continue
                complexity = sum(sum(transform_complexity(name)) for name in transform_set)
                score = (
                    len(transform_set),
                    POOL_RANK.get(pool_name, 9),
                    complexity,
                    tuple(transform_set),
                    pool_name,
                    pool,
                    transform_set,
                )
                if best is None or score < best:
                    best = score
            if best is not None:
                _count, _pool_rank, _complexity, _names, pool_name, pool, transform_set = best
                row["candidate_pool"] = pool_name
                row["transform_count"] = str(len(transform_set))
                row["candidate_transform_set"] = "+".join(transform_set)
                row["candidate_plan"] = candidate_plan(pool, unique_values, transform_set)
                row["candidate_kind"] = "single_transform" if len(transform_set) == 1 else "mixed_transform"
        else:
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
    if not row:
        return ""
    return f"{row.get('pool')}|{row.get('transform_set')}"


def build_group_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    palette_sizes: dict[tuple[str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if not row.get("candidate_pool"):
            continue
        key = row.get("candidate_pool", ""), row.get("candidate_transform_set", "")
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
                "transform_set": key[1],
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
            int_value(row, "rows"),
            row.get("pool", ""),
            row.get("transform_set", ""),
        )
    )
    return output


def build_summary(
    rows: list[dict[str, str]],
    groups: list[dict[str, str]],
    fixture_issues: list[str],
    *,
    max_palette_size: int,
    max_mix_transforms: int,
) -> dict[str, str]:
    candidates = [row for row in rows if row.get("candidate_pool")]
    control_candidates = [row for row in candidates if row.get("candidate_pool") == "control_window"]
    mixed_candidates = [row for row in candidates if row.get("candidate_kind") == "mixed_transform"]
    single_candidates = [row for row in candidates if row.get("candidate_kind") == "single_transform"]
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
        "mixed_candidate_rows": str(len(mixed_candidates)),
        "mixed_candidate_bytes": str(sum(int_value(row, "length") for row in mixed_candidates)),
        "single_transform_rows": str(len(single_candidates)),
        "single_transform_bytes": str(sum(int_value(row, "length") for row in single_candidates)),
        "multirow_group_rows": str(len(multirow_groups)),
        "best_group_rows": best_group.get("rows", "0"),
        "best_group_bytes": best_group.get("bytes", "0"),
        "best_group": group_label(best_group),
        "copy_unlock_rows": str(sum(int_value(row, "copy_unlock_rows") for row in candidates)),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in candidates)),
        "total_candidate_plus_unlock_bytes": str(sum(int_value(row, "total_potential_bytes") for row in candidates)),
        "max_palette_size": str(max_palette_size),
        "max_mix_transforms": str(max_mix_transforms),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + len(fixture_issues)),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
    *,
    max_palette_size: int,
    max_mix_transforms: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(
        target_rows,
        operation_rows,
        fixture_rows,
        backref_rows,
        max_palette_size=max_palette_size,
        max_mix_transforms=max_mix_transforms,
    )
    groups = build_group_rows(rows)
    summary = build_summary(
        rows,
        groups,
        fixture_issues,
        max_palette_size=max_palette_size,
        max_mix_transforms=max_mix_transforms,
    )
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
            ("by_pool_transform_set.csv", output_dir / "by_pool_transform_set.csv"),
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
.wrap {{ width: min(1760px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1720px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores compact mixed-transform palette covers for flat-walk rows; singleton groups remain review-only.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidates</div><div class="value">{summary['candidate_rows']}</div></div>
    <div class="stat"><div class="label">Candidate bytes</div><div class="value warn">{summary['candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Mixed bytes</div><div class="value warn">{summary['mixed_candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Copy unlock bytes</div><div class="value warn">{summary['copy_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_candidate_plus_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Multirow groups</div><div class="value">{summary['multirow_group_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 140)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_MIX_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex flat-walk mixed-transform palette seeds.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("--max-palette-size", type=int, default=9)
    parser.add_argument("--max-mix-transforms", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Palette Mix Probe",
    )
    args = parser.parse_args()

    summary, targets, groups = build_rows(
        read_csv(args.targets),
        read_csv(args.operations),
        read_csv(args.fixtures),
        read_csv(args.backref_targets),
        max_palette_size=args.max_palette_size,
        max_mix_transforms=args.max_mix_transforms,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_pool_transform_set.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, groups, args.output, args.title))

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Mixed candidate bytes: {summary['mixed_candidate_bytes']}")
    print(f"Copy unlock bytes: {summary['copy_unlock_bytes']}")
    print(f"Total potential bytes: {summary['total_candidate_plus_unlock_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
