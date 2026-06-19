#!/usr/bin/env python3
"""Map segment/control bytes to fixed-dy1 signed small-delta tokens for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_literal_stream_probe as literal_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_mapping_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_GRAMMAR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_grammar_probe/summary.csv"
)
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)

TRANSFORMS = (
    "identity",
    "low2_signed",
    "low2_nonzero",
    "low3_signed",
    "low3_nonzero",
    "high3_signed",
    "low_nibble_signed",
    "low_nibble_small",
    "high_nibble_signed",
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "segment_bytes",
    "small_delta_pixels",
    "small_delta_token_rows",
    "large_delta_pixels",
    "best_transform",
    "best_source_bytes",
    "best_lcs_pixels",
    "best_lcs_ratio",
    "best_source_match_ratio",
    "best_exact_token_rows",
    "best_exact_token_pixels",
    "best_exact_token_ratio",
    "best_prefix_token_pixels",
    "best_prefix_token_ratio",
    "best_unmatched_small_delta_pixels",
    "best_unmatched_token_rows",
    "issue_rows",
    "small_delta_mapping_verdict",
    "next_action",
]

MAPPING_FIELDNAMES = [
    "rank",
    "transform",
    "source_bytes",
    "target_pixels",
    "lcs_pixels",
    "lcs_ratio",
    "source_match_ratio",
    "exact_token_rows",
    "exact_token_pixels",
    "exact_token_ratio",
    "prefix_token_pixels",
    "prefix_token_ratio",
    "unmatched_small_delta_pixels",
    "unmatched_token_rows",
]

TOKEN_FIELDNAMES = [
    "rank",
    "transform",
    "token_index",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "delta_signature",
    "exact_source_offset",
    "best_prefix_pixels",
    "best_prefix_source_offset",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def signed_bits(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    sign = 1 << (bits - 1)
    if value & sign:
        value -= 1 << bits
    return value & 0xFF


def signed_nibble(value: int) -> int:
    nibble = value & 0x0F
    return (nibble - 16 if nibble >= 8 else nibble) & 0xFF


def transform_segment(segment: bytes, transform: str) -> bytes:
    if transform == "identity":
        return segment
    if transform == "low2_signed":
        return bytes(signed_bits(value, 2) for value in segment)
    if transform == "low2_nonzero":
        values = [signed_bits(value, 2) for value in segment]
        return bytes(value for value in values if value != 0)
    if transform == "low3_signed":
        return bytes(signed_bits(value, 3) for value in segment)
    if transform == "low3_nonzero":
        values = [signed_bits(value, 3) for value in segment]
        return bytes(value for value in values if value != 0)
    if transform == "high3_signed":
        return bytes(signed_bits(value >> 5, 3) for value in segment)
    if transform == "low_nibble_signed":
        return bytes(signed_nibble(value) for value in segment)
    if transform == "low_nibble_small":
        values = [signed_nibble(value) for value in segment]
        return bytes(value for value in values if 1 <= abs(signed_byte(value)) <= 3)
    if transform == "high_nibble_signed":
        return bytes(signed_bits(value >> 4, 4) for value in segment)
    raise ValueError(f"unknown transform: {transform}")


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def token_signature(row: dict[str, str]) -> bytes:
    values: list[int] = []
    for part in row.get("delta_signature", "").split("|"):
        if part:
            values.append(int(part, 0) & 0xFF)
    return bytes(values)


def is_small_delta_pixel(row: dict[str, str], max_abs_delta: int) -> bool:
    value = abs(int_value(row, "delta_signed"))
    return 1 <= value <= max_abs_delta


def full_token_row(rows: list[dict[str, str]]) -> dict[str, str]:
    first = rows[0]
    last = rows[-1]
    return {
        "token_kind": "small_delta",
        "target_y": first.get("target_y", ""),
        "x_start": first.get("target_x", ""),
        "x_end": last.get("target_x", ""),
        "pixels": str(len(rows)),
        "target_absolute_start": first.get("target_absolute", ""),
        "target_absolute_end": last.get("target_absolute", ""),
        "delta_signature": "|".join(row.get("delta_signed", "") for row in rows),
    }


def full_small_delta_tokens(pixel_rows: list[dict[str, str]], max_abs_delta: int) -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    current: list[dict[str, str]] = []
    previous_y = -1
    previous_x = -2
    for row in pixel_rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        contiguous = y == previous_y and x == previous_x + 1
        small = is_small_delta_pixel(row, max_abs_delta)
        if current and (not contiguous or not small):
            tokens.append(full_token_row(current))
            current = []
        if small:
            current.append(row)
        previous_y = y
        previous_x = x
    if current:
        tokens.append(full_token_row(current))
    return tokens


def find_exact(source: bytes, needle: bytes) -> int:
    if not needle:
        return -1
    return source.find(needle)


def best_prefix(source: bytes, needle: bytes) -> tuple[int, int]:
    best_len = 0
    best_offset = -1
    if not source or not needle:
        return best_len, best_offset
    for offset in range(len(source)):
        length = 0
        while offset + length < len(source) and length < len(needle) and source[offset + length] == needle[length]:
            length += 1
        if length > best_len:
            best_len = length
            best_offset = offset
            if best_len == len(needle):
                break
    return best_len, best_offset


def build_token_rows(transform: str, source: bytes, tokens: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, token in enumerate(tokens, 1):
        signature = token_signature(token)
        exact_offset = find_exact(source, signature)
        prefix_pixels, prefix_offset = best_prefix(source, signature)
        verdict = "exact" if exact_offset >= 0 else "prefix" if prefix_pixels > 0 else "unmatched"
        rows.append(
            {
                "rank": "0",
                "transform": transform,
                "token_index": str(index),
                "target_y": token.get("target_y", ""),
                "x_start": token.get("x_start", ""),
                "x_end": token.get("x_end", ""),
                "pixels": token.get("pixels", ""),
                "delta_signature": token.get("delta_signature", ""),
                "exact_source_offset": str(exact_offset),
                "best_prefix_pixels": str(prefix_pixels),
                "best_prefix_source_offset": str(prefix_offset),
                "verdict": verdict,
            }
        )
    return rows


def summarize_mapping(transform: str, source: bytes, target: bytes, token_rows: list[dict[str, str]]) -> dict[str, str]:
    exact_rows = [row for row in token_rows if row.get("verdict") == "exact"]
    exact_pixels = sum(int_value(row, "pixels") for row in exact_rows)
    prefix_pixels = sum(int_value(row, "best_prefix_pixels") for row in token_rows)
    lcs = literal_probe.lcs_len(source, target)
    target_pixels = len(target)
    unmatched_pixels = max(0, target_pixels - exact_pixels)
    unmatched_tokens = sum(1 for row in token_rows if row.get("verdict") != "exact")
    return {
        "rank": "0",
        "transform": transform,
        "source_bytes": str(len(source)),
        "target_pixels": str(target_pixels),
        "lcs_pixels": str(lcs),
        "lcs_ratio": float_text(lcs / target_pixels if target_pixels else 0.0),
        "source_match_ratio": float_text(lcs / len(source) if source else 0.0),
        "exact_token_rows": str(len(exact_rows)),
        "exact_token_pixels": str(exact_pixels),
        "exact_token_ratio": float_text(exact_pixels / target_pixels if target_pixels else 0.0),
        "prefix_token_pixels": str(prefix_pixels),
        "prefix_token_ratio": float_text(prefix_pixels / target_pixels if target_pixels else 0.0),
        "unmatched_small_delta_pixels": str(unmatched_pixels),
        "unmatched_token_rows": str(unmatched_tokens),
    }


def best_mapping(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    return max(
        rows,
        key=lambda row: (
            float(row.get("lcs_ratio", "0") or 0),
            float(row.get("source_match_ratio", "0") or 0),
            int_value(row, "exact_token_pixels"),
        ),
    )


def build_summary(
    grammar_summary: dict[str, str],
    segment: bytes,
    mapping_rows: list[dict[str, str]],
    *,
    issues: list[str],
) -> dict[str, str]:
    best = best_mapping(mapping_rows)
    small_delta_pixels = int_value(grammar_summary, "small_delta_pixels")
    issue_rows = len(issues)
    best_lcs_ratio = float(best.get("lcs_ratio", "0") or 0)
    best_source_ratio = float(best.get("source_match_ratio", "0") or 0)
    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_mapping_issues"
        next_action = "fix shared 0x2700302b small-delta mapping inputs"
    elif best_lcs_ratio >= 0.30 and best_source_ratio >= 0.75:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_low2_source_partial"
        next_action = (
            "derive low2 signed selector for shared 0x2700302b small-delta stream; "
            f"{best.get('lcs_pixels', '0')}/{small_delta_pixels} small-delta pixels align, "
            f"{grammar_summary.get('large_delta_pixels', '0')} large-delta pixels remain"
        )
    elif best_lcs_ratio >= 0.20:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_mapping_weak_partial"
        next_action = (
            "split shared 0x2700302b small-delta tokens by source transform before promotion; "
            f"best {best.get('transform', '')} covers {best.get('lcs_pixels', '0')}/{small_delta_pixels}"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_mapping_weak"
        next_action = "seek non-segment source for shared 0x2700302b signed small-delta tokens"
    return {
        "scope": "total",
        "archive": grammar_summary.get("archive", ""),
        "archive_tag": grammar_summary.get("archive_tag", ""),
        "pcx_name": grammar_summary.get("pcx_name", ""),
        "frontier_id": grammar_summary.get("frontier_id", ""),
        "dy": grammar_summary.get("dy", ""),
        "shift": grammar_summary.get("shift", ""),
        "segment_bytes": str(len(segment)),
        "small_delta_pixels": grammar_summary.get("small_delta_pixels", "0"),
        "small_delta_token_rows": grammar_summary.get("small_delta_token_rows", "0"),
        "large_delta_pixels": grammar_summary.get("large_delta_pixels", "0"),
        "best_transform": best.get("transform", ""),
        "best_source_bytes": best.get("source_bytes", "0"),
        "best_lcs_pixels": best.get("lcs_pixels", "0"),
        "best_lcs_ratio": best.get("lcs_ratio", "0"),
        "best_source_match_ratio": best.get("source_match_ratio", "0"),
        "best_exact_token_rows": best.get("exact_token_rows", "0"),
        "best_exact_token_pixels": best.get("exact_token_pixels", "0"),
        "best_exact_token_ratio": best.get("exact_token_ratio", "0"),
        "best_prefix_token_pixels": best.get("prefix_token_pixels", "0"),
        "best_prefix_token_ratio": best.get("prefix_token_ratio", "0"),
        "best_unmatched_small_delta_pixels": best.get("unmatched_small_delta_pixels", "0"),
        "best_unmatched_token_rows": best.get("unmatched_token_rows", "0"),
        "issue_rows": str(issue_rows),
        "small_delta_mapping_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fieldnames: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fieldnames) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    mapping_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "mapping": mapping_rows, "tokens": token_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("mapping", output_dir / "mapping.csv"),
            ("token_support", output_dir / "token_support.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; background: #101114; color: #eceff4; }}
a {{ color: #8ec5ff; margin-right: 12px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
.stat {{ background: #1b1d22; border: 1px solid #343842; padding: 12px; border-radius: 6px; }}
.label {{ color: #a9b0bd; font-size: 12px; text-transform: uppercase; }}
.value {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; margin: 18px 0 28px; background: #17191e; }}
th, td {{ border-bottom: 1px solid #343842; padding: 7px 9px; text-align: left; font-size: 12px; vertical-align: top; }}
th {{ color: #cfd6e4; background: #22252c; position: sticky; top: 0; }}
td {{ max-width: 380px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Best Transform</div><div class="value">{html.escape(summary['best_transform'])}</div></div>
  <div class="stat"><div class="label">Best LCS</div><div class="value">{html.escape(summary['best_lcs_pixels'])}</div></div>
  <div class="stat"><div class="label">Best LCS Ratio</div><div class="value">{html.escape(summary['best_lcs_ratio'])}</div></div>
  <div class="stat"><div class="label">Source Match</div><div class="value">{html.escape(summary['best_source_match_ratio'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Mapping</h2>{render_table(mapping_rows, MAPPING_FIELDNAMES)}
<h2>Token Support</h2>{render_table(token_rows[:160], TOKEN_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    grammar_summary = read_summary(args.grammar_summary)
    if not grammar_summary:
        issues.append("missing_grammar_summary")
    residual_pixel_rows = read_csv(args.residual_pixels)
    if not residual_pixel_rows:
        issues.append("missing_residual_pixels")
    token_source_rows = full_small_delta_tokens(residual_pixel_rows, args.max_abs_delta)
    if not token_source_rows:
        issues.append("missing_small_delta_tokens")
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    frontier, _comparison, _pixels, _width, segment, load_issues = residual_profile.load_reference(load_args)
    issues.extend(load_issues)
    target = b"".join(token_signature(row) for row in token_source_rows)
    mapping_rows: list[dict[str, str]] = []
    all_token_rows: list[dict[str, str]] = []
    for transform in TRANSFORMS:
        source = transform_segment(segment, transform)
        token_rows = build_token_rows(transform, source, token_source_rows)
        mapping_rows.append(summarize_mapping(transform, source, target, token_rows))
        all_token_rows.extend(token_rows)
    mapping_rows.sort(
        key=lambda row: (
            float(row.get("lcs_ratio", "0") or 0),
            float(row.get("source_match_ratio", "0") or 0),
            int_value(row, "exact_token_pixels"),
        ),
        reverse=True,
    )
    for rank, row in enumerate(mapping_rows, 1):
        row["rank"] = str(rank)
    transform_rank = {row["transform"]: row["rank"] for row in mapping_rows}
    all_token_rows.sort(
        key=lambda row: (
            int(transform_rank.get(row.get("transform", ""), "999")),
            int_value(row, "token_index"),
        )
    )
    for rank, row in enumerate(all_token_rows, 1):
        row["rank"] = str(rank)
    summary = build_summary(grammar_summary or frontier, segment, mapping_rows, issues=issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "mapping.csv", MAPPING_FIELDNAMES, mapping_rows)
    write_csv(args.output / "token_support.csv", TOKEN_FIELDNAMES, all_token_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, mapping_rows, all_token_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, mapping_rows, all_token_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Map shared 0x2700302b small-delta tokens to segment transforms.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--grammar-summary", type=Path, default=DEFAULT_GRAMMAR_SUMMARY)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--max-abs-delta", type=int, default=3)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Small-Delta Mapping")
    args = parser.parse_args()
    summary, _mapping, _tokens = write_report(args)
    print(f"Best transform: {summary['best_transform']}")
    print(f"Best LCS pixels: {summary['best_lcs_pixels']}")
    print(f"Best LCS ratio: {summary['best_lcs_ratio']}")
    print(f"Best source match ratio: {summary['best_source_match_ratio']}")
    print(f"Verdict: {summary['small_delta_mapping_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
