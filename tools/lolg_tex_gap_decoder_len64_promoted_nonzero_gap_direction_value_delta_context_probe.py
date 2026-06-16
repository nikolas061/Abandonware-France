#!/usr/bin/env python3
"""Check whether direction/value offset conflicts split by local context."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_delta_context_probe"
)
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "context_profiles",
    "best_context_name",
    "best_stable_bytes",
    "best_repeated_stable_bytes",
    "best_conflict_bytes",
    "singleton_stable_bytes",
    "split_all_singleton_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CONTEXT_FIELDNAMES = [
    "context_name",
    "groups",
    "stable_groups",
    "stable_rows",
    "stable_bytes",
    "repeated_stable_groups",
    "repeated_stable_rows",
    "repeated_stable_bytes",
    "singleton_stable_groups",
    "singleton_stable_rows",
    "singleton_stable_bytes",
    "conflict_groups",
    "conflict_rows",
    "conflict_bytes",
    "max_group_rows",
    "max_group_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_context_key",
    "sample_deltas",
]

TARGET_FIELDNAMES = [
    "surface",
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
    "direction_value_key",
    "direction_offset",
    "best_value_offset",
    "offset_delta",
    "start_mod64",
    "best_value_ratio",
    "best_value_exact",
    "payload_signature",
    "head4",
    "tail4",
    "issues",
]

PAYLOAD_FIELDNAMES = [
    "payload_signature",
    "rows",
    "bytes",
    "direction_value_keys",
    "surfaces",
    "pcx_values",
    "offset_deltas",
    "sample_surface",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def payload_signature(row: dict[str, str]) -> str:
    return f"len={row.get('length', '0')}|head={row.get('head_hex', '')}|tail={row.get('tail_hex', '')}"


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if float_value(row, "best_value_ratio") < 0.75:
            continue
        output.append(
            {
                "surface": row.get("surface", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "length": row.get("length", "0"),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "direction_value_key": row.get("direction_value_key", ""),
                "direction_offset": row.get("direction_offset", ""),
                "best_value_offset": row.get("best_value_offset", ""),
                "offset_delta": row.get("offset_delta", ""),
                "start_mod64": row.get("start_mod64", ""),
                "best_value_ratio": row.get("best_value_ratio", "0"),
                "best_value_exact": row.get("best_value_exact", "0"),
                "payload_signature": payload_signature(row),
                "head4": row.get("head_hex", "")[:8],
                "tail4": row.get("tail_hex", "")[-8:],
                "issues": row.get("issues", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("direction_value_key", ""),
            row.get("surface", ""),
            row.get("start_mod64", ""),
            int_value(row, "start"),
        )
    )
    return output


def row_stats(rows: list[dict[str, str]]) -> Counter[str]:
    stats: Counter[str] = Counter()
    for row in rows:
        stats["rows"] += 1
        stats["bytes"] += int_value(row, "length")
        if row.get("issues"):
            stats["issue_rows"] += 1
    return stats


def context_key_text(parts: tuple[str, ...]) -> str:
    return "|".join(parts)


def context_specs() -> list[tuple[str, Callable[[dict[str, str]], tuple[str, ...]]]]:
    return [
        ("direction_value_key", lambda row: (row["direction_value_key"],)),
        ("surface", lambda row: (row["surface"],)),
        ("surface+key", lambda row: (row["surface"], row["direction_value_key"])),
        ("key+pcx", lambda row: (row["direction_value_key"], row["pcx_name"])),
        ("key+length", lambda row: (row["direction_value_key"], row["length"])),
        ("key+mod64", lambda row: (row["direction_value_key"], row["start_mod64"])),
        (
            "surface+key+length",
            lambda row: (row["surface"], row["direction_value_key"], row["length"]),
        ),
        (
            "surface+key+mod64",
            lambda row: (row["surface"], row["direction_value_key"], row["start_mod64"]),
        ),
        (
            "surface+key+head4",
            lambda row: (row["surface"], row["direction_value_key"], row["head4"]),
        ),
        (
            "surface+key+tail4",
            lambda row: (row["surface"], row["direction_value_key"], row["tail4"]),
        ),
    ]


def build_context_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for name, key_func in context_specs():
        grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[key_func(row)].append(row)

        stable_groups = []
        repeated_stable_groups = []
        singleton_stable_groups = []
        conflict_groups = []
        for key, group_rows in grouped.items():
            deltas = {row.get("offset_delta", "") for row in group_rows}
            if len(deltas) == 1:
                stable_groups.append((key, group_rows))
                if len(group_rows) > 1:
                    repeated_stable_groups.append((key, group_rows))
                else:
                    singleton_stable_groups.append((key, group_rows))
            else:
                conflict_groups.append((key, group_rows))

        if repeated_stable_groups:
            verdict = "repeated_stable_context_review"
        elif stable_groups and not conflict_groups:
            verdict = "singleton_split_only"
        elif stable_groups:
            verdict = "partial_singleton_split"
        else:
            verdict = "context_conflict_reject"

        largest = max(grouped.items(), key=lambda item: sum(int_value(row, "length") for row in item[1]))
        sample_key, sample_rows = largest
        output.append(
            {
                "context_name": name,
                "groups": str(len(grouped)),
                "stable_groups": str(len(stable_groups)),
                "stable_rows": str(sum(len(group_rows) for _key, group_rows in stable_groups)),
                "stable_bytes": str(
                    sum(int_value(row, "length") for _key, group_rows in stable_groups for row in group_rows)
                ),
                "repeated_stable_groups": str(len(repeated_stable_groups)),
                "repeated_stable_rows": str(
                    sum(len(group_rows) for _key, group_rows in repeated_stable_groups)
                ),
                "repeated_stable_bytes": str(
                    sum(int_value(row, "length") for _key, group_rows in repeated_stable_groups for row in group_rows)
                ),
                "singleton_stable_groups": str(len(singleton_stable_groups)),
                "singleton_stable_rows": str(
                    sum(len(group_rows) for _key, group_rows in singleton_stable_groups)
                ),
                "singleton_stable_bytes": str(
                    sum(int_value(row, "length") for _key, group_rows in singleton_stable_groups for row in group_rows)
                ),
                "conflict_groups": str(len(conflict_groups)),
                "conflict_rows": str(sum(len(group_rows) for _key, group_rows in conflict_groups)),
                "conflict_bytes": str(
                    sum(int_value(row, "length") for _key, group_rows in conflict_groups for row in group_rows)
                ),
                "max_group_rows": str(len(sample_rows)),
                "max_group_bytes": str(sum(int_value(row, "length") for row in sample_rows)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_context_key": context_key_text(sample_key),
                "sample_deltas": "|".join(sorted({row.get("offset_delta", "") for row in sample_rows})),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "repeated_stable_bytes"),
            int_value(row, "conflict_bytes"),
            -int_value(row, "stable_bytes"),
            row.get("context_name", ""),
        )
    )
    return output


def build_payload_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("payload_signature", "")].append(row)
    output: list[dict[str, str]] = []
    for signature, group_rows in grouped.items():
        sample = group_rows[0]
        output.append(
            {
                "payload_signature": signature,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group_rows})),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group_rows})),
                "pcx_values": "|".join(sorted({row.get("pcx_name", "") for row in group_rows})),
                "offset_deltas": "|".join(sorted({row.get("offset_delta", "") for row in group_rows})),
                "sample_surface": sample.get("surface", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("payload_signature", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    stats = row_stats(rows)
    best = max(
        context_rows,
        key=lambda row: (
            int_value(row, "repeated_stable_bytes"),
            -int_value(row, "conflict_bytes"),
            int_value(row, "stable_bytes"),
        ),
    )
    split_all_singleton = max(
        (
            int_value(row, "stable_bytes")
            for row in context_rows
            if int_value(row, "conflict_bytes") == 0 and int_value(row, "repeated_stable_bytes") == 0
        ),
        default=0,
    )
    repeated_payloads = [row for row in payload_rows if int_value(row, "rows") > 1]
    return {
        "scope": "total",
        "target_rows": str(stats["rows"]),
        "target_bytes": str(stats["bytes"]),
        "context_profiles": str(len(context_rows)),
        "best_context_name": best.get("context_name", ""),
        "best_stable_bytes": best.get("stable_bytes", "0"),
        "best_repeated_stable_bytes": best.get("repeated_stable_bytes", "0"),
        "best_conflict_bytes": best.get("conflict_bytes", "0"),
        "singleton_stable_bytes": best.get("singleton_stable_bytes", "0"),
        "split_all_singleton_bytes": str(split_all_singleton),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payloads)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payloads)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(stats["issue_rows"]),
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
    rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "contextRows": context_rows,
        "payloadRows": payload_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("contexts.csv", output_dir / "contexts.csv"),
            ("by_payload.csv", output_dir / "by_payload.csv"),
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
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
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
    <div class="sub">Checks whether offset conflicts split into reusable local context groups.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Best context</div><div class="value">{html.escape(summary['best_context_name'])}</div></div>
    <div class="stat"><div class="label">Repeated stable bytes</div><div class="value warn">{summary['best_repeated_stable_bytes']}</div></div>
    <div class="stat"><div class="label">Split-only bytes</div><div class="value warn">{summary['split_all_singleton_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Context profiles</h2>{render_table(context_rows, CONTEXT_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 180)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_DELTA_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local context splits for direction/value offset deltas.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Direction Value Delta Context Probe",
    )
    args = parser.parse_args()

    rows = normalize_rows(read_csv(args.targets))
    context_rows = build_context_rows(rows)
    payload_rows = build_payload_rows(rows)
    summary = build_summary(rows, context_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, context_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, rows, context_rows, payload_rows, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Delta-context rows: {summary['target_rows']}")
    print(f"Best context: {summary['best_context_name']}")
    print(f"Repeated stable bytes: {summary['best_repeated_stable_bytes']}")
    print(f"Split-all-singleton bytes: {summary['split_all_singleton_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
