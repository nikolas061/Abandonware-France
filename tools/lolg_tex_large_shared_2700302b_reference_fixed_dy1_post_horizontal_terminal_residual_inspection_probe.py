#!/usr/bin/env python3
"""Inspect terminal residual pixels after horizontal replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile


DEFAULT_OUTPUT = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_residual_inspection_probe"
)
DEFAULT_FRONTIERS = residual_profile.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = residual_profile.DEFAULT_COMPARISONS
DEFAULT_POST_HORIZONTAL_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_residual_profile_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_horizontal_residual_profile_probe/remaining_pixels.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "terminal_pixels",
    "local_supported_pixels",
    "local_exact_pixels",
    "local_small_only_pixels",
    "local_unsupported_pixels",
    "source_zero_pixels",
    "candidate_rows",
    "issue_rows",
    "terminal_inspection_verdict",
    "next_action",
]

PIXEL_FIELDNAMES = [
    "rank",
    "target_y",
    "target_x",
    "target_value_hex",
    "dy1_source_value_hex",
    "dy1_delta_signed",
    "source_zero",
    "candidate_count",
    "exact_candidate_count",
    "small_candidate_count",
    "best_match_kind",
    "best_local_dy",
    "best_local_dx",
    "best_source_value_hex",
    "best_delta_signed",
    "candidate_signature_head",
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


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def hex_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "0")
    return int(raw, 16) if raw else 0


def signed_delta(target: int, source: int) -> int:
    return ((target - source + 128) & 0xFF) - 128


def load_reference_pixels(args: argparse.Namespace) -> tuple[bytes, int, int, list[str]]:
    load_args = argparse.Namespace(
        frontiers=args.frontiers,
        comparisons=args.comparisons,
        archive_tag=args.archive_tag,
        pcx_name=args.pcx_name,
        frontier_id=args.frontier_id,
        mix_entry_index=args.mix_entry_index,
    )
    _frontier, _comparison, pixels, width, _segment, issues = residual_profile.load_reference(load_args)
    height = len(pixels) // width if width else 0
    return pixels, width, height, issues


def local_candidates(
    pixels: bytes,
    width: int,
    height: int,
    target_y: int,
    target_x: int,
    target_value: int,
    radius_y: int,
    radius_x: int,
) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for local_dy in range(-radius_y, radius_y + 1):
        for local_dx in range(-radius_x, radius_x + 1):
            if local_dy == 0 and local_dx == 0:
                continue
            source_y = target_y + local_dy
            source_x = target_x + local_dx
            if not (0 <= source_y < height and 0 <= source_x < width):
                continue
            source = pixels[source_y * width + source_x]
            delta = signed_delta(target_value, source)
            if source == target_value or abs(delta) <= 3:
                rows.append(
                    {
                        "local_dy": local_dy,
                        "local_dx": local_dx,
                        "source": source,
                        "delta": delta,
                    }
                )
    rows.sort(key=lambda row: (abs(row["delta"]), abs(row["local_dy"]) + abs(row["local_dx"]), abs(row["local_dy"]), abs(row["local_dx"])))
    return rows


def build_pixel_rows(
    remaining_rows: list[dict[str, str]],
    pixels: bytes,
    width: int,
    height: int,
    radius_y: int,
    radius_x: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rank, row in enumerate(remaining_rows, 1):
        target_y = int_value(row, "target_y")
        target_x = int_value(row, "target_x")
        target_value = hex_value(row, "target_value_hex")
        candidates = local_candidates(pixels, width, height, target_y, target_x, target_value, radius_y, radius_x)
        exact = [candidate for candidate in candidates if candidate["delta"] == 0]
        small = [candidate for candidate in candidates if candidate["delta"] != 0]
        best = candidates[0] if candidates else {}
        signature = " ".join(
            f"dy{candidate['local_dy']:+}dx{candidate['local_dx']:+}:{candidate['source']:02x}:{candidate['delta']:+}"
            for candidate in candidates[:12]
        )
        rows.append(
            {
                "rank": str(rank),
                "target_y": row.get("target_y", ""),
                "target_x": row.get("target_x", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "dy1_source_value_hex": row.get("source_value_hex", ""),
                "dy1_delta_signed": row.get("delta_signed", ""),
                "source_zero": "1" if hex_value(row, "source_value_hex") == 0 else "0",
                "candidate_count": str(len(candidates)),
                "exact_candidate_count": str(len(exact)),
                "small_candidate_count": str(len(small)),
                "best_match_kind": "exact" if best and best.get("delta") == 0 else ("small_delta" if best else "unsupported"),
                "best_local_dy": str(best.get("local_dy", "")),
                "best_local_dx": str(best.get("local_dx", "")),
                "best_source_value_hex": f"{best['source']:02x}" if best else "",
                "best_delta_signed": str(best.get("delta", "")),
                "candidate_signature_head": signature,
            }
        )
    return rows


def build_summary(
    post_summary: dict[str, str],
    pixel_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    terminal = len(pixel_rows)
    supported = sum(1 for row in pixel_rows if row.get("best_match_kind") != "unsupported")
    exact = sum(1 for row in pixel_rows if row.get("best_match_kind") == "exact")
    small = sum(1 for row in pixel_rows if row.get("best_match_kind") == "small_delta")
    unsupported = terminal - supported
    source_zero = sum(int_value(row, "source_zero") for row in pixel_rows)
    candidate_rows = sum(int_value(row, "candidate_count") for row in pixel_rows)

    if issues:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_inspection_issues"
        next_action = "fix shared 0x2700302b terminal residual inspection inputs"
    elif unsupported <= 1 and supported >= 1:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_local_support"
        next_action = (
            "derive sparse terminal residual guard after horizontal replay for shared 0x2700302b; "
            f"{supported}/{terminal} pixels have local exact/small support and {unsupported} remain unsupported"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_horizontal_terminal_mixed_support"
        next_action = (
            "search alternate terminal residual source for shared 0x2700302b; "
            f"{unsupported}/{terminal} pixels lack local support"
        )

    return {
        "scope": "total",
        "archive": post_summary.get("archive", ""),
        "archive_tag": post_summary.get("archive_tag", ""),
        "pcx_name": post_summary.get("pcx_name", ""),
        "frontier_id": post_summary.get("frontier_id", ""),
        "dy": post_summary.get("dy", ""),
        "shift": post_summary.get("shift", ""),
        "terminal_pixels": str(terminal),
        "local_supported_pixels": str(supported),
        "local_exact_pixels": str(exact),
        "local_small_only_pixels": str(small),
        "local_unsupported_pixels": str(unsupported),
        "source_zero_pixels": str(source_zero),
        "candidate_rows": str(candidate_rows),
        "issue_rows": str(len(issues)),
        "terminal_inspection_verdict": verdict,
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    pixel_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "pixels": pixel_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary", output_dir / "summary.csv"), ("pixels", output_dir / "pixels.csv"))
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
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Terminal</div><div class="value">{html.escape(summary['terminal_pixels'])}</div></div>
  <div class="stat"><div class="label">Local Support</div><div class="value">{html.escape(summary['local_supported_pixels'])}</div></div>
  <div class="stat"><div class="label">Exact</div><div class="value">{html.escape(summary['local_exact_pixels'])}</div></div>
  <div class="stat"><div class="label">Unsupported</div><div class="value">{html.escape(summary['local_unsupported_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Pixels</h2>{render_table(pixel_rows, PIXEL_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    summary_rows = read_csv(args.post_horizontal_summary)
    post_summary = summary_rows[0] if summary_rows else {}
    if not post_summary:
        issues.append("missing_post_horizontal_summary")
    remaining_rows = read_csv(args.remaining_pixels)
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    if len(remaining_rows) != int_value(post_summary, "remaining_nonzero_pixels"):
        issues.append("remaining_summary_gap")
    pixels, width, height, load_issues = load_reference_pixels(args)
    issues.extend(load_issues)
    pixel_rows = build_pixel_rows(remaining_rows, pixels, width, height, args.radius_y, args.radius_x)
    summary = build_summary(post_summary, pixel_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pixels.csv", PIXEL_FIELDNAMES, pixel_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(build_html(summary, pixel_rows, args.output, args.title), encoding="utf-8")
    return summary, pixel_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect terminal residual pixels after horizontal replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-horizontal-summary", type=Path, default=DEFAULT_POST_HORIZONTAL_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument("--radius-y", type=int, default=8)
    parser.add_argument("--radius-x", type=int, default=16)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-horizontal Terminal Residual Inspection",
    )
    args = parser.parse_args()
    summary, _pixels = write_report(args)
    print(f"Terminal pixels: {summary['terminal_pixels']}")
    print(f"Local supported pixels: {summary['local_supported_pixels']}")
    print(f"Local unsupported pixels: {summary['local_unsupported_pixels']}")
    print(f"Verdict: {summary['terminal_inspection_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
