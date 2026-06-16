#!/usr/bin/env python3
"""Check context stability for repeated jump-token shapes."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_context_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "shape_kinds",
    "repeated_group_rows",
    "repeated_group_bytes",
    "repeated_candidate_rows",
    "repeated_candidate_bytes",
    "same_length_groups",
    "same_structure_groups",
    "same_control_ref_groups",
    "same_start_mod64_groups",
    "same_top_pair_groups",
    "shared_context_groups",
    "shared_context_bytes",
    "conflicted_context_groups",
    "conflicted_context_bytes",
    "copy_backed_group_rows",
    "copy_backed_group_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GROUP_FIELDNAMES = [
    "shape_kind",
    "shape_key",
    "shape_preview",
    "rows",
    "bytes",
    "fixtures",
    "pcx_values",
    "frontier_values",
    "length_values",
    "structure_values",
    "control_ref_mod64_values",
    "start_mod64_values",
    "top_jump_nibble_pair_values",
    "same_length",
    "same_structure",
    "same_control_ref_mod64",
    "same_start_mod64",
    "same_top_jump_nibble_pair",
    "shared_context",
    "copy_backed",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]

TARGET_FIELDNAMES = [
    "shape_kind",
    "shape_key",
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
    "start_mod64",
    "control_ref_mod64",
    "jump_structure_class",
    "top_jump_nibble_pair",
    "jump_delta_count",
    "long_island_bytes",
    "head_hex",
    "tail_hex",
    "issues",
]


SHAPE_FIELDS = [
    ("island_length_shape", "island_length_shape_key", "island_length_shape_preview"),
    ("jump_signed_shape", "jump_signed_shape_key", "jump_signed_shape_preview"),
    ("jump_nibble_pair", "jump_nibble_pair_key", "jump_nibble_pair_preview"),
    ("jump_exact_pair", "jump_exact_pair_key", "jump_exact_pair_preview"),
]


def row_id(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def fixture_id(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def compact_values(values: set[str]) -> str:
    return "|".join(sorted(value if value else "missing" for value in values))


def single_value(rows: list[dict[str, str]], field: str) -> bool:
    return len({row.get(field, "") for row in rows}) == 1


def build_repeated_groups(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    group_rows: list[dict[str, str]] = []
    target_rows: list[dict[str, str]] = []
    for shape_kind, key_field, preview_field in SHAPE_FIELDS:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            key = row.get(key_field, "")
            if key:
                grouped[key].append(row)
        for key, members in grouped.items():
            if len(members) <= 1:
                continue
            same_length = single_value(members, "length")
            same_structure = single_value(members, "jump_structure_class")
            same_control = single_value(members, "control_ref_mod64")
            same_start = single_value(members, "start_mod64")
            same_top_pair = single_value(members, "top_jump_nibble_pair")
            shared_context = same_length and same_structure and same_control and same_start and same_top_pair
            copy_backed = shape_kind in {"jump_signed_shape", "jump_nibble_pair"} and same_structure and same_top_pair
            verdict = (
                "shared_context_review"
                if shared_context
                else "copy_backed_context_review"
                if copy_backed
                else "context_conflict_reject"
            )
            sample = members[0]
            group_rows.append(
                {
                    "shape_kind": shape_kind,
                    "shape_key": key,
                    "shape_preview": sample.get(preview_field, ""),
                    "rows": str(len(members)),
                    "bytes": str(sum(int_value(row, "length") for row in members)),
                    "fixtures": str(len({fixture_id(row) for row in members})),
                    "pcx_values": compact_values({row.get("pcx_name", "") for row in members}),
                    "frontier_values": compact_values({row.get("frontier_id", "") for row in members}),
                    "length_values": compact_values({row.get("length", "") for row in members}),
                    "structure_values": compact_values({row.get("jump_structure_class", "") for row in members}),
                    "control_ref_mod64_values": compact_values({row.get("control_ref_mod64", "") for row in members}),
                    "start_mod64_values": compact_values({row.get("start_mod64", "") for row in members}),
                    "top_jump_nibble_pair_values": compact_values({row.get("top_jump_nibble_pair", "") for row in members}),
                    "same_length": "1" if same_length else "0",
                    "same_structure": "1" if same_structure else "0",
                    "same_control_ref_mod64": "1" if same_control else "0",
                    "same_start_mod64": "1" if same_start else "0",
                    "same_top_jump_nibble_pair": "1" if same_top_pair else "0",
                    "shared_context": "1" if shared_context else "0",
                    "copy_backed": "1" if copy_backed else "0",
                    "promotion_ready_bytes": "0",
                    "verdict": verdict,
                    "sample_pcx": sample.get("pcx_name", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                    "sample_start": sample.get("start", ""),
                }
            )
            for member in members:
                target_rows.append(
                    {
                        "shape_kind": shape_kind,
                        "shape_key": key,
                        "archive": member.get("archive", ""),
                        "archive_tag": member.get("archive_tag", ""),
                        "pcx_name": member.get("pcx_name", ""),
                        "frontier_id": member.get("frontier_id", ""),
                        "span_index": member.get("span_index", ""),
                        "run_index": member.get("run_index", ""),
                        "op_index": member.get("op_index", ""),
                        "length": member.get("length", ""),
                        "start": member.get("start", ""),
                        "end": member.get("end", ""),
                        "start_mod64": member.get("start_mod64", ""),
                        "control_ref_mod64": member.get("control_ref_mod64", ""),
                        "jump_structure_class": member.get("jump_structure_class", ""),
                        "top_jump_nibble_pair": member.get("top_jump_nibble_pair", ""),
                        "jump_delta_count": member.get("jump_delta_count", ""),
                        "long_island_bytes": member.get("long_island_bytes", ""),
                        "head_hex": member.get("head_hex", ""),
                        "tail_hex": member.get("tail_hex", ""),
                        "issues": member.get("issues", ""),
                    }
                )
    group_rows.sort(key=lambda row: (-int_value(row, "bytes"), row.get("shape_kind", ""), row.get("shape_key", "")))
    target_rows.sort(
        key=lambda row: (
            row.get("shape_kind", ""),
            row.get("shape_key", ""),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return group_rows, target_rows


def build_summary(rows: list[dict[str, str]], groups: list[dict[str, str]], targets: list[dict[str, str]]) -> dict[str, str]:
    candidate_ids = {
        (
            target.get("archive", ""),
            target.get("pcx_name", ""),
            target.get("frontier_id", ""),
            target.get("start", ""),
            target.get("end", ""),
        )
        for target in targets
    }
    row_by_id = {row_id(row): row for row in rows}
    shared_groups = [row for row in groups if row.get("shared_context") == "1"]
    conflicted_groups = [row for row in groups if row.get("shared_context") != "1"]
    copy_backed_groups = [row for row in groups if row.get("copy_backed") == "1"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "shape_kinds": str(len(SHAPE_FIELDS)),
        "repeated_group_rows": str(len(groups)),
        "repeated_group_bytes": str(sum(int_value(row, "bytes") for row in groups)),
        "repeated_candidate_rows": str(len(candidate_ids)),
        "repeated_candidate_bytes": str(sum(int_value(row_by_id[row_key], "length") for row_key in candidate_ids)),
        "same_length_groups": str(sum(1 for row in groups if row.get("same_length") == "1")),
        "same_structure_groups": str(sum(1 for row in groups if row.get("same_structure") == "1")),
        "same_control_ref_groups": str(sum(1 for row in groups if row.get("same_control_ref_mod64") == "1")),
        "same_start_mod64_groups": str(sum(1 for row in groups if row.get("same_start_mod64") == "1")),
        "same_top_pair_groups": str(sum(1 for row in groups if row.get("same_top_jump_nibble_pair") == "1")),
        "shared_context_groups": str(len(shared_groups)),
        "shared_context_bytes": str(sum(int_value(row, "bytes") for row in shared_groups)),
        "conflicted_context_groups": str(len(conflicted_groups)),
        "conflicted_context_bytes": str(sum(int_value(row, "bytes") for row in conflicted_groups)),
        "copy_backed_group_rows": str(len(copy_backed_groups)),
        "copy_backed_group_bytes": str(sum(int_value(row, "bytes") for row in copy_backed_groups)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 180) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    groups: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "groups": groups, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("by_context.csv", output_dir / "by_context.csv"),
            ("targets.csv", output_dir / "targets.csv"),
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
  --ok: #80df94;
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
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1600px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks whether repeated jump-token shapes share stable decoder context.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Repeated groups</div><div class="value">{summary['repeated_group_rows']}</div></div>
    <div class="stat"><div class="label">Candidate bytes</div><div class="value">{summary['repeated_candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Shared context bytes</div><div class="value warn">{summary['shared_context_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['conflicted_context_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Repeated contexts</h2>{render_table(groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES, 160)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_JUMP_TOKEN_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe repeated jump-token contexts.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Jump Token Context Probe",
    )
    args = parser.parse_args()

    rows = read_csv(args.targets)
    groups, targets = build_repeated_groups(rows)
    summary = build_summary(rows, groups, targets)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "by_context.csv", GROUP_FIELDNAMES, groups)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, groups, targets, args.output, args.title))

    print(f"Jump-token repeated groups: {summary['repeated_group_rows']}")
    print(f"Repeated candidate bytes: {summary['repeated_candidate_bytes']}")
    print(f"Shared context bytes: {summary['shared_context_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
