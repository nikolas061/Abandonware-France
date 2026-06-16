#!/usr/bin/env python3
"""Join promoted zero-queue runs with source/control operation evidence."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_source_probe import (
    CONTROL_FIELDNAMES,
    REF_FIELDNAMES,
    control_signature,
    fixture_key,
    read_csv,
    render_table,
    span_key,
)
from lolg_tex_gap_decoder_unresolved_zero_queue import QUEUE_FIELDNAMES
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_zero_source_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_zero_queue/queue.csv")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "joined_rows",
    "target_bytes",
    "joined_bytes",
    "missing_rows",
    "missing_bytes",
    "length_u8_hit_rows",
    "length_u16le_hit_rows",
    "source_delta_u8_hit_rows",
    "control_ref_rows",
    "unique_control_refs",
    "unique_control_windows",
    "top_control_window_rows",
    "top_control_window_bytes",
    "top_control_ref_offset",
    "top_control_ref_rows",
    "issue_rows",
]

TARGET_FIELDNAMES = QUEUE_FIELDNAMES + [
    "op_index",
    "op_kind",
    "control_ref_offset",
    "control_window_head8",
    "control_window_tail8",
    "control_window_signature",
    "length_u8_hit_offsets",
    "length_u16le_hit_offsets",
    "source_delta_u8_hit_offsets",
    "source_delta_u16le_hit_offsets",
    "issues",
]


def target_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    operation_lookup = {
        (
            row.get("rank", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("expected_start", ""),
            row.get("expected_end", ""),
        ): row
        for row in operation_rows
    }

    output_rows: list[dict[str, str]] = []
    for target in target_rows:
        issues: list[str] = []
        operation = operation_lookup.get(target_key(target), {})
        if not operation:
            issues.append("missing_operation")
        elif operation.get("op_kind") != "zero":
            issues.append("operation_not_zero")

        window = operation.get("control_window_hex", "")
        output_rows.append(
            {
                **{field: target.get(field, "") for field in QUEUE_FIELDNAMES},
                "op_index": operation.get("op_index", ""),
                "op_kind": operation.get("op_kind", ""),
                "control_ref_offset": operation.get("control_ref_offset", ""),
                "control_window_head8": window[:16],
                "control_window_tail8": window[-16:],
                "control_window_signature": control_signature(operation) if operation else "",
                "length_u8_hit_offsets": operation.get("length_u8_hit_offsets", ""),
                "length_u16le_hit_offsets": operation.get("length_u16le_hit_offsets", ""),
                "source_delta_u8_hit_offsets": operation.get("source_delta_u8_hit_offsets", ""),
                "source_delta_u16le_hit_offsets": operation.get("source_delta_u16le_hit_offsets", ""),
                "issues": ";".join(issues),
            }
        )

    joined_rows = [row for row in output_rows if not row.get("issues")]
    missing_rows = [row for row in output_rows if row.get("issues")]

    by_control: dict[str, Counter[str]] = defaultdict(Counter)
    control_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    control_spans: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    control_refs: dict[str, set[str]] = defaultdict(set)
    control_sample: dict[str, dict[str, str]] = {}
    by_ref: dict[str, Counter[str]] = defaultdict(Counter)
    ref_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    ref_spans: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    ref_windows: dict[str, set[str]] = defaultdict(set)
    ref_sample: dict[str, dict[str, str]] = {}

    for row in joined_rows:
        signature = row.get("control_window_signature", "")
        by_control[signature]["rows"] += 1
        by_control[signature]["bytes"] += int_value(row, "length")
        by_control[signature]["length_u8_hit_rows"] += 1 if row.get("length_u8_hit_offsets") else 0
        control_fixtures[signature].add(fixture_key(row))
        control_spans[signature].add(span_key(row))
        if row.get("control_ref_offset"):
            control_refs[signature].add(row["control_ref_offset"])
        control_sample.setdefault(signature, row)

        ref = row.get("control_ref_offset", "") or "missing"
        by_ref[ref]["rows"] += 1
        by_ref[ref]["bytes"] += int_value(row, "length")
        ref_fixtures[ref].add(fixture_key(row))
        ref_spans[ref].add(span_key(row))
        ref_windows[ref].add(signature)
        ref_sample.setdefault(ref, row)

    control_rows = []
    for signature, totals in by_control.items():
        sample = control_sample[signature]
        control_rows.append(
            {
                "control_window_signature": signature,
                "rows": str(totals["rows"]),
                "bytes": str(totals["bytes"]),
                "fixtures": str(len(control_fixtures[signature])),
                "spans": str(len(control_spans[signature])),
                "control_ref_offsets": ";".join(
                    sorted(
                        control_refs[signature],
                        key=lambda item: int(item) if item.isdigit() else 999999,
                    )
                ),
                "length_u8_hit_rows": str(totals["length_u8_hit_rows"]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    control_rows.sort(
        key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row["control_window_signature"])
    )

    ref_rows = []
    for ref, totals in by_ref.items():
        sample = ref_sample[ref]
        ref_rows.append(
            {
                "control_ref_offset": ref,
                "rows": str(totals["rows"]),
                "bytes": str(totals["bytes"]),
                "fixtures": str(len(ref_fixtures[ref])),
                "spans": str(len(ref_spans[ref])),
                "control_window_signatures": str(len(ref_windows[ref])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    ref_rows.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row["control_ref_offset"]))

    top_control = control_rows[0] if control_rows else {}
    top_ref = ref_rows[0] if ref_rows else {}
    summary = {
        "scope": "total",
        "target_rows": str(len(output_rows)),
        "joined_rows": str(len(joined_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in output_rows)),
        "joined_bytes": str(sum(int_value(row, "length") for row in joined_rows)),
        "missing_rows": str(len(missing_rows)),
        "missing_bytes": str(sum(int_value(row, "length") for row in missing_rows)),
        "length_u8_hit_rows": str(sum(1 for row in joined_rows if row.get("length_u8_hit_offsets"))),
        "length_u16le_hit_rows": str(sum(1 for row in joined_rows if row.get("length_u16le_hit_offsets"))),
        "source_delta_u8_hit_rows": str(sum(1 for row in joined_rows if row.get("source_delta_u8_hit_offsets"))),
        "control_ref_rows": str(sum(1 for row in joined_rows if row.get("control_ref_offset"))),
        "unique_control_refs": str(len({row.get("control_ref_offset", "") for row in joined_rows if row.get("control_ref_offset")})),
        "unique_control_windows": str(len(control_rows)),
        "top_control_window_rows": top_control.get("rows", "0"),
        "top_control_window_bytes": top_control.get("bytes", "0"),
        "top_control_ref_offset": top_ref.get("control_ref_offset", ""),
        "top_control_ref_rows": top_ref.get("rows", "0"),
        "issue_rows": str(sum(1 for row in output_rows if row.get("issues"))),
    }
    return summary, output_rows, control_rows, ref_rows


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    ref_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "controls": control_rows,
        "refs": ref_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_control_window.csv", output_dir / "by_control_window.csv"),
            ("by_control_ref.csv", output_dir / "by_control_ref.csv"),
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
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1440px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Joins promoted zero-queue runs to source/control operations for selector work.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Joined rows</div><div class="value ok">{summary['joined_rows']}</div></div>
    <div class="stat"><div class="label">Joined bytes</div><div class="value ok">{summary['joined_bytes']}</div></div>
    <div class="stat"><div class="label">Missing rows</div><div class="value warn">{summary['missing_rows']}</div></div>
    <div class="stat"><div class="label">Control refs</div><div class="value">{summary['unique_control_refs']}</div></div>
    <div class="stat"><div class="label">Windows</div><div class="value">{summary['unique_control_windows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Control refs</h2>{render_table(ref_rows, REF_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Control windows</h2>{render_table(control_rows, CONTROL_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES, 260)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Join promoted .tex zero queue rows with source/control operation evidence."
    )
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Zero Source Probe")
    args = parser.parse_args()

    summary, targets, controls, refs = build_rows(
        read_csv(args.targets),
        read_csv(args.operations),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_control_window.csv", CONTROL_FIELDNAMES, controls)
    write_csv(args.output / "by_control_ref.csv", REF_FIELDNAMES, refs)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, controls, refs, args.output, args.title))

    print(f"Joined rows: {summary['joined_rows']}/{summary['target_rows']}")
    print(f"Joined bytes: {summary['joined_bytes']}/{summary['target_bytes']}")
    print(f"Control refs: {summary['unique_control_refs']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
