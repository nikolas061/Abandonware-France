#!/usr/bin/env python3
"""Probe width-32 high-prefix rows against nearby signed-delta sources."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_width32_delta_neighborhood_probe")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_transfer_guard_promoted_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_prefix_bytes",
    "best_shared_relative_offset",
    "best_shared_small_delta_le2_bytes",
    "best_shared_small_delta_le2_ratio",
    "best_shared_exact_bytes",
    "best_shared_source_known_min",
    "best_per_target_small_delta_le2_min",
    "candidate_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "target_start",
    "source_start",
    "relative_offset",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "top_delta",
    "top_delta_count",
    "source_known_bytes",
    "source_high_plateau_bytes",
    "source_zero_bytes",
    "source_head_hex",
    "target_head_hex",
]

RELATIVE_FIELDNAMES = [
    "relative_offset",
    "target_rows",
    "small_delta_le2_bytes",
    "small_delta_le2_ratio",
    "exact_bytes",
    "source_known_min",
    "source_known_total",
    "top_delta_signature",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def is_high_plateau(value: int) -> bool:
    return 0x67 <= value <= 0x6E


def load_targets(
    run_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> list[tuple[dict[str, str], bytes, bytes]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    largest = max(int_value(row, "length") for row in nonzero)
    targets: list[tuple[dict[str, str], bytes, bytes]] = []
    for row in nonzero:
        if int_value(row, "length") != largest:
            continue
        key = fixture_key(row)
        manifest = manifest_by_key.get(key)
        clean = clean_by_key.get(key)
        if not manifest:
            issues.append(f"{target_id(row)}:missing_manifest_row")
            continue
        if not clean:
            issues.append(f"{target_id(row)}:missing_clean_fixture_row")
            continue
        try:
            expected = Path(manifest.get("expected_gap_path", "")).read_bytes()
            known_mask = Path(clean.get("known_mask_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"{target_id(row)}:read_fixture_failed:{exc}")
            continue
        targets.append(({**row, "target_id": target_id(row)}, expected, known_mask))
    return targets


def score_candidate(
    target: dict[str, str],
    expected: bytes,
    known_mask: bytes,
    relative_offset: int,
) -> dict[str, str] | None:
    target_start = int_value(target, "start")
    source_start = target_start + relative_offset
    if source_start < 0 or source_start + 32 > len(expected):
        return None
    if max(source_start, target_start) < min(source_start + 32, target_start + 32):
        return None
    source = expected[source_start : source_start + 32]
    target_prefix = expected[target_start : target_start + 32]
    if len(target_prefix) != 32:
        return None
    deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, target_prefix)]
    abs_deltas = [abs(delta) for delta in deltas]
    top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
    return {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "target_start": str(target_start),
        "source_start": str(source_start),
        "relative_offset": str(relative_offset),
        "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
        "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
        "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
        "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
        "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
        "top_delta": str(top_delta),
        "top_delta_count": str(top_delta_count),
        "source_known_bytes": str(sum(1 for value in known_mask[source_start : source_start + 32] if value)),
        "source_high_plateau_bytes": str(sum(1 for value in source if is_high_plateau(value))),
        "source_zero_bytes": str(source.count(0)),
        "source_head_hex": source[:16].hex(),
        "target_head_hex": target_prefix[:16].hex(),
    }


def build_candidate_rows(
    targets: list[tuple[dict[str, str], bytes, bytes]],
    *,
    max_relative: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target, expected, known_mask in targets:
        for relative_offset in range(-max_relative, max_relative + 1):
            candidate = score_candidate(target, expected, known_mask, relative_offset)
            if candidate and int_value(candidate, "small_delta_le2_bytes") >= 24:
                rows.append(candidate)
    rows.sort(
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "source_known_bytes"),
            abs(int_value(row, "relative_offset")),
            row.get("target_id", ""),
        )
    )
    return rows


def build_relative_rows(candidate_rows: list[dict[str, str]], target_count: int) -> list[dict[str, str]]:
    by_relative: dict[int, list[dict[str, str]]] = {}
    for row in candidate_rows:
        by_relative.setdefault(int_value(row, "relative_offset"), []).append(row)
    rows: list[dict[str, str]] = []
    for relative_offset, rel_rows in by_relative.items():
        if len(rel_rows) != target_count:
            continue
        small_total = sum(int_value(row, "small_delta_le2_bytes") for row in rel_rows)
        exact_total = sum(int_value(row, "exact_bytes") for row in rel_rows)
        known_values = [int_value(row, "source_known_bytes") for row in rel_rows]
        top_signature = "|".join(f"{row.get('top_delta', '')}:{row.get('top_delta_count', '')}" for row in rel_rows)
        rows.append(
            {
                "relative_offset": str(relative_offset),
                "target_rows": str(len(rel_rows)),
                "small_delta_le2_bytes": str(small_total),
                "small_delta_le2_ratio": f"{small_total / (target_count * 32):.6f}",
                "exact_bytes": str(exact_total),
                "source_known_min": str(min(known_values) if known_values else 0),
                "source_known_total": str(sum(known_values)),
                "top_delta_signature": top_signature,
            }
        )
    rows.sort(
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            abs(int_value(row, "relative_offset")),
        )
    )
    return rows


def build_summary(
    candidate_rows: list[dict[str, str]],
    relative_rows: list[dict[str, str]],
    *,
    target_count: int,
    issue_count: int,
) -> dict[str, str]:
    best_shared = relative_rows[0] if relative_rows else {}
    best_per_target: dict[str, int] = {}
    for row in candidate_rows:
        tid = row.get("target_id", "")
        best_per_target[tid] = max(best_per_target.get(tid, 0), int_value(row, "small_delta_le2_bytes"))
    shared_signal = (
        best_shared.get("relative_offset") == "-32"
        and int_value(best_shared, "small_delta_le2_bytes") >= target_count * 30
    )
    verdict = (
        "frontier80_clean_width32_previous_row_delta_signal"
        if shared_signal
        else "frontier80_clean_width32_delta_neighborhood_profile"
    )
    next_probe = (
        "derive non-oracle producer for prior high-row window feeding -32 small-delta signal"
        if shared_signal
        else "expand width32 delta-neighborhood sources for frontier80 high-prefix rows"
    )
    return {
        "scope": "total",
        "target_runs": str(target_count),
        "target_prefix_bytes": str(target_count * 32),
        "best_shared_relative_offset": best_shared.get("relative_offset", ""),
        "best_shared_small_delta_le2_bytes": best_shared.get("small_delta_le2_bytes", "0"),
        "best_shared_small_delta_le2_ratio": best_shared.get("small_delta_le2_ratio", "0.000000"),
        "best_shared_exact_bytes": best_shared.get("exact_bytes", "0"),
        "best_shared_source_known_min": best_shared.get("source_known_min", "0"),
        "best_per_target_small_delta_le2_min": str(min(best_per_target.values()) if best_per_target else 0),
        "candidate_rows": str(len(candidate_rows)),
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
    relative_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "relative": relative_rows, "candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("relative_offsets.csv", output_dir / "relative_offsets.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
    <div class="sub">Scores width-32 high-prefix rows against nearby signed-delta source windows.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best shared relative</div><div class="value">{html.escape(summary['best_shared_relative_offset'])}</div></div>
    <div class="stat"><div class="label">Small delta <=2</div><div class="value">{html.escape(summary['best_shared_small_delta_le2_bytes'])}</div></div>
    <div class="stat"><div class="label">Exact bytes</div><div class="value">{html.escape(summary['best_shared_exact_bytes'])}</div></div>
    <div class="stat"><div class="label">Known source min</div><div class="value">{html.escape(summary['best_shared_source_known_min'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Relative offsets</h2>{render_table(relative_rows, RELATIVE_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="delta-neighborhood-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    runs_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    max_relative: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = load_targets(read_csv(runs_path), read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    candidate_rows = build_candidate_rows(targets, max_relative=max_relative)
    relative_rows = build_relative_rows(candidate_rows, len(targets))
    summary = build_summary(candidate_rows, relative_rows, target_count=len(targets), issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "relative_offsets.csv", RELATIVE_FIELDNAMES, relative_rows)
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, relative_rows, candidate_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe width-32 delta-neighborhood sources for .tex high prefixes.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--max-relative", type=int, default=128)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Width32 Delta Neighborhood Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.runs,
        args.manifest,
        args.clean_fixtures,
        max_relative=args.max_relative,
        title=args.title,
    )
    print(f"Best shared relative: {summary['best_shared_relative_offset']}")
    print(f"Best shared small delta <=2: {summary['best_shared_small_delta_le2_bytes']}")
    print(f"Best shared source known min: {summary['best_shared_source_known_min']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
