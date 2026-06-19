#!/usr/bin/env python3
"""Tokenize signed small-delta residuals after fixed dy1 replay for shared 0x2700302b."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_reference_fixed_dy1_small_delta_grammar_probe")
DEFAULT_RESIDUAL_PIXELS = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/residual_pixels.csv"
)
DEFAULT_RESIDUAL_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_residual_profile_probe/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "dy",
    "shift",
    "residual_nonzero_pixels",
    "small_delta_pixels",
    "small_delta_ratio",
    "large_delta_pixels",
    "large_delta_ratio",
    "small_delta_token_rows",
    "large_delta_token_rows",
    "max_small_delta_token_pixels",
    "max_large_delta_token_pixels",
    "small_delta_symbols",
    "dominant_delta",
    "dominant_delta_pixels",
    "row_rows",
    "rows_with_small_delta",
    "rows_with_large_delta",
    "source_zero_large_delta_pixels",
    "profile_small_delta_pixels",
    "profile_gap_pixels",
    "issue_rows",
    "small_delta_grammar_verdict",
    "next_action",
]

TOKEN_FIELDNAMES = [
    "token_kind",
    "target_y",
    "x_start",
    "x_end",
    "pixels",
    "target_absolute_start",
    "target_absolute_end",
    "delta_signature",
    "target_head",
    "source_head",
]

ROW_FIELDNAMES = [
    "target_y",
    "residual_pixels",
    "small_delta_pixels",
    "small_delta_ratio",
    "large_delta_pixels",
    "large_delta_ratio",
    "small_delta_tokens",
    "large_delta_tokens",
    "top_small_deltas",
    "top_large_deltas",
]

DELTA_FIELDNAMES = [
    "rank",
    "token_kind",
    "delta_signed",
    "delta_hex",
    "count",
    "ratio",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def float_text(value: float) -> str:
    return f"{value:.6f}"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def is_small_delta(row: dict[str, str], max_abs_delta: int) -> bool:
    value = abs(int_value(row, "delta_signed"))
    return 1 <= value <= max_abs_delta


def delta_hex(delta_signed: int) -> str:
    return f"{delta_signed & 0xFF:02x}"


def compact_deltas(rows: list[dict[str, str]]) -> str:
    return "|".join(row.get("delta_signed", "") for row in rows[:32])


def hex_head(rows: list[dict[str, str]], field: str, limit: int = 16) -> str:
    values = [int(row.get(field, "00"), 16) for row in rows[:limit]]
    return bytes(values).hex()


def token_row(kind: str, rows: list[dict[str, str]]) -> dict[str, str]:
    first = rows[0]
    last = rows[-1]
    return {
        "token_kind": kind,
        "target_y": first.get("target_y", ""),
        "x_start": first.get("target_x", ""),
        "x_end": last.get("target_x", ""),
        "pixels": str(len(rows)),
        "target_absolute_start": first.get("target_absolute", ""),
        "target_absolute_end": last.get("target_absolute", ""),
        "delta_signature": compact_deltas(rows),
        "target_head": hex_head(rows, "target_value_hex"),
        "source_head": hex_head(rows, "source_value_hex"),
    }


def build_tokens(pixel_rows: list[dict[str, str]], *, max_abs_delta: int) -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    current_rows: list[dict[str, str]] = []
    current_kind = ""
    previous_y = -1
    previous_x = -2

    for row in pixel_rows:
        y = int_value(row, "target_y")
        x = int_value(row, "target_x")
        kind = "small_delta" if is_small_delta(row, max_abs_delta) else "large_delta"
        contiguous = y == previous_y and x == previous_x + 1
        if current_rows and (kind != current_kind or not contiguous):
            tokens.append(token_row(current_kind, current_rows))
            current_rows = []
        current_rows.append(row)
        current_kind = kind
        previous_y = y
        previous_x = x

    if current_rows:
        tokens.append(token_row(current_kind, current_rows))
    return tokens


def build_row_rows(pixel_rows: list[dict[str, str]], token_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_y: dict[str, list[dict[str, str]]] = defaultdict(list)
    tokens_by_y: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pixel_rows:
        by_y[row.get("target_y", "")].append(row)
    for row in token_rows:
        tokens_by_y[row.get("target_y", "")].append(row)

    rows: list[dict[str, str]] = []
    for y in sorted(by_y, key=lambda value: int(value or 0)):
        pixels = by_y[y]
        small = [row for row in pixels if is_small_delta(row, 3)]
        large = [row for row in pixels if not is_small_delta(row, 3)]
        small_counter = Counter(int_value(row, "delta_signed") for row in small)
        large_counter = Counter(int_value(row, "delta_signed") for row in large)
        small_tokens = [row for row in tokens_by_y[y] if row.get("token_kind") == "small_delta"]
        large_tokens = [row for row in tokens_by_y[y] if row.get("token_kind") == "large_delta"]
        rows.append(
            {
                "target_y": y,
                "residual_pixels": str(len(pixels)),
                "small_delta_pixels": str(len(small)),
                "small_delta_ratio": float_text(len(small) / len(pixels) if pixels else 0.0),
                "large_delta_pixels": str(len(large)),
                "large_delta_ratio": float_text(len(large) / len(pixels) if pixels else 0.0),
                "small_delta_tokens": str(len(small_tokens)),
                "large_delta_tokens": str(len(large_tokens)),
                "top_small_deltas": "|".join(f"{delta}:{count}" for delta, count in small_counter.most_common(8)),
                "top_large_deltas": "|".join(f"{delta}:{count}" for delta, count in large_counter.most_common(8)),
            }
        )
    return rows


def build_delta_rows(pixel_rows: list[dict[str, str]], *, max_abs_delta: int) -> list[dict[str, str]]:
    total_by_kind = Counter("small_delta" if is_small_delta(row, max_abs_delta) else "large_delta" for row in pixel_rows)
    counters: dict[str, Counter[int]] = {"small_delta": Counter(), "large_delta": Counter()}
    for row in pixel_rows:
        kind = "small_delta" if is_small_delta(row, max_abs_delta) else "large_delta"
        counters[kind][int_value(row, "delta_signed")] += 1
    rows: list[dict[str, str]] = []
    for kind in ("small_delta", "large_delta"):
        total = total_by_kind[kind]
        for rank, (delta, count) in enumerate(counters[kind].most_common(), 1):
            rows.append(
                {
                    "rank": str(rank),
                    "token_kind": kind,
                    "delta_signed": str(delta),
                    "delta_hex": delta_hex(delta),
                    "count": str(count),
                    "ratio": float_text(count / total if total else 0.0),
                }
            )
    return rows


def build_summary(
    profile_summary: dict[str, str],
    pixel_rows: list[dict[str, str]],
    token_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    *,
    max_abs_delta: int,
    issues: list[str],
) -> dict[str, str]:
    total = len(pixel_rows)
    small_rows = [row for row in pixel_rows if is_small_delta(row, max_abs_delta)]
    large_rows = [row for row in pixel_rows if not is_small_delta(row, max_abs_delta)]
    small_tokens = [row for row in token_rows if row.get("token_kind") == "small_delta"]
    large_tokens = [row for row in token_rows if row.get("token_kind") == "large_delta"]
    delta_counter = Counter(int_value(row, "delta_signed") for row in small_rows)
    dominant_delta, dominant_count = delta_counter.most_common(1)[0] if delta_counter else (0, 0)
    source_zero_large = sum(1 for row in large_rows if int(row.get("source_value_hex", "0"), 16) == 0)
    profile_small = int_value(profile_summary, "small_delta_pixels")
    profile_gap = len(small_rows) - profile_small if profile_small else 0
    issue_rows = len(issues)
    small_ratio = len(small_rows) / total if total else 0.0
    large_ratio = len(large_rows) / total if total else 0.0

    if issue_rows:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_grammar_issues"
        next_action = "fix shared 0x2700302b fixed dy1 small-delta grammar inputs"
    elif profile_small and profile_gap != 0:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_grammar_profile_mismatch"
        next_action = "align small-delta grammar with residual profile accounting"
    elif small_ratio >= 0.70:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_grammar_ready"
        next_action = (
            "map segment/control bytes to signed small-delta tokens for shared 0x2700302b frontier "
            f"{profile_summary.get('frontier_id', '')}; {len(large_rows)} large-delta residual pixels remain"
        )
    else:
        verdict = "shared_2700302b_reference_fixed_dy1_small_delta_grammar_weak"
        next_action = (
            "split fixed dy1 residuals before signed small-delta promotion for shared 0x2700302b frontier "
            f"{profile_summary.get('frontier_id', '')}"
        )

    return {
        "scope": "total",
        "archive": profile_summary.get("archive", ""),
        "archive_tag": profile_summary.get("archive_tag", ""),
        "pcx_name": profile_summary.get("pcx_name", ""),
        "frontier_id": profile_summary.get("frontier_id", ""),
        "dy": profile_summary.get("dy", ""),
        "shift": profile_summary.get("shift", ""),
        "residual_nonzero_pixels": str(total),
        "small_delta_pixels": str(len(small_rows)),
        "small_delta_ratio": float_text(small_ratio),
        "large_delta_pixels": str(len(large_rows)),
        "large_delta_ratio": float_text(large_ratio),
        "small_delta_token_rows": str(len(small_tokens)),
        "large_delta_token_rows": str(len(large_tokens)),
        "max_small_delta_token_pixels": str(max((int_value(row, "pixels") for row in small_tokens), default=0)),
        "max_large_delta_token_pixels": str(max((int_value(row, "pixels") for row in large_tokens), default=0)),
        "small_delta_symbols": str(len(delta_counter)),
        "dominant_delta": str(dominant_delta),
        "dominant_delta_pixels": str(dominant_count),
        "row_rows": str(len(row_rows)),
        "rows_with_small_delta": str(sum(1 for row in row_rows if int_value(row, "small_delta_pixels") > 0)),
        "rows_with_large_delta": str(sum(1 for row in row_rows if int_value(row, "large_delta_pixels") > 0)),
        "source_zero_large_delta_pixels": str(source_zero_large),
        "profile_small_delta_pixels": str(profile_small),
        "profile_gap_pixels": str(profile_gap),
        "issue_rows": str(issue_rows),
        "small_delta_grammar_verdict": verdict,
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
    token_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    delta_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "tokens": token_rows, "rows": row_rows, "deltas": delta_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary", output_dir / "summary.csv"),
            ("tokens", output_dir / "tokens.csv"),
            ("rows", output_dir / "rows.csv"),
            ("delta_profile", output_dir / "delta_profile.csv"),
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
  <div class="stat"><div class="label">Small Delta Pixels</div><div class="value">{html.escape(summary['small_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Delta Ratio</div><div class="value">{html.escape(summary['small_delta_ratio'])}</div></div>
  <div class="stat"><div class="label">Large Delta Pixels</div><div class="value">{html.escape(summary['large_delta_pixels'])}</div></div>
  <div class="stat"><div class="label">Small Tokens</div><div class="value">{html.escape(summary['small_delta_token_rows'])}</div></div>
</div>
<p>{html.escape(summary['next_action'])}</p>
<h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rows</h2>{render_table(row_rows, ROW_FIELDNAMES)}
<h2>Delta Profile</h2>{render_table(delta_rows, DELTA_FIELDNAMES)}
<h2>Tokens</h2>{render_table(token_rows[:120], TOKEN_FIELDNAMES)}
<script type="application/json" id="data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> dict[str, str]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    profile_summary = read_summary(args.residual_summary)
    if not profile_summary:
        issues.append("missing_residual_profile_summary")
    pixel_rows = read_csv(args.residual_pixels)
    if not pixel_rows:
        issues.append("missing_residual_pixels")
    token_rows = build_tokens(pixel_rows, max_abs_delta=args.max_abs_delta)
    row_rows = build_row_rows(pixel_rows, token_rows)
    delta_rows = build_delta_rows(pixel_rows, max_abs_delta=args.max_abs_delta)
    summary = build_summary(
        profile_summary,
        pixel_rows,
        token_rows,
        row_rows,
        max_abs_delta=args.max_abs_delta,
        issues=issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "tokens.csv", TOKEN_FIELDNAMES, token_rows)
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, row_rows)
    write_csv(args.output / "delta_profile.csv", DELTA_FIELDNAMES, delta_rows)
    (args.output / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""), encoding="utf-8")
    (args.output / "index.html").write_text(
        build_html(summary, token_rows, row_rows, delta_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Tokenize fixed dy1 signed small-delta residuals.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--residual-pixels", type=Path, default=DEFAULT_RESIDUAL_PIXELS)
    parser.add_argument("--residual-summary", type=Path, default=DEFAULT_RESIDUAL_SUMMARY)
    parser.add_argument("--max-abs-delta", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Fixed dy1 Small-Delta Grammar")
    args = parser.parse_args()
    summary = write_report(args)
    print(f"Small delta pixels: {summary['small_delta_pixels']}")
    print(f"Small delta ratio: {summary['small_delta_ratio']}")
    print(f"Large delta pixels: {summary['large_delta_pixels']}")
    print(f"Verdict: {summary['small_delta_grammar_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
