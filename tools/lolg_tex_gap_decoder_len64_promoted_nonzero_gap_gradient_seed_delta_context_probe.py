#!/usr/bin/env python3
"""Probe local source context for gradient seed delta selection."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_OPERATIONS,
    safe_bytes_fromhex,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe")
DEFAULT_VALUES = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe/values.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "mapping_rows",
    "mapping_value_bytes",
    "source_context_selector_families",
    "source_context_selector_groups",
    "source_context_deterministic_groups",
    "source_context_deterministic_bytes",
    "source_context_repeated_deterministic_groups",
    "source_context_repeated_deterministic_bytes",
    "source_context_singleton_deterministic_groups",
    "source_context_singleton_deterministic_bytes",
    "source_context_conflicted_groups",
    "source_context_conflicted_bytes",
    "best_source_context_family",
    "best_source_context_repeated_deterministic_bytes",
    "best_source_context_conflicted_bytes",
    "delta_values",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CONTEXT_VALUE_FIELDNAMES = [
    "seed_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "start",
    "end",
    "length",
    "palette_index",
    "target_value_hex",
    "source_value_hex",
    "delta",
    "source_offset",
    "value_bytes",
    "copy_unlock_bytes",
    "control_window_len",
    "prev2_hex",
    "prev_hex",
    "cur_hex",
    "next_hex",
    "next2_hex",
    "prev_cur_hex",
    "cur_next_hex",
    "prev_cur_next_hex",
    "delta_prev_cur",
    "delta_cur_next",
    "delta_pair",
    "offset_mod4",
    "offset_bucket4",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "selector_family",
    "selector_key",
    "rows",
    "seed_rows",
    "value_bytes",
    "deltas_seen",
    "deterministic",
    "repeated_deterministic",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

FAMILY_FIELDNAMES = [
    "selector_family",
    "groups",
    "rows",
    "value_bytes",
    "deterministic_groups",
    "deterministic_bytes",
    "repeated_deterministic_groups",
    "repeated_deterministic_bytes",
    "singleton_deterministic_groups",
    "singleton_deterministic_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def operation_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def operation_map(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str, str], bytes]:
    return {
        (
            row.get("rank", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("expected_start", ""),
            row.get("expected_end", ""),
        ): safe_bytes_fromhex(row.get("control_window_hex", ""))
        for row in rows
    }


def byte_at(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset >= len(data):
        return None
    return data[offset]


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"{value:02x}"


def signed_delta(left: int | None, right: int | None) -> str:
    if left is None or right is None:
        return ""
    return str(((right - left + 128) & 0xFF) - 128)


def offset_bucket4(offset: int) -> str:
    start = (offset // 4) * 4
    return f"{start}-{start + 3}"


def build_context_values(value_rows: list[dict[str, str]], operations: dict[tuple[str, str, str, str, str], bytes]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in value_rows:
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        window = operations.get(operation_key(row), b"")
        if not window:
            issues.append("missing_control_window")
        offset = int_value(row, "source_offset")
        prev2 = byte_at(window, offset - 2)
        prev = byte_at(window, offset - 1)
        cur = byte_at(window, offset)
        nxt = byte_at(window, offset + 1)
        next2 = byte_at(window, offset + 2)
        if cur is None:
            issues.append("source_offset_out_of_window")
        delta_prev_cur = signed_delta(prev, cur)
        delta_cur_next = signed_delta(cur, nxt)
        output.append(
            {
                "seed_id": row.get("seed_id", ""),
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "length": row.get("length", ""),
                "palette_index": row.get("palette_index", ""),
                "target_value_hex": row.get("target_value_hex", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "delta": row.get("delta", ""),
                "source_offset": row.get("source_offset", ""),
                "value_bytes": row.get("value_bytes", "0"),
                "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
                "control_window_len": str(len(window)),
                "prev2_hex": hex_byte(prev2),
                "prev_hex": hex_byte(prev),
                "cur_hex": hex_byte(cur),
                "next_hex": hex_byte(nxt),
                "next2_hex": hex_byte(next2),
                "prev_cur_hex": f"{hex_byte(prev)}{hex_byte(cur)}",
                "cur_next_hex": f"{hex_byte(cur)}{hex_byte(nxt)}",
                "prev_cur_next_hex": f"{hex_byte(prev)}{hex_byte(cur)}{hex_byte(nxt)}",
                "delta_prev_cur": delta_prev_cur,
                "delta_cur_next": delta_cur_next,
                "delta_pair": f"{delta_prev_cur}|{delta_cur_next}",
                "offset_mod4": str(offset % 4),
                "offset_bucket4": offset_bucket4(offset),
                "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
            }
        )
    return output


def selector_entries(row: dict[str, str]) -> list[tuple[str, str]]:
    return [
        ("prev_cur_hex", row.get("prev_cur_hex", "")),
        ("cur_next_hex", row.get("cur_next_hex", "")),
        ("prev_cur_next_hex", row.get("prev_cur_next_hex", "")),
        ("prev2_prev_cur_hex", f"{row.get('prev2_hex', '')}{row.get('prev_hex', '')}{row.get('cur_hex', '')}"),
        ("cur_next_next2_hex", f"{row.get('cur_hex', '')}{row.get('next_hex', '')}{row.get('next2_hex', '')}"),
        ("delta_prev_cur", row.get("delta_prev_cur", "")),
        ("delta_cur_next", row.get("delta_cur_next", "")),
        ("delta_pair", row.get("delta_pair", "")),
        ("source_value_context3", f"{row.get('prev_hex', '')}|{row.get('source_value_hex', '')}|{row.get('next_hex', '')}"),
        ("source_value_offset_mod4", f"{row.get('source_value_hex', '')}|{row.get('offset_mod4', '')}"),
        ("source_value_offset_bucket4", f"{row.get('source_value_hex', '')}|{row.get('offset_bucket4', '')}"),
        ("source_offset_context3", f"{row.get('source_offset', '')}|{row.get('prev_hex', '')}|{row.get('cur_hex', '')}|{row.get('next_hex', '')}"),
    ]


def build_selector_rows(context_values: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in context_values:
        for family, key in selector_entries(row):
            if key:
                grouped[family, key].append(row)
    output: list[dict[str, str]] = []
    for (family, key), rows in grouped.items():
        deltas = sorted({int_value(row, "delta") for row in rows})
        seed_rows = {row.get("seed_id", "") for row in rows}
        deterministic = len(deltas) == 1
        repeated_deterministic = deterministic and len(seed_rows) > 1
        if repeated_deterministic:
            verdict = "source_context_repeated_delta_candidate"
        elif deterministic:
            verdict = "source_context_singleton_delta_review"
        else:
            verdict = "source_context_delta_conflict"
        sample = rows[0]
        output.append(
            {
                "selector_family": family,
                "selector_key": key,
                "rows": str(len(rows)),
                "seed_rows": str(len(seed_rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deltas_seen": "|".join(str(delta) for delta in deltas),
                "deterministic": "1" if deterministic else "0",
                "repeated_deterministic": "1" if repeated_deterministic else "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("selector_family", ""),
            -int_value(row, "repeated_deterministic"),
            -int_value(row, "value_bytes"),
            row.get("selector_key", ""),
        )
    )
    return output


def build_family_rows(selector_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selector_rows:
        grouped[row.get("selector_family", "")].append(row)
    output: list[dict[str, str]] = []
    for family, rows in grouped.items():
        deterministic = [row for row in rows if row.get("deterministic") == "1"]
        repeated = [row for row in rows if row.get("repeated_deterministic") == "1"]
        singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
        conflicted = [row for row in rows if row.get("deterministic") != "1"]
        if repeated:
            verdict = "source_context_delta_candidate"
        elif deterministic:
            verdict = "source_context_singleton_only"
        else:
            verdict = "source_context_delta_blocked"
        output.append(
            {
                "selector_family": family,
                "groups": str(len(rows)),
                "rows": str(sum(int_value(row, "rows") for row in rows)),
                "value_bytes": str(sum(int_value(row, "value_bytes") for row in rows)),
                "deterministic_groups": str(len(deterministic)),
                "deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
                "repeated_deterministic_groups": str(len(repeated)),
                "repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
                "singleton_deterministic_groups": str(len(singleton)),
                "singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
                "conflicted_groups": str(len(conflicted)),
                "conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (-int_value(row, "repeated_deterministic_bytes"), -int_value(row, "conflicted_bytes"), row.get("selector_family", "")))
    return output


def build_summary(
    context_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
) -> dict[str, str]:
    deterministic = [row for row in selector_rows if row.get("deterministic") == "1"]
    repeated = [row for row in selector_rows if row.get("repeated_deterministic") == "1"]
    singleton = [row for row in deterministic if row.get("repeated_deterministic") != "1"]
    conflicted = [row for row in selector_rows if row.get("deterministic") != "1"]
    best_repeated = max(family_rows, key=lambda row: int_value(row, "repeated_deterministic_bytes"), default={})
    best_conflicted = max(family_rows, key=lambda row: int_value(row, "conflicted_bytes"), default={})
    copy_unlock_by_seed: dict[str, int] = {}
    seed_bytes_by_seed: dict[str, int] = {}
    for row in context_values:
        copy_unlock_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "copy_unlock_bytes"))
        seed_bytes_by_seed.setdefault(row.get("seed_id", ""), int_value(row, "length"))
    return {
        "scope": "total",
        "mapping_rows": str(len(context_values)),
        "mapping_value_bytes": str(sum(int_value(row, "value_bytes") for row in context_values)),
        "source_context_selector_families": str(len(family_rows)),
        "source_context_selector_groups": str(len(selector_rows)),
        "source_context_deterministic_groups": str(len(deterministic)),
        "source_context_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in deterministic)),
        "source_context_repeated_deterministic_groups": str(len(repeated)),
        "source_context_repeated_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in repeated)),
        "source_context_singleton_deterministic_groups": str(len(singleton)),
        "source_context_singleton_deterministic_bytes": str(sum(int_value(row, "value_bytes") for row in singleton)),
        "source_context_conflicted_groups": str(len(conflicted)),
        "source_context_conflicted_bytes": str(sum(int_value(row, "value_bytes") for row in conflicted)),
        "best_source_context_family": best_repeated.get("selector_family", ""),
        "best_source_context_repeated_deterministic_bytes": best_repeated.get("repeated_deterministic_bytes", "0"),
        "best_source_context_conflicted_bytes": best_conflicted.get("conflicted_bytes", "0"),
        "delta_values": str(len({row.get("delta", "") for row in context_values})),
        "copy_unlock_rows": str(sum(1 for value in copy_unlock_by_seed.values() if value)),
        "copy_unlock_bytes": str(sum(copy_unlock_by_seed.values())),
        "total_potential_bytes": str(sum(seed_bytes_by_seed.values()) + sum(copy_unlock_by_seed.values())),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in context_values if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    context_values: list[dict[str, str]],
    selector_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "contextValues": context_values,
        "selectorRows": selector_rows,
        "familyRows": family_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("context_values.csv", output_dir / "context_values.csv"),
            ("by_context_selector.csv", output_dir / "by_context_selector.csv"),
            ("by_context_family.csv", output_dir / "by_context_family.csv"),
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
.wrap {{ width: min(1780px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1720px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks whether immediate source-side control-window context can select the per-value shift delta.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mapping bytes</div><div class="value warn">{summary['mapping_value_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated deterministic bytes</div><div class="value">{summary['source_context_repeated_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Singleton deterministic bytes</div><div class="value warn">{summary['source_context_singleton_deterministic_bytes']}</div></div>
    <div class="stat"><div class="label">Conflicted bytes</div><div class="value warn">{summary['source_context_conflicted_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_potential_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Context families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Context selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Context values</h2>{render_table(context_values, CONTEXT_VALUE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source context for .tex gradient seed delta selectors.")
    parser.add_argument("--values", type=Path, default=DEFAULT_VALUES)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Delta Context Probe",
    )
    args = parser.parse_args()

    context_values = build_context_values(read_csv(args.values), operation_map(read_csv(args.operations)))
    selector_rows = build_selector_rows(context_values)
    family_rows = build_family_rows(selector_rows)
    summary = build_summary(context_values, selector_rows, family_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "context_values.csv", CONTEXT_VALUE_FIELDNAMES, context_values)
    write_csv(args.output / "by_context_selector.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(args.output / "by_context_family.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, context_values, selector_rows, family_rows, args.output, args.title))

    print(f"Mapping bytes: {summary['mapping_value_bytes']}")
    print(f"Repeated deterministic bytes: {summary['source_context_repeated_deterministic_bytes']}")
    print(f"Conflicted bytes: {summary['source_context_conflicted_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
