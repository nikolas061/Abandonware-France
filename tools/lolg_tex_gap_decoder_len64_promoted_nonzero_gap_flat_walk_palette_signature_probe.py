#!/usr/bin/env python3
"""Group flat-walk rows by first-use palette signatures."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import fixture_key, read_csv
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe")
DEFAULT_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "signature_groups",
    "repeated_signature_groups",
    "repeated_signature_rows",
    "repeated_signature_bytes",
    "copy_backed_signature_groups",
    "copy_backed_signature_rows",
    "copy_backed_signature_bytes",
    "candidate_repeated_rows",
    "candidate_repeated_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SIGNATURE_FIELDNAMES = [
    "signature_id",
    "palette_size",
    "unique_values_hex",
    "rows",
    "bytes",
    "exact_copy_rows",
    "exact_copy_bytes",
    "exact_source_rows",
    "exact_source_bytes",
    "candidate_rows",
    "candidate_bytes",
    "candidate_pools",
    "transform_sets",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
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


def exact_copy_keys(backref_rows: list[dict[str, str]]) -> tuple[set[tuple[str, str, str, str, str]], set[tuple[str, str, str, str, str]]]:
    copies: set[tuple[str, str, str, str, str]] = set()
    sources: set[tuple[str, str, str, str, str]] = set()
    for row in backref_rows:
        if row.get("best_exact") != "1":
            continue
        copies.add(target_key(row))
        sources.add(target_key(row, "best_source_start", "best_source_end"))
    return copies, sources


def signature_key(row: dict[str, str]) -> str:
    return row.get("unique_values_hex", "")


def signature_verdict(row: dict[str, str]) -> str:
    rows = int_value(row, "rows")
    exact_copy_rows = int_value(row, "exact_copy_rows")
    exact_source_rows = int_value(row, "exact_source_rows")
    candidate_rows = int_value(row, "candidate_rows")
    if rows > 1 and exact_copy_rows and exact_source_rows and candidate_rows:
        return "copy_backed_repeated_signature_review"
    if rows > 1 and candidate_rows:
        return "repeated_signature_candidate_review"
    if rows > 1:
        return "repeated_signature_no_candidate"
    return "singleton_signature"


def build_signature_rows(
    target_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    copy_keys, source_keys = exact_copy_keys(backref_rows)
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    pools: dict[str, set[str]] = defaultdict(set)
    transforms: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    palette_sizes: dict[str, set[str]] = defaultdict(set)

    for row in target_rows:
        key = signature_key(row)
        if not key:
            continue
        length = int_value(row, "length")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += length
        if target_key(row) in copy_keys:
            counters[key]["exact_copy_rows"] += 1
            counters[key]["exact_copy_bytes"] += length
        if target_key(row) in source_keys:
            counters[key]["exact_source_rows"] += 1
            counters[key]["exact_source_bytes"] += length
        if row.get("candidate_pool"):
            counters[key]["candidate_rows"] += 1
            counters[key]["candidate_bytes"] += length
            pools[key].add(row.get("candidate_pool", ""))
            transforms[key].add(row.get("candidate_transform_set", ""))
        fixtures[key].add(fixture_key(row))
        palette_sizes[key].add(row.get("palette_size", ""))
        samples.setdefault(key, row)

    rows: list[dict[str, str]] = []
    for index, (key, counter) in enumerate(counters.items(), 1):
        sample = samples[key]
        row = {
            "signature_id": f"sig{index:03d}",
            "palette_size": " ".join(sorted(palette_sizes[key])),
            "unique_values_hex": key,
            "rows": str(counter["rows"]),
            "bytes": str(counter["bytes"]),
            "exact_copy_rows": str(counter["exact_copy_rows"]),
            "exact_copy_bytes": str(counter["exact_copy_bytes"]),
            "exact_source_rows": str(counter["exact_source_rows"]),
            "exact_source_bytes": str(counter["exact_source_bytes"]),
            "candidate_rows": str(counter["candidate_rows"]),
            "candidate_bytes": str(counter["candidate_bytes"]),
            "candidate_pools": " ".join(sorted(value for value in pools[key] if value)),
            "transform_sets": " | ".join(sorted(value for value in transforms[key] if value)),
            "fixtures": str(len(fixtures[key])),
            "sample_pcx": sample.get("pcx_name", ""),
            "sample_frontier_id": sample.get("frontier_id", ""),
            "sample_start": sample.get("start", ""),
            "verdict": "",
        }
        row["verdict"] = signature_verdict(row)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            -int_value(row, "exact_copy_bytes"),
            row.get("sample_pcx", ""),
            int_value(row, "sample_start"),
        )
    )
    for index, row in enumerate(rows, 1):
        row["signature_id"] = f"sig{index:03d}"
    return rows


def build_summary(target_rows: list[dict[str, str]], signature_rows: list[dict[str, str]]) -> dict[str, str]:
    repeated = [row for row in signature_rows if int_value(row, "rows") > 1]
    copy_backed = [
        row
        for row in repeated
        if int_value(row, "exact_copy_rows") > 0 and int_value(row, "exact_source_rows") > 0
    ]
    candidate_repeated = [row for row in repeated if int_value(row, "candidate_rows") > 0]
    return {
        "scope": "total",
        "target_rows": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in target_rows)),
        "signature_groups": str(len(signature_rows)),
        "repeated_signature_groups": str(len(repeated)),
        "repeated_signature_rows": str(sum(int_value(row, "rows") for row in repeated)),
        "repeated_signature_bytes": str(sum(int_value(row, "bytes") for row in repeated)),
        "copy_backed_signature_groups": str(len(copy_backed)),
        "copy_backed_signature_rows": str(sum(int_value(row, "rows") for row in copy_backed)),
        "copy_backed_signature_bytes": str(sum(int_value(row, "bytes") for row in copy_backed)),
        "candidate_repeated_rows": str(sum(int_value(row, "candidate_rows") for row in candidate_repeated)),
        "candidate_repeated_bytes": str(sum(int_value(row, "candidate_bytes") for row in candidate_repeated)),
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }


def build_rows(
    target_rows: list[dict[str, str]],
    backref_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    signatures = build_signature_rows(target_rows, backref_rows)
    return build_summary(target_rows, signatures), signatures


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 120) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, str], signatures: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "signatures": signatures}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("by_signature.csv", output_dir / "by_signature.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1560px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Groups flat-walk rows by first-use palette value signatures and exact-copy links.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Signatures</div><div class="value">{summary['signature_groups']}</div></div>
    <div class="stat"><div class="label">Repeated bytes</div><div class="value warn">{summary['repeated_signature_bytes']}</div></div>
    <div class="stat"><div class="label">Copy-backed bytes</div><div class="value warn">{summary['copy_backed_signature_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Signatures</h2>{render_table(signatures, SIGNATURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_SIGNATURE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Group .tex flat-walk rows by first-use palette signatures.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Palette Signature Probe",
    )
    args = parser.parse_args()

    summary, signatures = build_rows(read_csv(args.targets), read_csv(args.backref_targets))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "by_signature.csv", SIGNATURE_FIELDNAMES, signatures)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, signatures, args.output, args.title))

    print(f"Signature groups: {summary['signature_groups']}")
    print(f"Repeated signature bytes: {summary['repeated_signature_bytes']}")
    print(f"Copy-backed signature bytes: {summary['copy_backed_signature_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
