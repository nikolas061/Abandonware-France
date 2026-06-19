#!/usr/bin/env python3
"""Replay palette-walk values from seeds, small deltas, and the low-tail guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_value_producer_probe"
)
DEFAULT_REPLAY_ROWS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_replay_probe/replay_rows.csv"
)
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/candidates.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "candidate_bytes",
    "palette_bytes",
    "terminal_bytes",
    "seed_value_rows",
    "replay_delta_rows",
    "small_delta_rows",
    "guard_delta_rows",
    "large_delta_rows",
    "produced_palette_bytes",
    "exact_palette_bytes",
    "run_exact_rows",
    "drift_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

RUN_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "palette_bytes",
    "terminal_bytes",
    "seed_value_hex",
    "transition_rows",
    "small_delta_rows",
    "guard_delta_rows",
    "large_delta_rows",
    "produced_palette_bytes",
    "exact_palette_bytes",
    "issue_rows",
    "verdict",
]

VALUE_FIELDNAMES = [
    "target_id",
    "palette_index",
    "run_offset",
    "absolute",
    "row",
    "col",
    "mode",
    "source_class",
    "expected_value_hex",
    "produced_value_hex",
    "from_value_hex",
    "replay_delta",
    "guard_key",
    "exact",
    "issue",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_hex_byte(value: str) -> int | None:
    text = value.strip().lower()
    if not text:
        return None
    if text.startswith("0x"):
        text = text[2:]
    try:
        return int(text, 16)
    except ValueError:
        return None


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"{value & 0xFF:02x}"


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def grouped_replay_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("target_id", "")].append(row)
    for target_rows in grouped.values():
        target_rows.sort(key=lambda row: int_value(row, "transition_index"))
    return dict(grouped)


def candidate_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("target_id", ""): row for row in rows}


def build_value_rows_for_target(
    target_id: str,
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    value_rows: list[dict[str, str]] = []
    counters = {
        "small_delta_rows": 0,
        "guard_delta_rows": 0,
        "large_delta_rows": 0,
        "exact_palette_bytes": 0,
        "drift_rows": 0,
        "issue_rows": 0,
    }
    if not rows:
        return value_rows, counters

    first = rows[0]
    current = parse_hex_byte(first.get("from_value_hex", ""))
    seed_issue = "" if current is not None else "missing_seed_value"
    value_rows.append(
        {
            "target_id": target_id,
            "palette_index": "0",
            "run_offset": first.get("from_run_offset", ""),
            "absolute": first.get("from_abs", ""),
            "row": first.get("from_row", ""),
            "col": first.get("from_col", ""),
            "mode": first.get("from_mode", ""),
            "source_class": "seed_value",
            "expected_value_hex": first.get("from_value_hex", ""),
            "produced_value_hex": hex_byte(current),
            "from_value_hex": "",
            "replay_delta": "",
            "guard_key": "",
            "exact": "1" if not seed_issue else "0",
            "issue": seed_issue,
        }
    )
    if seed_issue:
        counters["issue_rows"] += 1
    else:
        counters["exact_palette_bytes"] += 1

    last_transition = -1
    for row in rows:
        row_issues: list[str] = []
        transition_index = int_value(row, "transition_index")
        if transition_index != last_transition + 1:
            row_issues.append("transition_index_gap")
        last_transition = transition_index

        expected_from = parse_hex_byte(row.get("from_value_hex", ""))
        expected_to = parse_hex_byte(row.get("to_value_hex", ""))
        replay_delta_text = row.get("replay_delta", "")
        try:
            replay_delta = int(replay_delta_text)
        except ValueError:
            replay_delta = None
            row_issues.append("missing_replay_delta")

        if current is None:
            row_issues.append("missing_current_value")
        elif expected_from is None:
            row_issues.append("missing_expected_from")
        elif current != expected_from:
            row_issues.append("source_value_drift")
            counters["drift_rows"] += 1

        produced = (current + replay_delta) & 0xFF if current is not None and replay_delta is not None else None
        if expected_to is None:
            row_issues.append("missing_expected_to")
        if produced is not None and expected_to is not None and produced != expected_to:
            row_issues.append("produced_value_mismatch")

        source_class = row.get("selected_class", "")
        counters["small_delta_rows"] += 1 if source_class == "base_small_delta" else 0
        counters["guard_delta_rows"] += 1 if source_class == "low_tail_anchor_guard" else 0
        counters["large_delta_rows"] += 1 if row.get("large_delta") == "1" else 0

        exact = produced is not None and expected_to is not None and produced == expected_to and not row_issues
        value_rows.append(
            {
                "target_id": target_id,
                "palette_index": str(transition_index + 1),
                "run_offset": row.get("to_run_offset", ""),
                "absolute": row.get("to_abs", ""),
                "row": row.get("to_row", ""),
                "col": row.get("to_col", ""),
                "mode": row.get("to_mode", ""),
                "source_class": source_class,
                "expected_value_hex": row.get("to_value_hex", ""),
                "produced_value_hex": hex_byte(produced),
                "from_value_hex": row.get("from_value_hex", ""),
                "replay_delta": replay_delta_text,
                "guard_key": row.get("guard_key", ""),
                "exact": "1" if exact else "0",
                "issue": ";".join(row_issues),
            }
        )
        if row_issues:
            counters["issue_rows"] += 1
        if exact:
            counters["exact_palette_bytes"] += 1
        current = produced

    return value_rows, counters


def build_rows(
    replay_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    grouped_rows = grouped_replay_rows(replay_rows)
    candidates = candidate_lookup(candidate_rows)
    all_value_rows: list[dict[str, str]] = []
    run_rows: list[dict[str, str]] = []

    total_small = 0
    total_guard = 0
    total_large = 0
    total_exact = 0
    total_drift = 0
    total_issues = 0
    run_exact = 0

    for target_id in sorted(grouped_rows):
        target_rows = grouped_rows[target_id]
        candidate = candidates.get(target_id, {})
        value_rows, counters = build_value_rows_for_target(target_id, target_rows)
        all_value_rows.extend(value_rows)
        exact_rows = sum(1 for row in value_rows if row.get("exact") == "1")
        issue_rows = counters["issue_rows"]
        produced_rows = len(value_rows)
        expected_palette = int_field(candidate, "palette_bytes", produced_rows)
        if candidate and produced_rows != expected_palette:
            issue_rows += 1
        verdict = "value_producer_exact" if issue_rows == 0 and exact_rows == produced_rows else "value_producer_issues"
        run_exact += 1 if verdict == "value_producer_exact" else 0
        total_small += counters["small_delta_rows"]
        total_guard += counters["guard_delta_rows"]
        total_large += counters["large_delta_rows"]
        total_exact += exact_rows
        total_drift += counters["drift_rows"]
        total_issues += issue_rows

        run_rows.append(
            {
                "target_id": target_id,
                "rank": candidate.get("rank", ""),
                "archive": candidate.get("archive", ""),
                "archive_tag": candidate.get("archive_tag", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "start": candidate.get("start", ""),
                "end": candidate.get("end", ""),
                "length": candidate.get("length", ""),
                "palette_bytes": candidate.get("palette_bytes", str(produced_rows)),
                "terminal_bytes": candidate.get("terminal_bytes", "0"),
                "seed_value_hex": value_rows[0].get("produced_value_hex", "") if value_rows else "",
                "transition_rows": str(len(target_rows)),
                "small_delta_rows": str(counters["small_delta_rows"]),
                "guard_delta_rows": str(counters["guard_delta_rows"]),
                "large_delta_rows": str(counters["large_delta_rows"]),
                "produced_palette_bytes": str(produced_rows),
                "exact_palette_bytes": str(exact_rows),
                "issue_rows": str(issue_rows),
                "verdict": verdict,
            }
        )

    candidate_bytes = sum(int_value(row, "length") for row in candidate_rows if row.get("target_id", "") in grouped_rows)
    palette_bytes = sum(int_value(row, "palette_bytes") for row in candidate_rows if row.get("target_id", "") in grouped_rows)
    terminal_bytes = sum(int_value(row, "terminal_bytes") for row in candidate_rows if row.get("target_id", "") in grouped_rows)
    produced_palette = len(all_value_rows)
    if palette_bytes == 0:
        palette_bytes = produced_palette
    if produced_palette != palette_bytes:
        total_issues += 1

    if total_issues == 0 and total_exact == palette_bytes and run_exact == len(run_rows):
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_guard_value_producer_ready"
        next_probe = "promote palette-walk value producer into Frontier80 fixture replay"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_low_tail_guard_value_producer_issues"
        next_probe = "review palette-walk value producer mismatches before fixture replay"

    summary = {
        "scope": "total",
        "target_runs": str(len(run_rows)),
        "candidate_bytes": str(candidate_bytes),
        "palette_bytes": str(palette_bytes),
        "terminal_bytes": str(terminal_bytes),
        "seed_value_rows": str(len(run_rows)),
        "replay_delta_rows": str(len(replay_rows)),
        "small_delta_rows": str(total_small),
        "guard_delta_rows": str(total_guard),
        "large_delta_rows": str(total_large),
        "produced_palette_bytes": str(produced_palette),
        "exact_palette_bytes": str(total_exact),
        "run_exact_rows": str(run_exact),
        "drift_rows": str(total_drift),
        "issue_rows": str(total_issues),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    return summary, run_rows, all_value_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 180) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    run_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "runs": run_rows, "values": value_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("runs.csv", output_dir / "runs.csv"),
            ("value_rows.csv", output_dir / "value_rows.csv"),
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
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
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
.warn {{ color: var(--warn); }}
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
    <div class="sub">Replays palette values from per-run seeds, small deltas, and the low-tail guard deltas.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Exact palette</div><div class="value">{html.escape(summary['exact_palette_bytes'])}/{html.escape(summary['palette_bytes'])}</div></div>
    <div class="stat"><div class="label">Runs exact</div><div class="value">{html.escape(summary['run_exact_rows'])}/{html.escape(summary['target_runs'])}</div></div>
    <div class="stat"><div class="label">Guard deltas</div><div class="value">{html.escape(summary['guard_delta_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value warn">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Runs</h2>{render_table(run_rows, RUN_FIELDNAMES)}</section>
  <section class="panel"><h2>Values</h2>{render_table(value_rows, VALUE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-low-tail-value-producer-data">{data_json}</script>
</body>
</html>
"""


