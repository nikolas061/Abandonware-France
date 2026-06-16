#!/usr/bin/env python3
"""Replay false-free nonzero fill selector rules after the tiny zero replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    DEFAULT_PATTERNS,
    build_targets,
    fixture_key,
    read_csv,
    rule_label,
    transform_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_replay import (
    count_mask,
    overlap_bytes,
    rejected_ranges,
    render_table,
)
from lolg_tex_gap_decoder_seed_replay import (
    fixture_sort_key,
    frontier_lookup,
    load_bytes,
    render_preview,
    safe_stem,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_BASE_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")
DEFAULT_RULES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_selector_probe/rule_candidates.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rule_rows",
    "selected_rule_rows",
    "target_rows",
    "selected_target_rows",
    "base_clean_bytes",
    "fill_added_bytes",
    "fill_exact_bytes",
    "fill_false_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "base_clean_bytes",
    "fill_target_rows",
    "fill_added_bytes",
    "fill_exact_bytes",
    "fill_false_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "fill_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

PROMOTION_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "expected_start",
    "expected_end",
    "length",
    "rule_label",
    "rule_family",
    "pool",
    "transform",
    "source_offset",
    "condition",
    "fill_byte_hex",
    "predicted_byte_hex",
    "base_known_overlap_bytes",
    "fill_overlap_bytes",
    "rejected_overlap_bytes",
    "fill_added_bytes",
    "fill_exact_bytes",
    "fill_false_bytes",
    "issues",
]

RULE_REPLAY_FIELDNAMES = [
    "rule_label",
    "rule_family",
    "pool",
    "transform",
    "source_offset",
    "condition",
    "candidate_rows",
    "candidate_bytes",
    "selected_rows",
    "selected_bytes",
    "selected_exact_bytes",
    "selected_false_bytes",
    "skipped_selected_rows",
    "skipped_overlap_rows",
    "issue_rows",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def condition_matches(target: dict[str, str], rule: dict[str, str]) -> bool:
    family = rule.get("rule_family", "")
    condition = rule.get("condition", "")
    if family == "offset_only":
        return condition == "all"
    if "=" not in condition:
        return False
    field, value = condition.split("=", 1)
    return target.get(field, "") == value


def promoted_rules(rule_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    candidates = [
        row
        for row in rule_rows
        if int_value(row, "false_bytes") == 0
        and int_value(row, "correct_bytes") > 0
        and int_value(row, "correct_rows") > 1
    ]
    candidates.sort(
        key=lambda row: (
            -int_value(row, "correct_bytes"),
            -int_value(row, "correct_rows"),
            row.get("rule_family", ""),
            row.get("pool", ""),
            row.get("transform", ""),
            int_value(row, "source_offset"),
            row.get("condition", ""),
        )
    )
    return candidates


def predicted_fill_byte(target: dict[str, str], pools: dict[str, bytes], rule: dict[str, str]) -> int | None:
    pool = pools.get(rule.get("pool", ""), b"")
    transformed = transform_bytes(pool, rule.get("transform", ""))
    offset = int_value(rule, "source_offset")
    if offset < 0 or offset >= len(transformed):
        return None
    return transformed[offset]


def target_matches_for_rule(
    targets: list[dict[str, str]],
    pools_by_target: list[dict[str, bytes]],
    rule: dict[str, str],
) -> list[tuple[int, int | None]]:
    matches: list[tuple[int, int | None]] = []
    for index, (target, pools) in enumerate(zip(targets, pools_by_target)):
        if condition_matches(target, rule):
            matches.append((index, predicted_fill_byte(target, pools, rule)))
    return matches


def build_rule_rows(rule_stats: dict[str, Counter[str]], rule_samples: dict[str, dict[str, str]], rule_fixtures: dict[str, set[tuple[str, str, str]]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, counter in rule_stats.items():
        sample = rule_samples[label]
        rows.append(
            {
                "rule_label": label,
                "rule_family": sample.get("rule_family", ""),
                "pool": sample.get("pool", ""),
                "transform": sample.get("transform", ""),
                "source_offset": sample.get("source_offset", ""),
                "condition": sample.get("condition", ""),
                "candidate_rows": sample.get("applies_rows", "0"),
                "candidate_bytes": sample.get("applies_bytes", "0"),
                "selected_rows": str(counter["selected_rows"]),
                "selected_bytes": str(counter["selected_bytes"]),
                "selected_exact_bytes": str(counter["selected_exact_bytes"]),
                "selected_false_bytes": str(counter["selected_false_bytes"]),
                "skipped_selected_rows": str(counter["skipped_selected_rows"]),
                "skipped_overlap_rows": str(counter["skipped_overlap_rows"]),
                "issue_rows": str(counter["issue_rows"]),
                "fixtures": str(len(rule_fixtures[label])),
                "sample_pcx": sample.get("sample_pcx", ""),
                "sample_frontier_id": sample.get("sample_frontier_id", ""),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "selected_bytes"), row.get("rule_label", "")))
    return rows


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    clean_decision_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    pools_by_target: list[dict[str, bytes]],
    rule_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {fixture_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    rejected_by_fixture = rejected_ranges(clean_decision_rows)
    targets_by_fixture: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, target in enumerate(target_rows):
        targets_by_fixture[fixture_key(target)].append(index)

    selected_target_indices: dict[int, str] = {}
    rule_stats: dict[str, Counter[str]] = defaultdict(Counter)
    rule_samples: dict[str, dict[str, str]] = {}
    rule_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)

    for rule in promoted_rules(rule_rows):
        label = rule_label(rule)
        rule_samples.setdefault(label, rule)
        matches = target_matches_for_rule(target_rows, pools_by_target, rule)
        has_new = False
        for target_index, predicted in matches:
            if target_index in selected_target_indices:
                rule_stats[label]["skipped_selected_rows"] += 1
                continue
            target = target_rows[target_index]
            if predicted is None:
                rule_stats[label]["issue_rows"] += 1
                continue
            expected_value = int(target.get("fill_byte_hex", "0"), 16)
            if predicted != expected_value:
                rule_stats[label]["issue_rows"] += 1
                continue
            has_new = True
        if not has_new:
            continue
        for target_index, predicted in matches:
            if target_index in selected_target_indices:
                continue
            target = target_rows[target_index]
            if predicted is None or predicted != int(target.get("fill_byte_hex", "0"), 16):
                continue
            selected_target_indices[target_index] = label
            rule_fixtures[label].add(fixture_key(target))

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(base_fixture_rows, key=lambda row: fixture_sort_key(fixture_key(row))):
        key = fixture_key(base_fixture)
        manifest = manifest_by_key.get(key, {})
        fixture_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), fixture_issues, "expected")
        decoded = bytearray(load_bytes(base_fixture.get("decoded_path", ""), fixture_issues, "decoded"))
        known_mask = bytearray(load_bytes(base_fixture.get("known_mask_path", ""), fixture_issues, "known_mask"))
        if len(decoded) != len(expected):
            fixture_issues.append("decoded_size_mismatch")
            decoded = decoded[: len(expected)] + bytearray(max(0, len(expected) - len(decoded)))
        if len(known_mask) != len(expected):
            fixture_issues.append("known_mask_size_mismatch")
            known_mask = known_mask[: len(expected)] + bytearray(max(0, len(expected) - len(known_mask)))

        base_known_mask = bytearray(known_mask)
        rejected_mask = bytearray(len(expected))
        for start, end in rejected_by_fixture.get(key, []):
            bounded_start = max(0, min(start, len(expected)))
            bounded_end = max(bounded_start, min(end, len(expected)))
            rejected_mask[bounded_start:bounded_end] = b"\xff" * (bounded_end - bounded_start)

        fill_mask = bytearray(len(expected))
        stats = Counter()
        for target_index in sorted(
            targets_by_fixture.get(key, []),
            key=lambda index: (int_value(target_rows[index], "start"), int_value(target_rows[index], "op_index")),
        ):
            if target_index not in selected_target_indices:
                continue
            target = target_rows[target_index]
            rule = next(row for row in rule_rows if rule_label(row) == selected_target_indices[target_index])
            label = selected_target_indices[target_index]
            target_issues: list[str] = []
            start = max(0, min(int_value(target, "start"), len(expected)))
            end = max(start, min(int_value(target, "end"), len(expected)))
            length = int_value(target, "length")
            predicted = predicted_fill_byte(target, pools_by_target[target_index], rule)
            expected_slice = expected[start:end]
            predicted_slice = bytes([predicted or 0]) * (end - start)
            base_overlap = overlap_bytes(base_known_mask, start, end)
            fill_overlap = overlap_bytes(fill_mask, start, end)
            rejected_overlap = overlap_bytes(rejected_mask, start, end)
            false_bytes = sum(1 for left, right in zip(predicted_slice, expected_slice) if left != right)
            exact_bytes = len(expected_slice) - false_bytes
            if end - start != length:
                target_issues.append("target_range_length_mismatch")
            if predicted is None:
                target_issues.append("missing_predicted_byte")
            if base_overlap:
                target_issues.append("base_known_overlap")
            if fill_overlap:
                target_issues.append("fill_overlap")
            if rejected_overlap:
                target_issues.append("rejected_overlap")
            if false_bytes:
                target_issues.append("fill_would_write_false_bytes")

            if not target_issues:
                decoded[start:end] = predicted_slice
                known_mask[start:end] = b"\xff" * (end - start)
                fill_mask[start:end] = b"\xff" * (end - start)
                stats["fill_added_bytes"] += end - start
                stats["fill_exact_bytes"] += exact_bytes
                stats["fill_false_bytes"] += false_bytes
                rule_stats[label]["selected_rows"] += 1
                rule_stats[label]["selected_bytes"] += end - start
                rule_stats[label]["selected_exact_bytes"] += exact_bytes
                rule_stats[label]["selected_false_bytes"] += false_bytes
            else:
                issue_rows += 1
                if base_overlap or fill_overlap or rejected_overlap:
                    rule_stats[label]["skipped_overlap_rows"] += 1
                else:
                    rule_stats[label]["issue_rows"] += 1
            stats["fill_target_rows"] += 1

            promotion_rows.append(
                {
                    "rank": target.get("rank", ""),
                    "archive": target.get("archive", ""),
                    "archive_tag": target.get("archive_tag", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "run_index": target.get("run_index", ""),
                    "op_index": target.get("op_index", ""),
                    "expected_start": str(start),
                    "expected_end": str(end),
                    "length": str(length),
                    "rule_label": label,
                    "rule_family": rule.get("rule_family", ""),
                    "pool": rule.get("pool", ""),
                    "transform": rule.get("transform", ""),
                    "source_offset": rule.get("source_offset", ""),
                    "condition": rule.get("condition", ""),
                    "fill_byte_hex": target.get("fill_byte_hex", ""),
                    "predicted_byte_hex": "" if predicted is None else f"0x{predicted:02x}",
                    "base_known_overlap_bytes": str(base_overlap),
                    "fill_overlap_bytes": str(fill_overlap),
                    "rejected_overlap_bytes": str(rejected_overlap),
                    "fill_added_bytes": str(0 if target_issues else end - start),
                    "fill_exact_bytes": str(0 if target_issues else exact_bytes),
                    "fill_false_bytes": str(false_bytes),
                    "issues": ";".join(target_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(key[0]):03d}" if key[0].isdigit() else f"rank{key[0]}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_nonzero_fill.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        fill_mask_path = fixture_output_dir / f"{stem}_fill_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        fill_mask_path.write_bytes(fill_mask)
        native_preview_path = native_preview_dir / f"{stem}_nonzero_fill.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_nonzero_fill_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(fill_mask),
            frontier=frontiers.get((manifest.get("archive", ""), key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        base_clean = int_value(base_fixture, "total_clean_bytes")
        rejected_false = int_value(base_fixture, "rejected_false_bytes")
        total_clean = count_mask(known_mask)
        fixture_bytes = len(expected)
        output_fixture_rows.append(
            {
                "rank": key[0],
                "archive": manifest.get("archive", base_fixture.get("archive", "")),
                "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "base_clean_bytes": str(base_clean),
                "fill_target_rows": str(stats["fill_target_rows"]),
                "fill_added_bytes": str(stats["fill_added_bytes"]),
                "fill_exact_bytes": str(stats["fill_exact_bytes"]),
                "fill_false_bytes": str(stats["fill_false_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(fixture_bytes - total_clean - rejected_false),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "fill_mask_path": fill_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    rule_output_rows = build_rule_rows(rule_stats, rule_samples, rule_fixtures)
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "candidate_rule_rows": str(len(promoted_rules(rule_rows))),
        "selected_rule_rows": str(sum(1 for row in rule_output_rows if int_value(row, "selected_bytes") > 0)),
        "target_rows": str(len(target_rows)),
        "selected_target_rows": str(len(promotion_rows)),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in output_fixture_rows)),
        "fill_added_bytes": str(sum(int_value(row, "fill_added_bytes") for row in output_fixture_rows)),
        "fill_exact_bytes": str(sum(int_value(row, "fill_exact_bytes") for row in output_fixture_rows)),
        "fill_false_bytes": str(sum(int_value(row, "fill_false_bytes") for row in output_fixture_rows)),
        "total_clean_bytes": str(sum(int_value(row, "total_clean_bytes") for row in output_fixture_rows)),
        "rejected_false_bytes": str(sum(int_value(row, "rejected_false_bytes") for row in output_fixture_rows)),
        "remaining_unresolved_bytes": str(sum(int_value(row, "remaining_unresolved_bytes") for row in output_fixture_rows)),
        "native_previews": str(sum(1 for row in output_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(sum(1 for row in output_fixture_rows if row.get("fullhd_preview_path"))),
        "issue_rows": str(issue_rows),
    }
    return summary, output_fixture_rows, promotion_rows, rule_output_rows


def build_html(
    summary: dict[str, str],
    fixtures: list[dict[str, str]],
    promotions: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixtures, "promotions": promotions, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("promotions.csv", output_dir / "promotions.csv"),
            ("rules.csv", output_dir / "rules.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1500px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Applies false-free multi-row nonzero fill selectors after the tiny zero replay.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fill added bytes</div><div class="value ok">{summary['fill_added_bytes']}</div></div>
    <div class="stat"><div class="label">Total clean bytes</div><div class="value">{summary['total_clean_bytes']}</div></div>
    <div class="stat"><div class="label">False bytes</div><div class="value warn">{summary['fill_false_bytes']}</div></div>
    <div class="stat"><div class="label">Remaining unresolved</div><div class="value">{summary['remaining_unresolved_bytes']}</div></div>
    <div class="stat"><div class="label">Full HD previews</div><div class="value">{summary['fullhd_previews']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Rules</h2>{render_table(rules, RULE_REPLAY_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Promotions</h2>{render_table(promotions, PROMOTION_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixtures, FIXTURE_FIELDNAMES, 80)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_TINY_NONZERO_FILL_REPLAY = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay false-free nonzero fill selectors after tiny zero replay.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Fill Replay",
    )
    args = parser.parse_args()

    target_rows, pools_by_target, fixture_issues = build_targets(
        read_csv(args.patterns),
        read_csv(args.operations),
        read_csv(args.fixtures),
    )
    summary, fixtures, promotions, rules = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        target_rows=target_rows,
        pools_by_target=pools_by_target,
        rule_rows=read_csv(args.rules),
    )
    if fixture_issues:
        summary["issue_rows"] = str(int_value(summary, "issue_rows") + len(fixture_issues))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixtures)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotions)
    write_csv(args.output / "rules.csv", RULE_REPLAY_FIELDNAMES, rules)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fixtures, promotions, rules, args.output, args.title))

    print(f"Fill added bytes: {summary['fill_added_bytes']}")
    print(f"Fill false bytes: {summary['fill_false_bytes']}")
    print(f"Total clean bytes: {summary['total_clean_bytes']}")
    print(f"Remaining unresolved bytes: {summary['remaining_unresolved_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
