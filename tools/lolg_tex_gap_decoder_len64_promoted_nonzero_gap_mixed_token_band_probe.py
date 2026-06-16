#!/usr/bin/env python3
"""Probe value-band structure inside mixed-token rows."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_band_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "top_nibble_groups",
    "dominant_top_nibble",
    "dominant_top_nibble_rows",
    "dominant_top_nibble_bytes",
    "low_profile_groups",
    "low_profile_repeated_groups",
    "low_profile_repeated_rows",
    "low_profile_repeated_bytes",
    "dominant_top_low_profile_groups",
    "dominant_top_low_profile_repeated_groups",
    "dominant_top_low_profile_repeated_bytes",
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
    "low_top3",
    "low_profile_key",
    "low_profile_preview",
    "control_ref_mod64",
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


def shape_key(text: str) -> str:
    digest = hashlib.sha1(text.encode("ascii")).hexdigest()[:14]
    return f"len={len(text)}|sha1={digest}"


def low_profile(data: bytes) -> tuple[str, str, str]:
    lows = [value & 0x0F for value in data]
    top3 = " ".join(f"{value:x}:{count}" for value, count in Counter(lows).most_common(3))
    deltas = [((lows[index] - lows[index - 1] + 8) & 0x0F) - 8 for index in range(1, len(lows))]
    buckets = Counter(
        "0"
        if delta == 0
        else "+s"
        if 0 < delta <= 2
        else "-s"
        if -2 <= delta < 0
        else "+j"
        if delta > 0
        else "-j"
        for delta in deltas
    )
    profile = ";".join(f"{key}:{buckets[key]}" for key in ("0", "+s", "-s", "+j", "-j") if buckets[key])
    return top3, shape_key(profile), profile


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


def build_target_rows(
    all_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for source in all_rows:
        if source.get("micro_class") != "mixed_token_walk":
            continue
        issues = [issue for issue in source.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(source), b"")
        start = int_value(source, "start")
        end = int_value(source, "end")
        data = expected_all[start:end]
        if not data:
            issues.append("missing_expected_chunk")
            continue
        low_top3, profile_key, profile = low_profile(data)
        rows.append(
            {
                "rank": source.get("rank", ""),
                "archive": source.get("archive", ""),
                "archive_tag": source.get("archive_tag", ""),
                "pcx_name": source.get("pcx_name", ""),
                "frontier_id": source.get("frontier_id", ""),
                "span_index": source.get("span_index", ""),
                "run_index": source.get("run_index", ""),
                "op_index": source.get("op_index", ""),
                "length": source.get("length", ""),
                "start": source.get("start", ""),
                "end": source.get("end", ""),
                "top_nibble": source.get("top_nibble", ""),
                "top_nibble_ratio": source.get("top_nibble_ratio", ""),
                "low_top3": low_top3,
                "low_profile_key": profile_key,
                "low_profile_preview": profile,
                "control_ref_mod64": source.get("control_ref_mod64", ""),
                "head_hex": source.get("head_hex", ""),
                "tail_hex": source.get("tail_hex", ""),
                "issues": ";".join(issues),
            }
        )
    return rows, fixture_issues


def build_summary(
    rows: list[dict[str, str]],
    top_groups: list[dict[str, str]],
    low_groups: list[dict[str, str]],
    fixture_issues: list[str],
) -> dict[str, str]:
    low_repeated = repeated_stats(low_groups)
    dominant_top = top_groups[0] if top_groups else {}
    dominant_rows = [row for row in rows if row.get("top_nibble") == dominant_top.get("group_key")]
    dominant_low_groups = group_rows(dominant_rows, "low_profile_key", "dominant_top_low_profile")
    dominant_low_repeated = repeated_stats(dominant_low_groups)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "top_nibble_groups": str(len(top_groups)),
        "dominant_top_nibble": dominant_top.get("group_key", ""),
        "dominant_top_nibble_rows": dominant_top.get("rows", "0"),
        "dominant_top_nibble_bytes": dominant_top.get("bytes", "0"),
        "low_profile_groups": str(len(low_groups)),
        "low_profile_repeated_groups": str(low_repeated[0]),
        "low_profile_repeated_rows": str(low_repeated[1]),
        "low_profile_repeated_bytes": str(low_repeated[2]),
        "dominant_top_low_profile_groups": str(len(dominant_low_groups)),
        "dominant_top_low_profile_repeated_groups": str(dominant_low_repeated[0]),
        "dominant_top_low_profile_repeated_bytes": str(dominant_low_repeated[2]),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + len(fixture_issues)),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    top_groups = group_rows(rows, "top_nibble", "top_nibble")
    low_groups = group_rows(rows, "low_profile_key", "low_profile")
    summary = build_summary(rows, top_groups, low_groups, fixture_issues)
    return summary, rows, top_groups + low_groups


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
    <div class="sub">Splits mixed-token rows by high-nibble and low-nibble transition profiles.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mixed-token bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant top-nibble bytes</div><div class="value warn">{summary['dominant_top_nibble_bytes']}</div></div>
    <div class="stat"><div class="label">Low profile repeats</div><div class="value">{summary['low_profile_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES, 180)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_BAND_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex mixed-token value bands.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Mixed Token Band Probe",
    )
    args = parser.parse_args()

    summary, targets, groups = build_rows(read_csv(args.targets), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_group.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, groups, args.output, args.title))

    print(f"Mixed-token bytes: {summary['target_bytes']}")
    print(f"Dominant top-nibble bytes: {summary['dominant_top_nibble_bytes']}")
    print(f"Low-profile repeated bytes: {summary['low_profile_repeated_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