def write_report(output_dir: Path, replay_rows_path: Path, candidates_path: Path, *, title: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    try:
        replay_rows = read_csv(replay_rows_path)
    except OSError as exc:
        issues.append(f"read_replay_rows_failed:{exc}")
        replay_rows = []
    try:
        candidate_rows = read_csv(candidates_path)
    except OSError as exc:
        issues.append(f"read_candidates_failed:{exc}")
        candidate_rows = []

    summary, run_rows, value_rows = build_rows(replay_rows, candidate_rows)
    if issues:
        summary["issue_rows"] = str(int_value(summary, "issue_rows") + len(issues))
        if summary["review_verdict"] == "frontier80_clean_nonzero_palette_walk_low_tail_guard_value_producer_ready":
            summary["review_verdict"] = "frontier80_clean_nonzero_palette_walk_low_tail_guard_value_producer_issues"
            summary["next_probe"] = "review palette-walk value producer inputs before fixture replay"

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "runs.csv", RUN_FIELDNAMES, run_rows)
    write_csv(output_dir / "value_rows.csv", VALUE_FIELDNAMES, value_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, run_rows, value_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay palette-walk values from low-tail guarded deltas.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replay-rows", type=Path, default=DEFAULT_REPLAY_ROWS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Low-Tail Guard Value Producer Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.replay_rows, args.candidates, title=args.title)
    print(f"Exact palette: {summary['exact_palette_bytes']}/{summary['palette_bytes']}")
    print(f"Runs exact: {summary['run_exact_rows']}/{summary['target_runs']}")
    print(f"Guard deltas: {summary['guard_delta_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
