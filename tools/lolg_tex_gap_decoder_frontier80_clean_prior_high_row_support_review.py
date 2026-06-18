#!/usr/bin/env python3
"""Review known support for prior high rows feeding frontier80 width-32 deltas."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_transfer_guard_promoted_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "source_bytes",
    "exact_copy_nonself_matches",
    "exact_copy_known_nonself_matches",
    "best_known_family_small_delta_le2_min",
    "best_known_family_small_delta_le2_total",
    "best_known_family_exact_total",
    "best_known_family_source_known_min",
    "source_pairwise_small_delta_le2_min",
    "support_candidate_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SOURCE_FIELDNAMES = [
    "source_id",
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "source_start",
    "source_end",
    "known_bytes",
    "high_plateau_bytes",
    "zero_bytes",
    "distinct_bytes",
    "top_byte_hex",
    "top_byte_count",
    "head_hex",
    "tail_hex",
]

EXACT_FIELDNAMES = [
    "source_id",
    "match_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "known_bytes",
    "known_source",
    "self_match",
    "head_hex",
    "tail_hex",
]

SUPPORT_FIELDNAMES = [
    "source_id",
    "support_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "known_bytes",
    "high_plateau_bytes",
    "exact_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "mean_abs_delta",
    "top_delta",
    "top_delta_count",
    "self_match",
    "support_head_hex",
    "source_head_hex",
]

PAIRWISE_FIELDNAMES = [
    "left_source_id",
    "right_source_id",
    "same_bytes",
    "small_delta_le1_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "top_delta",
    "top_delta_count",
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


def source_id(row: dict[str, str]) -> str:
    return f"{row.get('target_id', target_id(row))}_srcm32"


def hex_byte(value: int | None) -> str:
    return f"0x{value:02x}" if value is not None else ""


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def is_high_plateau(value: int) -> bool:
    return 0x67 <= value <= 0x6E


def load_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    if not path_text:
        issues.append(f"{key}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key}:read_{label}_failed:{exc}")
        return b""


def load_fixtures(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[tuple[str, str, str], dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    fixtures: dict[tuple[str, str, str], dict[str, object]] = {}
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key, {})
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", key)
        known_mask = load_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key) if clean else b""
        fixtures[key] = {
            "manifest": manifest,
            "clean": clean,
            "expected": expected,
            "known_mask": known_mask,
        }
    return fixtures


def select_source_rows(
    run_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
) -> list[tuple[dict[str, str], bytes, bytes]]:
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    largest = max(int_value(row, "length") for row in nonzero)
    sources: list[tuple[dict[str, str], bytes, bytes]] = []
    for run in nonzero:
        if int_value(run, "length") != largest:
            continue
        key = fixture_key(run)
        fixture = fixtures.get(key, {})
        expected = fixture.get("expected", b"")
        known_mask = fixture.get("known_mask", b"")
        if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
            issues.append(f"{target_id(run)}:missing_fixture_bytes")
            continue
        start = int_value(run, "start")
        source_start = start - 32
        source_end = start
        if source_start < 0 or source_end > len(expected):
            issues.append(f"{target_id(run)}:source_m32_out_of_bounds")
            continue
        source = {**run, "target_id": target_id(run)}
        source["source_id"] = source_id(source)
        source["source_start"] = str(source_start)
        source["source_end"] = str(source_end)
        sources.append((source, expected[source_start:source_end], known_mask[source_start:source_end]))
    return sources


def build_source_rows(sources: list[tuple[dict[str, str], bytes, bytes]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source, data, mask in sources:
        top_byte, top_count = Counter(data).most_common(1)[0] if data else (None, 0)
        rows.append(
            {
                "source_id": source.get("source_id", ""),
                "target_id": source.get("target_id", ""),
                "rank": source.get("rank", ""),
                "archive": source.get("archive", ""),
                "archive_tag": source.get("archive_tag", ""),
                "pcx_name": source.get("pcx_name", ""),
                "frontier_id": source.get("frontier_id", ""),
                "span_index": source.get("span_index", ""),
                "run_index": source.get("run_index", ""),
                "source_start": source.get("source_start", ""),
                "source_end": source.get("source_end", ""),
                "known_bytes": str(sum(1 for value in mask if value)),
                "high_plateau_bytes": str(sum(1 for value in data if is_high_plateau(value))),
                "zero_bytes": str(data.count(0)),
                "distinct_bytes": str(len(set(data))),
                "top_byte_hex": hex_byte(top_byte),
                "top_byte_count": str(top_count),
                "head_hex": data[:16].hex(),
                "tail_hex": data[-16:].hex(),
            }
        )
    return rows


def find_exact_matches(
    sources: list[tuple[dict[str, str], bytes, bytes]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source, data, _mask in sources:
        if not data:
            continue
        source_key = fixture_key(source)
        source_start = int_value(source, "source_start")
        match_index = 0
        for key, fixture in fixtures.items():
            expected = fixture.get("expected", b"")
            known_mask = fixture.get("known_mask", b"")
            manifest = fixture.get("manifest", {})
            if not isinstance(expected, bytes) or not isinstance(known_mask, bytes) or not isinstance(manifest, dict):
                continue
            pos = expected.find(data)
            while pos >= 0:
                match_end = pos + len(data)
                known_bytes = sum(1 for value in known_mask[pos:match_end] if value)
                self_match = key == source_key and pos == source_start
                rows.append(
                    {
                        "source_id": source.get("source_id", ""),
                        "match_id": str(match_index),
                        "rank": manifest.get("rank", key[0]),
                        "archive": manifest.get("archive", ""),
                        "archive_tag": manifest.get("archive_tag", ""),
                        "pcx_name": manifest.get("pcx_name", key[1]),
                        "frontier_id": manifest.get("frontier_id", key[2]),
                        "start": str(pos),
                        "end": str(match_end),
                        "known_bytes": str(known_bytes),
                        "known_source": "1" if known_bytes == len(data) else "0",
                        "self_match": "1" if self_match else "0",
                        "head_hex": expected[pos : pos + 16].hex(),
                        "tail_hex": expected[match_end - 16 : match_end].hex(),
                    }
                )
                match_index += 1
                pos = expected.find(data, pos + 1)
    return rows


def score_support(source_data: bytes, support_data: bytes) -> dict[str, str]:
    deltas = [signed_delta(support, source) for support, source in zip(support_data, source_data)]
    abs_deltas = [abs(delta) for delta in deltas]
    top_delta, top_delta_count = Counter(deltas).most_common(1)[0]
    return {
        "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
        "small_delta_le1_bytes": str(sum(1 for delta in abs_deltas if delta <= 1)),
        "small_delta_le2_bytes": str(sum(1 for delta in abs_deltas if delta <= 2)),
        "small_delta_le4_bytes": str(sum(1 for delta in abs_deltas if delta <= 4)),
        "mean_abs_delta": f"{sum(abs_deltas) / len(abs_deltas):.6f}",
        "top_delta": str(top_delta),
        "top_delta_count": str(top_delta_count),
    }


def find_known_family_support(
    sources: list[tuple[dict[str, str], bytes, bytes]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    *,
    output_limit_per_source: int,
    min_known: int,
    min_small_delta: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source, source_data, _mask in sources:
        source_key = fixture_key(source)
        source_start = int_value(source, "source_start")
        source_rows: list[dict[str, str]] = []
        for key, fixture in fixtures.items():
            expected = fixture.get("expected", b"")
            known_mask = fixture.get("known_mask", b"")
            manifest = fixture.get("manifest", {})
            if not isinstance(expected, bytes) or not isinstance(known_mask, bytes) or not isinstance(manifest, dict):
                continue
            for pos in range(0, max(0, len(expected) - 31)):
                support = expected[pos : pos + 32]
                known_bytes = sum(1 for value in known_mask[pos : pos + 32] if value)
                high_bytes = sum(1 for value in support if is_high_plateau(value))
                self_match = key == source_key and pos == source_start
                if self_match:
                    continue
                if known_bytes < min_known or high_bytes < 24:
                    continue
                score = score_support(source_data, support)
                if int_value(score, "small_delta_le2_bytes") < min_small_delta:
                    continue
                source_rows.append(
                    {
                        "source_id": source.get("source_id", ""),
                        "support_id": "",
                        "rank": manifest.get("rank", key[0]),
                        "archive": manifest.get("archive", ""),
                        "archive_tag": manifest.get("archive_tag", ""),
                        "pcx_name": manifest.get("pcx_name", key[1]),
                        "frontier_id": manifest.get("frontier_id", key[2]),
                        "start": str(pos),
                        "end": str(pos + 32),
                        "known_bytes": str(known_bytes),
                        "high_plateau_bytes": str(high_bytes),
                        **score,
                        "self_match": "1" if self_match else "0",
                        "support_head_hex": support[:16].hex(),
                        "source_head_hex": source_data[:16].hex(),
                    }
                )
        source_rows.sort(
            key=lambda row: (
                -int_value(row, "small_delta_le2_bytes"),
                -int_value(row, "exact_bytes"),
                -int_value(row, "known_bytes"),
                int_value(row, "rank"),
                int_value(row, "start"),
            )
        )
        for index, row in enumerate(source_rows[:output_limit_per_source]):
            rows.append({**row, "support_id": str(index)})
    return rows


def build_pairwise_rows(sources: list[tuple[dict[str, str], bytes, bytes]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for left_index, (left, left_data, _left_mask) in enumerate(sources):
        for right, right_data, _right_mask in sources[left_index + 1 :]:
            score = score_support(right_data, left_data)
            rows.append(
                {
                    "left_source_id": left.get("source_id", ""),
                    "right_source_id": right.get("source_id", ""),
                    "same_bytes": score["exact_bytes"],
                    "small_delta_le1_bytes": score["small_delta_le1_bytes"],
                    "small_delta_le2_bytes": score["small_delta_le2_bytes"],
                    "small_delta_le4_bytes": score["small_delta_le4_bytes"],
                    "top_delta": score["top_delta"],
                    "top_delta_count": score["top_delta_count"],
                }
            )
    rows.sort(key=lambda row: (-int_value(row, "small_delta_le2_bytes"), row.get("left_source_id", "")))
    return rows


def best_support_by_source(support_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    best: dict[str, dict[str, str]] = {}
    for row in support_rows:
        source = row.get("source_id", "")
        if source and source not in best:
            best[source] = row
    return best


def build_summary(
    source_rows: list[dict[str, str]],
    exact_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    nonself_exact = [row for row in exact_rows if row.get("self_match") != "1"]
    known_exact = [row for row in nonself_exact if row.get("known_source") == "1"]
    best_support = best_support_by_source(support_rows)
    best_values = [int_value(row, "small_delta_le2_bytes") for row in best_support.values()]
    best_exact_values = [int_value(row, "exact_bytes") for row in best_support.values()]
    best_known_values = [int_value(row, "known_bytes") for row in best_support.values()]
    pairwise_values = [int_value(row, "small_delta_le2_bytes") for row in pairwise_rows]
    support_signal = len(best_support) == len(source_rows) and min(best_values or [0]) >= 30
    verdict = (
        "frontier80_prior_high_row_known_family_support"
        if support_signal
        else "frontier80_prior_high_row_no_known_family_support"
    )
    next_probe = (
        "derive compact selector for known high-row family plus signed delta <=2"
        if support_signal
        else "expand prior high-row support search beyond current clean fixtures"
    )
    return {
        "scope": "total",
        "source_rows": str(len(source_rows)),
        "source_bytes": str(sum(32 for _row in source_rows)),
        "exact_copy_nonself_matches": str(len(nonself_exact)),
        "exact_copy_known_nonself_matches": str(len(known_exact)),
        "best_known_family_small_delta_le2_min": str(min(best_values) if best_values else 0),
        "best_known_family_small_delta_le2_total": str(sum(best_values)),
        "best_known_family_exact_total": str(sum(best_exact_values)),
        "best_known_family_source_known_min": str(min(best_known_values) if best_known_values else 0),
        "source_pairwise_small_delta_le2_min": str(min(pairwise_values) if pairwise_values else 0),
        "support_candidate_rows": str(len(support_rows)),
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
    source_rows: list[dict[str, str]],
    exact_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "sources": source_rows,
        "exact": exact_rows,
        "support": support_rows,
        "pairwise": pairwise_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("sources.csv", output_dir / "sources.csv"),
            ("exact_matches.csv", output_dir / "exact_matches.csv"),
            ("known_family_support.csv", output_dir / "known_family_support.csv"),
            ("pairwise_sources.csv", output_dir / "pairwise_sources.csv"),
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
    <div class="sub">Reviews exact and small-delta support for prior high rows that feed frontier80 width-32 prefixes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Source rows</div><div class="value">{html.escape(summary['source_rows'])}</div></div>
    <div class="stat"><div class="label">Exact known copies</div><div class="value">{html.escape(summary['exact_copy_known_nonself_matches'])}</div></div>
    <div class="stat"><div class="label">Known family min</div><div class="value">{html.escape(summary['best_known_family_small_delta_le2_min'])}</div></div>
    <div class="stat"><div class="label">Pairwise min</div><div class="value">{html.escape(summary['source_pairwise_small_delta_le2_min'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Known family support</h2>{render_table(support_rows, SUPPORT_FIELDNAMES)}</section>
  <section class="panel"><h2>Sources</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</section>
  <section class="panel"><h2>Exact matches</h2>{render_table(exact_rows, EXACT_FIELDNAMES)}</section>
  <section class="panel"><h2>Pairwise sources</h2>{render_table(pairwise_rows, PAIRWISE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="prior-high-row-support-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    runs_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    output_limit_per_source: int,
    min_known: int,
    min_small_delta: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    fixtures = load_fixtures(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    sources = select_source_rows(read_csv(runs_path), fixtures, issues)
    source_rows = build_source_rows(sources)
    exact_rows = find_exact_matches(sources, fixtures)
    support_rows = find_known_family_support(
        sources,
        fixtures,
        output_limit_per_source=output_limit_per_source,
        min_known=min_known,
        min_small_delta=min_small_delta,
    )
    pairwise_rows = build_pairwise_rows(sources)
    summary = build_summary(source_rows, exact_rows, support_rows, pairwise_rows, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "sources.csv", SOURCE_FIELDNAMES, source_rows)
    write_csv(output_dir / "exact_matches.csv", EXACT_FIELDNAMES, exact_rows)
    write_csv(output_dir / "known_family_support.csv", SUPPORT_FIELDNAMES, support_rows)
    write_csv(output_dir / "pairwise_sources.csv", PAIRWISE_FIELDNAMES, pairwise_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, source_rows, exact_rows, support_rows, pairwise_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Review prior high-row support for frontier80 width-32 deltas.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--output-limit-per-source", type=int, default=48)
    parser.add_argument("--min-known", type=int, default=24)
    parser.add_argument("--min-small-delta", type=int, default=24)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Support Review",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.runs,
        args.manifest,
        args.clean_fixtures,
        output_limit_per_source=args.output_limit_per_source,
        min_known=args.min_known,
        min_small_delta=args.min_small_delta,
        title=args.title,
    )
    print(f"Source rows: {summary['source_rows']}")
    print(f"Exact known nonself: {summary['exact_copy_known_nonself_matches']}")
    print(f"Known family small-delta min: {summary['best_known_family_small_delta_le2_min']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
