#!/usr/bin/env python3
"""Profile byte structure inside the largest post-frontier80 clean-gap runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_largest_run_structural_profile")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_transfer_guard_promoted_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
WIDTH_CANDIDATES = [4, 6, 8, 12, 16, 24, 32, 48, 96]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_run_bytes",
    "largest_run_bytes",
    "high_prefix_min",
    "high_prefix_max",
    "high_prefix_all_targets",
    "best_width",
    "best_width_rows",
    "best_width_signature",
    "best_width_stable_rows",
    "best_width_prefix_boundary_targets",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "high_prefix_bytes",
    "high_prefix_boundary32",
    "high_plateau_bytes",
    "low_payload_bytes",
    "control_high_bytes",
    "other_low_bytes",
    "other_bytes",
    "distinct_bytes",
    "top_byte_hex",
    "top_byte_count",
    "top_delta",
    "top_delta_count",
    "head_hex",
    "tail_hex",
]

WIDTH_FIELDNAMES = [
    "width",
    "rows_per_target",
    "stable_rows",
    "stable_ratio",
    "prefix_boundary_targets",
    "first_row_high_targets",
    "majority_signature",
    "structural_score",
]

ROW_FIELDNAMES = [
    "target_id",
    "width",
    "row_index",
    "row_start",
    "row_end",
    "dominant_class",
    "dominant_count",
    "high_plateau_bytes",
    "low_payload_bytes",
    "control_high_bytes",
    "other_low_bytes",
    "other_bytes",
    "small_delta_bytes",
    "min_byte_hex",
    "max_byte_hex",
    "top_byte_hex",
    "top_byte_count",
    "row_hex",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def signed_delta(left: int, right: int) -> int:
    value = (right - left) & 0xFF
    return value if value < 128 else value - 256


def byte_class(value: int) -> str:
    if 0x67 <= value <= 0x6E:
        return "high_plateau"
    if 0x4F <= value <= 0x5B:
        return "low_payload"
    if value >= 0x80:
        return "control_high"
    if value < 0x4F:
        return "other_low"
    return "other"


def hex_byte(value: int | None) -> str:
    return f"0x{value:02x}" if value is not None else ""


def class_counts(data: bytes) -> Counter[str]:
    return Counter(byte_class(value) for value in data)


def dominant_class(data: bytes) -> tuple[str, int]:
    counts = class_counts(data)
    return counts.most_common(1)[0] if counts else ("", 0)


def high_prefix_len(data: bytes) -> int:
    prefix = 0
    for value in data:
        if byte_class(value) != "high_plateau":
            break
        prefix += 1
    return prefix


def load_targets(
    run_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    issues: list[str],
) -> list[tuple[dict[str, str], bytes]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    largest = max(int_value(row, "length") for row in nonzero)
    targets: list[tuple[dict[str, str], bytes]] = []
    for row in nonzero:
        if int_value(row, "length") != largest:
            continue
        key = fixture_key(row)
        manifest = manifest_by_key.get(key)
        if not manifest:
            issues.append(f"{target_id(row)}:missing_manifest_row")
            continue
        try:
            expected = Path(manifest.get("expected_gap_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"{target_id(row)}:read_expected_failed:{exc}")
            continue
        start = int_value(row, "start")
        end = int_value(row, "end")
        data = expected[start:end]
        if len(data) != largest:
            issues.append(f"{target_id(row)}:target_window_out_of_bounds")
        targets.append(({**row, "target_id": target_id(row)}, data))
    return targets


def build_target_rows(targets: list[tuple[dict[str, str], bytes]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target, data in targets:
        counts = class_counts(data)
        top_byte, top_count = Counter(data).most_common(1)[0] if data else (None, 0)
        deltas = [signed_delta(data[index], data[index + 1]) for index in range(len(data) - 1)]
        top_delta, top_delta_count = Counter(deltas).most_common(1)[0] if deltas else (None, 0)
        prefix = high_prefix_len(data)
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "length": target.get("length", ""),
                "high_prefix_bytes": str(prefix),
                "high_prefix_boundary32": "1" if prefix == 32 else "0",
                "high_plateau_bytes": str(counts.get("high_plateau", 0)),
                "low_payload_bytes": str(counts.get("low_payload", 0)),
                "control_high_bytes": str(counts.get("control_high", 0)),
                "other_low_bytes": str(counts.get("other_low", 0)),
                "other_bytes": str(counts.get("other", 0)),
                "distinct_bytes": str(len(set(data))),
                "top_byte_hex": hex_byte(top_byte),
                "top_byte_count": str(top_count),
                "top_delta": "" if top_delta is None else str(top_delta),
                "top_delta_count": str(top_delta_count),
                "head_hex": data[:16].hex(),
                "tail_hex": data[-16:].hex(),
            }
        )
    return rows


def build_width_and_row_rows(
    targets: list[tuple[dict[str, str], bytes]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    width_rows: list[dict[str, str]] = []
    row_rows: list[dict[str, str]] = []
    if not targets:
        return width_rows, row_rows

    target_length = len(targets[0][1])
    for width in WIDTH_CANDIDATES:
        if width <= 0 or target_length % width:
            continue
        rows_per_target = target_length // width
        signatures: list[list[str]] = []
        prefix_boundary_targets = 0
        first_row_high_targets = 0
        for target, data in targets:
            prefix = high_prefix_len(data)
            if prefix == 32 and prefix % width == 0:
                prefix_boundary_targets += 1
            signature: list[str] = []
            for row_index in range(rows_per_target):
                row_start = row_index * width
                row_end = row_start + width
                row_data = data[row_start:row_end]
                dom, dom_count = dominant_class(row_data)
                if row_index == 0 and dom == "high_plateau":
                    first_row_high_targets += 1
                signature.append(dom)
                counts = class_counts(row_data)
                deltas = [
                    abs(signed_delta(row_data[index], row_data[index + 1]))
                    for index in range(len(row_data) - 1)
                ]
                top_byte, top_count = Counter(row_data).most_common(1)[0] if row_data else (None, 0)
                row_rows.append(
                    {
                        "target_id": target.get("target_id", ""),
                        "width": str(width),
                        "row_index": str(row_index),
                        "row_start": str(row_start),
                        "row_end": str(row_end),
                        "dominant_class": dom,
                        "dominant_count": str(dom_count),
                        "high_plateau_bytes": str(counts.get("high_plateau", 0)),
                        "low_payload_bytes": str(counts.get("low_payload", 0)),
                        "control_high_bytes": str(counts.get("control_high", 0)),
                        "other_low_bytes": str(counts.get("other_low", 0)),
                        "other_bytes": str(counts.get("other", 0)),
                        "small_delta_bytes": str(sum(1 for delta in deltas if delta <= 2)),
                        "min_byte_hex": hex_byte(min(row_data) if row_data else None),
                        "max_byte_hex": hex_byte(max(row_data) if row_data else None),
                        "top_byte_hex": hex_byte(top_byte),
                        "top_byte_count": str(top_count),
                        "row_hex": row_data.hex(),
                    }
                )
            signatures.append(signature)

        stable_rows = 0
        majority_signature: list[str] = []
        for row_index in range(rows_per_target):
            votes = Counter(signature[row_index] for signature in signatures)
            majority, majority_count = votes.most_common(1)[0]
            majority_signature.append(majority)
            if majority_count == len(signatures):
                stable_rows += 1
        stable_ratio = stable_rows / rows_per_target if rows_per_target else 0.0
        boundary_ratio = prefix_boundary_targets / len(targets) if targets else 0.0
        first_high_ratio = first_row_high_targets / len(targets) if targets else 0.0
        structural_score = stable_ratio * 100.0 + boundary_ratio * 50.0 + first_high_ratio * 25.0 + width / 10.0
        width_rows.append(
            {
                "width": str(width),
                "rows_per_target": str(rows_per_target),
                "stable_rows": str(stable_rows),
                "stable_ratio": f"{stable_ratio:.6f}",
                "prefix_boundary_targets": str(prefix_boundary_targets),
                "first_row_high_targets": str(first_row_high_targets),
                "majority_signature": ">".join(majority_signature),
                "structural_score": f"{structural_score:.6f}",
            }
        )

    width_rows.sort(
        key=lambda row: (
            -float(row.get("structural_score", "0")),
            -int_value(row, "width"),
        )
    )
    row_rows.sort(
        key=lambda row: (
            int_value(row, "width"),
            row.get("target_id", ""),
            int_value(row, "row_index"),
        )
    )
    return width_rows, row_rows


def build_summary(
    target_rows: list[dict[str, str]],
    width_rows: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    largest = max([int_value(row, "length") for row in target_rows] or [0])
    target_bytes = sum(int_value(row, "length") for row in target_rows)
    prefixes = [int_value(row, "high_prefix_bytes") for row in target_rows]
    best_width = width_rows[0] if width_rows else {}
    stable_width32 = (
        best_width.get("width") == "32"
        and best_width.get("majority_signature") == "high_plateau>low_payload>low_payload"
    )
    verdict = (
        "frontier80_clean_largest_run_width32_structural_profile"
        if stable_width32
        else "frontier80_clean_largest_run_structural_profile"
    )
    next_probe = (
        "derive 32-byte high-prefix/low-payload producer for frontier80 clean-gap nonzero runs"
        if stable_width32
        else "derive structural producer for frontier80 clean-gap nonzero runs"
    )
    return {
        "scope": "total",
        "target_runs": str(len(target_rows)),
        "target_run_bytes": str(target_bytes),
        "largest_run_bytes": str(largest),
        "high_prefix_min": str(min(prefixes) if prefixes else 0),
        "high_prefix_max": str(max(prefixes) if prefixes else 0),
        "high_prefix_all_targets": str(sum(1 for value in prefixes if value == 32)),
        "best_width": best_width.get("width", ""),
        "best_width_rows": best_width.get("rows_per_target", ""),
        "best_width_signature": best_width.get("majority_signature", ""),
        "best_width_stable_rows": best_width.get("stable_rows", ""),
        "best_width_prefix_boundary_targets": best_width.get("prefix_boundary_targets", ""),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    width_rows: list[dict[str, str]],
    row_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": target_rows, "widths": width_rows, "rows": row_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("width_candidates.csv", output_dir / "width_candidates.csv"),
            ("rows.csv", output_dir / "rows.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Profiles high-prefix and low-payload structure for the largest post-frontier80 nonzero runs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target runs</div><div class="value">{html.escape(summary['target_runs'])}</div></div>
    <div class="stat"><div class="label">High prefix min/max</div><div class="value">{html.escape(summary['high_prefix_min'])}/{html.escape(summary['high_prefix_max'])}</div></div>
    <div class="stat"><div class="label">Best width</div><div class="value">{html.escape(summary['best_width'])}</div></div>
    <div class="stat"><div class="label">Best signature</div><div class="value">{html.escape(summary['best_width_signature'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Width candidates</h2>{render_table(width_rows, WIDTH_FIELDNAMES)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Rows</h2>{render_table(row_rows, ROW_FIELDNAMES)}</section>
</main>
<script type="application/json" id="structural-profile-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    runs_path: Path,
    manifest_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    targets = load_targets(read_csv(runs_path), read_csv(manifest_path), issues)
    target_rows = build_target_rows(targets)
    width_rows, row_rows = build_width_and_row_rows(targets)
    summary = build_summary(target_rows, width_rows, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output_dir / "width_candidates.csv", WIDTH_FIELDNAMES, width_rows)
    write_csv(output_dir / "rows.csv", ROW_FIELDNAMES, row_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, target_rows, width_rows, row_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile structure in largest post-frontier80 .tex runs.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Largest Run Structural Profile",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.runs, args.manifest, title=args.title)
    print(f"Target runs: {summary['target_runs']}")
    print(f"High prefix min/max: {summary['high_prefix_min']}/{summary['high_prefix_max']}")
    print(f"Best width: {summary['best_width']}")
    print(f"Best signature: {summary['best_width_signature']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
