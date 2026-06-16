#!/usr/bin/env python3
"""Score per-value delta selectors for repeated gradient seed candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv as read_fixture_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe")
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe/targets.csv"
)
DEFAULT_PALETTE_MIX_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "seed_rows",
    "seed_bytes",
    "mapping_rows",
    "mapping_value_bytes",
    "source_only_selector_families",
    "source_only_selector_groups",
    "source_only_repeated_deterministic_groups",
    "source_only_repeated_deterministic_bytes",
    "source_only_conflicted_groups",
    "source_only_conflicted_bytes",
    "best_source_only_family",
    "best_source_only_repeated_deterministic_bytes",
    "row_local_repeated_deterministic_bytes",
    "target_oracle_repeated_deterministic_bytes",
    "delta_values",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

VALUE_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "start",
    "end",
    "length",
    "candidate_kind",
    "palette_size",
    "palette_index",
    "target_value_hex",
    "source_value_hex",
    "delta",
    "source_offset",
    "value_bytes",
    "copy_unlock_bytes",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "selector_kind",
    "selector_family",
    "selector_key",
    "rows",
    "seed_rows",
    "value_bytes",
    "deltas_seen",
    "deterministic",
    "repeated_deterministic",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "selector_kind",
    "selector_family",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]

DELTA_FIELDNAMES = [
    "delta",
    "rows",
    "seed_rows",
    "value_bytes",
    "target_values_hex",
    "source_values_hex",
    "source_offsets",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("run_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def rank_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str, str, str], str]:
    output: dict[tuple[str, str, str, str, str, str, str], str] = {}
    for row in rows:
        output[target_key(row)] = row.get("rank", "")
    return output


def parse_transform(transform: str) -> tuple[str, int]:
    if "_shift" not in transform:
        return transform, 0
    base, delta_text = transform.split("_shift", 1)
    return base, int(delta_text)


def parse_plan(plan: str) -> list[dict[str, int | str]]:
    output: list[dict[str, int | str]] = []
    for index, token in enumerate(plan.split()):
        if "=" not in token or "@" not in token:
            continue
        value_hex, rest = token.split("=", 1)
        transform, offset_text = rest.rsplit("@", 1)
        try:
            target_value = int(value_hex, 16)
            offset = int(offset_text)
            _base, delta = parse_transform(transform)
        except ValueError:
            continue
        output.append(
            {
                "palette_index": index,
                "target_value": target_value,
                "source_value": (target_value - delta) & 0xFF,
                "delta": delta,
                "source_offset": offset,
            }
        )
    return output


def offset_bucket(offset: int) -> str:
    start = (offset // 4) * 4
    return f"{start}-{start + 3}"


def selector_entries(row: dict[str, str]) -> list[tuple[str, str, str]]:
    source_value = int(row["source_value_hex"], 16)
    target_value = int(row["target_value_hex"], 16)
    source_offset = int_value(row, "source_offset")
    palette_index = int_value(row, "palette_index")
    return [
        ("source_only", "source_value", f"0x{source_value:02x}"),
        ("source_only", "source_high_nibble", f"0x{source_value >> 4:x}"),
        ("source_only", "source_low_nibble", f"0x{source_value & 0x0f:x}"),
        ("source_only", "source_offset", str(source_offset)),
        ("source_only", "source_offset_mod2", str(source_offset % 2)),
        ("source_only", "source_offset_bucket4", offset_bucket(source_offset)),
        ("source_only", "source_value_offset", f"0x{source_value:02x}@{source_offset}"),
        ("row_local", "candidate_kind", row.get("candidate_kind", "")),
        ("row_local", "palette_size", row.get("palette_size", "")),
        ("row_local", "seed_length", row.get("length", "")),
        ("row_local", "frontier_id", row.get("frontier_id", "")),
        ("target_oracle", "target_value", f"0x{target_value:02x}"),
        ("target_oracle", "target_high_nibble", f"0x{target_value >> 4:x}"),
        ("target_oracle", "target_low_nibble", f"0x{target_value & 0x0f:x}"),
        ("target_oracle", "palette_index", str(palette_index)),
    ]


def build_value_rows(
    target_rows: list[dict[str, str]],
    palette_mix_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    ranks = rank_map(palette_mix_rows)
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        issues.extend(fixture_issues)
        rank = ranks.get(target_key(target), "")
        if not rank:
            issues.append("missing_palette_mix_rank")
        expected_all = expected_by_fixture.get((rank, target.get("pcx_name", ""), target.get("frontier_id", "")), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
        seed_id = f"{target.get('pcx_name', '')}|frontier{target.get('frontier_id', '')}|{start}-{end}"
        for plan_row in parse_plan(target.get("candidate_plan", "")):
            target_value = int(plan_row["target_value"])
            value_bytes = expected.count(target_value) if expected else 0
            output.append(
                {
                    "seed_id": seed_id,
                    "rank": rank,
                    "archive": target.get("archive", ""),
                    "archive_tag": target.get("archive_tag", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "run_index": target.get("run_index", ""),
                    "op_index": target.get("op_index", ""),
                    "start": target.get("start", ""),
                    "end": target.get("end", ""),
                    "length": target.get("length", ""),
                    "candidate_kind": target.get("candidate_kind", ""),
                    "palette_size": target.get("palette_size", ""),
                    "palette_index": str(plan_row["palette_index"]),
                    "target_value_hex": f"0x{target_value:02x}",
                    "source_value_hex": f"0x{int(plan_row['source_value']):02x}",
                    "delta": str(plan_row["delta"]),
                    "source_offset": str(plan_row["source_offset"]),
                    "value_bytes": str(value_bytes),
                    "copy_unlock_bytes": target.get("copy_unlock_bytes", "0"),
                    "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
                }
            )
    output.sort(key=lambda row: (row.get("seed_id", ""), int_value(row, "palette_index")))
    return output


def build_selector_rows(value_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in value_rows:
        for key in selector_entries(row):
            grouped[key].append(row)
    output: list[dict[str, str]] = []
    for (kind, family, key), rows in grouped.items():
        deltas = sorted({int_value(row, "delta") for row in rows})
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic and kind == "source_only":
            verdict = "source_only_repeated_delta_candidate"
        elif repeated_deterministic:
            verdict = f"{kind}_repeated_delta_review"
        elif deterministic:
            verdict = f"{kind}_singleton_delta_review"
        else:
            verdict = f"{kind}_delta_conflict"
        sample = rows[0]
        output.append(
            {
                "selector_kind": kind,
                "selector_family": family,
                "selector_key": key,
                "rows": str(len(rows)),
                "seed_rows": str(len(seed_rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deltas_seen": "|".join(str(delta) for delta in deltas),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("selector_kind", ""),
            row.get("selector_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("selector_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("selector_kind", ""), row.get("selector_family", "")].append(row)
    output: list[dict[str, str]] = []
    for (kind, family), rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if kind == "source_only" and repeated:
            verdict = "source_only_delta_candidate"
        elif kind == "source_only":
            verdict = "source_only_delta_blocked"
        elif repeated:
            verdict = f"{kind}_delta_review"
        else:
            verdict = f"{kind}_delta_blocked"
        output.append(
            {
                "selector_kind": kind,
                "selector_family": family,
                "groups": str(len(rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(len(deterministic)),
                "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
                "repeated_deterministic_groups": str(len(repeated)),
                "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
                "conflicted_groups": str(len(conflicted)),
                "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            row.get("selector_kind", ""),
            -int_value(row, "repeated_deterministic_bytes"),
            row.get("selector_family", ""),
        )
    )
    return output


def build_delta_rows(value_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in value_rows:
        grouped[row.get("delta", "")].append(row)
    output: list[dict[str, str]] = []
    for delta, rows in grouped.items():
        sample = rows[0]
        output.append(
            {
                "delta": delta,
                "rows": str(len(rows)),
                "seed_rows": str(len({row.get("seed_id", "") for row in rows})),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "target_values_hex": "|".join(sorted({row.get("target_value_hex", "") for row in rows})),
                "source_values_hex": "|".join(sorted({row.get("source_value_hex", "") for row in rows})),
                "source_offsets": "|".join(sorted({row.get("source_offset", "") for row in rows}, key=int)),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: int_value(row, "delta"))
    return output


def build_summary(
    value_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
) -> dict[str, str]:
    source_families = [row for row in family_rows if row.get("selector_kind") == "source_only"]
    source_selectors = [row for row in selector_rows if row.get("selector_kind") == "source_only"]
    source_repeated = [row for row in source_selectors if row.get("repeated_deterministic") == "1"]
    source_conflicted = [row for row in source_selectors if row.get("deterministic") != "1"]
    row_local_repeated = [
        row for row in selector_rows if row.get("selector_kind") == "row_local" and row.get("repeated_deterministic") == "1"
    ]
    target_repeated = [
        row
        for row in selector_rows
        if row.get("selector_kind") == "target_oracle" and row.get("repeated_deterministic") == "1"
    ]
    best_source = max(source_families, key=lambda row: int_value(row, "repeated_deterministic_bytes"), default={})
    seed_ids = {row.get("seed_id", "") for row in value_rows}
    copy_unlock_by_seed: dict[str, int] = {}
    seed_bytes_by_seed: dict[str, int] = {}
    for row in value_rows:
        copy_unlock_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "copy_unlock_bytes"))
        seed_bytes_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "length"))
    return {
        "scope": "total",
        "seed_rows": str(len(seed_ids)),
        "seed_bytes": str(sum(seed_bytes_by_seed.values())),
        "mapping_rows": str(len(value_rows)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in value_rows)),
        "source_only_selector_families": str(len(source_families)),
        "source_only_selector_groups": str(len(source_selectors)),
        "source_only_repeated_deterministic_groups": str(len(source_repeated)),
        "source_only_repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in source_repeated)),
        "source_only_conflicted_groups": str(len(source_conflicted)),
        "source_only_conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in source_conflicted)),
        "best_source_only_family": best_source.get("selector_family", ""),
        "best_source_only_repeated_deterministic_bytes": best_source.get("repeated_deterministic_bytes", "0"),
        "row_local_repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in row_local_repeated)),
        "target_oracle_repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in target_repeated)),
        "delta_values": str(len({row.get("delta", "") for row in value_rows})),
        "copy_unlock_rows": str(sum(1 for value in copy_unlock_by_seed.values() if value)),
        "copy_unlock_bytes": str(sum(copy_unlock_by_seed.values())),
        "total_potential_bytes": str(sum(seed_bytes_by_seed.values()) + sum(copy_unlock_by_seed.values())),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in value_rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    value_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "valueRows": value_rows,
        "selectorRows": selector_rows,
        "familyRows": family_rows,
        "deltaRows": delta_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("values.csv", output_dir / "values.csv"),
            ("by_selector.csv", output_dir / "by_selector.csv"),
            ("by_selector_family.csv", output_dir / "by_selector_family.csv"),
            ("by_delta.csv", output_dir / "by_delta.csv"),
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
.wrap {{ width: min(1780px, calc(100vw - 28px)); margin: 0 auto; }}
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
    <div class="sub">Weights each palette value by real bytes and checks whether source-only selectors can choose the shift delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mapping rows</div><div class="value">{summary['mapping_rows']}</div></div>
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Source-only repeated bytes</div><div class="value">{summary['source_only_repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Row-local repeated bytes</div><div class="value warn">{summary['row_local_repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Target-oracle repeated bytes</div><div class="value warn">{summary['target_oracle_repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Selector families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Deltas</h2>{render_table(delta_rows, DELTA_FIELDNAMES)}</section>
  <section class="panel"><h2>Selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Values</h2>{render_table(value_rows, VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_SELECTOR_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe per-value delta selectors for .tex gradient seed shifts.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--palette-mix-targets", type=Path, default=DEFAULT_PALETTE_MIX_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Selector Probe",
    )
    args = parser.parse_args()

    value_rows = build_value_rows(read_csv(args.targets), read_csv(args.palette_mix_targets), read_fixture_csv(args.fixtures))
    selector_rows = build_selector_rows(value_rows)
    family_rows = build_family_rows(selector_rows)
    delta_rows = build_delta_rows(value_rows)
    summary = build_summary(value_rows, selector_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "values.csv", VALUE_FIELDNAMES, value_rows)
    write_csv(args.output / "by_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_selector_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_delta.csv", DELTA_FIELDNAMES, delta_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, value_rows, selector_rows, family_rows, delta_rows, args.output, args.title)
    )

    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Source-only repeated deterministic bytes: {summary['source_only_repeated_deterministic_bytes']}")
    print(f"Row-local repeated deterministic bytes: {summary['row_local_repeated_deterministic_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
