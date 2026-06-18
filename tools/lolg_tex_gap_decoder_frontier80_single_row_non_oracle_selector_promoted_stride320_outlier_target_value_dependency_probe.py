#!/usr/bin/env python3
"""Profile target-value dependencies for stride-320 outliers after local-delta replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_dependency_probe"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_LOCAL_DELTA_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe/byte_profile.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_target_delta_candidate_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "top_pair_targets",
    "candidate_outlier_bytes",
    "distinct_target_values",
    "exact_supported_values",
    "exact_supported_bytes",
    "same_fixture_exact_supported_values",
    "same_fixture_exact_supported_bytes",
    "same_pcx_exact_supported_values",
    "same_pcx_exact_supported_bytes",
    "le4_supported_values",
    "le4_supported_bytes",
    "same_pcx_unsupported_values",
    "same_pcx_unsupported_target_offsets",
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
    "delta",
    "abs_delta",
    "source_value_class",
    "target_value_class",
    "local_note",
    "target_value_count",
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
    "target_value",
    "candidate_bytes",
    "byte_indexes",
    "target_offsets",
    "exact_support_rows",
    "le4_support_rows",
    "same_fixture_exact_support_rows",
    "same_pcx_exact_support_rows",
    "best_support_kind",
    "best_support_ref",
]

SUPPORT_FIELDNAMES = [
    "target_value",
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


def local_delta_resolved(row: dict[str, str]) -> bool:
    return row.get("bounded_prefix") == "1" or (
        row.get("bounded_prefix") != "1" and row.get("small_delta_le4") == "1"
    )


def positions_text(values: list[str]) -> str:
    return ";".join(values)


def candidate_rows(profile_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [row for row in profile_rows if not local_delta_resolved(row)]
    value_counts = Counter(int_value(row, "target_value") for row in selected)
    rows: list[dict[str, str]] = []
    for row in selected:
        target_value = int_value(row, "target_value")
        rows.append(
            {
                "byte_index": row.get("byte_index", ""),
                "source_offset": row.get("source_offset", ""),
                "target_offset": row.get("target_offset", ""),
                "source_value": row.get("source_value", ""),
                "target_value": row.get("target_value", ""),
                "delta": row.get("delta", ""),
                "abs_delta": row.get("abs_delta", ""),
                "source_value_class": row.get("source_value_class", ""),
                "target_value_class": row.get("target_value_class", ""),
                "local_note": row.get("local_note", ""),
                "target_value_count": str(value_counts[target_value]),
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
    rows.sort(key=lambda row: int_value(row, "target_offset"))
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
        for offset, (support_value, known) in enumerate(zip(expected, mask)):
            if not known:
                continue
            for target_value in values:
                delta = signed_delta(support_value, target_value)
                if abs(delta) > 4:
                    continue
                rows_by_value[target_value].append(
                    {
                        "target_value": str(target_value),
                        "support_rank": manifest.get("rank", ""),
                        "support_archive": manifest.get("archive", ""),
                        "support_archive_tag": manifest.get("archive_tag", ""),
                        "support_pcx_name": manifest.get("pcx_name", ""),
                        "support_frontier_id": manifest.get("frontier_id", ""),
                        "support_offset": str(offset),
                        "support_value": str(support_value),
                        "delta": str(delta),
                        "abs_delta": str(abs(delta)),
                        "support_kind": "exact" if delta == 0 else "le4",
                        "same_fixture": "1" if same_fixture else "0",
                        "same_pcx": "1" if same_pcx else "0",
                    }
                )

    output_rows: list[dict[str, str]] = []
    for target_value, rows in rows_by_value.items():
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
            int_value(row, "target_value"),
            int_value(row, "abs_delta"),
            0 if row.get("same_fixture") == "1" else 1,
            0 if row.get("same_pcx") == "1" else 1,
            int_value(row, "support_rank"),
            int_value(row, "support_offset"),
        )
    )
    return output_rows


def attach_support(candidates: list[dict[str, str]], supports: list[dict[str, str]]) -> None:
    supports_by_value: dict[str, list[dict[str, str]]] = defaultdict(list)
    for support in supports:
        supports_by_value[support.get("target_value", "")].append(support)
    for row in candidates:
        support_rows = supports_by_value.get(row.get("target_value", ""), [])
        exact = [support for support in support_rows if support.get("support_kind") == "exact"]
        same_fixture_exact = [support for support in exact if support.get("same_fixture") == "1"]
        same_pcx_exact = [support for support in exact if support.get("same_pcx") == "1"]
        best = same_fixture_exact[0] if same_fixture_exact else (same_pcx_exact[0] if same_pcx_exact else (exact[0] if exact else (support_rows[0] if support_rows else {})))
        row["exact_support_rows"] = str(len(exact))
        row["le4_support_rows"] = str(len(support_rows))
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
        row["support_ready"] = "1" if exact else "0"
        if same_pcx_exact:
            row["blocker_reason"] = "ready_same_pcx_exact_support"
        elif exact:
            row["blocker_reason"] = "cross_pcx_exact_support_only"
        elif support_rows:
            row["blocker_reason"] = "le4_support_only"
        else:
            row["blocker_reason"] = "missing_value_support"


def build_value_rows(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[row.get("target_value", "")].append(row)
    rows: list[dict[str, str]] = []
    for target_value, grouped_rows in grouped.items():
        best = grouped_rows[0]
        rows.append(
            {
                "target_value": target_value,
                "candidate_bytes": str(len(grouped_rows)),
                "byte_indexes": positions_text([row.get("byte_index", "") for row in grouped_rows]),
                "target_offsets": positions_text([row.get("target_offset", "") for row in grouped_rows]),
                "exact_support_rows": best.get("exact_support_rows", "0"),
                "le4_support_rows": best.get("le4_support_rows", "0"),
                "same_fixture_exact_support_rows": best.get("same_fixture_exact_support_rows", "0"),
                "same_pcx_exact_support_rows": best.get("same_pcx_exact_support_rows", "0"),
                "best_support_kind": best.get("best_support_kind", ""),
                "best_support_ref": (
                    f"rank={best.get('best_support_rank', '')}:"
                    f"pcx={best.get('best_support_pcx_name', '')}:"
                    f"frontier={best.get('best_support_frontier_id', '')}:"
                    f"offset={best.get('best_support_offset', '')}"
                ),
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "candidate_bytes"), int_value(row, "target_value")))
    return rows


def build_summary(
    pair: dict[str, str],
    candidates: list[dict[str, str]],
    value_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    exact_values = [row for row in value_rows if int_value(row, "exact_support_rows") > 0]
    same_fixture_values = [row for row in value_rows if int_value(row, "same_fixture_exact_support_rows") > 0]
    same_pcx_values = [row for row in value_rows if int_value(row, "same_pcx_exact_support_rows") > 0]
    le4_values = [row for row in value_rows if int_value(row, "le4_support_rows") > 0]
    no_same_pcx_values = [row for row in value_rows if int_value(row, "same_pcx_exact_support_rows") == 0]
    no_same_pcx_value_set = {row.get("target_value", "") for row in no_same_pcx_values}
    no_same_pcx_offsets = [
        row.get("target_offset", "") for row in candidates if row.get("target_value", "") in no_same_pcx_value_set
    ]
    exact_supported_bytes = sum(int_value(row, "candidate_bytes") for row in exact_values)
    same_fixture_supported_bytes = sum(int_value(row, "candidate_bytes") for row in same_fixture_values)
    same_pcx_supported_bytes = sum(int_value(row, "candidate_bytes") for row in same_pcx_values)
    le4_supported_bytes = sum(int_value(row, "candidate_bytes") for row in le4_values)
    histogram = json.dumps(
        {row.get("target_value", ""): int_value(row, "candidate_bytes") for row in value_rows},
        sort_keys=True,
        separators=(",", ":"),
    )
    if issues:
        verdict = "frontier80_stride320_outlier_target_value_dependency_issues"
        next_probe = "review stride-320 outlier target-value dependency input issues"
    elif exact_supported_bytes == len(candidates) and same_pcx_supported_bytes == len(candidates) and candidates:
        verdict = "frontier80_stride320_outlier_target_value_dependency_same_pcx_ready"
        next_probe = "build guarded target-value replay for stride-320 outliers"
    elif exact_supported_bytes == len(candidates) and candidates:
        verdict = "frontier80_stride320_outlier_target_value_dependency_cross_pcx_guard_needed"
        next_probe = "derive cross-PCX guard for target outlier values then build guarded target-value replay"
    elif exact_supported_bytes:
        verdict = "frontier80_stride320_outlier_target_value_dependency_partial_support"
        next_probe = "derive fallback support for unsupported stride-320 target outlier values"
    else:
        verdict = "frontier80_stride320_outlier_target_value_dependency_no_support"
        next_probe = "return to transition grammar search for stride-320 target outliers"

    return {
        "scope": "frontier80_stride320_outlier_target_value_dependency",
        "top_pair_targets": ";".join(value for value in (pair.get("target_a", ""), pair.get("target_b", "")) if value),
        "candidate_outlier_bytes": str(len(candidates)),
        "distinct_target_values": str(len(value_rows)),
        "exact_supported_values": str(len(exact_values)),
        "exact_supported_bytes": str(exact_supported_bytes),
        "same_fixture_exact_supported_values": str(len(same_fixture_values)),
        "same_fixture_exact_supported_bytes": str(same_fixture_supported_bytes),
        "same_pcx_exact_supported_values": str(len(same_pcx_values)),
        "same_pcx_exact_supported_bytes": str(same_pcx_supported_bytes),
        "le4_supported_values": str(len(le4_values)),
        "le4_supported_bytes": str(le4_supported_bytes),
        "same_pcx_unsupported_values": ";".join(row.get("target_value", "") for row in no_same_pcx_values),
        "same_pcx_unsupported_target_offsets": ";".join(no_same_pcx_offsets),
        "value_histogram": histogram,
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
    candidates: list[dict[str, str]],
    value_rows: list[dict[str, str]],
    supports: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "candidate_outlier_bytes",
            "exact_supported_bytes",
            "same_pcx_exact_supported_bytes",
            "same_pcx_unsupported_values",
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
  {table_html("Candidate outlier target bytes", "candidate_outlier_rows.csv", candidates, CANDIDATE_FIELDNAMES)}
  {table_html("Value support", "value_support_rows.csv", value_rows, VALUE_FIELDNAMES)}
  {table_html("Support examples", "support_examples.csv", supports, SUPPORT_FIELDNAMES)}
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
        default="Lands of Lore II .tex Frontier80 Stride-320 Outlier Target Value Dependency Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    pair_rows = read_csv(args.pair_rows)
    if not pair_rows:
        issues.append(f"missing_pair_rows:{args.pair_rows}")
    pair = pair_rows[0] if pair_rows else {}
    candidates = candidate_rows(read_csv(args.local_delta_profile))
    values = {int_value(row, "target_value") for row in candidates}
    supports = support_rows(
        values,
        read_csv(args.manifest),
        read_csv(args.clean_fixtures),
        fixture_key(pair),
        archive_pcx_key(pair),
        issues,
        per_value_limit=args.support_limit,
    )
    attach_support(candidates, supports)
    value_rows = build_value_rows(candidates)
    summary = build_summary(pair, candidates, value_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidate_outlier_rows.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "value_support_rows.csv", VALUE_FIELDNAMES, value_rows)
    write_csv(args.output / "support_examples.csv", SUPPORT_FIELDNAMES, supports)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, value_rows, supports, args.title))

    print(f"Candidate outlier bytes: {summary['candidate_outlier_bytes']}")
    print(f"Exact-supported bytes: {summary['exact_supported_bytes']}")
    print(f"Same-PCX exact-supported bytes: {summary['same_pcx_exact_supported_bytes']}")
    print(f"Same-PCX unsupported values: {summary['same_pcx_unsupported_values']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
