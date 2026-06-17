#!/usr/bin/env python3
"""Probe support for the refined compact-control five-byte guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_PAIR_MOD_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/summary.csv"
)
DEFAULT_PAIR_MOD_HIT_FEATURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/hit_features.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "refined_guard_family",
    "refined_guard_value",
    "refined_guard_key",
    "refined_pair_any_rows",
    "refined_pair_any_non_target_rows",
    "refined_pair_mod_rows",
    "refined_pair_mod_non_target_rows",
    "reference_window_rows",
    "reference_exact_rows",
    "reference_exact_non_target_rows",
    "target_exact_rows",
    "target_only_exact_rows",
    "non_target_frontiers",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

HIT_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "ref_offset",
    "control_ref_mod64",
    "matches_mod",
    "is_target_asset",
    "rule_type",
    "frontier_type",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "segment_prev4_hex",
    "segment_ref_hex",
    "segment_next4_hex",
]

WINDOW_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "ref_offset",
    "span_start",
    "span_end",
    "span_key",
    "anchor_offset",
    "anchor_rel",
    "anchor_byte",
    "expected_hex",
    "formula_output_hex",
    "formula_exact",
    "is_target_span",
    "window_verdict",
    "sampled",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def row_identity(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def refined_value(summary: dict[str, str]) -> tuple[str, str]:
    family = summary.get("best_refined_guard_family", "")
    guard_key = summary.get("best_refined_guard_key", "")
    prefix = f"{family}="
    for part in guard_key.split("|"):
        if part.startswith(prefix):
            return family, part.split("=", 1)[1]
    return family, ""


def span_key(frontier_id: str, start: int, end: int) -> str:
    return f"{frontier_id}:{start}-{end}"


def formula_output(segment: bytes, ref: int, anchor: int) -> bytes:
    return bytes([(anchor - 1) & 0xFF, segment[ref + 3], (anchor - 1) & 0xFF, segment[ref + 2], anchor])


def window_verdict(exact: bool, is_target: bool) -> str:
    if exact and is_target:
        return "target_reference_exact"
    if exact:
        return "non_target_reference_exact"
    return "reference_false"


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def build(
    pair_mod_summary_rows: list[dict[str, str]],
    hit_feature_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    false_samples_per_hit: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    pair_mod_summary = pair_mod_summary_rows[0] if pair_mod_summary_rows else {}
    family, value = refined_value(pair_mod_summary)
    manifest_by_key = {row_identity(row): row for row in manifest_rows}
    refined_hits = [row for row in hit_feature_rows if family and row.get(family, "") == value]
    issues: list[str] = []
    output_hits: list[dict[str, str]] = []
    windows: list[dict[str, str]] = []
    reference_window_rows = 0
    reference_exact_rows = 0
    reference_exact_non_target_rows = 0
    target_exact_rows = 0
    anchor_rel = -2
    span_length = 5

    for hit in refined_hits:
        manifest = manifest_by_key.get(row_identity(hit))
        if manifest is None:
            issues.append(f"{'|'.join(row_identity(hit))}:missing_manifest")
            continue
        segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        if not segment or not expected:
            continue
        ref = int_value(hit, "ref_offset", -1)
        if ref < 0 or ref + 3 >= len(segment):
            issues.append(f"{'|'.join(row_identity(hit))}:bad_ref_offset")
            continue
        output_hits.append(
            {
                "rank": "",
                "archive": hit.get("archive", ""),
                "archive_tag": hit.get("archive_tag", ""),
                "pcx_name": hit.get("pcx_name", ""),
                "frontier_id": hit.get("frontier_id", ""),
                "ref_offset": hit.get("ref_offset", ""),
                "control_ref_mod64": str(ref % 64),
                "matches_mod": hit.get("matches_mod", ""),
                "is_target_asset": hit.get("is_target_asset", ""),
                "rule_type": hit.get("rule_type", ""),
                "frontier_type": hit.get("frontier_type", ""),
                "segment_gap_bytes": hit.get("segment_gap_bytes", ""),
                "segment_gap_ratio": hit.get("segment_gap_ratio", ""),
                "segment_prev4_hex": hit.get("segment_prev4_hex", ""),
                "segment_ref_hex": hit.get("segment_ref_hex", ""),
                "segment_next4_hex": hit.get("segment_next4_hex", ""),
            }
        )
        false_samples = 0
        first_start = max(0, -anchor_rel)
        last_start = max(first_start, len(expected) - span_length)
        for start in range(first_start, last_start + 1):
            end = start + span_length
            anchor_offset = start + anchor_rel
            if end > len(expected) or anchor_offset < 0 or anchor_offset >= len(expected):
                continue
            reference_window_rows += 1
            anchor = expected[anchor_offset]
            output = formula_output(segment, ref, anchor)
            expected_hex = expected[start:end].hex()
            output_hex = output.hex()
            exact = output_hex == expected_hex
            is_target = hit.get("is_target_asset") == "1" and span_key(hit.get("frontier_id", ""), start, end) == "80:7-12"
            sampled = exact or false_samples < false_samples_per_hit
            if not sampled:
                continue
            if not exact:
                false_samples += 1
            if exact:
                reference_exact_rows += 1
                if is_target:
                    target_exact_rows += 1
                else:
                    reference_exact_non_target_rows += 1
            windows.append(
                {
                    "rank": "",
                    "archive": hit.get("archive", ""),
                    "archive_tag": hit.get("archive_tag", ""),
                    "pcx_name": hit.get("pcx_name", ""),
                    "frontier_id": hit.get("frontier_id", ""),
                    "ref_offset": hit.get("ref_offset", ""),
                    "span_start": str(start),
                    "span_end": str(end),
                    "span_key": span_key(hit.get("frontier_id", ""), start, end),
                    "anchor_offset": str(anchor_offset),
                    "anchor_rel": str(anchor_rel),
                    "anchor_byte": f"{anchor:02x}",
                    "expected_hex": expected_hex,
                    "formula_output_hex": output_hex,
                    "formula_exact": "1" if exact else "0",
                    "is_target_span": "1" if is_target else "0",
                    "window_verdict": window_verdict(exact, is_target),
                    "sampled": "1",
                }
            )

    output_hits.sort(
        key=lambda row: (
            row.get("is_target_asset") != "1",
            int_value(row, "frontier_id"),
            int_value(row, "ref_offset"),
        )
    )
    for index, row in enumerate(output_hits, start=1):
        row["rank"] = str(index)
    windows.sort(
        key=lambda row: (
            row.get("formula_exact") != "1",
            row.get("is_target_span") != "1",
            int_value(row, "frontier_id"),
            int_value(row, "span_start"),
        )
    )
    for index, row in enumerate(windows, start=1):
        row["rank"] = str(index)

    refined_pair_mod = [row for row in output_hits if row.get("matches_mod") == "1"]
    refined_pair_mod_non_target = [row for row in refined_pair_mod if row.get("is_target_asset") != "1"]
    refined_non_target = [row for row in output_hits if row.get("is_target_asset") != "1"]
    non_target_frontiers = ",".join(
        sorted({row.get("frontier_id", "") for row in refined_non_target}, key=lambda value: int(value or 0))
    )
    if reference_exact_non_target_rows:
        verdict = "refined_non_target_exact_support"
        next_probe = "review refined five-byte non-target exact support for promotion"
    elif refined_non_target:
        verdict = "refined_compact_pair_without_formula_exact"
        next_probe = "derive formula variant for compact-control five-byte non-target rows"
    else:
        verdict = "refined_target_only_support"
        next_probe = "expand compact-control five-byte support outside pair hits"

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_refined_support",
        "target_spans": pair_mod_summary.get("target_spans", "0"),
        "target_bytes": pair_mod_summary.get("target_bytes", "0"),
        "refined_guard_family": family,
        "refined_guard_value": value,
        "refined_guard_key": pair_mod_summary.get("best_refined_guard_key", ""),
        "refined_pair_any_rows": str(len(output_hits)),
        "refined_pair_any_non_target_rows": str(len(refined_non_target)),
        "refined_pair_mod_rows": str(len(refined_pair_mod)),
        "refined_pair_mod_non_target_rows": str(len(refined_pair_mod_non_target)),
        "reference_window_rows": str(reference_window_rows),
        "reference_exact_rows": str(reference_exact_rows),
        "reference_exact_non_target_rows": str(reference_exact_non_target_rows),
        "target_exact_rows": str(target_exact_rows),
        "target_only_exact_rows": str(target_exact_rows if target_exact_rows and not reference_exact_non_target_rows else 0),
        "non_target_frontiers": non_target_frontiers,
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, output_hits, windows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    hits: list[dict[str, str]],
    windows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "hits": hits, "windows": windows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("hits.csv", output_dir / "hits.csv"),
            ("windows.csv", output_dir / "windows.csv"),
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
  --bg: #111416;
  --panel: #182023;
  --line: #314247;
  --text: #edf4f2;
  --muted: #a4b2b5;
  --accent: #7bd5b4;
  --warn: #eebb70;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1320px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Scans refined compact-control pair hits for independent five-byte formula support.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Refined pair rows</div><div class="value">{summary['refined_pair_any_rows']}</div></div>
    <div class="stat"><div class="muted">Non-target rows</div><div class="value">{summary['refined_pair_any_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Exact non-target</div><div class="value warn">{summary['reference_exact_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Target-only exact</div><div class="value warn">{summary['target_only_exact_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Hits</h2>{render_table(hits, HIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Windows</h2>{render_table(windows, WINDOW_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-refined-support-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe support for the refined compact-control five-byte guard.")
    parser.add_argument("--pair-mod-summary", type=Path, default=DEFAULT_PAIR_MOD_SUMMARY)
    parser.add_argument("--pair-mod-hit-features", type=Path, default=DEFAULT_PAIR_MOD_HIT_FEATURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--false-samples-per-hit", type=int, default=6)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Refined Support Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, hits, windows = build(
        read_rows(args.pair_mod_summary),
        read_rows(args.pair_mod_hit_features),
        read_rows(args.manifest),
        false_samples_per_hit=args.false_samples_per_hit,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "hits.csv", HIT_FIELDNAMES, hits)
    write_csv(args.output / "windows.csv", WINDOW_FIELDNAMES, windows)
    (args.output / "index.html").write_text(
        build_html(summary, hits, windows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte refined support probe: "
        f"refined_pair={summary['refined_pair_any_rows']} "
        f"non_target={summary['refined_pair_any_non_target_rows']} "
        f"non_target_exact={summary['reference_exact_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
