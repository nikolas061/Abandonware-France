#!/usr/bin/env python3
"""Probe exact residual corrections after the threshold-guarded high-row selector."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_correction_probe")
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_integrated_replay/selector_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "baseline_exact_bytes",
    "baseline_le2_bytes",
    "best_compact_selector",
    "best_compact_exact_bytes",
    "best_compact_exact_ratio",
    "best_compact_key_count",
    "best_compact_singleton_keys",
    "best_compact_consensus_changed_bytes",
    "best_source_specific_selector",
    "best_source_specific_exact_bytes",
    "best_source_specific_exact_ratio",
    "best_source_specific_key_count",
    "best_source_specific_consensus_changed_bytes",
    "best_consensus_selector",
    "best_consensus_scope",
    "best_consensus_keys",
    "best_consensus_bytes",
    "best_consensus_changed_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SELECTOR_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "key_count",
    "singleton_keys",
    "exact_bytes",
    "exact_ratio",
    "false_bytes",
    "predicted_delta_domain",
    "repeated_consensus_keys",
    "repeated_consensus_bytes",
    "repeated_consensus_changed_bytes",
    "repeated_consensus_delta_domain",
    "table_preview",
]

PREDICTION_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "selector_key",
    "pair_id",
    "source_id",
    "byte_index",
    "chosen_support_value_hex",
    "source_value_hex",
    "observed_delta",
    "predicted_delta",
    "predicted_value_hex",
    "exact",
    "changed",
    "group_size",
]

Feature = tuple[str, str, Callable[[dict[str, str]], str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_hex_byte(value: str) -> int:
    return int(value, 16)


def hex_byte(value: int) -> str:
    return f"0x{value & 0xFF:02x}"


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def observed_delta(row: dict[str, str]) -> int:
    return parse_hex_byte(row.get("source_value_hex", "0x00")) - parse_hex_byte(
        row.get("chosen_support_value_hex", "0x00")
    )


def dominant(values: list[int]) -> tuple[int, int]:
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[0]


def histogram(values: list[int]) -> str:
    counts = Counter(values)
    return ";".join(f"{delta}:{counts[delta]}" for delta in sorted(counts))


def feature_defs() -> list[Feature]:
    return [
        ("global_delta", "compact", lambda row: "all"),
        ("byte_mod2_delta", "compact", lambda row: str(int_value(row, "byte_index") % 2)),
        ("byte_mod4_delta", "compact", lambda row: str(int_value(row, "byte_index") % 4)),
        ("byte_mod8_delta", "compact", lambda row: str(int_value(row, "byte_index") % 8)),
        ("byte_mod16_delta", "compact", lambda row: str(int_value(row, "byte_index") % 16)),
        ("byte_index_delta", "compact", lambda row: f"p{int_value(row, 'byte_index'):02d}"),
        ("chosen_value_delta", "compact", lambda row: row.get("chosen_support_value_hex", "")),
        (
            "chosen_value_mod4_delta",
            "compact",
            lambda row: f"{row.get('chosen_support_value_hex', '')}|m{int_value(row, 'byte_index') % 4}",
        ),
        (
            "chosen_value_mod8_delta",
            "compact",
            lambda row: f"{row.get('chosen_support_value_hex', '')}|m{int_value(row, 'byte_index') % 8}",
        ),
        ("chosen_start_delta", "compact", lambda row: row.get("chosen_start", "")),
        (
            "chosen_start_mod8_delta",
            "compact",
            lambda row: f"{row.get('chosen_start', '')}|m{int_value(row, 'byte_index') % 8}",
        ),
        (
            "base_known_mod8_delta",
            "compact",
            lambda row: f"{row.get('base_known', '')}|m{int_value(row, 'byte_index') % 8}",
        ),
        (
            "guard_reason_mod8_delta",
            "compact",
            lambda row: f"{row.get('guard_reason', '')}|m{int_value(row, 'byte_index') % 8}",
        ),
        ("source_id_delta", "source_specific", lambda row: row.get("source_id", "")),
        (
            "source_id_mod4_delta",
            "source_specific",
            lambda row: f"{row.get('source_id', '')}|m{int_value(row, 'byte_index') % 4}",
        ),
        (
            "source_id_mod8_delta",
            "source_specific",
            lambda row: f"{row.get('source_id', '')}|m{int_value(row, 'byte_index') % 8}",
        ),
        (
            "source_id_mod16_delta",
            "source_specific",
            lambda row: f"{row.get('source_id', '')}|m{int_value(row, 'byte_index') % 16}",
        ),
    ]


def selector_stats(rows: list[dict[str, str]], name: str, scope: str, feature: Callable[[dict[str, str]], str]) -> dict[str, str]:
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[feature(row)].append(observed_delta(row))

    table: dict[str, int] = {}
    previews: list[str] = []
    consensus_keys = 0
    consensus_bytes = 0
    consensus_changed = 0
    consensus_domain: set[int] = set()
    for key in sorted(groups):
        values = groups[key]
        selected, selected_count = dominant(values)
        table[key] = selected
        if len(previews) < 32:
            previews.append(f"{key}:{selected}/{selected_count}/{histogram(values)}")
        if len(values) >= 2 and len(set(values)) == 1:
            consensus_keys += 1
            consensus_bytes += len(values)
            consensus_domain.add(values[0])
            if values[0] != 0:
                consensus_changed += len(values)

    exact = sum(1 for row in rows if observed_delta(row) == table[feature(row)])
    return {
        "selector_name": name,
        "selector_scope": scope,
        "key_count": str(len(groups)),
        "singleton_keys": str(sum(1 for values in groups.values() if len(values) == 1)),
        "exact_bytes": str(exact),
        "exact_ratio": ratio(exact, len(rows)),
        "false_bytes": str(len(rows) - exact),
        "predicted_delta_domain": ";".join(str(delta) for delta in sorted(set(table.values()))),
        "repeated_consensus_keys": str(consensus_keys),
        "repeated_consensus_bytes": str(consensus_bytes),
        "repeated_consensus_changed_bytes": str(consensus_changed),
        "repeated_consensus_delta_domain": ";".join(str(delta) for delta in sorted(consensus_domain)),
        "table_preview": " | ".join(previews),
    }


def build_selector_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selector_rows = [selector_stats(rows, name, scope, feature) for name, scope, feature in feature_defs()]
    selector_rows.sort(
        key=lambda row: (
            row.get("selector_scope", ""),
            -int_value(row, "exact_bytes"),
            -int_value(row, "repeated_consensus_changed_bytes"),
            int_value(row, "singleton_keys"),
            int_value(row, "key_count"),
            row.get("selector_name", ""),
        )
    )
    return selector_rows


def best_selector(selector_rows: list[dict[str, str]], scope: str) -> dict[str, str]:
    scoped = [row for row in selector_rows if row.get("selector_scope") == scope]
    return scoped[0] if scoped else {}


def best_consensus_selector(selector_rows: list[dict[str, str]]) -> dict[str, str]:
    return sorted(
        selector_rows,
        key=lambda row: (
            -int_value(row, "repeated_consensus_changed_bytes"),
            -int_value(row, "repeated_consensus_bytes"),
            int_value(row, "singleton_keys"),
            int_value(row, "key_count"),
            row.get("selector_scope", ""),
            row.get("selector_name", ""),
        ),
    )[0] if selector_rows else {}


def build_predictions(
    rows: list[dict[str, str]],
    selector_name: str,
    selector_scope: str,
    feature: Callable[[dict[str, str]], str],
) -> list[dict[str, str]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[feature(row)].append(observed_delta(row))
    consensus = {key: values[0] for key, values in groups.items() if len(values) >= 2 and len(set(values)) == 1}

    predictions: list[dict[str, str]] = []
    for row in rows:
        key = feature(row)
        if key not in consensus:
            continue
        delta = consensus[key]
        chosen = parse_hex_byte(row.get("chosen_support_value_hex", "0x00"))
        predicted = chosen + delta
        actual_delta = observed_delta(row)
        predictions.append(
            {
                "selector_name": selector_name,
                "selector_scope": selector_scope,
                "selector_key": key,
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "byte_index": row.get("byte_index", ""),
                "chosen_support_value_hex": row.get("chosen_support_value_hex", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "observed_delta": str(actual_delta),
                "predicted_delta": str(delta),
                "predicted_value_hex": hex_byte(predicted),
                "exact": "1" if actual_delta == delta else "0",
                "changed": "1" if delta != 0 else "0",
                "group_size": str(len(groups[key])),
            }
        )
    return predictions


def build_summary(rows: list[dict[str, str]], selector_rows: list[dict[str, str]], prediction_rows: list[dict[str, str]]) -> dict[str, str]:
    total = len(rows)
    baseline_exact = sum(1 for row in rows if row.get("chosen_exact") == "1")
    baseline_le2 = sum(1 for row in rows if row.get("chosen_le2") == "1")
    compact = best_selector(selector_rows, "compact")
    source_specific = best_selector(selector_rows, "source_specific")
    consensus = best_consensus_selector(selector_rows)
    changed = int_value(consensus, "repeated_consensus_changed_bytes")
    if int_value(compact, "exact_bytes") == total and total:
        verdict = "frontier80_prior_high_row_exact_residual_compact_ready"
        next_probe = "promote compact exact residual correction for threshold-guarded high-row selector"
    elif changed > 0:
        verdict = "frontier80_prior_high_row_exact_residual_partial_consensus_ready"
        next_probe = "validate residual consensus correction against wider high-row support rows"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_correction_weak"
        next_probe = "expand residual correction features beyond selector-local context"

    return {
        "scope": "total",
        "total_bytes": str(total),
        "baseline_exact_bytes": str(baseline_exact),
        "baseline_le2_bytes": str(baseline_le2),
        "best_compact_selector": compact.get("selector_name", ""),
        "best_compact_exact_bytes": compact.get("exact_bytes", "0"),
        "best_compact_exact_ratio": compact.get("exact_ratio", "0.000000"),
        "best_compact_key_count": compact.get("key_count", "0"),
        "best_compact_singleton_keys": compact.get("singleton_keys", "0"),
        "best_compact_consensus_changed_bytes": compact.get("repeated_consensus_changed_bytes", "0"),
        "best_source_specific_selector": source_specific.get("selector_name", ""),
        "best_source_specific_exact_bytes": source_specific.get("exact_bytes", "0"),
        "best_source_specific_exact_ratio": source_specific.get("exact_ratio", "0.000000"),
        "best_source_specific_key_count": source_specific.get("key_count", "0"),
        "best_source_specific_consensus_changed_bytes": source_specific.get("repeated_consensus_changed_bytes", "0"),
        "best_consensus_selector": consensus.get("selector_name", ""),
        "best_consensus_scope": consensus.get("selector_scope", ""),
        "best_consensus_keys": consensus.get("repeated_consensus_keys", "0"),
        "best_consensus_bytes": consensus.get("repeated_consensus_bytes", "0"),
        "best_consensus_changed_bytes": str(sum(1 for row in prediction_rows if row.get("changed") == "1")),
        "issue_rows": "0",
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
    selector_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "selectors": selector_rows, "predictions": prediction_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("selector_candidates.csv", output_dir / "selector_candidates.csv"),
            ("consensus_predictions.csv", output_dir / "consensus_predictions.csv"),
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
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1360px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Profiles exact residual deltas after the threshold-guarded high-row selector.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Baseline exact</div><div class="value">{summary['baseline_exact_bytes']}/{summary['total_bytes']}</div></div>
    <div class="stat"><div class="label">Best compact exact</div><div class="value">{summary['best_compact_exact_bytes']}/{summary['total_bytes']}</div></div>
    <div class="stat"><div class="label">Best consensus changed</div><div class="value ok">{summary['best_consensus_changed_bytes']}</div></div>
    <div class="stat"><div class="label">Best consensus selector</div><div class="value">{html.escape(summary['best_consensus_selector'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Selector candidates</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Consensus predictions</h2>{render_table(prediction_rows, PREDICTION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="high-row-exact-residual-correction-data">{data_json}</script>
</body>
</html>
"""


def write_report(selector_rows_path: Path, output_dir: Path, *, title: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(selector_rows_path)
    selector_rows = build_selector_rows(rows)
    consensus = best_consensus_selector(selector_rows)
    feature_lookup = {name: (scope, feature) for name, scope, feature in feature_defs()}
    consensus_scope, consensus_feature = feature_lookup.get(
        consensus.get("selector_name", ""),
        ("", lambda row: ""),
    )
    prediction_rows = build_predictions(rows, consensus.get("selector_name", ""), consensus_scope, consensus_feature)
    summary = build_summary(rows, selector_rows, prediction_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "selector_candidates.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "consensus_predictions.csv", PREDICTION_FIELDNAMES, prediction_rows)
    (output_dir / "index.html").write_text(build_html(summary, selector_rows, prediction_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Correction Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.selector_rows, args.output, title=args.title)
    print(f"Baseline exact: {summary['baseline_exact_bytes']}/{summary['total_bytes']}")
    print(f"Best compact: {summary['best_compact_selector']} {summary['best_compact_exact_bytes']}/{summary['total_bytes']}")
    print(f"Best consensus: {summary['best_consensus_selector']} +{summary['best_consensus_changed_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
