#!/usr/bin/env python3
"""Promote compact target-delta guard for high-row residual target offsets."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay"
)
DEFAULT_TARGET_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_target_offset_probe/"
    "target_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "baseline_exact_bytes",
    "baseline_le2_bytes",
    "selector_name",
    "rule_keys",
    "singleton_keys",
    "changed_rule_keys",
    "promoted_rows",
    "promoted_changed_rows",
    "promoted_exact_bytes",
    "promoted_false_bytes",
    "final_exact_bytes",
    "final_le2_bytes",
    "target_unknown_bytes",
    "target_known_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RULE_FIELDNAMES = [
    "selector_name",
    "selector_key",
    "byte_index",
    "group_size",
    "selected_delta",
    "exact_bytes",
    "false_bytes",
    "changed",
    "delta_histogram",
]

SELECTOR_FIELDNAMES = [
    "pair_id",
    "source_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "original_source_offset",
    "source_offset",
    "target_offset",
    "byte_index",
    "source_residual_value_hex",
    "target_expected_hex",
    "target_base_known",
    "target_base_decoded_hex",
    "target_delta",
    "target_exact",
    "target_le2",
    "target_outlier",
    "residual_selector_name",
    "residual_selector_key",
    "residual_delta",
    "residual_value_hex",
    "residual_observed_delta",
    "residual_exact",
    "residual_le2",
    "residual_promoted",
    "residual_guard_key",
    "residual_rule_decision",
    "issues",
]

APPLICATION_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "target_offset",
    "selector_key",
    "source_residual_value_hex",
    "target_expected_hex",
    "residual_delta",
    "residual_value_hex",
    "baseline_exact",
    "residual_exact",
    "residual_promoted",
    "rule_decision",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_hex_byte(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value & 0xFF:02x}"


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def selector_key(row: dict[str, str]) -> str:
    return f"p{int_value(row, 'byte_index'):02d}"


def byte_index_from_key(key: str) -> str:
    return key[1:] if key.startswith("p") else ""


def dominant(values: list[int]) -> tuple[int, int]:
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[0]


def histogram(values: list[int]) -> str:
    counts = Counter(values)
    return ";".join(f"{delta}:{counts[delta]}" for delta in sorted(counts))


def build_rules(rows: list[dict[str, str]], issues: list[str]) -> tuple[dict[str, int], list[dict[str, str]]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        key = selector_key(row)
        groups[key].append(int_value(row, "target_delta"))

    rules: dict[str, int] = {}
    rule_rows: list[dict[str, str]] = []
    for key in sorted(groups, key=lambda value: (int(byte_index_from_key(value) or 0), value)):
        values = groups[key]
        selected_delta, exact_count = dominant(values)
        rules[key] = selected_delta
        rule_rows.append(
            {
                "selector_name": "byte_index_delta",
                "selector_key": key,
                "byte_index": byte_index_from_key(key),
                "group_size": str(len(values)),
                "selected_delta": str(selected_delta),
                "exact_bytes": str(exact_count),
                "false_bytes": str(len(values) - exact_count),
                "changed": "1" if selected_delta != 0 else "0",
                "delta_histogram": histogram(values),
            }
        )
    if not rules:
        issues.append("missing_target_delta_rules")
    return rules, rule_rows


def build_rows(
    target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    rules, rule_rows = build_rules(target_rows, issues)
    output_rows: list[dict[str, str]] = []
    application_rows: list[dict[str, str]] = []

    baseline_exact = 0
    baseline_le2 = 0
    final_exact = 0
    final_le2 = 0
    promoted = 0
    promoted_changed = 0
    promoted_exact = 0
    promoted_false = 0
    target_unknown = 0
    target_known = 0

    for row in target_rows:
        row_issues: list[str] = []
        key = selector_key(row)
        rule_delta = rules.get(key)
        source_value = parse_hex_byte(row.get("residual_value_hex", ""))
        target_value = parse_hex_byte(row.get("target_expected_hex", ""))
        baseline_is_exact = row.get("target_exact") == "1"
        baseline_is_le2 = row.get("target_le2") == "1"
        target_is_known = row.get("target_base_known") == "1"
        baseline_exact += 1 if baseline_is_exact else 0
        baseline_le2 += 1 if baseline_is_le2 else 0
        target_known += 1 if target_is_known else 0
        target_unknown += 0 if target_is_known else 1

        if source_value is None:
            row_issues.append("missing_source_residual_value")
        if target_value is None:
            row_issues.append("missing_target_expected")
        if rule_delta is None:
            row_issues.append("missing_target_delta_rule")

        residual_value = source_value
        promoted_row = False
        rule_decision = "reject"
        if source_value is not None and rule_delta is not None:
            residual_value = (source_value + rule_delta) & 0xFF
            promoted_row = True
            rule_decision = "accept"

        residual_is_exact = residual_value is not None and target_value is not None and residual_value == target_value
        residual_observed_delta = (
            signed_delta(residual_value, target_value)
            if residual_value is not None and target_value is not None
            else int_value(row, "target_delta")
        )
        residual_is_le2 = abs(residual_observed_delta) <= 2
        final_exact += 1 if residual_is_exact else 0
        final_le2 += 1 if residual_is_le2 else 0
        promoted += 1 if promoted_row else 0
        promoted_changed += 1 if promoted_row and rule_delta != 0 else 0
        promoted_exact += 1 if promoted_row and residual_is_exact else 0
        promoted_false += 1 if promoted_row and not residual_is_exact else 0

        if row_issues:
            issues.append(
                f"{row.get('pair_id', '')}:{row.get('source_id', '')}:{row.get('byte_index', '')}:"
                f"{';'.join(row_issues)}"
            )

        application_rows.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "byte_index": row.get("byte_index", ""),
                "target_offset": row.get("target_offset", ""),
                "selector_key": key,
                "source_residual_value_hex": row.get("residual_value_hex", ""),
                "target_expected_hex": row.get("target_expected_hex", ""),
                "residual_delta": "" if rule_delta is None else str(rule_delta),
                "residual_value_hex": hex_byte(residual_value),
                "baseline_exact": "1" if baseline_is_exact else "0",
                "residual_exact": "1" if residual_is_exact else "0",
                "residual_promoted": "1" if promoted_row else "0",
                "rule_decision": rule_decision,
            }
        )

        output_rows.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "original_source_offset": row.get("source_offset", ""),
                "source_offset": row.get("target_offset", ""),
                "target_offset": row.get("target_offset", ""),
                "byte_index": row.get("byte_index", ""),
                "source_residual_value_hex": row.get("residual_value_hex", ""),
                "target_expected_hex": row.get("target_expected_hex", ""),
                "target_base_known": row.get("target_base_known", ""),
                "target_base_decoded_hex": row.get("target_base_decoded_hex", ""),
                "target_delta": row.get("target_delta", ""),
                "target_exact": row.get("target_exact", ""),
                "target_le2": row.get("target_le2", ""),
                "target_outlier": row.get("target_outlier", ""),
                "residual_selector_name": "byte_index_delta",
                "residual_selector_key": key,
                "residual_delta": "" if rule_delta is None else str(rule_delta),
                "residual_value_hex": hex_byte(residual_value),
                "residual_observed_delta": str(residual_observed_delta),
                "residual_exact": "1" if residual_is_exact else "0",
                "residual_le2": "1" if residual_is_le2 else "0",
                "residual_promoted": "1" if promoted_row else "0",
                "residual_guard_key": f"byte_index_delta|{key}|d{rule_delta}" if rule_delta is not None else "",
                "residual_rule_decision": rule_decision,
                "issues": ";".join(row_issues),
            }
        )

    issue_count = len(issues)
    if issue_count:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay_issues"
        next_probe = "fix compact target-delta guard replay issues"
    elif promoted_false > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay_rejected"
        next_probe = "review compact target-delta guard false positives"
    elif final_exact == len(target_rows) and promoted > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay_ready"
        next_probe = "integrate compact target-delta guard into high-row residual fixture replay"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay_weak"
        next_probe = "expand compact target-delta guard before fixture integration"

    summary = {
        "scope": "total",
        "total_bytes": str(len(target_rows)),
        "baseline_exact_bytes": str(baseline_exact),
        "baseline_le2_bytes": str(baseline_le2),
        "selector_name": "byte_index_delta",
        "rule_keys": str(len(rule_rows)),
        "singleton_keys": str(sum(1 for rule in rule_rows if int_value(rule, "group_size") == 1)),
        "changed_rule_keys": str(sum(1 for rule in rule_rows if rule.get("changed") == "1")),
        "promoted_rows": str(promoted),
        "promoted_changed_rows": str(promoted_changed),
        "promoted_exact_bytes": str(promoted_exact),
        "promoted_false_bytes": str(promoted_false),
        "final_exact_bytes": str(final_exact),
        "final_le2_bytes": str(final_le2),
        "target_unknown_bytes": str(target_unknown),
        "target_known_bytes": str(target_known),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    return summary, rule_rows, output_rows, application_rows, issues


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rule_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    application_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "rules": rule_rows,
        "selector_rows": selector_rows,
        "applications": application_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("rules.csv", output_dir / "rules.csv"),
            ("selector_rows.csv", output_dir / "selector_rows.csv"),
            ("target_delta_applications.csv", output_dir / "target_delta_applications.csv"),
            ("issues.txt", output_dir / "issues.txt"),
        )
    )
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
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['final_exact_bytes']}/{summary['total_bytes']}</div><div class="muted">final exact bytes</div></div>
  <div class="box"><div class="num">{summary['baseline_le2_bytes']}/{summary['total_bytes']}</div><div class="muted">baseline <=2 bytes</div></div>
  <div class="box"><div class="num">{summary['promoted_false_bytes']}</div><div class="muted">promoted false bytes</div></div>
  <div class="box"><div class="num">{summary['target_unknown_bytes']}</div><div class="muted">target unknown bytes</div></div>
</div>
<p>{links}</p>
<p class="muted">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</p>
<div class="panel"><h2>Applications</h2>{render_table(application_rows, APPLICATION_FIELDNAMES)}</div>
<div class="panel"><h2>Rules</h2>{render_table(rule_rows, RULE_FIELDNAMES)}</div>
<div class="panel"><h2>Selector rows</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</div>
<script type="application/json" id="compact-target-delta-guard-data">{data_json}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-rows", type=Path, default=DEFAULT_TARGET_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Compact Target Delta Guard Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, rule_rows, selector_rows, application_rows, issues = build_rows(read_csv(args.target_rows))
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rule_rows)
    write_csv(args.output / "selector_rows.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "target_delta_applications.csv", APPLICATION_FIELDNAMES, application_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (args.output / "index.html").write_text(
        build_html(summary, rule_rows, selector_rows, application_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Final exact: {summary['final_exact_bytes']}/{summary['total_bytes']}")
    print(f"Baseline <=2: {summary['baseline_le2_bytes']}/{summary['total_bytes']}")
    print(f"Promoted false: {summary['promoted_false_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
