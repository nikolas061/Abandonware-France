#!/usr/bin/env python3
"""Profile remaining source dependencies after the stride-320 target-prefix replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_dependency_probe"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_LOCAL_DELTA_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe/byte_profile.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_target_prefix_delta_candidate_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "top_pair_targets",
    "candidate_source_bytes",
    "candidate_source_missing_bytes",
    "candidate_source_known_bytes",
    "distinct_source_values",
    "exact_supported_values",
    "exact_supported_bytes",
    "same_fixture_exact_supported_values",
    "same_fixture_exact_supported_bytes",
    "same_pcx_exact_supported_values",
    "same_pcx_exact_supported_bytes",
    "le4_supported_values",
    "le4_supported_bytes",
    "exact_unsupported_values",
    "exact_unsupported_source_offsets",
    "min_exact_support_rows_per_value",
    "max_exact_support_rows_per_value",
    "value_histogram",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "target_delta",
    "source_known",
    "source_missing",
    "source_value_count",
    "exact_support_rows",
    "le4_support_rows",
    "same_fixture_exact_support_rows",
    "same_pcx_exact_support_rows",
    "best_support_rank",
    "best_support_archive_tag",
    "best_support_pcx_name",
    "best_support_frontier_id",
    "best_support_offset",
    "best_support_value",
    "best_support_delta",
    "best_support_kind",
    "support_ready",
    "blocker_reason",
]

VALUE_FIELDNAMES = [
    "source_value",
    "candidate_bytes",
    "candidate_offsets",
    "target_offsets",
    "exact_support_rows",
    "le4_support_rows",
    "same_fixture_exact_support_rows",
    "same_pcx_exact_support_rows",
    "best_support_kind",
    "best_support_ref",
]

SUPPORT_FIELDNAMES = [
    "source_value",
    "support_rank",
    "support_archive",
    "support_archive_tag",
    "support_pcx_name",
    "support_frontier_id",
    "support_offset",
    "support_value",
    "delta",
    "abs_delta",
    "support_kind",
    "same_fixture",
    "same_pcx",
]


def signed_delta(source: int, target: int) -> int:
    delta = (target - source) & 0xFF
    return delta - 256 if delta >= 128 else delta


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def archive_pcx_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive", ""), row.get("pcx_name", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_failed:{exc}")
        return b""


def positions_text(values: list[str]) -> str:
    return ";".join(values)


def candidate_rows(
    profile_rows: list[dict[str, str]],
    expected: bytes,
    mask: bytes,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    selected = [
        row
        for row in profile_rows
        if row.get("bounded_prefix") != "1" and row.get("small_delta_le4") == "1"
    ]
    value_counts = Counter(int_value(row, "source_value") for row in selected)
    for row in selected:
        source_offset = int_value(row, "source_offset")
        source_known = bool(mask[source_offset]) if 0 <= source_offset < len(mask) else False
        rows.append(
            {
                "byte_index": row.get("byte_index", ""),
                "source_offset": row.get("source_offset", ""),
                "target_offset": row.get("target_offset", ""),
                "source_value": row.get("source_value", ""),
                "target_value": row.get("target_value", ""),
                "target_delta": row.get("delta", ""),
                "source_known": "1" if source_known else "0",
                "source_missing": "0" if source_known else "1",
                "source_value_count": str(value_counts[int_value(row, "source_value")]),
                "exact_support_rows": "0",
                "le4_support_rows": "0",
                "same_fixture_exact_support_rows": "0",
                "same_pcx_exact_support_rows": "0",
                "best_support_rank": "",
                "best_support_archive_tag": "",
                "best_support_pcx_name": "",
                "best_support_frontier_id": "",
                "best_support_offset": "",
                "best_support_value": "",
                "best_support_delta": "",
                "best_support_kind": "",
                "support_ready": "0",
                "blocker_reason": "unprofiled",
            }
        )
    rows.sort(key=lambda row: int_value(row, "source_offset"))
    return rows


def support_rows(
    values: set[int],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    top_key: tuple[str, str, str],
    top_archive_pcx: tuple[str, str],
    issues: list[str],
    *,
    per_value_limit: int,
) -> list[dict[str, str]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    rows_by_value: dict[int, list[dict[str, str]]] = defaultdict(list)
    for manifest in manifest_rows:
        clean = clean_by_key.get(fixture_key(manifest))
        if not clean:
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, f"{fixture_key(manifest)}:expected")
        mask = load_bytes(clean.get("known_mask_path", ""), issues, f"{fixture_key(manifest)}:known_mask")
        if not expected or not mask:
            continue
        key = fixture_key(manifest)
        same_fixture = key == top_key
        same_pcx = archive_pcx_key(manifest) == top_archive_pcx
        for offset, (candidate_value, known) in enumerate(zip(expected, mask)):
            if not known:
                continue
            for source_value in values:
                delta = signed_delta(candidate_value, source_value)
                if abs(delta) > 4:
                    continue
                rows_by_value[source_value].append(
                    {
                        "source_value": str(source_value),
                        "support_rank": manifest.get("rank", ""),
                        "support_archive": manifest.get("archive", ""),
                        "support_archive_tag": manifest.get("archive_tag", ""),
                        "support_pcx_name": manifest.get("pcx_name", ""),
                        "support_frontier_id": manifest.get("frontier_id", ""),
                        "support_offset": str(offset),
                        "support_value": str(candidate_value),
                        "delta": str(delta),
                        "abs_delta": str(abs(delta)),
                        "support_kind": "exact" if delta == 0 else "le4",
                        "same_fixture": "1" if same_fixture else "0",
                        "same_pcx": "1" if same_pcx else "0",
                    }
                )

    output_rows: list[dict[str, str]] = []
    for source_value, rows in rows_by_value.items():
        rows.sort(
            key=lambda row: (
                int_value(row, "abs_delta"),
                0 if row.get("same_fixture") == "1" else 1,
                0 if row.get("same_pcx") == "1" else 1,
                int_value(row, "support_rank"),
                int_value(row, "support_frontier_id"),
                int_value(row, "support_offset"),
            )
        )
        output_rows.extend(rows[:per_value_limit])
    output_rows.sort(
        key=lambda row: (
            int_value(row, "source_value"),
            int_value(row, "abs_delta"),
            0 if row.get("same_fixture") == "1" else 1,
            0 if row.get("same_pcx") == "1" else 1,
            int_value(row, "support_rank"),
            int_value(row, "support_offset"),
        )
    )
    return output_rows


def attach_support(candidate_rows: list[dict[str, str]], support_rows: list[dict[str, str]]) -> None:
    supports_by_value: dict[str, list[dict[str, str]]] = defaultdict(list)
    for support in support_rows:
        supports_by_value[support.get("source_value", "")].append(support)
    for row in candidate_rows:
        supports = supports_by_value.get(row.get("source_value", ""), [])
        exact = [support for support in supports if support.get("support_kind") == "exact"]
        le4 = supports
        same_fixture_exact = [support for support in exact if support.get("same_fixture") == "1"]
        same_pcx_exact = [support for support in exact if support.get("same_pcx") == "1"]
        best = exact[0] if exact else (le4[0] if le4 else {})
        row["exact_support_rows"] = str(len(exact))
        row["le4_support_rows"] = str(len(le4))
        row["same_fixture_exact_support_rows"] = str(len(same_fixture_exact))
        row["same_pcx_exact_support_rows"] = str(len(same_pcx_exact))
        row["best_support_rank"] = best.get("support_rank", "")
        row["best_support_archive_tag"] = best.get("support_archive_tag", "")
        row["best_support_pcx_name"] = best.get("support_pcx_name", "")
        row["best_support_frontier_id"] = best.get("support_frontier_id", "")
        row["best_support_offset"] = best.get("support_offset", "")
        row["best_support_value"] = best.get("support_value", "")
        row["best_support_delta"] = best.get("delta", "")
        row["best_support_kind"] = best.get("support_kind", "")
        ready = row.get("source_missing") == "1" and bool(exact)
        row["support_ready"] = "1" if ready else "0"
        if row.get("source_known") == "1":
            row["blocker_reason"] = "source_already_known"
        elif exact:
            row["blocker_reason"] = "ready_exact_value_support"
        elif le4:
            row["blocker_reason"] = "le4_value_support_only"
        else:
            row["blocker_reason"] = "missing_value_support"


def build_value_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        grouped[row.get("source_value", "")].append(row)
    rows: list[dict[str, str]] = []
    for source_value, candidates in grouped.items():
        best = candidates[0]
        rows.append(
            {
                "source_value": source_value,
                "candidate_bytes": str(len(candidates)),
                "candidate_offsets": positions_text([row.get("source_offset", "") for row in candidates]),
                "target_offsets": positions_text([row.get("target_offset", "") for row in candidates]),
                "exact_support_rows": best.get("exact_support_rows", "0"),
                "le4_support_rows": best.get("le4_support_rows", "0"),
                "same_fixture_exact_support_rows": best.get("same_fixture_exact_support_rows", "0"),
                "same_pcx_exact_support_rows": best.get("same_pcx_exact_support_rows", "0"),
                "best_support_kind": best.get("best_support_kind", ""),
                "best_support_ref": (
                    f"rank={best.get('best_support_rank', '')}:"
                    f"frontier={best.get('best_support_frontier_id', '')}:"
                    f"offset={best.get('best_support_offset', '')}"
                ),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "candidate_bytes"), int_value(row, "source_value")))
    return rows


def build_summary(
    pair: dict[str, str],
    candidate_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    missing = [row for row in candidate_rows if row.get("source_missing") == "1"]
    known = [row for row in candidate_rows if row.get("source_known") == "1"]
    exact_values = [row for row in value_rows if int_value(row, "exact_support_rows") > 0]
    le4_values = [row for row in value_rows if int_value(row, "le4_support_rows") > 0]
    unsupported_exact_values = [row for row in value_rows if int_value(row, "exact_support_rows") == 0]
    unsupported_exact_value_set = {row.get("source_value", "") for row in unsupported_exact_values}
    unsupported_exact_offsets = [
        row.get("source_offset", "")
        for row in candidate_rows
        if row.get("source_value", "") in unsupported_exact_value_set
    ]
    same_fixture_values = [row for row in value_rows if int_value(row, "same_fixture_exact_support_rows") > 0]
    same_pcx_values = [row for row in value_rows if int_value(row, "same_pcx_exact_support_rows") > 0]
    exact_support_counts = [int_value(row, "exact_support_rows") for row in value_rows]
    exact_supported_bytes = sum(int_value(row, "candidate_bytes") for row in exact_values)
    le4_supported_bytes = sum(int_value(row, "candidate_bytes") for row in le4_values)
    same_fixture_supported_bytes = sum(int_value(row, "candidate_bytes") for row in same_fixture_values)
    same_pcx_supported_bytes = sum(int_value(row, "candidate_bytes") for row in same_pcx_values)
    value_histogram = json.dumps(
        {row.get("source_value", ""): int_value(row, "candidate_bytes") for row in value_rows},
        sort_keys=True,
        separators=(",", ":"),
    )
    if issues:
        verdict = "frontier80_stride320_remaining_source_dependency_issues"
        next_probe = "review remaining stride-320 source dependency input issues"
    elif exact_supported_bytes == len(missing) and missing:
        verdict = "frontier80_stride320_remaining_source_dependency_value_support_ready"
        next_probe = "derive guarded value selector replay for 39 remaining stride-320 source bytes"
    elif exact_supported_bytes:
        verdict = "frontier80_stride320_remaining_source_dependency_partial_value_support"
        next_probe = "derive fallback support for unsupported remaining stride-320 source values"
    else:
        verdict = "frontier80_stride320_remaining_source_dependency_no_value_support"
        next_probe = "return to corpus source dependency search for remaining stride-320 bytes"

    return {
        "scope": "frontier80_stride320_remaining_source_dependency",
        "top_pair_targets": ";".join(value for value in (pair.get("target_a", ""), pair.get("target_b", "")) if value),
        "candidate_source_bytes": str(len(candidate_rows)),
        "candidate_source_missing_bytes": str(len(missing)),
        "candidate_source_known_bytes": str(len(known)),
        "distinct_source_values": str(len(value_rows)),
        "exact_supported_values": str(len(exact_values)),
        "exact_supported_bytes": str(exact_supported_bytes),
        "same_fixture_exact_supported_values": str(len(same_fixture_values)),
        "same_fixture_exact_supported_bytes": str(same_fixture_supported_bytes),
        "same_pcx_exact_supported_values": str(len(same_pcx_values)),
        "same_pcx_exact_supported_bytes": str(same_pcx_supported_bytes),
        "le4_supported_values": str(len(le4_values)),
        "le4_supported_bytes": str(le4_supported_bytes),
        "exact_unsupported_values": ";".join(row.get("source_value", "") for row in unsupported_exact_values),
        "exact_unsupported_source_offsets": ";".join(unsupported_exact_offsets),
        "min_exact_support_rows_per_value": str(min(exact_support_counts) if exact_support_counts else 0),
        "max_exact_support_rows_per_value": str(max(exact_support_counts) if exact_support_counts else 0),
        "value_histogram": value_histogram,
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 96) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><p><a href=\"{html.escape(filename)}\">"
        f"{html.escape(filename)}</a></p><table><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "candidate_source_bytes",
            "distinct_source_values",
            "exact_supported_bytes",
            "same_pcx_exact_supported_bytes",
            "review_verdict",
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1f2933; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .label {{ font-size: 12px; color: #52606d; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 4px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="stats">{stats}</div>
  <h2>Summary</h2>
  <pre>{summary_json}</pre>
  {table_html("Candidate source bytes", "candidate_source_rows.csv", candidate_rows, CANDIDATE_FIELDNAMES)}
  {table_html("Value support", "value_support_rows.csv", value_rows, VALUE_FIELDNAMES)}
  {table_html("Support examples", "support_examples.csv", support_rows, SUPPORT_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--local-delta-profile", type=Path, default=DEFAULT_LOCAL_DELTA_PROFILE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--support-limit", type=int, default=96)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Remaining Source Dependency Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    pair_rows = read_csv(args.pair_rows)
    profile_rows = read_csv(args.local_delta_profile)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    if not pair_rows:
        issues.append(f"missing_pair_rows:{args.pair_rows}")
    pair = pair_rows[0] if pair_rows else {}
    top_key = fixture_key(pair)
    top_archive_pcx = archive_pcx_key(pair)
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    manifest = manifest_by_key.get(top_key)
    clean = clean_by_key.get(top_key)
    if not manifest:
        issues.append(f"{top_key}:missing_manifest")
    if not clean:
        issues.append(f"{top_key}:missing_clean_fixture")
    expected = load_bytes(manifest.get("expected_gap_path", "") if manifest else "", issues, f"{top_key}:expected")
    mask = load_bytes(clean.get("known_mask_path", "") if clean else "", issues, f"{top_key}:known_mask")

    candidates = candidate_rows(profile_rows, expected, mask) if expected and mask else []
    values = {int_value(row, "source_value") for row in candidates}
    supports = support_rows(
        values,
        manifest_rows,
        clean_rows,
        top_key,
        top_archive_pcx,
        issues,
        per_value_limit=args.support_limit,
    )
    attach_support(candidates, supports)
    value_rows = build_value_rows(candidates)
    summary = build_summary(pair, candidates, value_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidate_source_rows.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "value_support_rows.csv", VALUE_FIELDNAMES, value_rows)
    write_csv(args.output / "support_examples.csv", SUPPORT_FIELDNAMES, supports)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, value_rows, supports, args.title))

    print(f"Candidate source bytes: {summary['candidate_source_bytes']}")
    print(f"Distinct source values: {summary['distinct_source_values']}")
    print(f"Exact-supported bytes: {summary['exact_supported_bytes']}")
    print(f"Same-PCX exact-supported bytes: {summary['same_pcx_exact_supported_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
