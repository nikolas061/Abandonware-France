#!/usr/bin/env python3
"""Probe value sources for structured promoted nonzero gap rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_value_probe")
DEFAULT_PATTERNS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe/patterns.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

STRUCTURED_CLASSES = {"fill_single_byte", "small_palette_2", "small_palette_4"}
SMALL_PALETTE_CLASSES = {"small_palette_2", "small_palette_4"}

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "fill_rows",
    "fill_bytes",
    "small_palette_rows",
    "small_palette_bytes",
    "control_identity_full_unique_rows",
    "control_identity_full_unique_bytes",
    "control_fixed_full_unique_rows",
    "control_fixed_full_unique_bytes",
    "control_any_full_unique_rows",
    "control_any_full_unique_bytes",
    "control_prefix_any_full_unique_rows",
    "control_prefix_any_full_unique_bytes",
    "fragment_any_full_unique_rows",
    "fragment_any_full_unique_bytes",
    "neighbor_any_full_unique_rows",
    "neighbor_any_full_unique_bytes",
    "best_full_unique_rows",
    "best_full_unique_bytes",
    "best_fixed_full_unique_rows",
    "best_fixed_full_unique_bytes",
    "best_exact_sequence_rows",
    "best_exact_sequence_bytes",
    "best_fixed_exact_sequence_rows",
    "best_fixed_exact_sequence_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "pattern_class",
    "length",
    "start",
    "end",
    "unique_bytes",
    "unique_hex",
    "dominant_byte_hex",
    "control_identity_unique_hits",
    "control_identity_full_unique",
    "control_fixed_transform",
    "control_fixed_unique_hits",
    "control_fixed_full_unique",
    "control_any_transform",
    "control_any_parameter",
    "control_any_unique_hits",
    "control_any_full_unique",
    "control_prefix_any_transform",
    "control_prefix_any_parameter",
    "control_prefix_any_unique_hits",
    "control_prefix_any_full_unique",
    "fragment_any_transform",
    "fragment_any_parameter",
    "fragment_any_unique_hits",
    "fragment_any_full_unique",
    "neighbor_any_transform",
    "neighbor_any_parameter",
    "neighbor_any_unique_hits",
    "neighbor_any_full_unique",
    "best_pool",
    "best_transform",
    "best_parameter",
    "best_unique_hits",
    "best_unique_ratio",
    "best_full_unique",
    "best_exact_sequence",
    "best_pool_size",
    "best_fixed_pool",
    "best_fixed_transform",
    "best_fixed_unique_hits",
    "best_fixed_unique_ratio",
    "best_fixed_full_unique",
    "best_fixed_exact_sequence",
    "issues",
]

GROUP_FIELDNAMES = [
    "best_pool",
    "best_transform",
    "best_parameter",
    "rows",
    "bytes",
    "full_unique_rows",
    "full_unique_bytes",
    "exact_sequence_rows",
    "exact_sequence_bytes",
    "pattern_classes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def pattern_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def safe_bytes_fromhex(value: str) -> bytes:
    if not value:
        return b""
    try:
        return bytes.fromhex(value)
    except ValueError:
        return b""


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def nibble_swap(data: bytes) -> bytes:
    return bytes((((value & 0x0F) << 4) | ((value & 0xF0) >> 4)) for value in data)


def transform_bytes(data: bytes, transform: str, parameter: int = 0) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "nibble_swap":
        return nibble_swap(data)
    if transform == "xor":
        return bytes(value ^ parameter for value in data)
    if transform == "add":
        return bytes((value + parameter) & 0xFF for value in data)
    return b""


def exact_sequence(expected: bytes, transformed: bytes) -> bool:
    return bool(expected) and expected in transformed


def score_pool(expected: bytes, pool: bytes, pool_name: str, include_parametric: bool = True) -> dict[str, str]:
    unique = set(expected)
    if not unique or not pool:
        return {
            "pool": pool_name,
            "transform": "missing",
            "parameter": "",
            "unique_hits": "0",
            "unique_ratio": "0.000000",
            "full_unique": "0",
            "exact_sequence": "0",
            "pool_size": str(len(pool)),
        }

    candidates: list[dict[str, str]] = []
    for transform in ("identity", "low7", "bit_not", "nibble_swap"):
        transformed = transform_bytes(pool, transform)
        hits = len(unique.intersection(transformed))
        candidates.append(
            {
                "pool": pool_name,
                "transform": transform,
                "parameter": "",
                "unique_hits": str(hits),
                "unique_ratio": f"{hits / len(unique):.6f}",
                "full_unique": "1" if hits == len(unique) else "0",
                "exact_sequence": "1" if exact_sequence(expected, transformed) else "0",
                "pool_size": str(len(pool)),
            }
        )

    if include_parametric:
        for transform in ("xor", "add"):
            for parameter in range(256):
                transformed = transform_bytes(pool, transform, parameter)
                hits = len(unique.intersection(transformed))
                if hits:
                    candidates.append(
                        {
                            "pool": pool_name,
                            "transform": transform,
                            "parameter": f"0x{parameter:02x}",
                            "unique_hits": str(hits),
                            "unique_ratio": f"{hits / len(unique):.6f}",
                            "full_unique": "1" if hits == len(unique) else "0",
                            "exact_sequence": "1" if exact_sequence(expected, transformed) else "0",
                            "pool_size": str(len(pool)),
                        }
                    )

    transform_rank = {
        "identity": 0,
        "low7": 1,
        "bit_not": 2,
        "nibble_swap": 3,
        "xor": 4,
        "add": 5,
        "missing": 6,
    }
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_sequence"),
            int_value(row, "unique_hits"),
            int_value(row, "full_unique"),
            -transform_rank.get(row.get("transform", ""), 99),
            -int(row.get("parameter", "0x00") or "0", 16) if row.get("parameter") else 0,
        ),
    )


def load_expected_by_fixture(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        expected[fixture_key(fixture)] = read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected")
        issues.extend(f"{fixture_key(fixture)}:{issue}" for issue in local_issues)
    return expected, issues


def build_rows(
    pattern_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    operations = {op_key(row): row for row in operation_rows}
    fixtures = {fixture_key(row): row for row in fixture_rows}
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)

    rows: list[dict[str, str]] = []
    for pattern in pattern_rows:
        if pattern.get("pattern_class") not in STRUCTURED_CLASSES:
            continue
        issues: list[str] = []
        key = fixture_key(pattern)
        expected_all = expected_by_fixture.get(key, b"")
        start = int_value(pattern, "start")
        end = int_value(pattern, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
        operation = operations.get(pattern_op_key(pattern), {})
        if not operation:
            issues.append("missing_operation")
        fixture = fixtures.get(key, {})

        fragment = read_bytes(fixture.get("fragment_path", ""), issues, "fragment") if fixture else b""
        control_prefix = read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix") if fixture else b""
        control_window = safe_bytes_fromhex(operation.get("control_window_hex", ""))
        neighbor = b"".join(
            safe_bytes_fromhex(operation.get(field, ""))
            for field in ("pre1_hex", "pre2_hex", "pre4_hex", "next2_hex")
        )
        pools = {
            "control_window": control_window,
            "control_prefix": control_prefix,
            "fragment": fragment,
            "neighbor": neighbor,
        }
        scores = {pool_name: score_pool(expected, pool, pool_name) for pool_name, pool in pools.items()}
        fixed_scores = {
            pool_name: score_pool(expected, pool, pool_name, include_parametric=False)
            for pool_name, pool in pools.items()
        }
        best = max(
            scores.values(),
            key=lambda row: (
                int_value(row, "exact_sequence"),
                int_value(row, "unique_hits"),
                int_value(row, "full_unique"),
                int_value(row, "pool_size"),
            ),
        )
        best_fixed = max(
            fixed_scores.values(),
            key=lambda row: (
                int_value(row, "exact_sequence"),
                int_value(row, "unique_hits"),
                int_value(row, "full_unique"),
                int_value(row, "pool_size"),
            ),
        )
        unique = sorted(set(expected))
        identity_control = transform_bytes(control_window, "identity")
        control_identity_hits = len(set(expected).intersection(identity_control))
        row = {
            "rank": pattern.get("rank", ""),
            "archive": pattern.get("archive", ""),
            "archive_tag": pattern.get("archive_tag", ""),
            "pcx_name": pattern.get("pcx_name", ""),
            "frontier_id": pattern.get("frontier_id", ""),
            "span_index": pattern.get("span_index", ""),
            "run_index": pattern.get("run_index", ""),
            "op_index": pattern.get("op_index", ""),
            "pattern_class": pattern.get("pattern_class", ""),
            "length": str(len(expected)),
            "start": pattern.get("start", ""),
            "end": pattern.get("end", ""),
            "unique_bytes": str(len(unique)),
            "unique_hex": ";".join(f"0x{value:02x}" for value in unique),
            "dominant_byte_hex": pattern.get("dominant_byte_hex", ""),
            "control_identity_unique_hits": str(control_identity_hits),
            "control_identity_full_unique": "1" if unique and control_identity_hits == len(unique) else "0",
            "control_fixed_transform": fixed_scores["control_window"]["transform"],
            "control_fixed_unique_hits": fixed_scores["control_window"]["unique_hits"],
            "control_fixed_full_unique": fixed_scores["control_window"]["full_unique"],
            "control_any_transform": scores["control_window"]["transform"],
            "control_any_parameter": scores["control_window"]["parameter"],
            "control_any_unique_hits": scores["control_window"]["unique_hits"],
            "control_any_full_unique": scores["control_window"]["full_unique"],
            "control_prefix_any_transform": scores["control_prefix"]["transform"],
            "control_prefix_any_parameter": scores["control_prefix"]["parameter"],
            "control_prefix_any_unique_hits": scores["control_prefix"]["unique_hits"],
            "control_prefix_any_full_unique": scores["control_prefix"]["full_unique"],
            "fragment_any_transform": scores["fragment"]["transform"],
            "fragment_any_parameter": scores["fragment"]["parameter"],
            "fragment_any_unique_hits": scores["fragment"]["unique_hits"],
            "fragment_any_full_unique": scores["fragment"]["full_unique"],
            "neighbor_any_transform": scores["neighbor"]["transform"],
            "neighbor_any_parameter": scores["neighbor"]["parameter"],
            "neighbor_any_unique_hits": scores["neighbor"]["unique_hits"],
            "neighbor_any_full_unique": scores["neighbor"]["full_unique"],
            "best_pool": best["pool"],
            "best_transform": best["transform"],
            "best_parameter": best["parameter"],
            "best_unique_hits": best["unique_hits"],
            "best_unique_ratio": best["unique_ratio"],
            "best_full_unique": best["full_unique"],
            "best_exact_sequence": best["exact_sequence"],
            "best_pool_size": best["pool_size"],
            "best_fixed_pool": best_fixed["pool"],
            "best_fixed_transform": best_fixed["transform"],
            "best_fixed_unique_hits": best_fixed["unique_hits"],
            "best_fixed_unique_ratio": best_fixed["unique_ratio"],
            "best_fixed_full_unique": best_fixed["full_unique"],
            "best_fixed_exact_sequence": best_fixed["exact_sequence"],
            "issues": ";".join(issues),
        }
        rows.append(row)

    summary = build_summary(rows, fixture_issues)
    groups = build_groups(rows)
    return summary, rows, groups


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(rows: list[dict[str, str]], fixture_issues: list[str]) -> dict[str, str]:
    fills = [row for row in rows if row.get("pattern_class") == "fill_single_byte"]
    small = [row for row in rows if row.get("pattern_class") in SMALL_PALETTE_CLASSES]
    control_identity = [row for row in rows if row.get("control_identity_full_unique") == "1"]
    control_fixed = [row for row in rows if row.get("control_fixed_full_unique") == "1"]
    control_any = [row for row in rows if row.get("control_any_full_unique") == "1"]
    control_prefix_any = [row for row in rows if row.get("control_prefix_any_full_unique") == "1"]
    fragment_any = [row for row in rows if row.get("fragment_any_full_unique") == "1"]
    neighbor_any = [row for row in rows if row.get("neighbor_any_full_unique") == "1"]
    best_full = [row for row in rows if row.get("best_full_unique") == "1"]
    best_fixed_full = [row for row in rows if row.get("best_fixed_full_unique") == "1"]
    best_exact = [row for row in rows if row.get("best_exact_sequence") == "1"]
    best_fixed_exact = [row for row in rows if row.get("best_fixed_exact_sequence") == "1"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "fill_rows": str(len(fills)),
        "fill_bytes": str(sum_bytes(fills)),
        "small_palette_rows": str(len(small)),
        "small_palette_bytes": str(sum_bytes(small)),
        "control_identity_full_unique_rows": str(len(control_identity)),
        "control_identity_full_unique_bytes": str(sum_bytes(control_identity)),
        "control_fixed_full_unique_rows": str(len(control_fixed)),
        "control_fixed_full_unique_bytes": str(sum_bytes(control_fixed)),
        "control_any_full_unique_rows": str(len(control_any)),
        "control_any_full_unique_bytes": str(sum_bytes(control_any)),
        "control_prefix_any_full_unique_rows": str(len(control_prefix_any)),
        "control_prefix_any_full_unique_bytes": str(sum_bytes(control_prefix_any)),
        "fragment_any_full_unique_rows": str(len(fragment_any)),
        "fragment_any_full_unique_bytes": str(sum_bytes(fragment_any)),
        "neighbor_any_full_unique_rows": str(len(neighbor_any)),
        "neighbor_any_full_unique_bytes": str(sum_bytes(neighbor_any)),
        "best_full_unique_rows": str(len(best_full)),
        "best_full_unique_bytes": str(sum_bytes(best_full)),
        "best_fixed_full_unique_rows": str(len(best_fixed_full)),
        "best_fixed_full_unique_bytes": str(sum_bytes(best_fixed_full)),
        "best_exact_sequence_rows": str(len(best_exact)),
        "best_exact_sequence_bytes": str(sum_bytes(best_exact)),
        "best_fixed_exact_sequence_rows": str(len(best_fixed_exact)),
        "best_fixed_exact_sequence_bytes": str(sum_bytes(best_fixed_exact)),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + len(fixture_issues)),
    }


def build_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    classes: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = row.get("best_pool", ""), row.get("best_transform", ""), row.get("best_parameter", "")
        length = int_value(row, "length")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += length
        counters[key]["full_unique_rows"] += 1 if row.get("best_full_unique") == "1" else 0
        counters[key]["full_unique_bytes"] += length if row.get("best_full_unique") == "1" else 0
        counters[key]["exact_sequence_rows"] += 1 if row.get("best_exact_sequence") == "1" else 0
        counters[key]["exact_sequence_bytes"] += length if row.get("best_exact_sequence") == "1" else 0
        fixtures[key].add(fixture_key(row))
        classes[key].add(row.get("pattern_class", ""))
        samples.setdefault(key, row)

    output_rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        pool, transform, parameter = key
        sample = samples[key]
        output_rows.append(
            {
                "best_pool": pool,
                "best_transform": transform,
                "best_parameter": parameter,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "full_unique_rows": str(counter["full_unique_rows"]),
                "full_unique_bytes": str(counter["full_unique_bytes"]),
                "exact_sequence_rows": str(counter["exact_sequence_rows"]),
                "exact_sequence_bytes": str(counter["exact_sequence_bytes"]),
                "pattern_classes": ";".join(sorted(classes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output_rows.sort(
        key=lambda row: (
            -int_value(row, "full_unique_bytes"),
            -int_value(row, "exact_sequence_bytes"),
            -int_value(row, "bytes"),
            row.get("best_pool", ""),
            row.get("best_transform", ""),
        )
    )
    return output_rows


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
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "rows": rows, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("value_rows.csv", output_dir / "value_rows.csv"),
            ("by_best_value_source.csv", output_dir / "by_best_value_source.csv"),
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
    <div class="sub">Checks whether structured nonzero gap values are present in control, prefix, fragment, or neighbor byte pools.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Control identity bytes</div><div class="value ok">{summary['control_identity_full_unique_bytes']}</div></div>
    <div class="stat"><div class="label">Control fixed bytes</div><div class="value ok">{summary['control_fixed_full_unique_bytes']}</div></div>
    <div class="stat"><div class="label">Control any bytes</div><div class="value">{summary['control_any_full_unique_bytes']}</div></div>
    <div class="stat"><div class="label">Best fixed bytes</div><div class="value">{summary['best_fixed_full_unique_bytes']}</div></div>
    <div class="stat"><div class="label">Best full unique bytes</div><div class="value warn">{summary['best_full_unique_bytes']}</div></div>
    <div class="stat"><div class="label">Exact sequence bytes</div><div class="value">{summary['best_exact_sequence_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Best value sources</h2>{render_table(groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Value rows</h2>{render_table(rows, ROW_FIELDNAMES, 300)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe possible byte-value sources for structured .tex nonzero gaps.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Value Probe",
    )
    args = parser.parse_args()

    summary, rows, groups = build_rows(read_csv(args.patterns), read_csv(args.operations), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "value_rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "by_best_value_source.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.output, args.title))

    print(f"Targets: {summary['target_rows']}")
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Control identity full unique bytes: {summary['control_identity_full_unique_bytes']}")
    print(f"Best full unique bytes: {summary['best_full_unique_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
