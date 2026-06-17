#!/usr/bin/env python3
"""Probe expanded gap-rule fixtures for frontier 80 five-byte bridge evidence."""

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
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "manifest_rows",
    "segment_positions_scanned",
    "pair_any_rows",
    "pair_any_assets",
    "pair_any_non_target_rows",
    "pair_mod_rows",
    "pair_mod_assets",
    "pair_mod_non_target_rows",
    "reference_window_rows",
    "reference_exact_rows",
    "reference_exact_non_target_rows",
    "target_exact_rows",
    "target_only_exact_rows",
    "pair_mod_non_target_frontiers",
    "best_target_span",
    "best_guard_key",
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
    "segment_pair",
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


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def parse_target_span(row: dict[str, str]) -> tuple[str, str, str, int, int]:
    span_key = row.get("span_key", "")
    start = -1
    end = -1
    if ":" in span_key and "-" in span_key:
        _frontier, bounds = span_key.split(":", 1)
        start_text, end_text = bounds.split("-", 1)
        try:
            start = int(start_text)
            end = int(end_text)
        except ValueError:
            start = -1
            end = -1
    return row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), start, end


def span_key(frontier_id: str, start: int, end: int) -> str:
    return f"{frontier_id}:{start}-{end}"


def context_hex(segment: bytes, ref: int, radius: int = 4) -> str:
    start = max(0, ref - radius)
    end = min(len(segment), ref + radius + 4)
    return segment[start:end].hex()


def formula_output(segment: bytes, ref: int, anchor: int) -> bytes:
    return bytes([(anchor - 1) & 0xFF, segment[ref + 3], (anchor - 1) & 0xFF, segment[ref + 2], anchor])


