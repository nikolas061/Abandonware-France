#!/usr/bin/env python3
"""Validate exact residual consensus rules against wider prior high-row support."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import lolg_tex_gap_decoder_frontier80_clean_prior_high_row_support_review as support_review
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_consensus_validation_probe"
)
DEFAULT_CONSENSUS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_correction_probe/consensus_predictions.csv"
)
DEFAULT_SUPPORT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/known_family_support.csv")
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selector_name",
    "selector_scope",
    "prediction_rows",
    "rule_rows",
    "rule_domain",
    "source_rows",
    "support_rows",
    "validation_bytes",
    "exact_bytes",
    "false_bytes",
    "exact_ratio",
    "changed_bytes",
    "changed_exact_bytes",
    "changed_false_bytes",
    "zero_rule_bytes",
    "zero_rule_exact_bytes",
    "zero_rule_false_bytes",
    "support_rows_with_false",
    "changed_false_support_rows",
    "training_signature_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RULE_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "selector_key",
    "predicted_delta",
    "changed",
    "prediction_rows",
    "source_ids",
    "byte_mods",
]

VALIDATION_FIELDNAMES = [
    "source_id",
    "support_id",
    "rank",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "support_start",
    "byte_index",
    "selector_name",
    "selector_key",
    "support_value_hex",
    "source_value_hex",
    "observed_delta",
    "predicted_delta",
    "predicted_value_hex",
    "exact",
    "changed",
    "training_signature",
]

SOURCE_FIELDNAMES = [
    "source_id",
    "support_rows",
    "validation_bytes",
    "exact_bytes",
    "false_bytes",
    "changed_bytes",
    "changed_exact_bytes",
    "changed_false_bytes",
    "zero_rule_bytes",
    "zero_rule_false_bytes",
    "support_rows_with_false",
    "changed_false_support_rows",
]

MOD_RE = re.compile(r"_mod(\d+)_delta$")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def hex_byte(value: int) -> str:
    return f"0x{value & 0xFF:02x}"


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def parse_hex_byte(value: str) -> int:
    return int(value, 16)


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def selector_mod(selector_name: str) -> int:
    match = MOD_RE.search(selector_name)
    return int(match.group(1)) if match else 0


def selector_key_for(
    selector_name: str,
    source_id: str,
    byte_index: int,
    support_value: int,
    support_start: str,
) -> str:
    mod = selector_mod(selector_name)
    if selector_name == "global_delta":
        return "all"
    if selector_name.startswith("byte_mod") and mod:
        return str(byte_index % mod)
    if selector_name == "byte_index_delta":
        return f"p{byte_index:02d}"
    if selector_name == "chosen_value_delta":
        return hex_byte(support_value)
    if selector_name.startswith("chosen_value_mod") and mod:
        return f"{hex_byte(support_value)}|m{byte_index % mod}"
    if selector_name == "chosen_start_delta":
        return support_start
    if selector_name.startswith("chosen_start_mod") and mod:
        return f"{support_start}|m{byte_index % mod}"
    if selector_name == "source_id_delta":
        return source_id
    if selector_name.startswith("source_id_mod") and mod:
        return f"{source_id}|m{byte_index % mod}"
    return ""


def build_rules(prediction_rows: list[dict[str, str]], issues: list[str]) -> tuple[list[dict[str, str]], dict[str, int]]:
    if not prediction_rows:
        issues.append("missing_consensus_predictions")
        return [], {}

    selector_counts = Counter(
        (row.get("selector_name", ""), row.get("selector_scope", "")) for row in prediction_rows
    )
    selector_name, selector_scope = selector_counts.most_common(1)[0][0]
    selected_rows = [
        row
        for row in prediction_rows
        if row.get("selector_name", "") == selector_name and row.get("selector_scope", "") == selector_scope
    ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected_rows:
        grouped[row.get("selector_key", "")].append(row)

    rules: list[dict[str, str]] = []
    rule_map: dict[str, int] = {}
    for key in sorted(grouped):
        rows = grouped[key]
        deltas = {int_value(row, "predicted_delta") for row in rows}
        if len(deltas) != 1:
            issues.append(f"{selector_name}:{key}:conflicting_predicted_deltas")
            continue
        delta = next(iter(deltas))
        source_ids = sorted({row.get("source_id", "") for row in rows if row.get("source_id", "")})
        byte_mods = sorted({str(int_value(row, "byte_index") % 16) for row in rows})
        rule_map[key] = delta
        rules.append(
            {
                "selector_name": selector_name,
                "selector_scope": selector_scope,
                "selector_key": key,
                "predicted_delta": str(delta),
                "changed": "1" if delta != 0 else "0",
                "prediction_rows": str(len(rows)),
                "source_ids": ";".join(source_ids),
                "byte_mods": ";".join(byte_mods),
            }
        )

    if not rule_map:
        issues.append(f"{selector_name}:no_valid_rules")
    return rules, rule_map


def fixture_window(
    row: dict[str, str],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    start_field: str,
    end_field: str,
    issues: list[str],
    label: str,
) -> bytes:
    key = support_review.fixture_key(row)
    fixture = fixtures.get(key, {})
    expected = fixture.get("expected", b"")
    if not isinstance(expected, bytes):
        issues.append(f"{label}:{key}:missing_expected_bytes")
        return b""
    start = int_value(row, start_field)
    end = int_value(row, end_field)
    if start < 0 or end > len(expected) or end < start:
        issues.append(f"{label}:{key}:{start}-{end}:out_of_bounds")
        return b""
    window = expected[start:end]
    if len(window) != 32:
        issues.append(f"{label}:{key}:{start}-{end}:expected_32_got_{len(window)}")
        return b""
    return window


def training_signatures(prediction_rows: list[dict[str, str]]) -> set[tuple[str, int, str, str, str]]:
    return {
        (
            row.get("source_id", ""),
            int_value(row, "byte_index") % 16,
            row.get("chosen_support_value_hex", ""),
            row.get("source_value_hex", ""),
            row.get("predicted_delta", ""),
        )
        for row in prediction_rows
    }


def build_validation_rows(
    rules: dict[str, int],
    prediction_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
) -> list[dict[str, str]]:
    if not prediction_rows:
        return []
    selector_name = prediction_rows[0].get("selector_name", "")
    source_by_id = {row.get("source_id", ""): row for row in source_rows}
    train = training_signatures(prediction_rows)
    rows: list[dict[str, str]] = []

    for support_row in support_rows:
        source_id = support_row.get("source_id", "")
        source_row = source_by_id.get(source_id)
        if not source_row:
            issues.append(f"{source_id}:missing_source_row")
            continue
        source_window = fixture_window(source_row, fixtures, "source_start", "source_end", issues, "source")
        support_window = fixture_window(support_row, fixtures, "start", "end", issues, "support")
        if not source_window or not support_window:
            continue
        for byte_index, (support_value, source_value) in enumerate(zip(support_window, source_window)):
            key = selector_key_for(
                selector_name,
                source_id,
                byte_index,
                support_value,
                support_row.get("start", ""),
            )
            if key not in rules:
                continue
            predicted_delta = rules[key]
            predicted_value = (support_value + predicted_delta) & 0xFF
            exact = predicted_value == source_value
            signature = (
                source_id,
                byte_index % 16,
                hex_byte(support_value),
                hex_byte(source_value),
                str(predicted_delta),
            )
            rows.append(
                {
                    "source_id": source_id,
                    "support_id": support_row.get("support_id", ""),
                    "rank": support_row.get("rank", ""),
                    "archive_tag": support_row.get("archive_tag", ""),
                    "pcx_name": support_row.get("pcx_name", ""),
                    "frontier_id": support_row.get("frontier_id", ""),
                    "support_start": support_row.get("start", ""),
                    "byte_index": str(byte_index),
                    "selector_name": selector_name,
                    "selector_key": key,
                    "support_value_hex": hex_byte(support_value),
                    "source_value_hex": hex_byte(source_value),
                    "observed_delta": str(signed_delta(support_value, source_value)),
                    "predicted_delta": str(predicted_delta),
                    "predicted_value_hex": hex_byte(predicted_value),
                    "exact": "1" if exact else "0",
                    "changed": "1" if predicted_delta != 0 else "0",
                    "training_signature": "1" if signature in train else "0",
                }
            )
    return rows


def source_summaries(rows: list[dict[str, str]], support_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    support_by_source: dict[str, set[str]] = defaultdict(set)
    for row in support_rows:
        support_by_source[row.get("source_id", "")].add(row.get("support_id", ""))

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("source_id", "")].append(row)

    summaries: list[dict[str, str]] = []
    for source_id in sorted(grouped):
        source_rows = grouped[source_id]
        false_supports = {
            row.get("support_id", "")
            for row in source_rows
            if row.get("exact") != "1"
        }
        changed_false_supports = {
            row.get("support_id", "")
            for row in source_rows
            if row.get("changed") == "1" and row.get("exact") != "1"
        }
        summaries.append(
            {
                "source_id": source_id,
                "support_rows": str(len(support_by_source.get(source_id, set()))),
                "validation_bytes": str(len(source_rows)),
                "exact_bytes": str(sum(1 for row in source_rows if row.get("exact") == "1")),
                "false_bytes": str(sum(1 for row in source_rows if row.get("exact") != "1")),
                "changed_bytes": str(sum(1 for row in source_rows if row.get("changed") == "1")),
                "changed_exact_bytes": str(
                    sum(1 for row in source_rows if row.get("changed") == "1" and row.get("exact") == "1")
                ),
                "changed_false_bytes": str(
                    sum(1 for row in source_rows if row.get("changed") == "1" and row.get("exact") != "1")
                ),
                "zero_rule_bytes": str(sum(1 for row in source_rows if row.get("changed") != "1")),
                "zero_rule_false_bytes": str(
                    sum(1 for row in source_rows if row.get("changed") != "1" and row.get("exact") != "1")
                ),
                "support_rows_with_false": str(len(false_supports)),
                "changed_false_support_rows": str(len(changed_false_supports)),
            }
        )
    return summaries


def build_summary(
    prediction_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    selector_name = rule_rows[0].get("selector_name", "") if rule_rows else ""
    selector_scope = rule_rows[0].get("selector_scope", "") if rule_rows else ""
    total = len(validation_rows)
    exact = sum(1 for row in validation_rows if row.get("exact") == "1")
    changed = [row for row in validation_rows if row.get("changed") == "1"]
    zero_rule = [row for row in validation_rows if row.get("changed") != "1"]
    changed_exact = sum(1 for row in changed if row.get("exact") == "1")
    changed_false = sum(1 for row in changed if row.get("exact") != "1")
    zero_exact = sum(1 for row in zero_rule if row.get("exact") == "1")
    zero_false = sum(1 for row in zero_rule if row.get("exact") != "1")
    false_supports = {
        (row.get("source_id", ""), row.get("support_id", ""))
        for row in validation_rows
        if row.get("exact") != "1"
    }
    changed_false_supports = {
        (row.get("source_id", ""), row.get("support_id", ""))
        for row in changed
        if row.get("exact") != "1"
    }
    training = sum(1 for row in validation_rows if row.get("training_signature") == "1")

    if issue_count:
        verdict = "frontier80_prior_high_row_exact_residual_consensus_validation_issues"
        next_probe = "fix residual consensus validation fixture/rule issues"
    elif changed and changed_false == 0:
        verdict = "frontier80_prior_high_row_exact_residual_consensus_validation_ready"
        next_probe = "promote validated residual consensus correction for threshold-guarded high-row selector"
    elif changed:
        verdict = "frontier80_prior_high_row_exact_residual_consensus_validation_rejected"
        next_probe = "split residual consensus correction by wider support context"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_consensus_validation_weak"
        next_probe = "expand residual correction features beyond selector-local consensus"

    return {
        "scope": "total",
        "selector_name": selector_name,
        "selector_scope": selector_scope,
        "prediction_rows": str(len(prediction_rows)),
        "rule_rows": str(len(rule_rows)),
        "rule_domain": ";".join(str(delta) for delta in sorted({int_value(row, "predicted_delta") for row in rule_rows})),
        "source_rows": str(len(source_rows)),
        "support_rows": str(len(support_rows)),
        "validation_bytes": str(total),
        "exact_bytes": str(exact),
        "false_bytes": str(total - exact),
        "exact_ratio": ratio(exact, total),
        "changed_bytes": str(len(changed)),
        "changed_exact_bytes": str(changed_exact),
        "changed_false_bytes": str(changed_false),
        "zero_rule_bytes": str(len(zero_rule)),
        "zero_rule_exact_bytes": str(zero_exact),
        "zero_rule_false_bytes": str(zero_false),
        "support_rows_with_false": str(len(false_supports)),
        "changed_false_support_rows": str(len(changed_false_supports)),
        "training_signature_bytes": str(training),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


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
    validation_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    issues: list[str],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "rules": rule_rows,
        "validation": validation_rows,
        "sources": source_rows,
        "issues": issues,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("rules.csv", output_dir / "rules.csv"),
            ("validation_rows.csv", output_dir / "validation_rows.csv"),
            ("source_summaries.csv", output_dir / "source_summaries.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1460px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Validates exact residual consensus deltas against the wider high-row support family.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Validation exact</div><div class="value">{summary['exact_bytes']}/{summary['validation_bytes']}</div></div>
    <div class="stat"><div class="label">Changed exact</div><div class="value ok">{summary['changed_exact_bytes']}/{summary['changed_bytes']}</div></div>
    <div class="stat"><div class="label">Changed false</div><div class="value warn">{summary['changed_false_bytes']}</div></div>
    <div class="stat"><div class="label">Rules</div><div class="value">{summary['rule_rows']}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Rules</h2>{render_table(rule_rows, RULE_FIELDNAMES)}</section>
  <section class="panel"><h2>Source summaries</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</section>
  <section class="panel"><h2>Validation rows</h2>{render_table(validation_rows, VALIDATION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="high-row-exact-residual-consensus-validation-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    consensus_path: Path,
    support_path: Path,
    sources_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    output_dir: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    prediction_rows = read_csv(consensus_path)
    rule_rows, rules = build_rules(prediction_rows, issues)
    support_rows = read_csv(support_path)
    source_rows = read_csv(sources_path)
    fixtures = support_review.load_fixtures(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    validation_rows = build_validation_rows(rules, prediction_rows, support_rows, source_rows, fixtures, issues)
    source_summary_rows = source_summaries(validation_rows, support_rows)
    summary = build_summary(
        prediction_rows,
        rule_rows,
        source_rows,
        support_rows,
        validation_rows,
        len(issues),
    )

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    write_csv(output_dir / "validation_rows.csv", VALIDATION_FIELDNAMES, validation_rows)
    write_csv(output_dir / "source_summaries.csv", SOURCE_FIELDNAMES, source_summary_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, rule_rows, validation_rows, source_summary_rows, issues, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consensus-predictions", type=Path, default=DEFAULT_CONSENSUS)
    parser.add_argument("--support", type=Path, default=DEFAULT_SUPPORT)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Consensus Validation Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.consensus_predictions,
        args.support,
        args.sources,
        args.manifest,
        args.clean_fixtures,
        args.output,
        title=args.title,
    )
    print(f"Validation exact: {summary['exact_bytes']}/{summary['validation_bytes']}")
    print(f"Changed exact: {summary['changed_exact_bytes']}/{summary['changed_bytes']}")
    print(f"Changed false: {summary['changed_false_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
