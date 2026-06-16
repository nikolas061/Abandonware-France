#!/usr/bin/env python3
"""Probe single-byte fill generators for structured nonzero gaps."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_rule_probe")
DEFAULT_PATTERNS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe/patterns.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

FIXED_TRANSFORMS = ("identity", "low7", "bit_not", "nibble_swap")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "candidate_rows",
    "covered_rows",
    "covered_bytes",
    "singleton_rows",
    "ambiguous_rows",
    "control_identity_rows",
    "control_identity_bytes",
    "control_fixed_rows",
    "control_fixed_bytes",
    "max_fill_length",
    "pool_groups",
    "transform_groups",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
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
    "candidate_index",
    "pool",
    "transform",
    "source_offset",
    "source_byte_hex",
    "fill_byte_hex",
    "pool_size",
    "control_ref_offset",
    "control_window_signature",
    "generated_hex_head",
    "issues",
]

GROUP_FIELDNAMES = [
    "pool",
    "transform",
    "rows",
    "bytes",
    "candidate_rows",
    "fixtures",
    "fill_bytes_seen",
    "max_length",
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


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
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


def transform_bytes(data: bytes, transform: str) -> bytes:
    if transform == "identity":
        return data
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "bit_not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "nibble_swap":
        return nibble_swap(data)
    return b""


def control_signature(control_window_hex: str) -> str:
    if not control_window_hex:
        return "missing"
    return f"head={control_window_hex[:8]}|tail={control_window_hex[-8:]}"


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
    fill_targets = [row for row in pattern_rows if row.get("pattern_class") == "fill_single_byte"]
    candidates: list[dict[str, str]] = []
    target_bytes = 0

    for pattern in fill_targets:
        issues: list[str] = []
        key = fixture_key(pattern)
        expected_all = expected_by_fixture.get(key, b"")
        start = int_value(pattern, "start")
        end = int_value(pattern, "end")
        expected = expected_all[start:end]
        target_bytes += len(expected)
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        if len(set(expected)) != 1:
            issues.append("not_single_byte_fill")
            continue
        fill_value = expected[0]
        operation = operations.get(pattern_op_key(pattern), {})
        if not operation:
            issues.append("missing_operation")
        fixture = fixtures.get(key, {})
        fragment = read_bytes(fixture.get("fragment_path", ""), issues, "fragment") if fixture else b""
        control_prefix = read_bytes(fixture.get("control_prefix_path", ""), issues, "control_prefix") if fixture else b""
        control_window_hex = operation.get("control_window_hex", "")
        control_window = safe_bytes_fromhex(control_window_hex)
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
        local_candidates: list[dict[str, str]] = []
        for pool_name, pool in pools.items():
            for transform in FIXED_TRANSFORMS:
                transformed = transform_bytes(pool, transform)
                for offset, value in enumerate(transformed):
                    if value != fill_value:
                        continue
                    source_byte = pool[offset] if offset < len(pool) else 0
                    local_candidates.append(
                        {
                            "rank": pattern.get("rank", ""),
                            "archive": pattern.get("archive", ""),
                            "archive_tag": pattern.get("archive_tag", ""),
                            "pcx_name": pattern.get("pcx_name", ""),
                            "frontier_id": pattern.get("frontier_id", ""),
                            "span_index": pattern.get("span_index", ""),
                            "run_index": pattern.get("run_index", ""),
                            "op_index": pattern.get("op_index", ""),
                            "length": str(len(expected)),
                            "start": pattern.get("start", ""),
                            "end": pattern.get("end", ""),
                            "candidate_index": "0",
                            "pool": pool_name,
                            "transform": transform,
                            "source_offset": str(offset),
                            "source_byte_hex": f"0x{source_byte:02x}",
                            "fill_byte_hex": f"0x{fill_value:02x}",
                            "pool_size": str(len(pool)),
                            "control_ref_offset": operation.get("control_ref_offset", "") or "missing",
                            "control_window_signature": control_signature(control_window_hex),
                            "generated_hex_head": (bytes([fill_value]) * min(len(expected), 16)).hex(),
                            "issues": ";".join(issues),
                        }
                    )
        for index, candidate in enumerate(local_candidates, start=1):
            candidate["candidate_index"] = str(index)
            candidates.append(candidate)

    groups = build_groups(candidates)
    summary = build_summary(fill_targets, target_bytes, candidates, groups, fixture_issues)
    return summary, candidates, groups


def build_summary(
    target_rows: list[dict[str, str]],
    target_bytes: int,
    candidates: list[dict[str, str]],
    groups: list[dict[str, str]],
    fixture_issues: list[str],
) -> dict[str, str]:
    target_candidates: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        target_candidates[target_key(row)].append(row)
    covered = [rows[0] for rows in target_candidates.values()]
    singleton = [rows for rows in target_candidates.values() if len(rows) == 1]
    ambiguous = [rows for rows in target_candidates.values() if len(rows) > 1]
    control_identity_keys = {
        target_key(row)
        for row in candidates
        if row.get("pool") == "control_window" and row.get("transform") == "identity"
    }
    control_fixed_keys = {target_key(row) for row in candidates if row.get("pool") == "control_window"}
    length_by_key = {target_key(row): int_value(row, "length") for row in candidates}
    return {
        "scope": "total",
        "target_rows": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "candidate_rows": str(len(candidates)),
        "covered_rows": str(len(covered)),
        "covered_bytes": str(sum(int_value(row, "length") for row in covered)),
        "singleton_rows": str(len(singleton)),
        "ambiguous_rows": str(len(ambiguous)),
        "control_identity_rows": str(len(control_identity_keys)),
        "control_identity_bytes": str(sum(length_by_key[key] for key in control_identity_keys)),
        "control_fixed_rows": str(len(control_fixed_keys)),
        "control_fixed_bytes": str(sum(length_by_key[key] for key in control_fixed_keys)),
        "max_fill_length": str(max([int_value(row, "length") for row in covered] or [0])),
        "pool_groups": str(len({row.get("pool", "") for row in candidates})),
        "transform_groups": str(len({row.get("transform", "") for row in candidates})),
        "issue_rows": str(sum(1 for row in candidates if row.get("issues")) + len(fixture_issues)),
    }


def build_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    fill_bytes: dict[tuple[str, str], set[str]] = defaultdict(set)
    target_keys: dict[tuple[str, str], set[tuple[str, str, str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = row.get("pool", ""), row.get("transform", "")
        length = int_value(row, "length")
        target = target_key(row)
        counters[key]["candidate_rows"] += 1
        if target not in target_keys[key]:
            counters[key]["rows"] += 1
            counters[key]["bytes"] += length
            counters[key]["max_length"] = max(counters[key]["max_length"], length)
            target_keys[key].add(target)
        fixtures[key].add(fixture_key(row))
        fill_bytes[key].add(row.get("fill_byte_hex", ""))
        samples.setdefault(key, row)

    output_rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        pool, transform = key
        sample = samples[key]
        output_rows.append(
            {
                "pool": pool,
                "transform": transform,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "candidate_rows": str(counter["candidate_rows"]),
                "fixtures": str(len(fixtures[key])),
                "fill_bytes_seen": ";".join(sorted(fill_bytes[key])),
                "max_length": str(counter["max_length"]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output_rows.sort(
        key=lambda row: (
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("pool", ""),
            row.get("transform", ""),
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
    candidates: list[dict[str, str]],
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
    <div class="sub">Tests whether single-byte nonzero fills can be generated by repeating a fixed source byte.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fill bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Covered bytes</div><div class="value ok">{summary['covered_bytes']}</div></div>
    <div class="stat"><div class="label">Control identity bytes</div><div class="value">{summary['control_identity_bytes']}</div></div>
    <div class="stat"><div class="label">Ambiguous rows</div><div class="value warn">{summary['ambiguous_rows']}</div></div>
    <div class="stat"><div class="label">Max fill length</div><div class="value">{summary['max_fill_length']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Pool and transform groups</h2>{render_table(groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES, 320)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FILL_RULE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe single-byte fill generators for .tex nonzero gaps.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Fill Rule Probe",
    )
    args = parser.parse_args()

    summary, candidates, groups = build_rows(read_csv(args.patterns), read_csv(args.operations), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "by_pool_transform.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, groups, args.output, args.title))

    print(f"Fill targets: {summary['target_rows']}")
    print(f"Fill bytes: {summary['target_bytes']}")
    print(f"Covered rows: {summary['covered_rows']}")
    print(f"Covered bytes: {summary['covered_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