def target_identity(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def window_verdict(exact: bool, is_target: bool) -> str:
    if exact and is_target:
        return "target_reference_exact"
    if exact:
        return "non_target_reference_exact"
    return "reference_false"


def build(
    support_summary_rows: list[dict[str, str]],
    support_target_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    false_samples_per_hit: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    support_summary = support_summary_rows[0] if support_summary_rows else {}
    target_rows = support_target_rows
    target_assets = {target_identity(row) for row in target_rows}
    target_spans = {parse_target_span(row) for row in target_rows}
    guard_parts = parse_guard_key(target_rows[0].get("guard_key", support_summary.get("best_guard_key", ""))) if target_rows else {}
    target_pair = guard_parts.get("segment_pair", "")
    target_mod = int(guard_parts.get("control_ref_mod64", "-1"))
    anchor_rel = int(guard_parts.get("anchor_rel", "-2"))
    span_length = int(guard_parts.get("span_length", "5"))

    issues: list[str] = []
    hits: list[dict[str, str]] = []
    windows: list[dict[str, str]] = []
    positions_scanned = 0
    reference_window_rows = 0
    reference_exact_rows = 0
    reference_exact_non_target_rows = 0
    target_exact_rows = 0

    for manifest in manifest_rows:
        segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        if not segment or not expected:
            continue
        positions_scanned += max(0, len(segment) - 3)
        asset = target_identity(manifest)
        is_target_asset = asset in target_assets
        for ref in range(max(0, len(segment) - 3)):
            pair = segment[ref + 2 : ref + 4].hex()
            if pair != target_pair:
                continue
            matches_mod = ref % 64 == target_mod
            hits.append(
                {
                    "rank": "",
                    "archive": manifest.get("archive", ""),
                    "archive_tag": manifest.get("archive_tag", ""),
                    "pcx_name": manifest.get("pcx_name", ""),
                    "frontier_id": manifest.get("frontier_id", ""),
                    "ref_offset": str(ref),
                    "control_ref_mod64": str(ref % 64),
                    "segment_pair": pair,
                    "matches_mod": "1" if matches_mod else "0",
                    "is_target_asset": "1" if is_target_asset else "0",
                    "segment_context_hex": context_hex(segment, ref),
                }
            )
            if not matches_mod:
                continue

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
                exact = expected_hex == output_hex
                target_key = (
                    manifest.get("archive_tag", ""),
                    manifest.get("pcx_name", ""),
                    manifest.get("frontier_id", ""),
                    start,
                    end,
                )
                is_target_span = target_key in target_spans
                sampled = exact or false_samples < false_samples_per_hit
                if not sampled:
                    continue
                if not exact:
                    false_samples += 1
                if exact:
                    reference_exact_rows += 1
                    if is_target_span:
                        target_exact_rows += 1
                    else:
                        reference_exact_non_target_rows += 1
                windows.append(
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
                        "anchor_byte": f"{anchor:02x}",
                        "expected_hex": expected_hex,
                        "formula_output_hex": output_hex,
                        "formula_exact": "1" if exact else "0",
                        "is_target_span": "1" if is_target_span else "0",
                        "window_verdict": window_verdict(exact, is_target_span),
                        "sampled": "1",
                    }
                )

    hits.sort(
        key=lambda row: (
            row.get("matches_mod") != "1",
            row.get("is_target_asset") != "1",
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "ref_offset"),
        )
    )
    for index, row in enumerate(hits, start=1):
        row["rank"] = str(index)

    windows.sort(
        key=lambda row: (
            row.get("formula_exact") != "1",
            row.get("is_target_span") != "1",
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "span_start"),
        )
    )
    for index, row in enumerate(windows, start=1):
        row["rank"] = str(index)

    pair_any_assets = {target_identity(row) for row in hits}
    pair_any_non_target = [row for row in hits if row.get("is_target_asset") != "1"]
    pair_mod_hits = [row for row in hits if row.get("matches_mod") == "1"]
    pair_mod_assets = {target_identity(row) for row in pair_mod_hits}
    pair_mod_non_target = [row for row in pair_mod_hits if row.get("is_target_asset") != "1"]
    pair_mod_non_target_frontiers = ",".join(
        sorted({row.get("frontier_id", "") for row in pair_mod_non_target}, key=lambda value: int(value or 0))
    )

    if reference_exact_non_target_rows:
        verdict = "expanded_reference_non_target_evidence"
        next_probe = "review expanded non-target reference evidence for frontier 80 five-byte guard"
    elif pair_mod_non_target:
        verdict = "expanded_pair_mod_without_formula_exact"
        next_probe = "inspect expanded pair-mod non-target rows for alternate five-byte guard"
    elif target_exact_rows:
        verdict = "expanded_target_only_reference"
        next_probe = "expand five-byte guard evidence beyond gap-rule queue"
    else:
        verdict = "expanded_no_reference_evidence"
        next_probe = "derive alternate non-target evidence for frontier 80 five-byte guard"

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_expanded_corpus_probe",
        "target_spans": support_summary.get("target_spans", str(len(target_rows))),
        "target_bytes": support_summary.get("target_bytes", "0"),
        "manifest_rows": str(len(manifest_rows)),
        "segment_positions_scanned": str(positions_scanned),
        "pair_any_rows": str(len(hits)),
        "pair_any_assets": str(len(pair_any_assets)),
        "pair_any_non_target_rows": str(len(pair_any_non_target)),
        "pair_mod_rows": str(len(pair_mod_hits)),
        "pair_mod_assets": str(len(pair_mod_assets)),
        "pair_mod_non_target_rows": str(len(pair_mod_non_target)),
        "reference_window_rows": str(reference_window_rows),
        "reference_exact_rows": str(reference_exact_rows),
        "reference_exact_non_target_rows": str(reference_exact_non_target_rows),
        "target_exact_rows": str(target_exact_rows),
        "target_only_exact_rows": str(target_exact_rows if target_exact_rows and not reference_exact_non_target_rows else 0),
        "pair_mod_non_target_frontiers": pair_mod_non_target_frontiers,
        "best_target_span": support_summary.get("best_target_span", ""),
        "best_guard_key": support_summary.get("best_guard_key", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, hits, windows


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
    <div class="muted">Scans all expanded gap-rule fixtures using reference anchors for non-target five-byte evidence.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Manifest rows</div><div class="value">{summary['manifest_rows']}</div></div>
    <div class="stat"><div class="muted">Pair+mod hits</div><div class="value">{summary['pair_mod_rows']}</div></div>
    <div class="stat"><div class="muted">Pair+mod non-target</div><div class="value">{summary['pair_mod_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Exact non-target</div><div class="value warn">{summary['reference_exact_non_target_rows']}</div></div>
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
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-expanded-corpus-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe expanded fixture evidence for the frontier 80 five-byte guard.")
    parser.add_argument("--support-summary", type=Path, default=DEFAULT_SUPPORT_SUMMARY)
    parser.add_argument("--support-targets", type=Path, default=DEFAULT_SUPPORT_TARGETS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--false-samples-per-hit", type=int, default=6)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Expanded Corpus Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, hits, windows = build(
        read_rows(args.support_summary),
        read_rows(args.support_targets),
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
        "External terminal spatial bridge five-byte expanded corpus probe: "
        f"pair_mod={summary['pair_mod_rows']} "
        f"non_target_pair_mod={summary['pair_mod_non_target_rows']} "
        f"non_target_exact={summary['reference_exact_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
