#!/usr/bin/env python3
"""Score fixed value transforms from source-profile windows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    read_bytes,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_value_probe"
)
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe/targets.csv"
)

SOURCE_POOLS = ("segment_gap", "control_prefix", "fragment")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "fixture_keys",
    "transform_count",
    "best_exact_total",
    "best_exact_ratio_max",
    "best_exact_ratio_avg",
    "rows_ge25",
    "bytes_ge25",
    "rows_ge50",
    "bytes_ge50",
    "rows_ge75",
    "bytes_ge75",
    "exact_match_rows",
    "exact_match_bytes",
    "best_transform_groups",
    "repeated_best_transform_groups",
    "repeated_best_transform_bytes",
    "top_best_transform",
    "top_best_transform_rows",
    "top_best_transform_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
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
    "source_pool",
    "source_offset",
    "best_transform",
    "best_exact",
    "best_ratio",
    "top5",
    "verdict",
    "issues",
]

TRANSFORM_FIELDNAMES = [
    "transform",
    "rows",
    "bytes",
    "exact_total",
    "ratio_max",
    "ratio_avg",
    "rows_ge25",
    "bytes_ge25",
    "surfaces",
    "direction_value_keys",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio_text(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def fixture_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("pcx_name", ""), row.get("frontier_id", "")


def source_path_field(pool: str) -> str:
    return f"{pool}_path"


def nibble_swap(data: bytes) -> bytes:
    return bytes((((value & 0x0F) << 4) | ((value & 0xF0) >> 4)) for value in data)


def transform_candidates(data: bytes) -> dict[str, bytes]:
    return {
        "identity": data,
        "low7": bytes(value & 0x7F for value in data),
        "bit_not": bytes(value ^ 0xFF for value in data),
        "xor80": bytes(value ^ 0x80 for value in data),
        "xor40": bytes(value ^ 0x40 for value in data),
        "nibble_swap": nibble_swap(data),
        "add1": bytes((value + 1) & 0xFF for value in data),
        "sub1": bytes((value - 1) & 0xFF for value in data),
        "add16": bytes((value + 16) & 0xFF for value in data),
        "sub16": bytes((value - 16) & 0xFF for value in data),
        "hi_keep": bytes(value & 0xF0 for value in data),
        "lo_keep": bytes(value & 0x0F for value in data),
        "hi_to_lo": bytes((value >> 4) & 0x0F for value in data),
        "lo_to_hi": bytes((value & 0x0F) << 4 for value in data),
    }


def load_fixture_sources(
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, bytes]], dict[tuple[str, str], dict[str, str]], list[str]]:
    sources: dict[tuple[str, str], dict[str, bytes]] = {}
    metadata: dict[tuple[str, str], dict[str, str]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        if key in sources:
            issues.append(f"duplicate_fixture_key:{key[0]}:{key[1]}")
            continue
        row_issues: list[str] = []
        pool_bytes = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), row_issues, "expected"),
        }
        for pool in SOURCE_POOLS:
            pool_bytes[pool] = read_bytes(fixture.get(source_path_field(pool), ""), row_issues, pool)
        sources[key] = pool_bytes
        metadata[key] = fixture
        issues.extend(row_issues)
    return sources, metadata, issues


def exact_score(expected: bytes, candidate: bytes) -> tuple[int, str]:
    total = min(len(expected), len(candidate))
    exact = sum(1 for index in range(total) if expected[index] == candidate[index])
    return exact, ratio_text(exact, len(expected))


def best_transform(expected: bytes, source: bytes) -> tuple[str, int, str, list[tuple[str, int, str]]]:
    scored: list[tuple[str, int, str]] = []
    for name, transformed in transform_candidates(source).items():
        exact, ratio = exact_score(expected, transformed)
        scored.append((name, exact, ratio))
    scored.sort(key=lambda item: (float(item[2]), item[1], item[0]), reverse=True)
    best_name, best_exact, best_ratio = scored[0] if scored else ("", 0, "0.000000")
    return best_name, best_exact, best_ratio, scored[:5]


def classify(row: dict[str, str]) -> str:
    best_ratio = float_value(row, "best_ratio")
    if best_ratio >= 1.0:
        return "exact_value_match_review"
    if best_ratio >= 0.75:
        return "high_value_match_review"
    if best_ratio >= 0.50:
        return "medium_value_match_review"
    if best_ratio >= 0.25:
        return "weak_value_match_review"
    return "value_transform_reject"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    sources, metadata, fixture_issues = load_fixture_sources(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        key = fixture_key(target)
        pools = sources.get(key, {})
        expected_all = pools.get("expected", b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        source_pool = target.get("best_pool", "")
        source_offset = int_value(target, "best_offset")
        source_all = pools.get(source_pool, b"")
        source = source_all[source_offset : source_offset + len(expected)]
        if len(source) != len(expected):
            issues.append("missing_source_window")
        transform_name, transform_exact, transform_ratio, top5 = best_transform(expected, source)
        fixture = metadata.get(key, {})
        top5_text = "|".join(f"{name}:{exact}:{score}" for name, exact, score in top5)
        row = {
            "rank": target.get("rank", fixture.get("rank", "")),
            "surface": target.get("surface", ""),
            "archive": target.get("archive", fixture.get("archive", "")),
            "archive_tag": target.get("archive_tag", fixture.get("archive_tag", "")),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(expected)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "direction_value_key": target.get("direction_value_key", ""),
            "source_pool": source_pool,
            "source_offset": target.get("best_offset", ""),
            "best_transform": transform_name,
            "best_exact": str(transform_exact),
            "best_ratio": transform_ratio,
            "top5": top5_text,
            "verdict": "",
            "issues": ";".join(issues),
        }
        row["verdict"] = classify(row)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("verdict", ""),
            -float_value(row, "best_ratio"),
            -int_value(row, "best_exact"),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return rows, fixture_issues


def build_transform_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("best_transform", "")].append(row)
    output: list[dict[str, str]] = []
    for transform, group in grouped.items():
        sample = group[0]
        exact_total = sum(int_value(row, "best_exact") for row in group)
        ratio_values = [float_value(row, "best_ratio") for row in group]
        ge25 = [row for row in group if float_value(row, "best_ratio") >= 0.25]
        output.append(
            {
                "transform": transform,
                "rows": str(len(group)),
                "bytes": str(sum(int_value(row, "length") for row in group)),
                "exact_total": str(exact_total),
                "ratio_max": f"{max(ratio_values) if ratio_values else 0.0:.6f}",
                "ratio_avg": f"{(sum(ratio_values) / len(ratio_values)) if ratio_values else 0.0:.6f}",
                "rows_ge25": str(len(ge25)),
                "bytes_ge25": str(sum(int_value(row, "length") for row in ge25)),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group})),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group})),
                "promotion_ready_bytes": "0",
                "verdict": "repeated_weak_transform" if len(group) > 1 else "singleton_weak_transform",
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "bytes"),
            -int_value(row, "exact_total"),
            row.get("transform", ""),
        )
    )
    return output


def build_summary(rows: list[dict[str, str]], transform_rows: list[dict[str, str]]) -> dict[str, str]:
    ge25 = [row for row in rows if float_value(row, "best_ratio") >= 0.25]
    ge50 = [row for row in rows if float_value(row, "best_ratio") >= 0.50]
    ge75 = [row for row in rows if float_value(row, "best_ratio") >= 0.75]
    exact = [row for row in rows if float_value(row, "best_ratio") >= 1.0]
    repeated_transforms = [row for row in transform_rows if int_value(row, "rows") > 1]
    top = max(transform_rows, key=lambda row: int_value(row, "bytes"), default={})
    ratio_values = [float_value(row, "best_ratio") for row in rows]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "fixture_keys": str(len({fixture_key(row) for row in rows})),
        "transform_count": str(len(transform_candidates(b""))),
        "best_exact_total": str(sum(int_value(row, "best_exact") for row in rows)),
        "best_exact_ratio_max": f"{max(ratio_values) if ratio_values else 0.0:.6f}",
        "best_exact_ratio_avg": f"{(sum(ratio_values) / len(ratio_values)) if ratio_values else 0.0:.6f}",
        "rows_ge25": str(len(ge25)),
        "bytes_ge25": str(sum(int_value(row, "length") for row in ge25)),
        "rows_ge50": str(len(ge50)),
        "bytes_ge50": str(sum(int_value(row, "length") for row in ge50)),
        "rows_ge75": str(len(ge75)),
        "bytes_ge75": str(sum(int_value(row, "length") for row in ge75)),
        "exact_match_rows": str(len(exact)),
        "exact_match_bytes": str(sum(int_value(row, "length") for row in exact)),
        "best_transform_groups": str(len(transform_rows)),
        "repeated_best_transform_groups": str(len(repeated_transforms)),
        "repeated_best_transform_bytes": str(sum(int_value(row, "bytes") for row in repeated_transforms)),
        "top_best_transform": top.get("transform", ""),
        "top_best_transform_rows": top.get("rows", "0"),
        "top_best_transform_bytes": top.get("bytes", "0"),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
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
    transform_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "transforms": transform_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_transform.csv", output_dir / "by_transform.csv"),
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
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.table-wrap {{ overflow: auto; max-height: 58vh; border: 1px solid var(--line); border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1200px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #26363b; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #1d292d; z-index: 1; }}
td {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Fixed transforms from selected source-profile windows to expected payload bytes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target rows</div><div class="value">{html.escape(summary['target_rows'])}</div></div>
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Best exact total</div><div class="value">{html.escape(summary['best_exact_total'])}</div></div>
    <div class="stat"><div class="label">Max ratio</div><div class="value">{html.escape(summary['best_exact_ratio_max'])}</div></div>
    <div class="stat"><div class="label">Rows >=25%</div><div class="value">{html.escape(summary['rows_ge25'])}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </section>
  <section class="panel">
    <h2>Files</h2>
    <div class="links">{links}</div>
  </section>
  <section class="panel">
    <h2>Transforms</h2>
    <div class="table-wrap">{render_table(transform_rows, TRANSFORM_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Targets</h2>
    <div class="table-wrap">{render_table(rows, TARGET_FIELDNAMES)}</div>
  </section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_SOURCE_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Direction/Value Source Value Probe",
    )
    args = parser.parse_args()

    rows, fixture_issues = build_target_rows(read_csv(args.targets), read_csv(args.fixtures))
    if fixture_issues:
        fixture_issue_text = ";".join(sorted(set(fixture_issues)))
        for row in rows:
            row["issues"] = ";".join(issue for issue in (row.get("issues", ""), fixture_issue_text) if issue)
    transform_rows = build_transform_rows(rows)
    summary = build_summary(rows, transform_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_transform.csv", TRANSFORM_FIELDNAMES, transform_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, transform_rows, args.output, args.title))

    print(f"Source value rows: {summary['target_rows']}")
    print(f"Best exact total: {summary['best_exact_total']}")
    print(f"Max exact ratio: {summary['best_exact_ratio_max']}")
    print(f"Rows >=25%: {summary['rows_ge25']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
