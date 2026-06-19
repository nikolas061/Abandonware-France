#!/usr/bin/env python3
"""Probe same-row horizontal residuals after large-delta replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import Counter
from pathlib import Path

import lolg_tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe as residual_profile


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_residual_probe")
DEFAULT_FRONTIERS = residual_profile.DEFAULT_FRONTIERS
DEFAULT_COMPARISONS = residual_profile.DEFAULT_COMPARISONS
DEFAULT_POST_LARGE_DELTA_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_residual_profile_probe/summary.csv"
)
DEFAULT_REMAINING_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_post_large_delta_residual_profile_probe/remaining_pixels.csv"
)

SHIFT_CANDIDATES = [
    ("left_1", (-1,)),
    ("right_1", (1,)),
    ("adjacent_lr", (-1, 1)),
    ("near_lr_2", (-2, -1, 1, 2)),
    ("left_8", tuple(range(-8, 0))),
    ("right_8", tuple(range(1, 9))),
    ("near_lr_8", tuple(list(range(-8, 0)) + list(range(1, 9)))),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "remaining_nonzero_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "candidate_rows",
    "best_candidate_id",
    "best_candidate_shifts",
    "best_covered_pixels",
    "best_covered_ratio",
    "best_exact_pixels",
    "best_small_only_pixels",
    "best_small_delta_covered_pixels",
    "best_large_delta_covered_pixels",
    "plateau_run_rows",
    "plateau_covered_pixels",
    "plateau_covered_ratio",
    "plateau_exact_pixels",
    "max_plateau_run_pixels",
    "issue_rows",
    "horizontal_residual_verdict",
    "next_action",
]

SHIFT_FIELDNAMES = [
    "rank",
    "candidate_id",
    "shifts",
    "valid_pixels",
    "covered_pixels",
    "covered_ratio",
    "exact_pixels",
    "small_only_pixels",
    "large_uncovered_pixels",
    "small_delta_covered_pixels",
    "large_delta_covered_pixels",
]

RUN_FIELDNAMES = [
    "rank",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "mode_value_hex",
    "mode_count",
    "mode_ratio",
    "mode_or_small_pixels",
    "exact_mode_pixels",
    "small_delta_pixels",
    "large_delta_pixels",
    "source_zero_pixels",
    "target_values",
    "delta_values",
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


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


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


def source_value(pixels: bytes, width: int, height: int, target_y: int, target_x: int, shift: int) -> int | None:
    source_x = target_x + shift
    if not (0 <= target_y < height and 0 <= source_x < width):
        return None
    offset = target_y * width + source_x
    return pixels[offset] if 0 <= offset < len(pixels) else None


def annotate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    annotated: list[dict[str, str]] = []
    for row in rows:
        copy = dict(row)
        copy["_target_y"] = str(int_value(row, "target_y"))
        copy["_target_x"] = str(int_value(row, "target_x"))
        copy["_target_value"] = str(hex_value(row, "target_value_hex"))
        copy["_source_value"] = str(hex_value(row, "source_value_hex"))
        copy["_delta_signed"] = str(int_value(row, "delta_signed"))
        annotated.append(copy)
    return annotated


def build_shift_rows(
    rows: list[dict[str, str]],
    pixels: bytes,
    width: int,
    height: int,
) -> list[dict[str, str]]:
    shift_rows: list[dict[str, str]] = []
    for candidate_id, shifts in SHIFT_CANDIDATES:
        valid = 0
        covered = 0
        exact = 0
        small_only = 0
        small_delta_covered = 0
        large_delta_covered = 0
        for row in rows:
            target_y = int(row["_target_y"])
            target_x = int(row["_target_x"])
            target_value = int(row["_target_value"])
            source_values = [
                value
                for shift in shifts
                if (value := source_value(pixels, width, height, target_y, target_x, shift)) is not None
            ]
            if source_values:
                valid += 1
            if any(value == target_value for value in source_values):
                exact += 1
                covered += 1
                if row.get("residual_kind") == "small_delta":
                    small_delta_covered += 1
                elif row.get("residual_kind") == "large_delta":
                    large_delta_covered += 1
            elif any(abs(signed_delta(target_value, value)) <= 3 for value in source_values):
                small_only += 1
                covered += 1
                if row.get("residual_kind") == "small_delta":
                    small_delta_covered += 1
                elif row.get("residual_kind") == "large_delta":
                    large_delta_covered += 1
        shift_rows.append(
            {
                "rank": "0",
                "candidate_id": candidate_id,
                "shifts": ",".join(str(shift) for shift in shifts),
                "valid_pixels": str(valid),
                "covered_pixels": str(covered),
                "covered_ratio": float_text(covered / len(rows) if rows else 0.0),
                "exact_pixels": str(exact),
                "small_only_pixels": str(small_only),
                "large_uncovered_pixels": str(len(rows) - covered),
                "small_delta_covered_pixels": str(small_delta_covered),
                "large_delta_covered_pixels": str(large_delta_covered),
            }
        )
    shift_rows.sort(
        key=lambda row: (
            int_value(row, "covered_pixels"),
            int_value(row, "exact_pixels"),
            -abs(int(row.get("shifts", "0").split(",")[0] or "0")),
        ),
        reverse=True,
    )
    for rank, row in enumerate(shift_rows, 1):
        row["rank"] = str(rank)
    return shift_rows


def contiguous_runs(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    by_y: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        by_y.setdefault(int(row["_target_y"]), []).append(row)

    runs: list[list[dict[str, str]]] = []
    for _y, row_group in sorted(by_y.items()):
        ordered = sorted(row_group, key=lambda row: int(row["_target_x"]))
        current = [ordered[0]]
        for row in ordered[1:]:
            if int(row["_target_x"]) == int(current[-1]["_target_x"]) + 1:
                current.append(row)
            else:
                runs.append(current)
                current = [row]
        runs.append(current)
    return runs


def build_run_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    run_rows: list[dict[str, str]] = []
    for run in contiguous_runs(rows):
        values = [int(row["_target_value"]) for row in run]
        deltas = [int(row["_delta_signed"]) for row in run]
        mode_value, mode_count = Counter(values).most_common(1)[0]
        mode_or_small = sum(1 for value in values if abs(signed_delta(value, mode_value)) <= 3)
        exact_mode = sum(1 for value in values if value == mode_value)
        run_rows.append(
            {
                "rank": "0",
                "target_y": run[0]["_target_y"],
                "x_start": run[0]["_target_x"],
                "x_end": run[-1]["_target_x"],
                "pixels": str(len(run)),
                "mode_value_hex": f"{mode_value:02x}",
                "mode_count": str(mode_count),
                "mode_ratio": float_text(mode_count / len(run) if run else 0.0),
                "mode_or_small_pixels": str(mode_or_small),
                "exact_mode_pixels": str(exact_mode),
                "small_delta_pixels": str(sum(1 for row in run if row.get("residual_kind") == "small_delta")),
                "large_delta_pixels": str(sum(1 for row in run if row.get("residual_kind") == "large_delta")),
                "source_zero_pixels": str(sum(1 for row in run if int(row["_source_value"]) == 0)),
                "target_values": " ".join(f"{value:02x}" for value in values),
                "delta_values": " ".join(str(delta) for delta in deltas),
            }
        )
    run_rows.sort(key=lambda row: int_value(row, "pixels"), reverse=True)
    for rank, row in enumerate(run_rows, 1):
        row["rank"] = str(rank)
    return run_rows


def build_summary(
    post_summary: dict[str, str],
    rows: list[dict[str, str]],
    shift_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    best = shift_rows[0] if shift_rows else {}
    small_delta_pixels = sum(1 for row in rows if row.get("residual_kind") == "small_delta")
    large_delta_pixels = sum(1 for row in rows if row.get("residual_kind") == "large_delta")
    plateau_covered = sum(int_value(row, "mode_or_small_pixels") for row in run_rows)
    plateau_exact = sum(int_value(row, "exact_mode_pixels") for row in run_rows)
    max_run = max((int_value(row, "pixels") for row in run_rows), default=0)
    best_covered = int_value(best, "covered_pixels")
    best_ratio = best_covered / len(rows) if rows else 0.0
    plateau_ratio = plateau_covered / len(rows) if rows else 0.0

    if issues:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_residual_issues"
        next_action = "fix shared 0x2700302b post-large-delta horizontal residual probe inputs"
    elif best_ratio >= 0.90 and plateau_ratio >= 0.85:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_plateau_signal"
        next_action = (
            "derive guarded same-row plateau selector after large-delta replay for shared 0x2700302b; "
            f"{best.get('candidate_id', '')} covers {best_covered}/{len(rows)}"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_post_large_delta_horizontal_signal_weak"
        next_action = (
            "search non-horizontal residual producer after large-delta replay for shared 0x2700302b; "
            f"best same-row candidate covers {best_covered}/{len(rows)}"
        )

    return {
        "scope": "total",
        "archive": post_summary.get("archive", ""),
        "archive_tag": post_summary.get("archive_tag", ""),
        "pcx_name": post_summary.get("pcx_name", ""),
        "frontier_id": post_summary.get("frontier_id", ""),
        "dy": post_summary.get("dy", ""),
        "shift": post_summary.get("shift", ""),
        "remaining_nonzero_pixels": str(len(rows)),
        "small_delta_pixels": str(small_delta_pixels),
        "large_delta_pixels": str(large_delta_pixels),
        "candidate_rows": str(len(shift_rows)),
        "best_candidate_id": best.get("candidate_id", ""),
        "best_candidate_shifts": best.get("shifts", ""),
        "best_covered_pixels": str(best_covered),
        "best_covered_ratio": float_text(best_ratio),
        "best_exact_pixels": best.get("exact_pixels", "0"),
        "best_small_only_pixels": best.get("small_only_pixels", "0"),
        "best_small_delta_covered_pixels": best.get("small_delta_covered_pixels", "0"),
        "best_large_delta_covered_pixels": best.get("large_delta_covered_pixels", "0"),
        "plateau_run_rows": str(len(run_rows)),
        "plateau_covered_pixels": str(plateau_covered),
        "plateau_covered_ratio": float_text(plateau_ratio),
        "plateau_exact_pixels": str(plateau_exact),
        "max_plateau_run_pixels": str(max_run),
        "issue_rows": str(len(issues)),
        "horizontal_residual_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    shift_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "shift_candidates": shift_rows, "runs": run_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("shift candidates", output_dir / "shift_candidates.csv"),
            ("runs", output_dir / "runs.csv"),
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
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{links}</p>
<div class="stats">
  <div class="stat"><div class="label">Best Candidate</div><div class="value">{html.escape(summary['best_candidate_id'])}</div></div>
  <div class="stat"><div class="label">Best Coverage</div><div class="value">{html.escape(summary['best_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Plateau Coverage</div><div class="value">{html.escape(summary['plateau_covered_pixels'])}</div></div>
  <div class="stat"><div class="label">Max Run</div><div class="value">{html.escape(summary['max_plateau_run_pixels'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Shift Candidates</h2>{render_table(shift_rows, SHIFT_FIELDNAMES)}
<h2>Largest Runs</h2>{render_table(run_rows[:120], RUN_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    post_summary_rows = read_csv(args.post_large_delta_summary)
    post_summary = post_summary_rows[0] if post_summary_rows else {}
    if not post_summary:
        issues.append("missing_post_large_delta_summary")
    remaining_rows = annotate_rows(read_csv(args.remaining_pixels))
    if not remaining_rows:
        issues.append("missing_remaining_pixels")
    if len(remaining_rows) != int_value(post_summary, "remaining_nonzero_pixels"):
        issues.append("remaining_summary_gap")
    pixels, width, height, load_issues = load_reference_pixels(args)
    issues.extend(load_issues)
    shift_rows = build_shift_rows(remaining_rows, pixels, width, height)
    run_rows = build_run_rows(remaining_rows)
    summary = build_summary(post_summary, remaining_rows, shift_rows, run_rows, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "shift_candidates.csv", SHIFT_FIELDNAMES, shift_rows)
    write_csv(args.output / "runs.csv", RUN_FIELDNAMES, run_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, shift_rows, run_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, shift_rows, run_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe same-row horizontal residuals after large-delta replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--post-large-delta-summary", type=Path, default=DEFAULT_POST_LARGE_DELTA_SUMMARY)
    parser.add_argument("--remaining-pixels", type=Path, default=DEFAULT_REMAINING_PIXELS)
    parser.add_argument("--archive-tag", default="L4_HJ")
    parser.add_argument("--pcx-name", default="dinodead.pcx")
    parser.add_argument("--frontier-id", type=int, default=6)
    parser.add_argument("--mix-entry-index", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Post-large-delta Horizontal Residual Probe",
    )
    args = parser.parse_args()
    summary, _shift_rows, _run_rows = write_report(args)
    print(f"Remaining pixels: {summary['remaining_nonzero_pixels']}")
    print(f"Best candidate: {summary['best_candidate_id']} shifts {summary['best_candidate_shifts']}")
    print(f"Best coverage: {summary['best_covered_pixels']}/{summary['remaining_nonzero_pixels']}")
    print(f"Plateau coverage: {summary['plateau_covered_pixels']}/{summary['remaining_nonzero_pixels']}")
    print(f"Verdict: {summary['horizontal_residual_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
