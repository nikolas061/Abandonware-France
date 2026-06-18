#!/usr/bin/env python3
"""Audit source-byte prerequisites for the high-row selected-delta split."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

from lolg_tex_gap_decoder_frontier80_clean_prior_high_row_support_review import (
    fixture_key,
    load_fixtures,
    signed_delta,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_source_byte_prereq_probe")
DEFAULT_SWITCHES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_source_split_probe/"
    "source_split_switch_rows.csv"
)
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")
DEFAULT_SUPPORT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/known_family_support.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "switch_rows",
    "source_unknown_switch_rows",
    "target_source_unknown_rows",
    "false_source_unknown_rows",
    "prerequisite_offsets",
    "expected_value_domain",
    "current_known_rows",
    "current_decoded_exact_rows",
    "same_fixture_known_value_hit_rows",
    "same_source_support_candidate_rows",
    "source_support_exact_candidate_rows",
    "source_support_threshold_candidate_rows",
    "all_unknown_have_exact_candidate",
    "all_unknown_have_threshold_candidate",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

PREREQ_FIELDNAMES = [
    "pair_id",
    "source_id",
    "source_rank",
    "source_pcx_name",
    "source_frontier_id",
    "source_start",
    "byte_index",
    "absolute_offset",
    "selected_support_value_hex",
    "expected_source_value_hex",
    "switch_source_value_hex",
    "current_decoded_value_hex",
    "current_known",
    "decoded_matches_expected",
    "selected_delta",
    "selected_delta_abs_gt2",
    "selected_outlier",
    "false_switch",
    "nearest_known_left_offset",
    "nearest_known_left_value_hex",
    "nearest_known_right_offset",
    "nearest_known_right_value_hex",
    "local_expected_hex",
    "local_known_mask",
    "local_decoded_hex",
    "same_fixture_known_value_count",
    "same_fixture_known_value_offsets",
    "same_source_support_candidate_count",
    "source_support_exact_candidate_count",
    "source_support_threshold_candidate_count",
    "exact_support_ids",
    "threshold_support_ids",
]

SUPPORT_CANDIDATE_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selected_support_value_hex",
    "expected_source_value_hex",
    "selected_delta_abs_gt2",
    "support_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "start",
    "absolute_support_offset",
    "candidate_value_hex",
    "candidate_known",
    "candidate_delta",
    "candidate_abs_gt2",
    "matches_expected",
    "matches_threshold",
    "known_bytes",
    "exact_bytes",
    "small_delta_le2_bytes",
    "cluster_key",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def hex_value(text: str) -> int:
    return int(text, 16) if text else 0


def hex_byte(value: int | None) -> str:
    return f"0x{value:02x}" if value is not None else ""


def byte_at(data: bytes, offset: int) -> int | None:
    return data[offset] if 0 <= offset < len(data) else None


def byte_known(mask: bytes, offset: int) -> bool:
    return 0 <= offset < len(mask) and mask[offset] != 0


def load_decoded(fixture: dict[str, Any], issues: list[str], label: str) -> bytes:
    clean = fixture.get("clean", {})
    if not isinstance(clean, dict):
        issues.append(f"{label}:missing_clean_row")
        return b""
    path_text = clean.get("decoded_path", "")
    if not path_text:
        issues.append(f"{label}:missing_decoded_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_decoded_failed:{exc}")
        return b""


def fixture_payload(
    fixture: dict[str, Any],
    issues: list[str],
    label: str,
) -> tuple[bytes, bytes, bytes]:
    expected = fixture.get("expected", b"")
    known_mask = fixture.get("known_mask", b"")
    decoded = load_decoded(fixture, issues, label)
    if not isinstance(expected, bytes):
        issues.append(f"{label}:missing_expected_bytes")
        expected = b""
    if not isinstance(known_mask, bytes):
        issues.append(f"{label}:missing_known_mask")
        known_mask = b""
    return expected, known_mask, decoded


def local_hex(data: bytes, offset: int, radius: int = 4) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + radius + 1)
    return data[start:end].hex()


def local_mask(mask: bytes, offset: int, radius: int = 4) -> str:
    start = max(0, offset - radius)
    end = min(len(mask), offset + radius + 1)
    return "".join("1" if value else "0" for value in mask[start:end])


def nearest_known(mask: bytes, expected: bytes, offset: int, direction: int) -> tuple[str, str]:
    cursor = offset + direction
    while 0 <= cursor < len(mask):
        if mask[cursor]:
            return str(cursor), hex_byte(byte_at(expected, cursor))
        cursor += direction
    return "", ""


def known_value_offsets(expected: bytes, mask: bytes, offset: int, value: int, *, limit: int = 16) -> tuple[int, str]:
    offsets = [index for index, known in enumerate(mask) if known and index != offset and expected[index] == value]
    offsets.sort(key=lambda index: (abs(index - offset), index))
    return len(offsets), ";".join(str(index) for index in offsets[:limit])


def candidate_support_rows(
    row: dict[str, str],
    support_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, Any]],
    issues: list[str],
) -> list[dict[str, str]]:
    pair_id = row.get("pair_id", "")
    source_id = row.get("source_id", "")
    byte_index = int_value(row, "byte_index")
    selected_support_value = hex_value(row.get("selected_support_value_hex", ""))
    expected_source_value = hex_value(row.get("expected_source_value_hex", row.get("source_value_hex", "")))
    actual_abs_gt2 = row.get("selected_delta_abs_gt2", "") == "1"
    candidates: list[dict[str, str]] = []

    for support in support_rows:
        if support.get("source_id", "") != source_id:
            continue
        fixture = fixtures.get(fixture_key(support))
        if not fixture:
            issues.append(f"{pair_id}:support_{support.get('support_id', '')}:missing_fixture")
            continue
        expected, known_mask, _decoded = fixture_payload(
            fixture,
            issues,
            f"{pair_id}:support_{support.get('support_id', '')}",
        )
        support_offset = int_value(support, "start") + byte_index
        candidate_value = byte_at(expected, support_offset)
        if candidate_value is None:
            issues.append(f"{pair_id}:support_{support.get('support_id', '')}:offset_oob")
            continue
        candidate_known = byte_known(known_mask, support_offset)
        if not candidate_known:
            continue
        candidate_delta = signed_delta(selected_support_value, candidate_value)
        candidate_abs_gt2 = abs(candidate_delta) > 2
        candidates.append(
            {
                "pair_id": pair_id,
                "source_id": source_id,
                "byte_index": str(byte_index),
                "selected_support_value_hex": hex_byte(selected_support_value),
                "expected_source_value_hex": hex_byte(expected_source_value),
                "selected_delta_abs_gt2": "1" if actual_abs_gt2 else "0",
                "support_id": support.get("support_id", ""),
                "rank": support.get("rank", ""),
                "pcx_name": support.get("pcx_name", ""),
                "frontier_id": support.get("frontier_id", ""),
                "start": support.get("start", ""),
                "absolute_support_offset": str(support_offset),
                "candidate_value_hex": hex_byte(candidate_value),
                "candidate_known": "1",
                "candidate_delta": str(candidate_delta),
                "candidate_abs_gt2": "1" if candidate_abs_gt2 else "0",
                "matches_expected": "1" if candidate_value == expected_source_value else "0",
                "matches_threshold": "1" if candidate_abs_gt2 == actual_abs_gt2 else "0",
                "known_bytes": support.get("known_bytes", ""),
                "exact_bytes": support.get("exact_bytes", ""),
                "small_delta_le2_bytes": support.get("small_delta_le2_bytes", ""),
                "cluster_key": support.get("cluster_key", ""),
            }
        )
    candidates.sort(
        key=lambda candidate: (
            candidate.get("matches_expected", "") != "1",
            candidate.get("matches_threshold", "") != "1",
            -int_value(candidate, "small_delta_le2_bytes"),
            -int_value(candidate, "exact_bytes"),
            int_value(candidate, "support_id"),
        )
    )
    return candidates


def build_prerequisites(
    switch_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, Any]],
    issues: list[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sources_by_id = {row.get("source_id", ""): row for row in source_rows}
    prereq_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []

    for switch in switch_rows:
        if switch.get("source_known", "") == "1":
            continue
        source = sources_by_id.get(switch.get("source_id", ""))
        if not source:
            issues.append(f"{switch.get('pair_id', '')}:missing_source:{switch.get('source_id', '')}")
            continue
        fixture = fixtures.get(fixture_key(source))
        if not fixture:
            issues.append(f"{switch.get('pair_id', '')}:missing_source_fixture")
            continue
        expected, known_mask, decoded = fixture_payload(fixture, issues, f"{switch.get('pair_id', '')}:source")
        source_start = int_value(source, "source_start")
        byte_index = int_value(switch, "byte_index")
        absolute_offset = source_start + byte_index
        expected_value = byte_at(expected, absolute_offset)
        decoded_value = byte_at(decoded, absolute_offset)
        if expected_value is None:
            issues.append(f"{switch.get('pair_id', '')}:source_offset_oob:{absolute_offset}")
            continue
        current_known = byte_known(known_mask, absolute_offset)
        same_value_count, same_value_offsets = known_value_offsets(expected, known_mask, absolute_offset, expected_value)
        left_offset, left_value = nearest_known(known_mask, expected, absolute_offset, -1)
        right_offset, right_value = nearest_known(known_mask, expected, absolute_offset, 1)

        prereq = {
            "pair_id": switch.get("pair_id", ""),
            "source_id": switch.get("source_id", ""),
            "source_rank": source.get("rank", ""),
            "source_pcx_name": source.get("pcx_name", ""),
            "source_frontier_id": source.get("frontier_id", ""),
            "source_start": source.get("source_start", ""),
            "byte_index": switch.get("byte_index", ""),
            "absolute_offset": str(absolute_offset),
            "selected_support_value_hex": switch.get("selected_support_value_hex", ""),
            "expected_source_value_hex": hex_byte(expected_value),
            "switch_source_value_hex": switch.get("source_value_hex", ""),
            "current_decoded_value_hex": hex_byte(decoded_value),
            "current_known": "1" if current_known else "0",
            "decoded_matches_expected": "1" if decoded_value == expected_value else "0",
            "selected_delta": switch.get("selected_delta", ""),
            "selected_delta_abs_gt2": switch.get("selected_delta_abs_gt2", ""),
            "selected_outlier": switch.get("selected_outlier", ""),
            "false_switch": switch.get("false_switch", ""),
            "nearest_known_left_offset": left_offset,
            "nearest_known_left_value_hex": left_value,
            "nearest_known_right_offset": right_offset,
            "nearest_known_right_value_hex": right_value,
            "local_expected_hex": local_hex(expected, absolute_offset),
            "local_known_mask": local_mask(known_mask, absolute_offset),
            "local_decoded_hex": local_hex(decoded, absolute_offset),
            "same_fixture_known_value_count": str(same_value_count),
            "same_fixture_known_value_offsets": same_value_offsets,
            "same_source_support_candidate_count": "0",
            "source_support_exact_candidate_count": "0",
            "source_support_threshold_candidate_count": "0",
            "exact_support_ids": "",
            "threshold_support_ids": "",
        }
        candidates = candidate_support_rows({**switch, **prereq}, support_rows, fixtures, issues)
        exact_candidates = [candidate for candidate in candidates if candidate.get("matches_expected") == "1"]
        threshold_candidates = [candidate for candidate in candidates if candidate.get("matches_threshold") == "1"]
        prereq["same_source_support_candidate_count"] = str(len(candidates))
        prereq["source_support_exact_candidate_count"] = str(len(exact_candidates))
        prereq["source_support_threshold_candidate_count"] = str(len(threshold_candidates))
        prereq["exact_support_ids"] = ";".join(candidate.get("support_id", "") for candidate in exact_candidates[:12])
        prereq["threshold_support_ids"] = ";".join(
            candidate.get("support_id", "") for candidate in threshold_candidates[:12]
        )
        prereq_rows.append(prereq)
        candidate_rows.extend(candidates)

    return prereq_rows, candidate_rows


def build_summary(
    switch_rows: list[dict[str, str]],
    prereq_rows: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    target_unknown = [row for row in prereq_rows if row.get("selected_outlier") == "1"]
    false_unknown = [row for row in prereq_rows if row.get("false_switch") == "1"]
    unique_offsets = {
        (
            row.get("source_rank", ""),
            row.get("source_pcx_name", ""),
            row.get("source_frontier_id", ""),
            row.get("absolute_offset", ""),
        )
        for row in prereq_rows
    }
    all_have_exact = bool(prereq_rows) and all(
        int_value(row, "source_support_exact_candidate_count") > 0 for row in prereq_rows
    )
    all_have_threshold = bool(prereq_rows) and all(
        int_value(row, "source_support_threshold_candidate_count") > 0 for row in prereq_rows
    )
    if not prereq_rows:
        verdict = "frontier80_prior_high_row_source_prereq_not_needed"
        next_probe = "promote source-dependent split for byte-local high-row guard"
    elif all(row.get("current_known") == "1" for row in prereq_rows):
        verdict = "frontier80_prior_high_row_source_prereq_already_known"
        next_probe = "promote source-dependent split for byte-local high-row guard"
    elif all_have_exact:
        verdict = "frontier80_prior_high_row_source_prereq_exact_support_ready"
        next_probe = "validate exact support source-byte guard for selected-delta high-row split"
    elif all_have_threshold:
        verdict = "frontier80_prior_high_row_source_prereq_threshold_support_ready"
        next_probe = "validate threshold support source-byte guard for selected-delta high-row split"
    else:
        verdict = "frontier80_prior_high_row_source_prereq_candidates_needed"
        next_probe = "derive exact source-byte producer for remaining selected-delta high-row prerequisites"
    return {
        "scope": "total",
        "switch_rows": str(len(switch_rows)),
        "source_unknown_switch_rows": str(len(prereq_rows)),
        "target_source_unknown_rows": str(len(target_unknown)),
        "false_source_unknown_rows": str(len(false_unknown)),
        "prerequisite_offsets": str(len(unique_offsets)),
        "expected_value_domain": ";".join(sorted({row.get("expected_source_value_hex", "") for row in prereq_rows})),
        "current_known_rows": str(sum(1 for row in prereq_rows if row.get("current_known") == "1")),
        "current_decoded_exact_rows": str(sum(1 for row in prereq_rows if row.get("decoded_matches_expected") == "1")),
        "same_fixture_known_value_hit_rows": str(
            sum(1 for row in prereq_rows if int_value(row, "same_fixture_known_value_count") > 0)
        ),
        "same_source_support_candidate_rows": str(
            sum(1 for row in prereq_rows if int_value(row, "same_source_support_candidate_count") > 0)
        ),
        "source_support_exact_candidate_rows": str(
            sum(1 for row in prereq_rows if int_value(row, "source_support_exact_candidate_count") > 0)
        ),
        "source_support_threshold_candidate_rows": str(
            sum(1 for row in prereq_rows if int_value(row, "source_support_threshold_candidate_count") > 0)
        ),
        "all_unknown_have_exact_candidate": "1" if all_have_exact else "0",
        "all_unknown_have_threshold_candidate": "1" if all_have_threshold else "0",
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
    prereq_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "prerequisites": prereq_rows, "support_candidates": candidate_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("source_prerequisites.csv", output_dir / "source_prerequisites.csv"),
            ("support_candidates.csv", output_dir / "support_candidates.csv"),
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
    <div class="sub">Audits source-byte prerequisites needed by the selected-delta split.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Source unknown</div><div class="value">{html.escape(summary['source_unknown_switch_rows'])}</div></div>
    <div class="stat"><div class="label">Target unknown</div><div class="value">{html.escape(summary['target_source_unknown_rows'])}</div></div>
    <div class="stat"><div class="label">Exact support candidates</div><div class="value">{html.escape(summary['source_support_exact_candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Threshold candidates</div><div class="value">{html.escape(summary['source_support_threshold_candidate_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Source prerequisites</h2>{render_table(prereq_rows, PREREQ_FIELDNAMES)}</section>
  <section class="panel"><h2>Support candidates</h2>{render_table(candidate_rows, SUPPORT_CANDIDATE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="source-prereq-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    switches_path: Path,
    sources_path: Path,
    support_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    switch_rows = read_csv(switches_path)
    source_rows = read_csv(sources_path)
    support_rows = read_csv(support_path)
    fixtures = load_fixtures(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)
    prereq_rows, candidate_rows = build_prerequisites(switch_rows, source_rows, support_rows, fixtures, issues)
    summary = build_summary(switch_rows, prereq_rows, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "source_prerequisites.csv", PREREQ_FIELDNAMES, prereq_rows)
    write_csv(output_dir / "support_candidates.csv", SUPPORT_CANDIDATE_FIELDNAMES, candidate_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, prereq_rows, candidate_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit source-byte prerequisites for high-row selected-delta splits.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--switches", type=Path, default=DEFAULT_SWITCHES)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--support", type=Path, default=DEFAULT_SUPPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Source Byte Prerequisite Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.switches,
        args.sources,
        args.support,
        args.manifest,
        args.clean_fixtures,
        title=args.title,
    )
    print(f"Source unknown: {summary['source_unknown_switch_rows']}")
    print(f"Exact support candidate rows: {summary['source_support_exact_candidate_rows']}")
    print(f"Threshold support candidate rows: {summary['source_support_threshold_candidate_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
