#!/usr/bin/env python3
"""Promote compact exact residual corrections on high-row selector rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_promoted_replay"
)
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_integrated_replay/"
    "selector_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "baseline_exact_bytes",
    "baseline_le2_bytes",
    "selector_name",
    "selector_scope",
    "rule_keys",
    "singleton_keys",
    "consensus_keys",
    "non_consensus_keys",
    "changed_rule_keys",
    "promoted_rows",
    "promoted_changed_rows",
    "promoted_exact_bytes",
    "promoted_false_bytes",
    "final_exact_bytes",
    "final_le2_bytes",
    "exact_gain_bytes",
    "le2_gain_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RULE_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "selector_key",
    "byte_index",
    "group_size",
    "selected_delta",
    "exact_bytes",
    "false_bytes",
    "changed",
    "delta_histogram",
    "source_ids",
]

SELECTOR_FIELDNAMES = [
    "pair_id",
    "source_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "source_start",
    "byte_index",
    "source_offset",
    "source_value_hex",
    "selected_start",
    "selected_support_value_hex",
    "selected_delta",
    "selected_exact",
    "selected_le2",
    "chosen_start",
    "chosen_support_value_hex",
    "chosen_delta",
    "chosen_exact",
    "chosen_le2",
    "selector_promoted",
    "guard_reason",
    "base_known",
    "base_decoded_value_hex",
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
    "selector_key",
    "chosen_support_value_hex",
    "source_value_hex",
    "residual_delta",
    "residual_value_hex",
    "baseline_exact",
    "residual_exact",
    "residual_promoted",
    "rule_decision",
]

Feature = tuple[str, str, Callable[[dict[str, str]], str]]


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


def observed_delta(row: dict[str, str]) -> int | None:
    source = parse_hex_byte(row.get("source_value_hex", ""))
    chosen = parse_hex_byte(row.get("chosen_support_value_hex", ""))
    if source is None or chosen is None:
        return None
    return signed_delta(chosen, source)


def dominant(values: list[int]) -> tuple[int, int]:
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[0]


def histogram(values: list[int]) -> str:
    counts = Counter(values)
    return ";".join(f"{delta}:{counts[delta]}" for delta in sorted(counts))


def feature_defs() -> dict[str, Feature]:
    return {
        "byte_index_delta": ("byte_index_delta", "compact", lambda row: f"p{int_value(row, 'byte_index'):02d}"),
    }


def byte_index_from_key(key: str) -> str:
    return key[1:] if key.startswith("p") else ""


def build_rules(
    rows: list[dict[str, str]],
    selector_name: str,
    selector_scope: str,
    feature: Callable[[dict[str, str]], str],
    issues: list[str],
) -> tuple[dict[str, int], list[dict[str, str]]]:
    groups: dict[str, list[tuple[dict[str, str], int]]] = defaultdict(list)
    for row in rows:
        delta = observed_delta(row)
        key = feature(row)
        if delta is None:
            issues.append(f"{row.get('pair_id', '')}:{row.get('byte_index', '')}:missing_delta_inputs")
            continue
        groups[key].append((row, delta))

    rules: dict[str, int] = {}
    rule_rows: list[dict[str, str]] = []
    for key in sorted(groups, key=lambda value: (int(byte_index_from_key(value) or 0), value)):
        grouped = groups[key]
        deltas = [delta for _, delta in grouped]
        selected_delta, exact_count = dominant(deltas)
        rules[key] = selected_delta
        source_ids = sorted({row.get("source_id", "") for row, _ in grouped})
        rule_rows.append(
            {
                "selector_name": selector_name,
                "selector_scope": selector_scope,
                "selector_key": key,
                "byte_index": byte_index_from_key(key),
                "group_size": str(len(grouped)),
                "selected_delta": str(selected_delta),
                "exact_bytes": str(exact_count),
                "false_bytes": str(len(grouped) - exact_count),
                "changed": "1" if selected_delta != 0 else "0",
                "delta_histogram": histogram(deltas),
                "source_ids": ";".join(source_ids),
            }
        )
    if not rules:
        issues.append("missing_compact_residual_rules")
    return rules, rule_rows


def build_rows(
    selector_rows: list[dict[str, str]],
    selector_name: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    features = feature_defs()
    if selector_name not in features:
        raise ValueError(f"unsupported selector: {selector_name}")
    selector_name, selector_scope, feature = features[selector_name]

    issues: list[str] = []
    rules, rule_rows = build_rules(selector_rows, selector_name, selector_scope, feature, issues)
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

    for row in selector_rows:
        row_issues: list[str] = []
        source_value = parse_hex_byte(row.get("source_value_hex", ""))
        chosen_value = parse_hex_byte(row.get("chosen_support_value_hex", ""))
        baseline_is_exact = row.get("chosen_exact") == "1"
        baseline_is_le2 = row.get("chosen_le2") == "1"
        baseline_exact += 1 if baseline_is_exact else 0
        baseline_le2 += 1 if baseline_is_le2 else 0

        selector_key = feature(row)
        rule_delta = rules.get(selector_key)
        residual_value = chosen_value
        residual_promoted = False
        rule_decision = "reject"
        if source_value is None:
            row_issues.append("missing_source_value")
        if chosen_value is None:
            row_issues.append("missing_chosen_support_value")
        if rule_delta is None:
            row_issues.append("missing_residual_rule")
        elif chosen_value is not None:
            residual_value = (chosen_value + rule_delta) & 0xFF
            residual_promoted = True
            rule_decision = "accept"

        residual_is_exact = residual_value is not None and source_value is not None and residual_value == source_value
        residual_observed_delta = (
            signed_delta(residual_value, source_value)
            if residual_value is not None and source_value is not None
            else int_value(row, "chosen_delta")
        )
        residual_is_le2 = abs(residual_observed_delta) <= 2
        final_exact += 1 if residual_is_exact else 0
        final_le2 += 1 if residual_is_le2 else 0
        promoted += 1 if residual_promoted else 0
        promoted_changed += 1 if residual_promoted and rule_delta != 0 else 0
        promoted_exact += 1 if residual_promoted and residual_is_exact else 0
        promoted_false += 1 if residual_promoted and not residual_is_exact else 0

        if residual_promoted or baseline_is_exact != residual_is_exact:
            application_rows.append(
                {
                    "pair_id": row.get("pair_id", ""),
                    "source_id": row.get("source_id", ""),
                    "byte_index": row.get("byte_index", ""),
                    "selector_key": selector_key,
                    "chosen_support_value_hex": row.get("chosen_support_value_hex", ""),
                    "source_value_hex": row.get("source_value_hex", ""),
                    "residual_delta": "" if rule_delta is None else str(rule_delta),
                    "residual_value_hex": hex_byte(residual_value),
                    "baseline_exact": "1" if baseline_is_exact else "0",
                    "residual_exact": "1" if residual_is_exact else "0",
                    "residual_promoted": "1" if residual_promoted else "0",
                    "rule_decision": rule_decision,
                }
            )

        if row_issues:
            issues.append(
                f"{row.get('pair_id', '')}:{row.get('source_id', '')}:{row.get('byte_index', '')}:"
                f"{';'.join(row_issues)}"
            )

        output_rows.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "source_start": row.get("source_start", ""),
                "byte_index": row.get("byte_index", ""),
                "source_offset": row.get("source_offset", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "selected_start": row.get("selected_start", ""),
                "selected_support_value_hex": row.get("selected_support_value_hex", ""),
                "selected_delta": row.get("selected_delta", ""),
                "selected_exact": row.get("selected_exact", ""),
                "selected_le2": row.get("selected_le2", ""),
                "chosen_start": row.get("chosen_start", ""),
                "chosen_support_value_hex": row.get("chosen_support_value_hex", ""),
                "chosen_delta": row.get("chosen_delta", ""),
                "chosen_exact": "1" if baseline_is_exact else "0",
                "chosen_le2": "1" if baseline_is_le2 else "0",
                "selector_promoted": row.get("selector_promoted", ""),
                "guard_reason": row.get("guard_reason", ""),
                "base_known": row.get("base_known", ""),
                "base_decoded_value_hex": row.get("base_decoded_value_hex", ""),
                "residual_selector_name": selector_name,
                "residual_selector_key": selector_key,
                "residual_delta": "" if rule_delta is None else str(rule_delta),
                "residual_value_hex": hex_byte(residual_value),
                "residual_observed_delta": str(residual_observed_delta),
                "residual_exact": "1" if residual_is_exact else "0",
                "residual_le2": "1" if residual_is_le2 else "0",
                "residual_promoted": "1" if residual_promoted else "0",
                "residual_guard_key": f"{selector_name}|{selector_key}|d{rule_delta}" if rule_delta is not None else "",
                "residual_rule_decision": rule_decision,
                "issues": ";".join(row_issues),
            }
        )

    exact_gain = final_exact - baseline_exact
    le2_gain = final_le2 - baseline_le2
    issue_count = len(issues)
    non_consensus_keys = sum(1 for rule in rule_rows if int_value(rule, "false_bytes") > 0)
    if issue_count:
        verdict = "frontier80_prior_high_row_exact_residual_compact_promoted_replay_issues"
        next_probe = "fix compact residual replay input issues"
    elif promoted_false > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_promoted_replay_rejected"
        next_probe = "review compact residual promotion false positives"
    elif final_exact == len(selector_rows) and exact_gain > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_promoted_replay_ready"
        next_probe = "integrate compact exact residual correction into support-only high-row fixture replay"
    elif exact_gain > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_promoted_replay_weak"
        next_probe = "expand compact residual selector coverage before fixture integration"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_compact_promoted_replay_weak"
        next_probe = "review compact residual selector before fixture integration"

    summary = {
        "scope": "total",
        "total_bytes": str(len(selector_rows)),
        "baseline_exact_bytes": str(baseline_exact),
        "baseline_le2_bytes": str(baseline_le2),
        "selector_name": selector_name,
        "selector_scope": selector_scope,
        "rule_keys": str(len(rule_rows)),
        "singleton_keys": str(sum(1 for rule in rule_rows if int_value(rule, "group_size") == 1)),
        "consensus_keys": str(len(rule_rows) - non_consensus_keys),
        "non_consensus_keys": str(non_consensus_keys),
        "changed_rule_keys": str(sum(1 for rule in rule_rows if rule.get("changed") == "1")),
        "promoted_rows": str(promoted),
        "promoted_changed_rows": str(promoted_changed),
        "promoted_exact_bytes": str(promoted_exact),
        "promoted_false_bytes": str(promoted_false),
        "final_exact_bytes": str(final_exact),
        "final_le2_bytes": str(final_le2),
        "exact_gain_bytes": str(exact_gain),
        "le2_gain_bytes": str(le2_gain),
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
            ("residual_applications.csv", output_dir / "residual_applications.csv"),
            ("issues.txt", output_dir / "issues.txt"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
  --warn: #f2c36b;
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
    <div class="sub">Applies compact byte-index residual deltas to support-only high-row selector rows.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Exact final</div><div class="value">{summary['final_exact_bytes']}/{summary['total_bytes']}</div></div>
    <div class="stat"><div class="label">Exact gain</div><div class="value ok">+{summary['exact_gain_bytes']}</div></div>
    <div class="stat"><div class="label">Promoted false</div><div class="value warn">{summary['promoted_false_bytes']}</div></div>
    <div class="stat"><div class="label">Rule keys</div><div class="value">{summary['rule_keys']}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Residual applications</h2>{render_table(application_rows, APPLICATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Compact rules</h2>{render_table(rule_rows, RULE_FIELDNAMES)}</section>
  <section class="panel"><h2>Selector rows</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
</main>
<script type="application/json" id="high-row-exact-residual-compact-promoted-replay-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    selector_rows_path: Path,
    selector_name: str,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, rule_rows, selector_rows, application_rows, issues = build_rows(read_csv(selector_rows_path), selector_name)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    write_csv(output_dir / "selector_rows.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "residual_applications.csv", APPLICATION_FIELDNAMES, application_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, rule_rows, selector_rows, application_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument("--selector-name", default="byte_index_delta", choices=sorted(feature_defs()))
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Compact Promoted Replay",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.selector_rows, args.selector_name, title=args.title)
    print(f"Promoted rows: {summary['promoted_rows']}")
    print(f"Final exact: {summary['final_exact_bytes']}/{summary['total_bytes']}")
    print(f"Exact gain: {summary['exact_gain_bytes']}")
    print(f"Promoted false: {summary['promoted_false_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
