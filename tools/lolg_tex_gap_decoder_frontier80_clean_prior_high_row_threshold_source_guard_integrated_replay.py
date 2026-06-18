#!/usr/bin/env python3
"""Integrate the threshold source guard into the high-row selector replay."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import lolg_tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_promoted_replay as guard_replay
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_integrated_replay")
DEFAULT_OBSERVATIONS = guard_replay.DEFAULT_OBSERVATIONS
DEFAULT_SWITCHES = guard_replay.DEFAULT_SWITCHES
DEFAULT_GUARD_PREDICTIONS = guard_replay.DEFAULT_GUARD_PREDICTIONS
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "source_rows",
    "outlier_bytes",
    "selector_promoted_rows",
    "selected_exact_bytes",
    "selected_le2_bytes",
    "chosen_exact_bytes",
    "chosen_le2_bytes",
    "exact_gain_bytes",
    "le2_gain_bytes",
    "base_known_selector_rows",
    "exact_promotable_rows",
    "blocked_false_switch_rows",
    "unresolved_outlier_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
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
    "issues",
]


def parse_hex_byte(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value:02x}"


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("pair_id", ""), row.get("source_id", ""), row.get("byte_index", "")


def source_fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str) -> bytes:
    return Path(path_text).read_bytes() if path_text else b""


def fixture_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {(row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")): row for row in rows}


def build_rows(
    *,
    observation_rows: list[dict[str, str]],
    switch_rows: list[dict[str, str]],
    guard_prediction_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    replay_summary, operations, decisions, replay_issues = guard_replay.build_replay(
        observation_rows,
        switch_rows,
        guard_prediction_rows,
    )
    operations_by_key = {row_key(row): row for row in operations if row.get("resolved_outlier") == "1"}
    sources_by_id = {row.get("source_id", ""): row for row in source_rows}
    fixtures_by_key = fixture_lookup(base_fixture_rows)
    loaded_fixtures: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}

    selector_rows: list[dict[str, str]] = []
    issues = list(replay_issues)
    selected_exact = 0
    selected_le2 = 0
    chosen_exact = 0
    chosen_le2 = 0
    selector_promoted = 0
    base_known_selector = 0
    exact_promotable = 0
    unresolved_outliers = 0

    for observation in observation_rows:
        key = row_key(observation)
        operation = operations_by_key.get(key)
        source = sources_by_id.get(observation.get("source_id", ""), {})
        row_issues: list[str] = []
        source_value = parse_hex_byte(observation.get("source_value_hex", ""))
        selected_value = parse_hex_byte(observation.get("selected_support_value_hex", ""))
        selected_delta = int_value(observation, "selected_delta")
        chosen_start = observation.get("selected_start", "")
        chosen_value = selected_value
        chosen_delta = selected_delta
        guard_reason = "selected"
        promoted = False

        if operation:
            promoted = True
            chosen_start = operation.get("chosen_start", chosen_start)
            chosen_value = parse_hex_byte(operation.get("chosen_support_value_hex", ""))
            chosen_delta = int_value(operation, "chosen_delta")
            guard_reason = operation.get("guard_reason", "")

        if source_value is None:
            row_issues.append("missing_source_value")
        if selected_value is None:
            row_issues.append("missing_selected_support_value")
        if chosen_value is None:
            row_issues.append("missing_chosen_support_value")

        selected_is_exact = selected_value is not None and source_value is not None and selected_value == source_value
        chosen_is_exact = chosen_value is not None and source_value is not None and chosen_value == source_value
        selected_is_le2 = abs(selected_delta) <= 2
        chosen_is_le2 = abs(chosen_delta) <= 2
        selected_exact += 1 if selected_is_exact else 0
        selected_le2 += 1 if selected_is_le2 else 0
        chosen_exact += 1 if chosen_is_exact else 0
        chosen_le2 += 1 if chosen_is_le2 else 0
        selector_promoted += 1 if promoted else 0
        exact_promotable += 1 if promoted and chosen_is_exact else 0
        if observation.get("selected_outlier") == "1" and not chosen_is_le2:
            unresolved_outliers += 1

        source_start = int_field(source, "source_start", int_field(source, "start", -1))
        byte_index = int_field(observation, "byte_index", -1)
        source_offset = source_start + byte_index if source_start >= 0 and byte_index >= 0 else -1
        base_known = False
        base_decoded_value: int | None = None
        if not source:
            row_issues.append("missing_source_row")
        else:
            fixture_key = source_fixture_key(source)
            fixture = fixtures_by_key.get(fixture_key, {})
            if not fixture:
                row_issues.append("missing_base_fixture")
            else:
                if fixture_key not in loaded_fixtures:
                    loaded_fixtures[fixture_key] = (
                        load_bytes(fixture.get("decoded_path", "")),
                        load_bytes(fixture.get("known_mask_path", "")),
                    )
                decoded, known_mask = loaded_fixtures[fixture_key]
                if source_offset < 0 or source_offset >= len(decoded) or source_offset >= len(known_mask):
                    row_issues.append("source_offset_out_of_range")
                else:
                    base_known = known_mask[source_offset] != 0
                    base_decoded_value = decoded[source_offset]
                    if promoted and base_known:
                        base_known_selector += 1

        if row_issues:
            issues.append(f"{key[0]}:{key[2]}:{';'.join(row_issues)}")

        selector_rows.append(
            {
                "pair_id": observation.get("pair_id", ""),
                "source_id": observation.get("source_id", ""),
                "archive": source.get("archive", ""),
                "archive_tag": source.get("archive_tag", ""),
                "pcx_name": source.get("pcx_name", ""),
                "frontier_id": source.get("frontier_id", ""),
                "source_start": str(source_start) if source_start >= 0 else "",
                "byte_index": observation.get("byte_index", ""),
                "source_offset": str(source_offset) if source_offset >= 0 else "",
                "source_value_hex": observation.get("source_value_hex", ""),
                "selected_start": observation.get("selected_start", ""),
                "selected_support_value_hex": observation.get("selected_support_value_hex", ""),
                "selected_delta": str(selected_delta),
                "selected_exact": "1" if selected_is_exact else "0",
                "selected_le2": "1" if selected_is_le2 else "0",
                "chosen_start": str(chosen_start),
                "chosen_support_value_hex": hex_byte(chosen_value),
                "chosen_delta": str(chosen_delta),
                "chosen_exact": "1" if chosen_is_exact else "0",
                "chosen_le2": "1" if chosen_is_le2 else "0",
                "selector_promoted": "1" if promoted else "0",
                "guard_reason": guard_reason,
                "base_known": "1" if base_known else "0",
                "base_decoded_value_hex": hex_byte(base_decoded_value),
                "issues": ";".join(row_issues),
            }
        )

    issue_rows = len(issues)
    clean = (
        replay_summary.get("review_verdict") == "frontier80_prior_high_row_threshold_source_guard_promoted_replay_ready"
        and chosen_le2 == len(observation_rows)
        and unresolved_outliers == 0
        and issue_rows == 0
    )
    summary = {
        "scope": "total",
        "total_bytes": str(len(observation_rows)),
        "source_rows": str(len(source_rows)),
        "outlier_bytes": replay_summary.get("outlier_bytes", "0"),
        "selector_promoted_rows": str(selector_promoted),
        "selected_exact_bytes": str(selected_exact),
        "selected_le2_bytes": str(selected_le2),
        "chosen_exact_bytes": str(chosen_exact),
        "chosen_le2_bytes": str(chosen_le2),
        "exact_gain_bytes": str(chosen_exact - selected_exact),
        "le2_gain_bytes": str(chosen_le2 - selected_le2),
        "base_known_selector_rows": str(base_known_selector),
        "exact_promotable_rows": str(exact_promotable),
        "blocked_false_switch_rows": replay_summary.get("blocked_false_switch_rows", "0"),
        "unresolved_outlier_rows": str(unresolved_outliers),
        "issue_rows": str(issue_rows),
        "review_verdict": (
            "frontier80_prior_high_row_threshold_source_guard_integrated_replay_ready"
            if clean
            else "frontier80_prior_high_row_threshold_source_guard_integrated_replay_weak"
        ),
        "next_probe": (
            "derive exact residual correction for threshold-guarded high-row selector"
            if clean
            else "review threshold-guarded high-row selector integration issues"
        ),
    }
    return summary, selector_rows, decisions, issues


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
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "selector_rows": selector_rows, "decisions": decision_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("selector_rows.csv", output_dir / "selector_rows.csv"),
            ("guard_decisions.csv", output_dir / "guard_decisions.csv"),
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
    <div class="sub">Integrates the threshold source guard as the high-row selector replay boundary.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Selector promoted</div><div class="value ok">{summary['selector_promoted_rows']}/{summary['outlier_bytes']}</div></div>
    <div class="stat"><div class="label">Chosen <=2</div><div class="value">{summary['chosen_le2_bytes']}/{summary['total_bytes']}</div></div>
    <div class="stat"><div class="label"><=2 gain</div><div class="value ok">+{summary['le2_gain_bytes']}</div></div>
    <div class="stat"><div class="label">Exact gain</div><div class="value">{summary['exact_gain_bytes']}</div></div>
    <div class="stat"><div class="label">Base-known selector rows</div><div class="value">{summary['base_known_selector_rows']}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Selector rows</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard decisions</h2>{render_table(decision_rows, guard_replay.DECISION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="threshold-source-guard-integrated-replay-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    observations_path: Path,
    switches_path: Path,
    guard_predictions_path: Path,
    sources_path: Path,
    base_fixtures_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, selector_rows, decisions, issues = build_rows(
        observation_rows=guard_replay.read_csv(observations_path),
        switch_rows=guard_replay.read_csv(switches_path),
        guard_prediction_rows=guard_replay.read_csv(guard_predictions_path),
        source_rows=guard_replay.read_csv(sources_path),
        base_fixture_rows=guard_replay.read_csv(base_fixtures_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "selector_rows.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "guard_decisions.csv", guard_replay.DECISION_FIELDNAMES, decisions)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, selector_rows, decisions, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    parser.add_argument("--switches", type=Path, default=DEFAULT_SWITCHES)
    parser.add_argument("--guard-predictions", type=Path, default=DEFAULT_GUARD_PREDICTIONS)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Threshold Source Guard Integrated Replay",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.observations,
        args.switches,
        args.guard_predictions,
        args.sources,
        args.base_fixtures,
        title=args.title,
    )
    print(f"Selector promoted: {summary['selector_promoted_rows']}/{summary['outlier_bytes']}")
    print(f"Chosen <=2: {summary['chosen_le2_bytes']}/{summary['total_bytes']}")
    print(f"<=2 gain: {summary['le2_gain_bytes']}")
    print(f"Exact gain: {summary['exact_gain_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
