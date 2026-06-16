#!/usr/bin/env python3
"""Compare control context for repeated flat-walk palette signatures."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_OPERATIONS,
    op_key,
    read_csv,
    safe_bytes_fromhex,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe")
DEFAULT_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "repeated_signature_groups",
    "repeated_signature_rows",
    "repeated_signature_bytes",
    "context_rows",
    "copy_distance_320_rows",
    "same_candidate_pool_rows",
    "same_transform_set_rows",
    "same_control_ref_mod64_rows",
    "shared_context_rows",
    "best_aligned_control_equal_bytes",
    "best_unique_control_overlap",
    "promotion_ready_bytes",
    "issue_rows",
]

CONTEXT_FIELDNAMES = [
    "signature_id",
    "palette_size",
    "unique_values_hex",
    "rows",
    "bytes",
    "starts",
    "frontier_ids",
    "control_ref_mod64_values",
    "candidate_pools",
    "transform_sets",
    "copy_distances",
    "same_candidate_pool",
    "same_transform_set",
    "same_control_ref_mod64",
    "aligned_control_equal_bytes",
    "unique_control_overlap",
    "verdict",
]


def target_key(row: dict[str, str], start_field: str = "start", end_field: str = "end") -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get(start_field, ""),
        row.get(end_field, ""),
    )


def target_op_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return target_key(row)


def exact_copy_distances(backref_rows: list[dict[str, str]]) -> dict[frozenset[tuple[str, str, str, str, str]], set[str]]:
    distances: dict[frozenset[tuple[str, str, str, str, str]], set[str]] = {}
    for row in backref_rows:
        if row.get("best_exact") != "1":
            continue
        pair = frozenset({target_key(row), target_key(row, "best_source_start", "best_source_end")})
        distances.setdefault(pair, set()).add(row.get("best_distance", ""))
    return distances


def control_window(row: dict[str, str], operations: dict[tuple[str, str, str, str, str], dict[str, str]]) -> bytes:
    operation = operations.get(target_op_key(row), {})
    return safe_bytes_fromhex(operation.get("control_window_hex", ""))


def aligned_equal(left: bytes, right: bytes) -> int:
    return sum(1 for a, b in zip(left, right) if a == b)


def unique_overlap(left: bytes, right: bytes) -> int:
    return len(set(left) & set(right))


def context_verdict(row: dict[str, str]) -> str:
    if row.get("same_candidate_pool") == "1" and row.get("same_transform_set") == "1":
        return "repeatable_palette_context_review"
    if row.get("copy_distances") == "320":
        return "copy_backed_distinct_context_blocked"
    return "repeated_palette_distinct_context_blocked"


def build_context_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    distances = exact_copy_distances(backref_rows)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in target_rows:
        grouped.setdefault(row.get("unique_values_hex", ""), []).append(row)

    output: list[dict[str, str]] = []
    for key, rows in grouped.items():
        if len(rows) < 2:
            continue
        pair_distances: set[str] = set()
        same_pool = len({row.get("candidate_pool", "") for row in rows}) == 1
        same_transform = len({row.get("candidate_transform_set", "") for row in rows}) == 1
        same_control_ref = len({row.get("control_ref_mod64", "") for row in rows}) == 1
        control_windows = [control_window(row, operations) for row in rows]
        best_equal = 0
        best_overlap = 0
        for left, right in itertools.combinations(rows, 2):
            pair_distances.update(distances.get(frozenset({target_key(left), target_key(right)}), set()))
        for left, right in itertools.combinations(control_windows, 2):
            best_equal = max(best_equal, aligned_equal(left, right))
            best_overlap = max(best_overlap, unique_overlap(left, right))
        length = sum(int_value(row, "length") for row in rows)
        context = {
            "signature_id": "",
            "palette_size": " ".join(sorted({row.get("palette_size", "") for row in rows})),
            "unique_values_hex": key,
            "rows": str(len(rows)),
            "bytes": str(length),
            "starts": " ".join(row.get("start", "") for row in rows),
            "frontier_ids": " ".join(sorted({row.get("frontier_id", "") for row in rows})),
            "control_ref_mod64_values": " ".join(sorted({row.get("control_ref_mod64", "") for row in rows})),
            "candidate_pools": " ".join(sorted({row.get("candidate_pool", "") for row in rows if row.get("candidate_pool")})),
            "transform_sets": " | ".join(
                sorted({row.get("candidate_transform_set", "") for row in rows if row.get("candidate_transform_set")})
            ),
            "copy_distances": " ".join(sorted(value for value in pair_distances if value)),
            "same_candidate_pool": "1" if same_pool else "0",
            "same_transform_set": "1" if same_transform else "0",
            "same_control_ref_mod64": "1" if same_control_ref else "0",
            "aligned_control_equal_bytes": str(best_equal),
            "unique_control_overlap": str(best_overlap),
            "verdict": "",
        }
        context["verdict"] = context_verdict(context)
        output.append(context)

    output.sort(
        key=lambda row: (
            -int_value(row, "bytes"),
            -int_value(row, "unique_control_overlap"),
            row.get("unique_values_hex", ""),
        )
    )
    for index, row in enumerate(output, 1):
        row["signature_id"] = f"ctx{index:03d}"
    return output


def build_summary(context_rows: list[dict[str, str]]) -> dict[str, str]:
    shared = [
        row
        for row in context_rows
        if row.get("same_candidate_pool") == "1"
        and row.get("same_transform_set") == "1"
        and row.get("same_control_ref_mod64") == "1"
    ]
    return {
        "scope": "total",
        "repeated_signature_groups": str(len(context_rows)),
        "repeated_signature_rows": str(sum(int_value(row, "rows") for row in context_rows)),
        "repeated_signature_bytes": str(sum(int_value(row, "bytes") for row in context_rows)),
        "context_rows": str(len(context_rows)),
        "copy_distance_320_rows": str(sum(1 for row in context_rows if row.get("copy_distances") == "320")),
        "same_candidate_pool_rows": str(sum(1 for row in context_rows if row.get("same_candidate_pool") == "1")),
        "same_transform_set_rows": str(sum(1 for row in context_rows if row.get("same_transform_set") == "1")),
        "same_control_ref_mod64_rows": str(sum(1 for row in context_rows if row.get("same_control_ref_mod64") == "1")),
        "shared_context_rows": str(len(shared)),
        "best_aligned_control_equal_bytes": str(max((int_value(row, "aligned_control_equal_bytes") for row in context_rows), default=0)),
        "best_unique_control_overlap": str(max((int_value(row, "unique_control_overlap") for row in context_rows), default=0)),
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }


def build_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    contexts = build_context_rows(target_rows, operation_rows, backref_rows)
    return build_summary(contexts), contexts


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 120) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, str], contexts: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "contexts": contexts}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("by_context.csv", output_dir / "by_context.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1540px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Compares control-side context for repeated flat-walk palette signatures.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Repeated signatures</div><div class="value">{summary['repeated_signature_groups']}</div></div>
    <div class="stat"><div class="label">Repeated bytes</div><div class="value warn">{summary['repeated_signature_bytes']}</div></div>
    <div class="stat"><div class="label">Shared contexts</div><div class="value">{summary['shared_context_rows']}</div></div>
    <div class="stat"><div class="label">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare .tex flat-walk repeated palette signature contexts.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Palette Context Probe",
    )
    args = parser.parse_args()

    summary, contexts = build_rows(read_csv(args.targets), read_csv(args.operations), read_csv(args.backref_targets))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "by_context.csv", CONTEXT_FIELDNAMES, contexts)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, contexts, args.output, args.title))

    print(f"Repeated signature bytes: {summary['repeated_signature_bytes']}")
    print(f"Shared context rows: {summary['shared_context_rows']}")
    print(f"Best control overlap: {summary['best_unique_control_overlap']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
