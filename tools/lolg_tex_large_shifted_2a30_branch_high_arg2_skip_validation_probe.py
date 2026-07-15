#!/usr/bin/env python3
"""Validate skip-only high-arg2 cmd20 grammar for the guarded 0x2a30 branch."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

try:
    from export_shp import read_palette
    from export_te_span_previews import render_indexed
    from score_te_raw_layouts import row_score
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    read_palette = None
    render_indexed = None
    row_score = None
else:
    OPTIONAL_IMPORT_ERROR = None
from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import catalog_payloads, key_for
from probe_te_span_decode import decode_span


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_high_arg2_skip_validation_probe")
DEFAULT_GRAMMAR_SUMMARY = Path("output/tex_large_shifted_2a30_branch_guarded_renderer_grammar_probe/summary.csv")
DEFAULT_RENDERER_TRACE = Path("output/tex_large_shifted_2a30_branch_selector_probe/renderer_trace.csv")
DEFAULT_SUPPORT_TRACE = Path("output/tex_large_shifted_2a30_branch_trace_probe/candidates.csv")
DEFAULT_BOUNDED_FAMILY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/family.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_PALETTE = Path("extracted/LOCAL/7231c8f9.pal")

SUMMARY_FIELDNAMES = [
    "scope",
    "grammar_target_high_arg2_rows",
    "grammar_support_rank1_high_arg2_max",
    "target_archive_tag",
    "target_pcx_name",
    "target_start",
    "target_current_mode",
    "target_proposed_mode",
    "target_current_score",
    "target_proposed_score",
    "target_score_delta",
    "target_pixels_equal",
    "target_changed_ratio",
    "target_high_arg2_skips",
    "target_zero_signature_seen",
    "target_zero_signature_skipped",
    "target_markerknown_skips",
    "support_rank1_rows",
    "support_applicable_rows",
    "support_applicable_high_arg2_skip_max",
    "support_high_arg2_skip_max",
    "support_forced_nonapplicable_high_arg2_skip_max",
    "support_zero_signature_seen_max",
    "support_zero_signature_skipped_max",
    "support_proposed_changed_rows",
    "variant_rows",
    "preview_rows",
    "issue_rows",
    "validation_verdict",
    "next_action",
]

VARIANT_FIELDNAMES = [
    "role",
    "archive_tag",
    "pcx_name",
    "variant",
    "start",
    "mode",
    "width",
    "height",
    "score",
    "score_delta_vs_current",
    "filled_ratio",
    "unique_colors",
    "high_arg2_skips",
    "zero_signature_seen",
    "zero_signature_skipped",
    "markerknown_skips",
    "final_x",
    "final_y",
    "pixels_equal_current",
    "changed_ratio_vs_current",
    "preview_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_text(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value), 0) if value not in (None, "") else default
    except ValueError:
        return default


def float_text(value: str | float | None, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def visible_ratio(pixels: bytes) -> float:
    return sum(1 for pixel in pixels if pixel) / max(1, len(pixels))


def changed_ratio(pixels: bytes, baseline: bytes) -> float:
    total = min(len(pixels), len(baseline))
    if total <= 0:
        return 0.0
    return sum(1 for index in range(total) if pixels[index] != baseline[index]) / total


def score_pixels(pixels: bytes, width: int, height: int) -> float:
    score = row_score(pixels, width, height)
    return float(score) if score is not None else 999999.0


def marker_lookup(family_rows: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    return {
        key_for(row.get("archive_tag", ""), row.get("pcx_name", "")): int_text(row.get("marker_pos"), -1)
        for row in family_rows
    }


def trace_start(row: dict[str, str], markers: dict[tuple[str, str], int]) -> int:
    start = int_text(row.get("start"), -1)
    if start >= 0:
        return start
    key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
    marker = markers.get(key, -1)
    if marker >= 0 and row.get("extra", "") != "":
        return marker + int_text(row.get("extra"))
    return -1


def proposed_mode(current_mode: str) -> str:
    suffix = "_markerknown" if current_mode.endswith("_markerknown") else ""
    return f"cmd20_high_arg2_skip4{suffix}"


def best_target_row(renderer_rows: list[dict[str, str]], grammar_summary: dict[str, str]) -> dict[str, str]:
    target_key = key_for(grammar_summary.get("target_archive_tag", ""), grammar_summary.get("target_pcx_name", ""))
    candidates = [
        row for row in renderer_rows if key_for(row.get("archive_tag", ""), row.get("pcx_name", "")) == target_key
    ]
    return min(candidates, key=lambda row: (float_text(row.get("score")), int_text(row.get("rank"))), default={})


def support_rank1_rows(support_rows: list[dict[str, str]], target: dict[str, str]) -> list[dict[str, str]]:
    target_key = key_for(target.get("archive_tag", ""), target.get("pcx_name", ""))
    rows = [
        row
        for row in support_rows
        if int_text(row.get("rank")) == 1
        and key_for(row.get("archive_tag", ""), row.get("pcx_name", "")) != target_key
    ]
    return sorted(rows, key=lambda row: (row.get("archive_tag", ""), row.get("pcx_name", "")))


def render_variant_preview(
    pixels: bytes,
    width: int,
    height: int,
    palette: list[tuple[int, int, int]],
    output_dir: Path,
    row: dict[str, str],
    variant: str,
) -> str:
    out_dir = output_dir / "previews" / safe_name(row.get("archive_tag", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_name(row.get('pcx_name', ''))}_{safe_name(variant)}.png"
    render_indexed(pixels, width, height, palette).save(path)
    return path.as_posix()


def build_variant_rows(
    grammar_summary: dict[str, str],
    renderer_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    catalog: Path,
    palette_path: Path,
    output_dir: Path,
    low: int,
    high: int,
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[str] = []
    target = best_target_row(renderer_rows, grammar_summary)
    if not target:
        return [], ["missing_target_renderer_row"]
    selected_rows = [("target", target)] + [("support_rank1", row) for row in support_rank1_rows(support_rows, target)]
    markers = marker_lookup(family_rows)
    payloads = catalog_payloads(
        catalog,
        [{"level": row.get("archive_tag", ""), "name": row.get("pcx_name", "")} for row in family_rows],
    )
    palette = read_palette(palette_path)
    variant_rows: list[dict[str, str]] = []

    for role, row in selected_rows:
        key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
        payload = payloads.get(key, b"")
        start = trace_start(row, markers)
        width = int_text(row.get("width"))
        height = int_text(row.get("height"))
        current_mode = row.get("mode", "")
        if not payload:
            issues.append(f"missing_payload:{key[0]}/{key[1]}")
            continue
        if start < 0 or start >= len(payload) or width <= 0 or height <= 0 or not current_mode:
            issues.append(f"invalid_variant_input:{key[0]}/{key[1]}:{row.get('rank', '')}")
            continue

        current_pixels, current_stats = decode_span(
            payload[start:],
            width,
            height,
            current_mode,
            low,
            high,
            return_stats=True,
        )
        current_score = score_pixels(current_pixels, width, height)
        current_preview = render_variant_preview(
            current_pixels,
            width,
            height,
            palette,
            output_dir,
            row,
            f"{role}_current",
        )
        current_variant = {
            "role": role,
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "variant": "current",
            "start": str(start),
            "mode": current_mode,
            "width": str(width),
            "height": str(height),
            "score": f"{current_score:.4f}",
            "score_delta_vs_current": "0.0000",
            "filled_ratio": f"{visible_ratio(current_pixels):.4f}",
            "unique_colors": str(len(set(current_pixels))),
            "high_arg2_skips": "",
            "zero_signature_seen": "",
            "zero_signature_skipped": "",
            "markerknown_skips": str(current_stats.get("control", 0)),
            "final_x": str(current_stats.get("final_x", "")),
            "final_y": str(current_stats.get("final_y", "")),
            "pixels_equal_current": "yes",
            "changed_ratio_vs_current": "0.0000",
            "preview_path": current_preview,
        }
        variant_rows.append(current_variant)

        local_mode = proposed_mode(current_mode)
        proposed_pixels, proposed_stats = decode_span(
            payload[start:],
            width,
            height,
            local_mode,
            low,
            high,
            return_stats=True,
        )
        proposed_score = score_pixels(proposed_pixels, width, height)
        proposed_preview = render_variant_preview(
            proposed_pixels,
            width,
            height,
            palette,
            output_dir,
            row,
            f"{role}_high_arg2_skip",
        )
        variant_rows.append(
            {
                "role": role,
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "variant": "high_arg2_skip_only",
                "start": str(start),
                "mode": local_mode,
                "width": str(width),
                "height": str(height),
                "score": f"{proposed_score:.4f}",
                "score_delta_vs_current": f"{proposed_score - current_score:.4f}",
                "filled_ratio": f"{visible_ratio(proposed_pixels):.4f}",
                "unique_colors": str(len(set(proposed_pixels))),
                "high_arg2_skips": str(proposed_stats.get("high_arg2_skips", 0)),
                "zero_signature_seen": str(proposed_stats.get("zero_signature_seen", 0)),
                "zero_signature_skipped": str(proposed_stats.get("zero_signature_skipped", 0)),
                "markerknown_skips": str(proposed_stats.get("markerknown_skips", 0)),
                "final_x": str(proposed_stats.get("final_x", "")),
                "final_y": str(proposed_stats.get("final_y", "")),
                "pixels_equal_current": "yes" if proposed_pixels == current_pixels else "no",
                "changed_ratio_vs_current": f"{changed_ratio(proposed_pixels, current_pixels):.4f}",
                "preview_path": proposed_preview,
            }
        )
    return variant_rows, issues


def build_summary(grammar_summary: dict[str, str], variant_rows: list[dict[str, str]], issues: list[str]) -> dict[str, str]:
    target_current = next((row for row in variant_rows if row.get("role") == "target" and row.get("variant") == "current"), {})
    target_proposed = next(
        (row for row in variant_rows if row.get("role") == "target" and row.get("variant") == "high_arg2_skip_only"),
        {},
    )
    support_proposed = [
        row for row in variant_rows if row.get("role") == "support_rank1" and row.get("variant") == "high_arg2_skip_only"
    ]
    support_current_by_key = {
        key_for(row.get("archive_tag", ""), row.get("pcx_name", "")): row
        for row in variant_rows
        if row.get("role") == "support_rank1" and row.get("variant") == "current"
    }
    support_applicable = [
        row
        for row in support_proposed
        if support_current_by_key.get(key_for(row.get("archive_tag", ""), row.get("pcx_name", "")), {})
        .get("mode", "")
        .startswith("cmd20")
    ]
    support_nonapplicable = [
        row
        for row in support_proposed
        if not support_current_by_key.get(key_for(row.get("archive_tag", ""), row.get("pcx_name", "")), {})
        .get("mode", "")
        .startswith("cmd20")
    ]
    support_changed = [row for row in support_proposed if row.get("pixels_equal_current") != "yes"]
    target_exact = target_proposed.get("pixels_equal_current") == "yes"
    target_high = int_text(target_proposed.get("high_arg2_skips"))
    support_high_max = max((int_text(row.get("high_arg2_skips")) for row in support_proposed), default=0)
    support_applicable_high_max = max((int_text(row.get("high_arg2_skips")) for row in support_applicable), default=0)
    support_forced_nonapplicable_high_max = max(
        (int_text(row.get("high_arg2_skips")) for row in support_nonapplicable),
        default=0,
    )
    support_zero_seen_max = max((int_text(row.get("zero_signature_seen")) for row in support_proposed), default=0)
    support_zero_skipped_max = max((int_text(row.get("zero_signature_skipped")) for row in support_proposed), default=0)
    if issues:
        verdict = "high_arg2_skip_validation_issues"
        next_action = "fix guarded high-arg2 skip validation inputs"
    elif target_exact and target_high > 0 and support_applicable_high_max == 0:
        verdict = "high_arg2_skip_only_integrated_for_guarded_extra64"
        next_action = "promote high-arg2 skip-only renderer through guarded 0x2a30 branch route"
    elif target_high <= 0:
        verdict = "high_arg2_skip_validation_missing_target_commands"
        next_action = "recheck guarded 0x2a30 target command extraction"
    else:
        verdict = "high_arg2_skip_validation_ambiguous"
        next_action = "broaden guarded high-arg2 skip validation before renderer integration"
    return {
        "scope": "total",
        "grammar_target_high_arg2_rows": grammar_summary.get("target_sig_high_arg2_skip_rows", "0"),
        "grammar_support_rank1_high_arg2_max": grammar_summary.get("support_rank1_sig_high_arg2_skip_max", "0"),
        "target_archive_tag": target_current.get("archive_tag", ""),
        "target_pcx_name": target_current.get("pcx_name", ""),
        "target_start": target_current.get("start", ""),
        "target_current_mode": target_current.get("mode", ""),
        "target_proposed_mode": target_proposed.get("mode", ""),
        "target_current_score": target_current.get("score", ""),
        "target_proposed_score": target_proposed.get("score", ""),
        "target_score_delta": target_proposed.get("score_delta_vs_current", ""),
        "target_pixels_equal": target_proposed.get("pixels_equal_current", ""),
        "target_changed_ratio": target_proposed.get("changed_ratio_vs_current", ""),
        "target_high_arg2_skips": target_proposed.get("high_arg2_skips", ""),
        "target_zero_signature_seen": target_proposed.get("zero_signature_seen", ""),
        "target_zero_signature_skipped": target_proposed.get("zero_signature_skipped", ""),
        "target_markerknown_skips": target_proposed.get("markerknown_skips", ""),
        "support_rank1_rows": str(len(support_proposed)),
        "support_applicable_rows": str(len(support_applicable)),
        "support_applicable_high_arg2_skip_max": str(support_applicable_high_max),
        "support_high_arg2_skip_max": str(support_high_max),
        "support_forced_nonapplicable_high_arg2_skip_max": str(support_forced_nonapplicable_high_max),
        "support_zero_signature_seen_max": str(support_zero_seen_max),
        "support_zero_signature_skipped_max": str(support_zero_skipped_max),
        "support_proposed_changed_rows": str(len(support_changed)),
        "variant_rows": str(len(variant_rows)),
        "preview_rows": str(sum(1 for row in variant_rows if row.get("preview_path"))),
        "issue_rows": str(len(issues)),
        "validation_verdict": verdict,
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(summary: dict[str, str], variant_rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "variants": variant_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("variants.csv", output_dir / "variants.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Validates a stricter cmd20 high-arg2 skip-only renderer against the current rank1 candidate.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Variants</h2>
{render_table(variant_rows, VARIANT_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_HIGH_ARG2_SKIP_VALIDATION_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    grammar_summary = (read_csv(args.grammar_summary) or [{}])[0]
    renderer_rows = read_csv(args.renderer_trace)
    support_rows = read_csv(args.support_trace)
    family_rows = read_csv(args.bounded_family)
    if not grammar_summary:
        issues.append("missing_grammar_summary")
    if not renderer_rows and grammar_summary.get("trace_candidate_rows") not in ("", "0"):
        issues.append("missing_renderer_trace")
    if not support_rows and grammar_summary.get("trace_candidate_rows") not in ("", "0"):
        issues.append("missing_support_trace")
    if not family_rows and grammar_summary.get("route_branch_start_guard_rows") not in ("", "0"):
        issues.append("missing_bounded_family")
    if not renderer_rows and not support_rows and not family_rows:
        variant_rows: list[dict[str, str]] = []
        summary = build_summary(grammar_summary, variant_rows, issues)
        write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variant_rows)
        (args.output / "index.html").write_text(
            build_html(summary, variant_rows, args.output, args.title),
            encoding="utf-8",
        )
        return summary, issues
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    variant_rows, variant_issues = build_variant_rows(
        grammar_summary,
        renderer_rows,
        support_rows,
        family_rows,
        args.catalog,
        args.palette,
        args.output,
        args.low,
        args.high,
    )
    issues.extend(variant_issues)
    summary = build_summary(grammar_summary, variant_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variant_rows)
    (args.output / "index.html").write_text(build_html(summary, variant_rows, args.output, args.title), encoding="utf-8")
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate skip-only high-arg2 cmd20 grammar for the guarded 0x2a30 branch."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--grammar-summary", type=Path, default=DEFAULT_GRAMMAR_SUMMARY)
    parser.add_argument("--renderer-trace", type=Path, default=DEFAULT_RENDERER_TRACE)
    parser.add_argument("--support-trace", type=Path, default=DEFAULT_SUPPORT_TRACE)
    parser.add_argument("--bounded-family", type=Path, default=DEFAULT_BOUNDED_FAMILY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--palette", type=Path, default=DEFAULT_PALETTE)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch High-Arg2 Skip Validation Probe",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Target pixels equal: {summary['target_pixels_equal']}")
    print(f"Target high-arg2 skips: {summary['target_high_arg2_skips']}")
    print(f"Support high-arg2 skip max: {summary['support_high_arg2_skip_max']}")
    print(f"Support applicable high-arg2 skip max: {summary['support_applicable_high_arg2_skip_max']}")
    print(
        "Support forced nonapplicable high-arg2 skip max: "
        f"{summary['support_forced_nonapplicable_high_arg2_skip_max']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Validation verdict: {summary['validation_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
