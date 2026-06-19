#!/usr/bin/env python3
"""Profile residual nonzero pixels after fixed dy1/shift0 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_replay_probe as fixed_replay
import lolg_tex_large_shared_2700302b_reference_frontier_probe as frontier_probe
import lolg_tex_large_shared_2700302b_reference_literal_stream_probe as literal_probe
import lolg_tex_large_shared_2700302b_reference_spatial_backref_probe as spatial_probe


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe")
DEFAULT_FRONTIERS = frontier_probe.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = frontier_probe.DEFAULT_COMPARISONS
DEFAULT_FIXED_REPLAY_SUMMARY = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_replay_probe/summary.csv")

STREAM_SOURCES = (
    ("segment_identity", "target", "identity"),
    ("segment_30_bf", "target", "30_bf"),
    ("segment_50_7f", "target", "50_7f"),
    ("segment_identity_delta", "delta", "identity"),
    ("segment_low_nibble_signed_delta", "delta", "low_nibble_signed"),
    ("segment_high_nibble_signed_delta", "delta", "high_nibble_signed"),
    ("segment_low2_signed_delta", "delta", "low2_signed"),
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "segment_bytes",
    "residual_nonzero_pixels",
    "residual_run_rows",
    "max_residual_run_pixels",
    "dy",
    "shift",
    "target_unique_values",
    "source_unique_values",
    "delta_unique_values",
    "tiny_delta_pixels",
    "tiny_delta_ratio",
    "small_delta_pixels",
    "small_delta_ratio",
    "positive_small_delta_pixels",
    "negative_small_delta_pixels",
    "source_zero_residual_pixels",
    "best_target_lcs_source",
    "best_target_lcs_bytes",
    "best_target_lcs_ratio",
    "best_delta_lcs_source",
    "best_delta_lcs_bytes",
    "best_delta_lcs_ratio",
    "fixed_replay_residual_nonzero_pixels",
    "fixed_replay_gap_pixels",
    "issue_rows",
    "residual_profile_verdict",
    "next_action",
]

PIXEL_FIELDNAMES = [
    "target_y",
    "target_x",
    "target_absolute",
    "source_y",
    "source_x",
    "target_value_hex",
    "source_value_hex",
    "delta_hex",
    "delta_signed",
    "abs_delta",
]

DELTA_FIELDNAMES = [
    "rank",
    "delta_signed",
    "delta_hex",
    "count",
    "ratio",
]

VALUE_FIELDNAMES = [
    "kind",
    "rank",
    "value_hex",
    "value",
    "count",
    "ratio",
]

LCS_FIELDNAMES = [
    "rank",
    "source_id",
    "target_kind",
    "transform",
    "source_bytes",
    "target_bytes",
    "lcs_bytes",
    "target_coverage",
    "source_match_ratio",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    return frontier_probe.int_value(row, field)


def float_text(value: float) -> str:
    return f"{value:.6f}"


def signed_byte(value: int) -> int:
    return ((value + 128) & 0xFF) - 128


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def load_segment_window(
    frontier: dict[str, str],
    comparison: dict[str, str],
    *,
    mix_entry_index: int,
) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    try:
        _file_id, payload = frontier_probe.read_mix_entry(Path(frontier["archive"]), mix_entry_index)
        body_offset = int_value(comparison, "texture_body_offset")
        segment_size = int_value(comparison, "texture_segment_size")
        segment = payload[body_offset : body_offset + segment_size]
        window = segment[int_value(frontier, "segment_gap_start") : int_value(frontier, "segment_gap_end") + 1]
    except Exception as exc:
        issues.append(f"segment_read_failed:{exc}")
        window = b""
    return window, issues


def load_reference(args: argparse.Namespace) -> tuple[dict[str, str], dict[str, str], bytes, int, bytes, list[str]]:
    frontier, comparison, pixels, width, _height, issues = spatial_probe.load_reference(args)
    segment_window, segment_issues = load_segment_window(frontier, comparison, mix_entry_index=args.mix_entry_index)
    return frontier, comparison, pixels, width, segment_window, issues + segment_issues


def build_pixel_rows(
    pixels: bytes,
    *,
    gap_start: int,
    gap_end: int,
    width: int,
    dy: int,
    shift: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for y, x_start, _x_end, target in spatial_probe.row_slices(
        pixels,
        gap_start=gap_start,
        gap_end=gap_end,
        width=width,
    ):
        source = spatial_probe.source_row_window(pixels, width, y - dy, x_start, len(target), shift)
        for index, (target_value, source_value) in enumerate(zip(target, source)):
            if target_value == 0 or target_value == source_value:
                continue
            delta = (target_value - source_value) & 0xFF
            delta_signed = signed_byte(delta)
            x = x_start + index
            rows.append(
                {
                    "target_y": str(y),
                    "target_x": str(x),
                    "target_absolute": str(y * width + x),
                    "source_y": str(y - dy),
                    "source_x": str(x + shift),
                    "target_value_hex": f"{target_value:02x}",
                    "source_value_hex": f"{source_value:02x}",
                    "delta_hex": f"{delta:02x}",
                    "delta_signed": str(delta_signed),
                    "abs_delta": str(abs(delta_signed)),
                }
            )
    return rows


def residual_runs(pixel_rows: list[dict[str, str]]) -> list[int]:
    runs: list[int] = []
    current_len = 0
    previous_y = -1
    previous_x = -2
    for row in pixel_rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        if current_len and y == previous_y and x == previous_x + 1:
            current_len += 1
        else:
            if current_len:
                runs.append(current_len)
            current_len = 1
        previous_y = y
        previous_x = x
    if current_len:
        runs.append(current_len)
    return runs


def stream_from_pixels(rows: list[dict[str, str]], field: str) -> bytes:
    return bytes(int(row[field], 16) if field.endswith("_hex") else int(row[field]) & 0xFF for row in rows)


def value_profile(kind: str, values: bytes) -> list[dict[str, str]]:
    total = len(values)
    output: list[dict[str, str]] = []
    for rank, (value, count) in enumerate(Counter(values).most_common(), 1):
        output.append(
            {
                "kind": kind,
                "rank": str(rank),
                "value_hex": f"{value:02x}",
                "value": str(value),
                "count": str(count),
                "ratio": float_text(count / total if total else 0.0),
            }
        )
    return output


def delta_profile(delta_values: bytes) -> list[dict[str, str]]:
    total = len(delta_values)
    output: list[dict[str, str]] = []
    for rank, (value, count) in enumerate(Counter(delta_values).most_common(), 1):
        output.append(
            {
                "rank": str(rank),
                "delta_signed": str(signed_byte(value)),
                "delta_hex": f"{value:02x}",
                "count": str(count),
                "ratio": float_text(count / total if total else 0.0),
            }
        )
    return output


def transformed_segment(segment: bytes, transform: str) -> bytes:
    if transform == "identity":
        return segment
    if transform == "30_bf":
        return bytes(value for value in segment if 0x30 <= value <= 0xBF)
    if transform == "50_7f":
        return bytes(value for value in segment if 0x50 <= value <= 0x7F)
    if transform == "low_nibble_signed":
        return bytes(((value & 0x0F) - 16 if (value & 0x0F) >= 8 else (value & 0x0F)) & 0xFF for value in segment)
    if transform == "high_nibble_signed":
        return bytes(((value >> 4) - 16 if (value >> 4) >= 8 else (value >> 4)) & 0xFF for value in segment)
    if transform == "low2_signed":
        return bytes(((value & 0x03) - 4 if (value & 0x03) >= 2 else (value & 0x03)) & 0xFF for value in segment)
    raise ValueError(f"unknown transform: {transform}")


def build_lcs_rows(segment: bytes, target_values: bytes, delta_values: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    targets = {"target": target_values, "delta": delta_values}
    for source_id, target_kind, transform in STREAM_SOURCES:
        source = transformed_segment(segment, transform)
        target = targets[target_kind]
        lcs = literal_probe.lcs_len(source, target)
        rows.append(
            {
                "rank": "0",
                "source_id": source_id,
                "target_kind": target_kind,
                "transform": transform,
                "source_bytes": str(len(source)),
                "target_bytes": str(len(target)),
                "lcs_bytes": str(lcs),
                "target_coverage": float_text(lcs / len(target) if target else 0.0),
                "source_match_ratio": float_text(lcs / len(source) if source else 0.0),
            }
        )
    rows.sort(key=lambda row: (float(row["target_coverage"]), int_value(row, "lcs_bytes")), reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def best_lcs(rows: list[dict[str, str]], target_kind: str) -> dict[str, str]:
    candidates = [row for row in rows if row.get("target_kind") == target_kind]
    return candidates[0] if candidates else {}


def build_summary(
    frontier: dict[str, str],
    segment: bytes,
    pixel_rows: list[dict[str, str]],
    lcs_rows: list[dict[str, str]],
    fixed_summary: dict[str, str],
    *,
    dy: int,
    shift: int,
    issues: list[str],
) -> dict[str, str]:
    target_values = stream_from_pixels(pixel_rows, "target_value_hex")
    source_values = stream_from_pixels(pixel_rows, "source_value_hex")
    delta_values = stream_from_pixels(pixel_rows, "delta_hex")
    runs = residual_runs(pixel_rows)
    total = len(pixel_rows)
    tiny_delta = sum(1 for value in delta_values if abs(signed_byte(value)) == 1)
    small_delta = sum(1 for value in delta_values if 1 <= abs(signed_byte(value)) <= 3)
    positive_small = sum(1 for value in delta_values if 1 <= signed_byte(value) <= 3)
    negative_small = sum(1 for value in delta_values if -3 <= signed_byte(value) <= -1)
    source_zero = sum(1 for value in source_values if value == 0)
    best_target = best_lcs(lcs_rows, "target")
    best_delta = best_lcs(lcs_rows, "delta")
    fixed_residual = int_value(fixed_summary, "residual_nonzero_pixels")
    fixed_gap = total - fixed_residual if fixed_residual else 0
    issue_rows = len(issues)
    small_delta_ratio = small_delta / total if total else 0.0

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_residual_profile_issues"
        next_action = "fix shared 0x2700302b fixed dy1 residual profile inputs"
    elif fixed_residual and fixed_gap != 0:
        verdict = "shared_2700302b_reference_fixed_dy1_residual_profile_replay_mismatch"
        next_action = "align fixed dy1 residual profile with fixed replay residual accounting"
    elif small_delta_ratio >= 0.65:
        verdict = "shared_2700302b_reference_fixed_dy1_residual_small_delta_dominant"
        next_action = (
            "derive signed small-delta grammar for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}; abs(delta)<=3 covers {small_delta}/{total} residual pixels"
        )
    elif float(best_delta.get("target_coverage", "0") or 0) >= 0.25:
        verdict = "shared_2700302b_reference_fixed_dy1_residual_segment_delta_promising"
        next_action = (
            "map segment bytes to fixed dy1 residual deltas for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_residual_mixed"
        next_action = (
            "split fixed dy1 residual runs by value/delta family for shared 0x2700302b frontier "
            f"{frontier.get('frontier_id', '')}"
        )

    return {
        "scope": "total",
        "archive": frontier.get("archive", ""),
        "archive_tag": frontier.get("archive_tag", ""),
        "pcx_name": frontier.get("pcx_name", ""),
        "frontier_id": frontier.get("frontier_id", ""),
        "segment_bytes": str(len(segment)),
        "residual_nonzero_pixels": str(total),
        "residual_run_rows": str(len(runs)),
        "max_residual_run_pixels": str(max(runs, default=0)),
        "dy": str(dy),
        "shift": str(shift),
        "target_unique_values": str(len(set(target_values))),
        "source_unique_values": str(len(set(source_values))),
        "delta_unique_values": str(len(set(delta_values))),
        "tiny_delta_pixels": str(tiny_delta),
        "tiny_delta_ratio": float_text(tiny_delta / total if total else 0.0),
        "small_delta_pixels": str(small_delta),
        "small_delta_ratio": float_text(small_delta_ratio),
        "positive_small_delta_pixels": str(positive_small),
        "negative_small_delta_pixels": str(negative_small),
        "source_zero_residual_pixels": str(source_zero),
        "best_target_lcs_source": best_target.get("source_id", ""),
        "best_target_lcs_bytes": best_target.get("lcs_bytes", "0"),
        "best_target_lcs_ratio": best_target.get("target_coverage", "0"),
        "best_delta_lcs_source": best_delta.get("source_id", ""),
        "best_delta_lcs_bytes": best_delta.get("lcs_bytes", "0"),
        "best_delta_lcs_ratio": best_delta.get("target_coverage", "0"),
        "fixed_replay_residual_nonzero_pixels": str(fixed_residual),
        "fixed_replay_gap_pixels": str(fixed_gap),
        "issue_rows": str(issue_rows),
        "residual_profile_verdict": verdict,
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
    pixels: list[dict[str, str]],
    deltas: list[dict[str, str]],
    values: list[dict[str, str]],
    lcs_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "deltas": deltas, "lcs": lcs_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("residual_pixels", output_dir / "residual_pixels.csv"),
            ("delta_profile", output_dir / "delta_profile.csv"),
            ("value_profile", output_dir / "value_profile.csv"),
            ("stream_lcs", output_dir / "stream_lcs.csv"),
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
td {{ max-width: 360px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Residual Pixels</div><div class="value">{html.escape(summary['residual_nonzero_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Delta</div><div class="value">{html.escape(summary['small_delta_ratio'])}</div></div>
  <div class="stat"><div class="label">Tiny Delta</div><div class="value">{html.escape(summary['tiny_delta_ratio'])}</div></div>
  <div class="stat"><div class="label">Best Delta LCS</div><div class="value">{html.escape(summary['best_delta_lcs_ratio'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Delta Profile</h2>{render_table(deltas[:32], DELTA_FIELDNAMES)}
<h2>Stream LCS</h2>{render_table(lcs_rows, LCS_FIELDNAMES)}
<h2>Value Profile</h2>{render_table(values[:48], VALUE_FIELDNAMES)}
<h2>Residual Pixels</h2>{render_table(pixels[:120], PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    frontier, _comparison, pixels, width, segment, issues = load_reference(args)
    pixel_rows = build_pixel_rows(
        pixels,
        gap_start=int_value(frontier, "gap_start"),
        gap_end=int_value(frontier, "gap_end"),
        width=width,
        dy=args.dy,
        shift=args.shift,
    )
    target_values = stream_from_pixels(pixel_rows, "target_value_hex")
    source_values = stream_from_pixels(pixel_rows, "source_value_hex")
    delta_values = stream_from_pixels(pixel_rows, "delta_hex")
    lcs_rows = build_lcs_rows(segment, target_values, delta_values)
    delta_rows = delta_profile(delta_values)
    value_rows = (
        value_profile("target", target_values)
        + value_profile("source", source_values)
        + value_profile("delta", delta_values)
    )
    fixed_summary = fixed_replay.read_summary(args.fixed_replay_summary)
    summary = build_summary(
        frontier,
        segment,
        pixel_rows,
        lcs_rows,
        fixed_summary,
        dy=args.dy,
        shift=args.shift,
        issues=issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "residual_pixels.csv", PIXEL_FIELDNAMES, pixel_rows)
    write_csv(args.output / "delta_profile.csv", DELTA_FIELDNAMES, delta_rows)
    write_csv(args.output / "value_profile.csv", VALUE_FIELDNAMES, value_rows)
    write_csv(args.output / "stream_lcs.csv", LCS_FIELDNAMES, lcs_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, pixel_rows, delta_rows, value_rows, lcs_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, pixel_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile fixed dy1 residual nonzero pixels for shared 0x2700302b.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--fixed-replay-summary", type=Path, default=DEFAULT_FIXED_REPLAY_SUMMARY)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--dy", type=int, default=1)
    parser.add_argument("--shift", type=int, default=0)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Residual Profile")
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Residual nonzero pixels: {summary['residual_nonzero_pixels']}")
    print(f"Small delta ratio: {summary['small_delta_ratio']}")
    print(f"Best delta LCS: {summary['best_delta_lcs_source']} {summary['best_delta_lcs_ratio']}")
    print(f"Verdict: {summary['residual_profile_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
