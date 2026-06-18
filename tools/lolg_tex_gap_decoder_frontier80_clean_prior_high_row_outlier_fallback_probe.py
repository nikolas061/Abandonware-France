#!/usr/bin/env python3
"""Isolate fallback support starts for prior high-row signed-delta outliers."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_signed_delta_selector_probe import (
    dominant_delta,
    fixture_key,
    hex_byte,
    ratio,
    read_csv,
    require_fixture,
)
from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_support_review import load_fixtures, signed_delta
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_outlier_fallback_probe")
DEFAULT_SELECTED_SUPPORT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_compact_selector_probe/selected_support.csv"
)
DEFAULT_SUPPORT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/known_family_support.csv")
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "pair_rows",
    "total_bytes",
    "selected_signed_delta_le2_bytes",
    "selected_signed_delta_le4_bytes",
    "selected_outlier_bytes",
    "cluster_candidate_rows",
    "best_single_support_le2_bytes",
    "best_single_support_outlier_bytes",
    "oracle_byte_alt_le2_bytes",
    "oracle_byte_alt_le2_ratio",
    "resolved_outlier_bytes",
    "unresolved_outlier_bytes",
    "byte_local_start_switches",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

PAIR_FIELDNAMES = [
    "pair_id",
    "source_id",
    "cluster_key",
    "selected_start",
    "selected_le2_bytes",
    "selected_le4_bytes",
    "selected_outlier_positions",
    "best_single_start",
    "best_single_le2_bytes",
    "best_single_le4_bytes",
    "best_single_outlier_positions",
    "byte_local_le2_bytes",
    "byte_local_outlier_positions",
    "byte_local_switch_positions",
]

CANDIDATE_FIELDNAMES = [
    "pair_id",
    "source_id",
    "cluster_key",
    "support_id",
    "rank",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "known_bytes",
    "exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "outlier_count",
    "outlier_positions",
    "resolves_selected_outliers",
    "introduces_new_outliers",
    "top_delta",
    "top_delta_count",
    "delta_values",
    "support_hex",
]

OUTLIER_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selected_start",
    "selected_support_value_hex",
    "source_value_hex",
    "selected_delta",
    "source_known",
    "support_known",
    "alt_start_count",
    "alt_starts_le2",
    "best_alt_start",
    "best_alt_support_value_hex",
    "best_alt_delta",
    "best_alt_row_le2_bytes",
    "best_alt_row_outlier_positions",
]


def cluster_key(row: dict[str, str], bucket_size: int) -> str:
    bucket = (int_value(row, "start") // bucket_size) * bucket_size
    return (
        f"rank{row.get('rank', '')}|{row.get('archive_tag', '')}|{row.get('pcx_name', '')}|"
        f"frontier{row.get('frontier_id', '')}|start{bucket}"
    )


def load_window(
    row: dict[str, str],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
    label: str,
    start_field: str,
    end_field: str,
) -> tuple[bytes, bytes]:
    fixture = require_fixture(fixtures, fixture_key(row), issues, label)
    if not fixture:
        return b"", b""
    expected = fixture["expected"]
    known_mask = fixture["known_mask"]
    if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
        return b"", b""
    start = int_value(row, start_field)
    end = int_value(row, end_field)
    return expected[start:end], known_mask[start:end]


def score_support(source_data: bytes, support_data: bytes) -> dict[str, object]:
    deltas = [signed_delta(support_value, source_value) for support_value, source_value in zip(support_data, source_data)]
    abs_deltas = [abs(delta) for delta in deltas]
    top_delta, top_delta_count = dominant_delta(deltas)
    return {
        "deltas": deltas,
        "exact_bytes": sum(1 for delta in deltas if delta == 0),
        "small_delta_le2_bytes": sum(1 for delta in abs_deltas if delta <= 2),
        "small_delta_le4_bytes": sum(1 for delta in abs_deltas if delta <= 4),
        "outlier_positions": [index for index, delta in enumerate(deltas) if abs(delta) > 2],
        "top_delta": top_delta,
        "top_delta_count": top_delta_count,
    }


def outlier_positions_text(positions: list[int]) -> str:
    return ";".join(str(position) for position in positions)


def build_candidate_rows(
    selected_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
    *,
    bucket_size: int,
    max_support_id: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, object]]]:
    sources_by_id = {row.get("source_id", ""): row for row in source_rows}
    candidate_rows: list[dict[str, str]] = []
    pair_rows: list[dict[str, str]] = []
    outlier_rows: list[dict[str, str]] = []
    pair_contexts: list[dict[str, object]] = []

    for pair_index, selected in enumerate(selected_rows):
        pair_id = f"p{pair_index:02d}"
        source_id = selected.get("source_id", "")
        source = sources_by_id.get(source_id)
        if not source:
            issues.append(f"{pair_id}:missing_source_row:{source_id}")
            continue
        source_data, source_mask = load_window(source, fixtures, issues, f"{pair_id}:source", "source_start", "source_end")
        selected_support, selected_mask = load_window(selected, fixtures, issues, f"{pair_id}:selected", "start", "end")
        if len(source_data) != 32 or len(selected_support) != 32:
            issues.append(f"{pair_id}:bad_selected_window")
            continue

        selected_score = score_support(source_data, selected_support)
        selected_outliers = selected_score["outlier_positions"]
        if not isinstance(selected_outliers, list):
            selected_outliers = []
        target_cluster = selected.get("cluster_key", "") or cluster_key(selected, bucket_size)
        candidates = [
            row
            for row in support_rows
            if row.get("source_id", "") == source_id
            and int_value(row, "support_id") <= max_support_id
            and cluster_key(row, bucket_size) == target_cluster
        ]
        scored_candidates: list[dict[str, object]] = []
        for candidate in candidates:
            support_data, support_mask = load_window(candidate, fixtures, issues, f"{pair_id}:candidate", "start", "end")
            if len(support_data) != 32:
                issues.append(f"{pair_id}:candidate_{candidate.get('support_id', '')}:bad_window")
                continue
            score = score_support(source_data, support_data)
            candidate_outliers = score["outlier_positions"]
            if not isinstance(candidate_outliers, list):
                candidate_outliers = []
            deltas = score["deltas"]
            if not isinstance(deltas, list):
                deltas = []
            resolves = [
                position
                for position in selected_outliers
                if position < len(deltas) and abs(int(deltas[position])) <= 2
            ]
            introduces = [position for position in candidate_outliers if position not in selected_outliers]
            candidate_rows.append(
                {
                    "pair_id": pair_id,
                    "source_id": source_id,
                    "cluster_key": target_cluster,
                    "support_id": candidate.get("support_id", ""),
                    "rank": candidate.get("rank", ""),
                    "archive_tag": candidate.get("archive_tag", ""),
                    "pcx_name": candidate.get("pcx_name", ""),
                    "frontier_id": candidate.get("frontier_id", ""),
                    "start": candidate.get("start", ""),
                    "end": candidate.get("end", ""),
                    "known_bytes": candidate.get("known_bytes", ""),
                    "exact_bytes": str(score["exact_bytes"]),
                    "small_delta_le2_bytes": str(score["small_delta_le2_bytes"]),
                    "small_delta_le4_bytes": str(score["small_delta_le4_bytes"]),
                    "outlier_count": str(len(candidate_outliers)),
                    "outlier_positions": outlier_positions_text(candidate_outliers),
                    "resolves_selected_outliers": outlier_positions_text(resolves),
                    "introduces_new_outliers": outlier_positions_text(introduces),
                    "top_delta": str(score["top_delta"]),
                    "top_delta_count": str(score["top_delta_count"]),
                    "delta_values": ";".join(str(int(delta)) for delta in deltas),
                    "support_hex": support_data.hex(),
                }
            )
            scored_candidates.append(
                {
                    "row": candidate,
                    "support_data": support_data,
                    "support_mask": support_mask,
                    "score": score,
                }
            )

        best_single = sorted(
            scored_candidates,
            key=lambda item: (
                -int(item["score"]["small_delta_le2_bytes"]),
                -int(item["score"]["exact_bytes"]),
                -int_value(item["row"], "known_bytes"),
                int_value(item["row"], "start"),
            ),
        )[0] if scored_candidates else {}

        byte_local_outliers: list[int] = []
        byte_local_switches: list[int] = []
        for byte_index in range(32):
            selected_delta = int(selected_score["deltas"][byte_index])
            selected_ok = abs(selected_delta) <= 2
            alt_ok = False
            alt_uses_switch = False
            for item in scored_candidates:
                deltas = item["score"]["deltas"]
                if byte_index < len(deltas) and abs(int(deltas[byte_index])) <= 2:
                    alt_ok = True
                    alt_uses_switch = int_value(item["row"], "start") != int_value(selected, "start")
                    break
            if not selected_ok and alt_ok and alt_uses_switch:
                byte_local_switches.append(byte_index)
            if not (selected_ok or alt_ok):
                byte_local_outliers.append(byte_index)

        best_score = best_single.get("score", {}) if best_single else {}
        best_row = best_single.get("row", {}) if best_single else {}
        best_outliers = best_score.get("outlier_positions", []) if isinstance(best_score, dict) else []
        if not isinstance(best_outliers, list):
            best_outliers = []
        pair_rows.append(
            {
                "pair_id": pair_id,
                "source_id": source_id,
                "cluster_key": target_cluster,
                "selected_start": selected.get("start", ""),
                "selected_le2_bytes": str(selected_score["small_delta_le2_bytes"]),
                "selected_le4_bytes": str(selected_score["small_delta_le4_bytes"]),
                "selected_outlier_positions": outlier_positions_text(selected_outliers),
                "best_single_start": best_row.get("start", "") if isinstance(best_row, dict) else "",
                "best_single_le2_bytes": str(best_score.get("small_delta_le2_bytes", "0")) if isinstance(best_score, dict) else "0",
                "best_single_le4_bytes": str(best_score.get("small_delta_le4_bytes", "0")) if isinstance(best_score, dict) else "0",
                "best_single_outlier_positions": outlier_positions_text(best_outliers),
                "byte_local_le2_bytes": str(32 - len(byte_local_outliers)),
                "byte_local_outlier_positions": outlier_positions_text(byte_local_outliers),
                "byte_local_switch_positions": outlier_positions_text(byte_local_switches),
            }
        )

        for position in selected_outliers:
            alternatives: list[dict[str, object]] = []
            for item in scored_candidates:
                deltas = item["score"]["deltas"]
                if position >= len(deltas):
                    continue
                delta = int(deltas[position])
                if abs(delta) <= 2 and int_value(item["row"], "start") != int_value(selected, "start"):
                    alternatives.append(item)
            alternatives.sort(
                key=lambda item: (
                    abs(int(item["score"]["deltas"][position])),
                    -int(item["score"]["small_delta_le2_bytes"]),
                    int_value(item["row"], "start"),
                )
            )
            best_alt = alternatives[0] if alternatives else {}
            best_alt_row = best_alt.get("row", {}) if best_alt else {}
            best_alt_score = best_alt.get("score", {}) if best_alt else {}
            best_alt_support = best_alt.get("support_data", b"") if best_alt else b""
            if not isinstance(best_alt_support, bytes):
                best_alt_support = b""
            best_alt_delta = ""
            if isinstance(best_alt_score, dict) and position < len(best_alt_score.get("deltas", [])):
                best_alt_delta = str(best_alt_score["deltas"][position])
            best_alt_outliers = best_alt_score.get("outlier_positions", []) if isinstance(best_alt_score, dict) else []
            if not isinstance(best_alt_outliers, list):
                best_alt_outliers = []
            outlier_rows.append(
                {
                    "pair_id": pair_id,
                    "source_id": source_id,
                    "byte_index": str(position),
                    "selected_start": selected.get("start", ""),
                    "selected_support_value_hex": hex_byte(selected_support[position]),
                    "source_value_hex": hex_byte(source_data[position]),
                    "selected_delta": str(selected_score["deltas"][position]),
                    "source_known": "1" if source_mask[position] else "0",
                    "support_known": "1" if selected_mask[position] else "0",
                    "alt_start_count": str(len(alternatives)),
                    "alt_starts_le2": ";".join(str(item["row"].get("start", "")) for item in alternatives),
                    "best_alt_start": best_alt_row.get("start", "") if isinstance(best_alt_row, dict) else "",
                    "best_alt_support_value_hex": hex_byte(best_alt_support[position]) if best_alt_support else "",
                    "best_alt_delta": best_alt_delta,
                    "best_alt_row_le2_bytes": str(best_alt_score.get("small_delta_le2_bytes", "0")) if isinstance(best_alt_score, dict) else "0",
                    "best_alt_row_outlier_positions": outlier_positions_text(best_alt_outliers),
                }
            )

        pair_contexts.append(
            {
                "pair_id": pair_id,
                "selected_score": selected_score,
                "best_single": best_single,
                "byte_local_outliers": byte_local_outliers,
                "byte_local_switches": byte_local_switches,
                "candidate_count": len(scored_candidates),
            }
        )

    candidate_rows.sort(
        key=lambda row: (
            row.get("pair_id", ""),
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            int_value(row, "start"),
        )
    )
    return pair_rows, candidate_rows, outlier_rows, pair_contexts


def build_summary(
    pair_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    pair_contexts: list[dict[str, object]],
    *,
    issue_count: int,
) -> dict[str, str]:
    total = len(pair_rows) * 32
    selected_le2 = sum(int_value(row, "selected_le2_bytes") for row in pair_rows)
    selected_le4 = sum(int_value(row, "selected_le4_bytes") for row in pair_rows)
    selected_outliers = total - selected_le2
    best_single_le2 = sum(int_value(row, "best_single_le2_bytes") for row in pair_rows)
    best_single_outliers = total - best_single_le2
    byte_local_le2 = sum(int_value(row, "byte_local_le2_bytes") for row in pair_rows)
    unresolved = total - byte_local_le2
    resolved = selected_outliers - unresolved
    switches = sum(len(context.get("byte_local_switches", [])) for context in pair_contexts)
    candidate_counts = [int(context.get("candidate_count", 0)) for context in pair_contexts]

    if total and selected_outliers > 0 and unresolved == 0 and resolved == selected_outliers:
        verdict = "frontier80_prior_high_row_outliers_alt_start_resolved"
        next_probe = f"derive byte-local support-start selector for {switches} prior high-row outliers"
    elif total and selected_le4 == total:
        verdict = "frontier80_prior_high_row_outliers_need_delta_le4"
        next_probe = "derive signed-delta <=4 producer for prior high-row outliers"
    else:
        verdict = "frontier80_prior_high_row_outlier_fallback_weak"
        next_probe = "expand prior high-row outlier fallback search"

    return {
        "scope": "total",
        "pair_rows": str(len(pair_rows)),
        "total_bytes": str(total),
        "selected_signed_delta_le2_bytes": str(selected_le2),
        "selected_signed_delta_le4_bytes": str(selected_le4),
        "selected_outlier_bytes": str(selected_outliers),
        "cluster_candidate_rows": str(sum(candidate_counts) if candidate_counts else len(candidate_rows)),
        "best_single_support_le2_bytes": str(best_single_le2),
        "best_single_support_outlier_bytes": str(best_single_outliers),
        "oracle_byte_alt_le2_bytes": str(byte_local_le2),
        "oracle_byte_alt_le2_ratio": ratio(byte_local_le2, total),
        "resolved_outlier_bytes": str(resolved),
        "unresolved_outlier_bytes": str(unresolved),
        "byte_local_start_switches": str(switches),
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
    candidate_rows: list[dict[str, str]],
    outlier_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "pairs": pair_rows,
        "candidates": candidate_rows,
        "outliers": outlier_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
            ("cluster_candidates.csv", output_dir / "cluster_candidates.csv"),
            ("outlier_alternatives.csv", output_dir / "outlier_alternatives.csv"),
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
    <div class="sub">Tests whether local support-start switches resolve signed-delta outliers inside the dominant high-row cluster.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Selected &lt;=2</div><div class="value">{html.escape(summary['selected_signed_delta_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Byte-local &lt;=2</div><div class="value">{html.escape(summary['oracle_byte_alt_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Resolved outliers</div><div class="value">{html.escape(summary['resolved_outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">Switches</div><div class="value">{html.escape(summary['byte_local_start_switches'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Pairs</h2>{render_table(pair_rows, PAIR_FIELDNAMES)}</section>
  <section class="panel"><h2>Outlier alternatives</h2>{render_table(outlier_rows, OUTLIER_FIELDNAMES)}</section>
  <section class="panel"><h2>Cluster candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="outlier-fallback-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    selected_support_path: Path,
    support_path: Path,
    sources_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    bucket_size: int,
    max_support_id: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    fixtures = load_fixtures(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    pair_rows, candidate_rows, outlier_rows, pair_contexts = build_candidate_rows(
        read_csv(selected_support_path),
        read_csv(support_path),
        read_csv(sources_path),
        fixtures,
        issues,
        bucket_size=bucket_size,
        max_support_id=max_support_id,
    )
    summary = build_summary(pair_rows, candidate_rows, outlier_rows, pair_contexts, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "pairs.csv", PAIR_FIELDNAMES, pair_rows)
    write_csv(output_dir / "cluster_candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "outlier_alternatives.csv", OUTLIER_FIELDNAMES, outlier_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, pair_rows, candidate_rows, outlier_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe support-start fallback for high-row signed-delta outliers.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selected-support", type=Path, default=DEFAULT_SELECTED_SUPPORT)
    parser.add_argument("--support", type=Path, default=DEFAULT_SUPPORT)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--bucket-size", type=int, default=8)
    parser.add_argument("--max-support-id", type=int, default=15)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Outlier Fallback Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.selected_support,
        args.support,
        args.sources,
        args.manifest,
        args.clean_fixtures,
        bucket_size=args.bucket_size,
        max_support_id=args.max_support_id,
        title=args.title,
    )
    print(f"Selected <=2: {summary['selected_signed_delta_le2_bytes']}/{summary['total_bytes']}")
    print(f"Byte-local <=2: {summary['oracle_byte_alt_le2_bytes']}/{summary['total_bytes']}")
    print(f"Resolved outliers: {summary['resolved_outlier_bytes']}/{summary['selected_outlier_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
