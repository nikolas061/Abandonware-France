#!/usr/bin/env python3
"""Profile signed-delta selectors for the dominant prior high-row cluster."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_support_review import load_fixtures, signed_delta
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_signed_delta_selector_probe")
DEFAULT_SELECTED_SUPPORT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_compact_selector_probe/selected_support.csv"
)
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "pair_rows",
    "total_bytes",
    "signed_delta_le2_bytes",
    "signed_delta_le2_ratio",
    "signed_delta_le2_min",
    "signed_delta_le4_bytes",
    "signed_delta_le4_ratio",
    "outlier_bytes",
    "max_abs_delta",
    "delta_domain",
    "best_compact_selector",
    "best_compact_selector_exact_bytes",
    "best_compact_selector_exact_ratio",
    "best_compact_selector_keys",
    "best_source_specific_selector",
    "best_source_specific_selector_exact_bytes",
    "best_source_specific_selector_exact_ratio",
    "best_source_specific_selector_keys",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

PAIR_FIELDNAMES = [
    "pair_id",
    "source_id",
    "cluster_key",
    "source_rank",
    "source_pcx_name",
    "source_frontier_id",
    "source_start",
    "source_end",
    "support_rank",
    "support_pcx_name",
    "support_frontier_id",
    "support_start",
    "support_end",
    "source_known_bytes",
    "support_known_bytes",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "max_abs_delta",
    "top_delta",
    "top_delta_count",
    "outlier_positions",
    "delta_values",
    "support_hex",
    "source_hex",
]

BYTE_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "support_value_hex",
    "source_value_hex",
    "signed_delta",
    "abs_delta",
    "in_le2",
    "in_le4",
    "source_known",
    "support_known",
]

POSITION_FIELDNAMES = [
    "byte_index",
    "observed_rows",
    "delta_values",
    "dominant_delta",
    "dominant_count",
    "exact_consensus",
    "small_delta_le2_count",
    "small_delta_le4_count",
    "outlier_count",
    "support_values_hex",
    "source_values_hex",
]

SELECTOR_FIELDNAMES = [
    "selector_name",
    "selector_scope",
    "key_count",
    "exact_bytes",
    "exact_ratio",
    "predicted_delta_domain",
    "predicted_delta_le2_bytes",
    "observed_delta_le2_bytes",
    "observed_delta_le4_bytes",
    "table_preview",
]

OUTLIER_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "support_value_hex",
    "source_value_hex",
    "signed_delta",
    "abs_delta",
    "source_known",
    "support_known",
]


Observation = dict[str, object]
Feature = tuple[str, str, Callable[[Observation], str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def hex_byte(value: int) -> str:
    return f"0x{value:02x}"


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def dominant_delta(values: list[int]) -> tuple[int, int]:
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[0]


def delta_histogram(values: list[int]) -> str:
    counts = Counter(values)
    return ";".join(f"{delta}:{counts[delta]}" for delta in sorted(counts))


def require_fixture(
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    key: tuple[str, str, str],
    issues: list[str],
    label: str,
) -> dict[str, object] | None:
    fixture = fixtures.get(key)
    if not fixture:
        issues.append(f"{label}:{key}:missing_fixture")
        return None
    expected = fixture.get("expected", b"")
    known_mask = fixture.get("known_mask", b"")
    if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
        issues.append(f"{label}:{key}:missing_fixture_bytes")
        return None
    return fixture


def known_count(mask: bytes) -> int:
    return sum(1 for value in mask if value)


def build_pairs(
    selected_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[Observation]]:
    sources_by_id = {row.get("source_id", ""): row for row in source_rows}
    pair_rows: list[dict[str, str]] = []
    byte_rows: list[dict[str, str]] = []
    observations: list[Observation] = []

    for pair_index, selected in enumerate(selected_rows):
        pair_id = f"p{pair_index:02d}"
        source_id = selected.get("source_id", "")
        source = sources_by_id.get(source_id)
        if not source:
            issues.append(f"{pair_id}:missing_source_row:{source_id}")
            continue

        source_fixture = require_fixture(fixtures, fixture_key(source), issues, f"{pair_id}:source")
        support_fixture = require_fixture(fixtures, fixture_key(selected), issues, f"{pair_id}:support")
        if not source_fixture or not support_fixture:
            continue

        source_expected = source_fixture["expected"]
        source_mask = source_fixture["known_mask"]
        support_expected = support_fixture["expected"]
        support_mask = support_fixture["known_mask"]
        if not isinstance(source_expected, bytes) or not isinstance(source_mask, bytes):
            continue
        if not isinstance(support_expected, bytes) or not isinstance(support_mask, bytes):
            continue

        source_start = int_value(source, "source_start")
        source_end = int_value(source, "source_end")
        support_start = int_value(selected, "start")
        support_end = int_value(selected, "end")
        source_data = source_expected[source_start:source_end]
        support_data = support_expected[support_start:support_end]
        source_known = source_mask[source_start:source_end]
        support_known = support_mask[support_start:support_end]
        if len(source_data) != 32:
            issues.append(f"{pair_id}:source_window_len_{len(source_data)}")
            continue
        if len(support_data) != 32:
            issues.append(f"{pair_id}:support_window_len_{len(support_data)}")
            continue

        deltas = [signed_delta(support_value, source_value) for support_value, source_value in zip(support_data, source_data)]
        abs_deltas = [abs(delta) for delta in deltas]
        top_delta, top_delta_count = dominant_delta(deltas)
        outlier_positions = [str(index) for index, delta in enumerate(deltas) if abs(delta) > 2]
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_id": source_id,
                "cluster_key": selected.get("cluster_key", ""),
                "source_rank": source.get("rank", ""),
                "source_pcx_name": source.get("pcx_name", ""),
                "source_frontier_id": source.get("frontier_id", ""),
                "source_start": str(source_start),
                "source_end": str(source_end),
                "support_rank": selected.get("rank", ""),
                "support_pcx_name": selected.get("pcx_name", ""),
                "support_frontier_id": selected.get("frontier_id", ""),
                "support_start": str(support_start),
                "support_end": str(support_end),
                "source_known_bytes": str(known_count(source_known)),
                "support_known_bytes": str(known_count(support_known)),
                "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
                "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
                "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
                "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
                "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
                "max_abs_delta": str(max(abs_deltas)),
                "top_delta": str(top_delta),
                "top_delta_count": str(top_delta_count),
                "outlier_positions": ";".join(outlier_positions),
                "delta_values": ";".join(str(delta) for delta in deltas),
                "support_hex": support_data.hex(),
                "source_hex": source_data.hex(),
            }
        )

        for byte_index, (support_value, source_value, delta, source_known_value, support_known_value) in enumerate(
            zip(support_data, source_data, deltas, source_known, support_known)
        ):
            byte_row = {
                "pair_id": pair_id,
                "source_id": source_id,
                "byte_index": str(byte_index),
                "support_value_hex": hex_byte(support_value),
                "source_value_hex": hex_byte(source_value),
                "signed_delta": str(delta),
                "abs_delta": str(abs(delta)),
                "in_le2": "1" if abs(delta) <= 2 else "0",
                "in_le4": "1" if abs(delta) <= 4 else "0",
                "source_known": "1" if source_known_value else "0",
                "support_known": "1" if support_known_value else "0",
            }
            byte_rows.append(byte_row)
            observations.append(
                {
                    "pair_id": pair_id,
                    "source_id": source_id,
                    "byte_index": byte_index,
                    "support_start": support_start,
                    "support_value": support_value,
                    "source_value": source_value,
                    "delta": delta,
                    "source_known": bool(source_known_value),
                    "support_known": bool(support_known_value),
                    "byte_row": byte_row,
                }
            )

    return pair_rows, byte_rows, observations


def build_position_rows(observations: list[Observation]) -> list[dict[str, str]]:
    by_position: dict[int, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_position[int(observation["byte_index"])].append(observation)

    rows: list[dict[str, str]] = []
    for byte_index in sorted(by_position):
        rows_at_pos = by_position[byte_index]
        deltas = [int(row["delta"]) for row in rows_at_pos]
        dominant, dominant_count = dominant_delta(deltas)
        rows.append(
            {
                "byte_index": str(byte_index),
                "observed_rows": str(len(rows_at_pos)),
                "delta_values": ";".join(str(delta) for delta in deltas),
                "dominant_delta": str(dominant),
                "dominant_count": str(dominant_count),
                "exact_consensus": "1" if dominant_count == len(rows_at_pos) else "0",
                "small_delta_le2_count": str(sum(1 for delta in deltas if abs(delta) <= 2)),
                "small_delta_le4_count": str(sum(1 for delta in deltas if abs(delta) <= 4)),
                "outlier_count": str(sum(1 for delta in deltas if abs(delta) > 2)),
                "support_values_hex": ";".join(hex_byte(int(row["support_value"])) for row in rows_at_pos),
                "source_values_hex": ";".join(hex_byte(int(row["source_value"])) for row in rows_at_pos),
            }
        )
    return rows


def selector_features() -> list[Feature]:
    return [
        ("global_delta", "compact", lambda row: "all"),
        ("position_mod2_delta", "compact", lambda row: f"m{int(row['byte_index']) % 2}"),
        ("position_mod4_delta", "compact", lambda row: f"m{int(row['byte_index']) % 4}"),
        ("position_mod8_delta", "compact", lambda row: f"m{int(row['byte_index']) % 8}"),
        ("position_mod16_delta", "compact", lambda row: f"m{int(row['byte_index']) % 16}"),
        ("position_delta", "compact", lambda row: f"p{int(row['byte_index']):02d}"),
        ("support_value_delta", "compact", lambda row: hex_byte(int(row["support_value"]))),
        (
            "support_value_pos_mod2_delta",
            "compact",
            lambda row: f"{hex_byte(int(row['support_value']))}|m{int(row['byte_index']) % 2}",
        ),
        (
            "support_value_pos_mod4_delta",
            "compact",
            lambda row: f"{hex_byte(int(row['support_value']))}|m{int(row['byte_index']) % 4}",
        ),
        (
            "support_value_pos_mod8_delta",
            "compact",
            lambda row: f"{hex_byte(int(row['support_value']))}|m{int(row['byte_index']) % 8}",
        ),
        ("pair_top_delta", "source_specific", lambda row: str(row["pair_id"])),
        (
            "source_id_pos_mod4_delta",
            "source_specific",
            lambda row: f"{row['source_id']}|m{int(row['byte_index']) % 4}",
        ),
        (
            "source_id_pos_mod8_delta",
            "source_specific",
            lambda row: f"{row['source_id']}|m{int(row['byte_index']) % 8}",
        ),
        (
            "source_id_pos_mod16_delta",
            "source_specific",
            lambda row: f"{row['source_id']}|m{int(row['byte_index']) % 16}",
        ),
    ]


def build_selector_rows(observations: list[Observation]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    observed_le2 = sum(1 for row in observations if abs(int(row["delta"])) <= 2)
    observed_le4 = sum(1 for row in observations if abs(int(row["delta"])) <= 4)
    total = len(observations)

    for selector_name, selector_scope, feature in selector_features():
        groups: dict[str, list[int]] = defaultdict(list)
        for observation in observations:
            groups[feature(observation)].append(int(observation["delta"]))

        table: dict[str, int] = {}
        preview: list[str] = []
        for key in sorted(groups):
            selected_delta, selected_count = dominant_delta(groups[key])
            table[key] = selected_delta
            if len(preview) < 32:
                preview.append(f"{key}:{selected_delta}/{selected_count}/{delta_histogram(groups[key])}")

        exact = sum(1 for observation in observations if int(observation["delta"]) == table[feature(observation)])
        predicted_deltas = [table[feature(observation)] for observation in observations]
        domain = sorted(set(table.values()))
        rows.append(
            {
                "selector_name": selector_name,
                "selector_scope": selector_scope,
                "key_count": str(len(table)),
                "exact_bytes": str(exact),
                "exact_ratio": ratio(exact, total),
                "predicted_delta_domain": ";".join(str(delta) for delta in domain),
                "predicted_delta_le2_bytes": str(sum(1 for delta in predicted_deltas if abs(delta) <= 2)),
                "observed_delta_le2_bytes": str(observed_le2),
                "observed_delta_le4_bytes": str(observed_le4),
                "table_preview": " | ".join(preview),
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("selector_scope", ""),
            -int_value(row, "exact_bytes"),
            int_value(row, "key_count"),
            row.get("selector_name", ""),
        )
    )
    return rows


def build_outlier_rows(byte_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {field: row.get(field, "") for field in OUTLIER_FIELDNAMES}
        for row in byte_rows
        if int_value(row, "abs_delta") > 2
    ]


def best_selector(selector_rows: list[dict[str, str]], scope: str) -> dict[str, str]:
    scoped = [row for row in selector_rows if row.get("selector_scope") == scope]
    return sorted(
        scoped,
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            int_value(row, "key_count"),
            row.get("selector_name", ""),
        ),
    )[0] if scoped else {}


def build_summary(
    pair_rows: list[dict[str, str]],
    observations: list[Observation],
    selector_rows: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    total = len(observations)
    le2 = sum(1 for row in observations if abs(int(row["delta"])) <= 2)
    le4 = sum(1 for row in observations if abs(int(row["delta"])) <= 4)
    outliers = total - le2
    max_abs = max([abs(int(row["delta"])) for row in observations] or [0])
    delta_domain = sorted({int(row["delta"]) for row in observations})
    pair_mins = [int_value(row, "small_delta_le2_bytes") for row in pair_rows]
    compact = best_selector(selector_rows, "compact")
    source_specific = best_selector(selector_rows, "source_specific")

    if total and le2 == total:
        verdict = "frontier80_prior_high_row_signed_delta_le2_selector_ready"
        next_probe = "promote signed-delta <=2 producer for dominant prior high-row cluster"
    elif total and le4 == total and le2 >= total - max(1, len(pair_rows) * 2):
        verdict = "frontier80_prior_high_row_signed_delta_le4_fallback_needed"
        next_probe = "isolate <=4 outlier producer for dominant prior high-row cluster"
    else:
        verdict = "frontier80_prior_high_row_signed_delta_selector_weak"
        next_probe = "expand signed-delta selector search beyond dominant prior high-row cluster"

    return {
        "scope": "total",
        "pair_rows": str(len(pair_rows)),
        "total_bytes": str(total),
        "signed_delta_le2_bytes": str(le2),
        "signed_delta_le2_ratio": ratio(le2, total),
        "signed_delta_le2_min": str(min(pair_mins) if pair_mins else 0),
        "signed_delta_le4_bytes": str(le4),
        "signed_delta_le4_ratio": ratio(le4, total),
        "outlier_bytes": str(outliers),
        "max_abs_delta": str(max_abs),
        "delta_domain": ";".join(str(delta) for delta in delta_domain),
        "best_compact_selector": compact.get("selector_name", ""),
        "best_compact_selector_exact_bytes": compact.get("exact_bytes", "0"),
        "best_compact_selector_exact_ratio": compact.get("exact_ratio", "0.000000"),
        "best_compact_selector_keys": compact.get("key_count", "0"),
        "best_source_specific_selector": source_specific.get("selector_name", ""),
        "best_source_specific_selector_exact_bytes": source_specific.get("exact_bytes", "0"),
        "best_source_specific_selector_exact_ratio": source_specific.get("exact_ratio", "0.000000"),
        "best_source_specific_selector_keys": source_specific.get("key_count", "0"),
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
    pair_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "pairs": pair_rows,
        "bytes": byte_rows,
        "positions": position_rows,
        "selectors": selector_rows,
        "outliers": outlier_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
            ("byte_deltas.csv", output_dir / "byte_deltas.csv"),
            ("positions.csv", output_dir / "positions.csv"),
            ("selector_candidates.csv", output_dir / "selector_candidates.csv"),
            ("outliers.csv", output_dir / "outliers.csv"),
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
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Profiles signed deltas between selected prior high-row support windows and source rows.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Signed delta &lt;=2</div><div class="value">{html.escape(summary['signed_delta_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Signed delta &lt;=4</div><div class="value">{html.escape(summary['signed_delta_le4_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Outliers</div><div class="value">{html.escape(summary['outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">Best compact selector</div><div class="value">{html.escape(summary['best_compact_selector_exact_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Pairs</h2>{render_table(pair_rows, PAIR_FIELDNAMES)}</section>
  <section class="panel"><h2>Outliers</h2>{render_table(outlier_rows, OUTLIER_FIELDNAMES)}</section>
  <section class="panel"><h2>Selector candidates</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Positions</h2>{render_table(position_rows, POSITION_FIELDNAMES)}</section>
  <section class="panel"><h2>Byte deltas</h2>{render_table(byte_rows, BYTE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="signed-delta-selector-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    selected_support_path: Path,
    sources_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    fixtures = load_fixtures(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    pair_rows, byte_rows, observations = build_pairs(
        read_csv(selected_support_path),
        read_csv(sources_path),
        fixtures,
        issues,
    )
    position_rows = build_position_rows(observations)
    selector_rows = build_selector_rows(observations)
    outlier_rows = build_outlier_rows(byte_rows)
    summary = build_summary(pair_rows, observations, selector_rows, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "pairs.csv", PAIR_FIELDNAMES, pair_rows)
    write_csv(output_dir / "byte_deltas.csv", BYTE_FIELDNAMES, byte_rows)
    write_csv(output_dir / "positions.csv", POSITION_FIELDNAMES, position_rows)
    write_csv(output_dir / "selector_candidates.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "outliers.csv", OUTLIER_FIELDNAMES, outlier_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, pair_rows, byte_rows, position_rows, selector_rows, outlier_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile signed-delta selectors for prior high-row support.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selected-support", type=Path, default=DEFAULT_SELECTED_SUPPORT)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Signed Delta Selector Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.selected_support,
        args.sources,
        args.manifest,
        args.clean_fixtures,
        title=args.title,
    )
    print(f"Signed delta <=2: {summary['signed_delta_le2_bytes']}/{summary['total_bytes']}")
    print(f"Signed delta <=4: {summary['signed_delta_le4_bytes']}/{summary['total_bytes']}")
    print(f"Outliers: {summary['outlier_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
