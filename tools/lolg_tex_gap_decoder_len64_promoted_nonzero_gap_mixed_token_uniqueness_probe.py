#!/usr/bin/env python3
"""Summarize uniqueness of mixed-token noisy rows."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import fixture_key, read_csv
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "coarse_shape_groups",
    "coarse_repeated_groups",
    "coarse_repeated_rows",
    "coarse_repeated_bytes",
    "signed_shape_groups",
    "signed_repeated_groups",
    "signed_repeated_rows",
    "signed_repeated_bytes",
    "transition_profile_groups",
    "transition_profile_repeated_groups",
    "transition_profile_repeated_rows",
    "transition_profile_repeated_bytes",
    "top_nibble_groups",
    "dominant_top_nibble",
    "dominant_top_nibble_rows",
    "dominant_top_nibble_bytes",
    "control_ref_groups",
    "control_ref_repeated_rows",
    "control_ref_repeated_bytes",
    "missing_control_ref_rows",
    "missing_control_ref_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "start",
    "end",
    "top_nibble",
    "top_nibble_ratio",
    "control_ref_mod64",
    "zero_delta_ratio",
    "small_delta_ratio",
    "jump_delta_ratio",
    "coarse_shape_key",
    "signed_shape_key",
    "transition_profile_key",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def mixed_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("micro_class") == "mixed_token_walk"]


def target_row(row: dict[str, str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in TARGET_FIELDNAMES}


def group_rows(rows: list[dict[str, str]], field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("group_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return (
        len(repeated),
        sum(int_value(row, "rows") for row in repeated),
        sum(int_value(row, "bytes") for row in repeated),
    )


def build_summary(
    rows: list[dict[str, str]],
    coarse_groups: list[dict[str, str]],
    signed_groups: list[dict[str, str]],
    profile_groups: list[dict[str, str]],
    top_groups: list[dict[str, str]],
    control_groups: list[dict[str, str]],
) -> dict[str, str]:
    coarse_repeated = repeated_stats(coarse_groups)
    signed_repeated = repeated_stats(signed_groups)
    profile_repeated = repeated_stats(profile_groups)
    control_repeated = repeated_stats(control_groups)
    dominant_top = top_groups[0] if top_groups else {}
    missing_control = [row for row in rows if row.get("control_ref_mod64") == "missing"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "coarse_shape_groups": str(len(coarse_groups)),
        "coarse_repeated_groups": str(coarse_repeated[0]),
        "coarse_repeated_rows": str(coarse_repeated[1]),
        "coarse_repeated_bytes": str(coarse_repeated[2]),
        "signed_shape_groups": str(len(signed_groups)),
        "signed_repeated_groups": str(signed_repeated[0]),
        "signed_repeated_rows": str(signed_repeated[1]),
        "signed_repeated_bytes": str(signed_repeated[2]),
        "transition_profile_groups": str(len(profile_groups)),
        "transition_profile_repeated_groups": str(profile_repeated[0]),
        "transition_profile_repeated_rows": str(profile_repeated[1]),
        "transition_profile_repeated_bytes": str(profile_repeated[2]),
        "top_nibble_groups": str(len(top_groups)),
        "dominant_top_nibble": dominant_top.get("group_key", ""),
        "dominant_top_nibble_rows": dominant_top.get("rows", "0"),
        "dominant_top_nibble_bytes": dominant_top.get("bytes", "0"),
        "control_ref_groups": str(len(control_groups)),
        "control_ref_repeated_rows": str(control_repeated[1]),
        "control_ref_repeated_bytes": str(control_repeated[2]),
        "missing_control_ref_rows": str(len(missing_control)),
        "missing_control_ref_bytes": str(sum(int_value(row, "length") for row in missing_control)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def build_rows(
    all_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows = mixed_rows(all_rows)
    targets = [target_row(row) for row in rows]
    coarse_groups = group_rows(rows, "coarse_shape_key", "coarse_shape")
    signed_groups = group_rows(rows, "signed_shape_key", "signed_shape")
    profile_groups = group_rows(rows, "transition_profile_key", "transition_profile")
    top_groups = group_rows(rows, "top_nibble", "top_nibble")
    control_groups = group_rows(rows, "control_ref_mod64", "control_ref_mod64")
    groups = coarse_groups + signed_groups + profile_groups + top_groups + control_groups
    summary = build_summary(rows, coarse_groups, signed_groups, profile_groups, top_groups, control_groups)
    return summary, targets, groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_group.csv", output_dir / "by_group.csv"),
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
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
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
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1520px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks whether mixed-token rows have reusable token shapes or only coarse bucket recurrence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mixed-token bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated shape bytes</div><div class="value">{summary['signed_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant top nibble</div><div class="value warn">{summary['dominant_top_nibble_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES, 180)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_UNIQUENESS_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize .tex mixed-token uniqueness.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Mixed Token Uniqueness Probe",
    )
    args = parser.parse_args()

    summary, targets, groups = build_rows(read_csv(args.targets))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_group.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, groups, args.output, args.title))

    print(f"Mixed-token targets: {summary['target_rows']}")
    print(f"Mixed-token bytes: {summary['target_bytes']}")
    print(f"Signed repeated bytes: {summary['signed_repeated_bytes']}")
    print(f"Dominant top-nibble bytes: {summary['dominant_top_nibble_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
