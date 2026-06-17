#!/usr/bin/env python3
"""Probe raw fixture evidence for the frontier 80 five-byte bridge guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support_probe import (
    parse_guard_key,
)


DEFAULT_SUPPORT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/summary.csv"
)
DEFAULT_SUPPORT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/targets.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "manifest_rows",
    "fixture_rows",
    "segment_positions_scanned",
    "pair_any_rows",
    "pair_any_assets",
    "pair_any_non_target_rows",
    "pair_mod_rows",
    "pair_mod_assets",
    "pair_mod_non_target_rows",
    "formula_window_rows",
    "formula_exact_rows",
    "formula_exact_non_target_rows",
    "formula_known_full_windows",
    "formula_known_full_exact_rows",
    "formula_known_full_false_rows",
    "target_exact_rows",
    "target_only_exact_rows",
    "best_target_span",
    "best_guard_key",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SEGMENT_HIT_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "ref_offset",
    "control_ref_mod64",
    "segment_pair",
    "matches_pair",
    "matches_mod",
    "is_target_asset",
    "segment_context_hex",
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
    "known_full",
    "is_target_span",
    "window_verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_span(row: dict[str, str]) -> tuple[str, str, str, int, int]:
    span_key = row.get("span_key", "")
    start = -1
    end = -1
    if ":" in span_key and "-" in span_key:
        _, rest = span_key.split(":", 1)
        start_text, end_text = rest.split("-", 1)
        try:
            start = int(start_text)
            end = int(end_text)
        except ValueError:
            start = -1
            end = -1
    return row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), start, end


def span_key(frontier_id: str, start: int, end: int) -> str:
    return f"{frontier_id}:{start}-{end}"


def fixture_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {row_key(row): row for row in rows}


def context_hex(segment: bytes, ref: int, radius: int = 4) -> str:
    start = max(0, ref - radius)
    end = min(len(segment), ref + radius + 4)
    return segment[start:end].hex()


def formula_output(segment: bytes, ref: int, anchor: int) -> bytes:
    return bytes([(anchor - 1) & 0xFF, segment[ref + 3], (anchor - 1) & 0xFF, segment[ref + 2], anchor])


def window_verdict(exact: bool, known_full: bool, is_target: bool) -> str:
    if exact and known_full and not is_target:
        return "known_non_target_exact"
    if exact and is_target:
        return "target_exact"
    if exact:
        return "reference_non_target_exact"
    if known_full:
        return "known_false"
    return "reference_false"


def build(
    support_summary_rows: list[dict[str, str]],
    support_target_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    support_summary = support_summary_rows[0] if support_summary_rows else {}
    target_rows = support_target_rows
    target_assets = {(row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in target_rows}
    target_spans = {target_span(row) for row in target_rows}
    guard_parts = parse_guard_key(target_rows[0].get("guard_key", support_summary.get("best_guard_key", ""))) if target_rows else {}
    target_pair = guard_parts.get("segment_pair", "")
    target_mod = int(guard_parts.get("control_ref_mod64", "-1"))
    anchor_rel = int(guard_parts.get("anchor_rel", "-2"))
    span_length = int(guard_parts.get("span_length", "5"))
    fixtures = fixture_map(fixture_rows)
    issues: list[str] = []
    segment_hits: list[dict[str, str]] = []
    formula_windows: list[dict[str, str]] = []
    positions_scanned = 0

    for manifest in manifest_rows:
        key = row_key(manifest)
        segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment")
        if not segment:
            continue
        positions_scanned += max(0, len(segment) - 3)
        fixture = fixtures.get(key)
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected") if fixture else b""
        decoded = load_bytes(fixture.get("decoded_path", ""), issues, "decoded") if fixture else b""
        known_mask = load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask") if fixture else b""
        if fixture and expected and decoded and len(expected) != len(decoded):
            issues.append(f"{'|'.join(key)}:decoded_size_mismatch")
        if fixture and expected and known_mask and len(expected) != len(known_mask):
            issues.append(f"{'|'.join(key)}:known_mask_size_mismatch")

        asset = (manifest.get("archive_tag", ""), manifest.get("pcx_name", ""), manifest.get("frontier_id", ""))
        is_target_asset = asset in target_assets
        for ref in range(max(0, len(segment) - 3)):
            pair = segment[ref + 2 : ref + 4].hex()
            matches_pair = pair == target_pair
            if not matches_pair:
                continue
            matches_mod = ref % 64 == target_mod
            segment_hits.append(
                {
                    "rank": "",
                    "archive": manifest.get("archive", ""),
                    "archive_tag": manifest.get("archive_tag", ""),
                    "pcx_name": manifest.get("pcx_name", ""),
                    "frontier_id": manifest.get("frontier_id", ""),
                    "ref_offset": str(ref),
                    "control_ref_mod64": str(ref % 64),
                    "segment_pair": pair,
                    "matches_pair": "1",
                    "matches_mod": "1" if matches_mod else "0",
                    "is_target_asset": "1" if is_target_asset else "0",
                    "segment_context_hex": context_hex(segment, ref),
                }
            )
            if not matches_mod or not fixture or not expected or not decoded or not known_mask:
                continue
            first_start = max(0, -anchor_rel)
            last_start = max(first_start, len(expected) - span_length)
            for start in range(first_start, last_start + 1):
                end = start + span_length
                anchor_offset = start + anchor_rel
                if end > len(expected) or anchor_offset < 0 or anchor_offset >= min(len(decoded), len(known_mask)):
                    continue
                if not known_mask[anchor_offset]:
                    continue
                output = formula_output(segment, ref, decoded[anchor_offset])
                expected_hex = expected[start:end].hex()
                output_hex = output.hex()
                exact = expected_hex == output_hex
                known_full = end <= len(known_mask) and all(known_mask[start:end])
                target_key = (
                    manifest.get("archive_tag", ""),
                    manifest.get("pcx_name", ""),
                    manifest.get("frontier_id", ""),
                    start,
                    end,
                )
                is_target_span = target_key in target_spans
                formula_windows.append(
                    {
                        "rank": "",
                        "archive": manifest.get("archive", ""),
                        "archive_tag": manifest.get("archive_tag", ""),
                        "pcx_name": manifest.get("pcx_name", ""),
                        "frontier_id": manifest.get("frontier_id", ""),
                        "ref_offset": str(ref),
                        "span_start": str(start),
                        "span_end": str(end),
                        "span_key": span_key(manifest.get("frontier_id", ""), start, end),
                        "anchor_offset": str(anchor_offset),
                        "anchor_rel": str(anchor_rel),
                        "anchor_byte": f"{decoded[anchor_offset]:02x}",
                        "expected_hex": expected_hex,
                        "formula_output_hex": output_hex,
                        "formula_exact": "1" if exact else "0",
                        "known_full": "1" if known_full else "0",
                        "is_target_span": "1" if is_target_span else "0",
                        "window_verdict": window_verdict(exact, known_full, is_target_span),
                    }
                )

    segment_hits.sort(
        key=lambda row: (
            row.get("matches_mod") != "1",
            row.get("is_target_asset") != "1",
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "ref_offset"),
        )
    )
    for index, row in enumerate(segment_hits, start=1):
        row["rank"] = str(index)

    formula_windows.sort(
        key=lambda row: (
            row.get("formula_exact") != "1",
            row.get("is_target_span") != "1",
            row.get("known_full") != "1",
            int_value(row, "span_start"),
        )
    )
    for index, row in enumerate(formula_windows, start=1):
        row["rank"] = str(index)

    pair_any_assets = {
        (row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in segment_hits
    }
    pair_mod_rows = [row for row in segment_hits if row.get("matches_mod") == "1"]
    pair_mod_assets = {
        (row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in pair_mod_rows
    }
    formula_exact = [row for row in formula_windows if row.get("formula_exact") == "1"]
    exact_non_target = [row for row in formula_exact if row.get("is_target_span") != "1"]
    known_full = [row for row in formula_windows if row.get("known_full") == "1"]
    known_full_exact = [row for row in known_full if row.get("formula_exact") == "1"]
    known_full_false = [row for row in known_full if row.get("formula_exact") != "1"]
    target_exact = [row for row in formula_exact if row.get("is_target_span") == "1"]
    pair_mod_non_target = [row for row in pair_mod_rows if row.get("is_target_asset") != "1"]
    pair_any_non_target = [row for row in segment_hits if row.get("is_target_asset") != "1"]

    if known_full_exact and not known_full_false:
        verdict = "known_full_independent_evidence"
        next_probe = "promote independently supported frontier 80 five-byte guard"
        promotion_ready = support_summary.get("target_bytes", "0")
    elif exact_non_target:
        verdict = "reference_non_target_evidence"
        next_probe = "review non-target reference evidence for frontier 80 five-byte guard"
        promotion_ready = "0"
    elif target_exact and not pair_mod_non_target:
        verdict = "raw_fixture_target_only"
        next_probe = "expand five-byte guard evidence outside current fixture corpus"
        promotion_ready = "0"
    else:
        verdict = "raw_fixture_no_independent_evidence"
        next_probe = "derive alternate non-target evidence for frontier 80 five-byte guard"
        promotion_ready = "0"

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_independent_evidence_probe",
        "target_spans": support_summary.get("target_spans", str(len(target_rows))),
        "target_bytes": support_summary.get("target_bytes", "0"),
        "manifest_rows": str(len(manifest_rows)),
        "fixture_rows": str(len(fixture_rows)),
        "segment_positions_scanned": str(positions_scanned),
        "pair_any_rows": str(len(segment_hits)),
        "pair_any_assets": str(len(pair_any_assets)),
        "pair_any_non_target_rows": str(len(pair_any_non_target)),
        "pair_mod_rows": str(len(pair_mod_rows)),
        "pair_mod_assets": str(len(pair_mod_assets)),
        "pair_mod_non_target_rows": str(len(pair_mod_non_target)),
        "formula_window_rows": str(len(formula_windows)),
        "formula_exact_rows": str(len(formula_exact)),
        "formula_exact_non_target_rows": str(len(exact_non_target)),
        "formula_known_full_windows": str(len(known_full)),
        "formula_known_full_exact_rows": str(len(known_full_exact)),
        "formula_known_full_false_rows": str(len(known_full_false)),
        "target_exact_rows": str(len(target_exact)),
        "target_only_exact_rows": str(len(target_exact) if target_exact and not exact_non_target else 0),
        "best_target_span": support_summary.get("best_target_span", ""),
        "best_guard_key": support_summary.get("best_guard_key", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": promotion_ready,
        "issue_rows": str(len(issues)),
    }
    return summary, segment_hits, formula_windows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    segment_hits: list[dict[str, str]],
    formula_windows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "segment_hits": segment_hits, "formula_windows": formula_windows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("segment_hits.csv", output_dir / "segment_hits.csv"),
            ("formula_windows.csv", output_dir / "formula_windows.csv"),
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
  --bg: #101416;
  --panel: #171f22;
  --line: #314247;
  --text: #edf5f2;
  --muted: #9eafb4;
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
    <div class="muted">Scans raw fixture segments and expected windows without relying on segmentation operation rows.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Segment positions</div><div class="value">{summary['segment_positions_scanned']}</div></div>
    <div class="stat"><div class="muted">Pair+mod hits</div><div class="value">{summary['pair_mod_rows']}</div></div>
    <div class="stat"><div class="muted">Non-target exact</div><div class="value warn">{summary['formula_exact_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Known exact</div><div class="value warn">{summary['formula_known_full_exact_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Segment Hits</h2>{render_table(segment_hits, SEGMENT_HIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Formula Windows</h2>{render_table(formula_windows, WINDOW_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-independent-evidence-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe raw independent evidence for the frontier 80 five-byte guard.")
    parser.add_argument("--support-summary", type=Path, default=DEFAULT_SUPPORT_SUMMARY)
    parser.add_argument("--support-targets", type=Path, default=DEFAULT_SUPPORT_TARGETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Independent Evidence Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, segment_hits, formula_windows = build(
        read_rows(args.support_summary),
        read_rows(args.support_targets),
        read_rows(args.manifest),
        read_rows(args.fixtures),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "segment_hits.csv", SEGMENT_HIT_FIELDNAMES, segment_hits)
    write_csv(args.output / "formula_windows.csv", WINDOW_FIELDNAMES, formula_windows)
    (args.output / "index.html").write_text(
        build_html(summary, segment_hits, formula_windows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte independent evidence probe: "
        f"pair_mod={summary['pair_mod_rows']} "
        f"non_target_exact={summary['formula_exact_non_target_rows']} "
        f"known_exact={summary['formula_known_full_exact_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
