#!/usr/bin/env python3
"""Cluster known high-row supports into compact selector candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_compact_selector_probe")
DEFAULT_SUPPORT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/known_family_support.csv")
DEFAULT_SOURCES = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/sources.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "cluster_rows",
    "best_cluster_key",
    "best_cluster_source_coverage",
    "best_cluster_support_rows",
    "best_cluster_small_delta_le2_min",
    "best_cluster_small_delta_le2_total",
    "best_cluster_exact_total",
    "best_cluster_known_min",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CLUSTER_FIELDNAMES = [
    "cluster_key",
    "rank",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start_bucket",
    "source_coverage",
    "support_rows",
    "small_delta_le2_min",
    "small_delta_le2_total",
    "exact_total",
    "known_min",
    "best_support_starts",
    "source_ids",
]

SELECTED_FIELDNAMES = [
    "source_id",
    "cluster_key",
    "rank",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "known_bytes",
    "exact_bytes",
    "small_delta_le2_bytes",
    "top_delta",
    "top_delta_count",
    "support_head_hex",
    "source_head_hex",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def cluster_key(row: dict[str, str], bucket_size: int) -> tuple[str, str, str, str, int]:
    start = int_value(row, "start")
    bucket = (start // bucket_size) * bucket_size
    return (
        row.get("rank", ""),
        row.get("archive_tag", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        bucket,
    )


def cluster_key_text(key: tuple[str, str, str, str, int]) -> str:
    rank, archive_tag, pcx_name, frontier_id, bucket = key
    return f"rank{rank}|{archive_tag}|{pcx_name}|frontier{frontier_id}|start{bucket}"


def best_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return sorted(
        rows,
        key=lambda row: (
            -int_value(row, "small_delta_le2_bytes"),
            -int_value(row, "exact_bytes"),
            -int_value(row, "known_bytes"),
            int_value(row, "start"),
        ),
    )[0]


def build_clusters(
    support_rows: list[dict[str, str]],
    source_ids: list[str],
    *,
    bucket_size: int,
    max_support_id: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    by_cluster: dict[tuple[str, str, str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in support_rows:
        if int_value(row, "support_id") > max_support_id:
            continue
        by_cluster[cluster_key(row, bucket_size)].append(row)

    cluster_rows: list[dict[str, str]] = []
    selected_by_cluster: dict[str, list[dict[str, str]]] = {}
    for key, rows in by_cluster.items():
        by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_source[row.get("source_id", "")].append(row)
        selected_source_ids = [source_id for source_id in source_ids if source_id in by_source]
        selected = [best_row(by_source[source_id]) for source_id in selected_source_ids]
        if not selected:
            continue
        rank, archive_tag, pcx_name, frontier_id, bucket = key
        selected_by_cluster[cluster_key_text(key)] = selected
        cluster_rows.append(
            {
                "cluster_key": cluster_key_text(key),
                "rank": rank,
                "archive_tag": archive_tag,
                "pcx_name": pcx_name,
                "frontier_id": frontier_id,
                "start_bucket": str(bucket),
                "source_coverage": str(len(selected_source_ids)),
                "support_rows": str(len(rows)),
                "small_delta_le2_min": str(min(int_value(row, "small_delta_le2_bytes") for row in selected)),
                "small_delta_le2_total": str(sum(int_value(row, "small_delta_le2_bytes") for row in selected)),
                "exact_total": str(sum(int_value(row, "exact_bytes") for row in selected)),
                "known_min": str(min(int_value(row, "known_bytes") for row in selected)),
                "best_support_starts": ";".join(row.get("start", "") for row in selected),
                "source_ids": ";".join(selected_source_ids),
            }
        )

    cluster_rows.sort(
        key=lambda row: (
            -int_value(row, "source_coverage"),
            -int_value(row, "small_delta_le2_min"),
            -int_value(row, "small_delta_le2_total"),
            -int_value(row, "exact_total"),
            -int_value(row, "support_rows"),
            row.get("cluster_key", ""),
        )
    )
    best_cluster = cluster_rows[0] if cluster_rows else {}
    selected_rows: list[dict[str, str]] = []
    for row in selected_by_cluster.get(best_cluster.get("cluster_key", ""), []):
        selected_rows.append(
            {
                "source_id": row.get("source_id", ""),
                "cluster_key": best_cluster.get("cluster_key", ""),
                "rank": row.get("rank", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "known_bytes": row.get("known_bytes", ""),
                "exact_bytes": row.get("exact_bytes", ""),
                "small_delta_le2_bytes": row.get("small_delta_le2_bytes", ""),
                "top_delta": row.get("top_delta", ""),
                "top_delta_count": row.get("top_delta_count", ""),
                "support_head_hex": row.get("support_head_hex", ""),
                "source_head_hex": row.get("source_head_hex", ""),
            }
        )
    return cluster_rows, selected_rows, best_cluster


def build_summary(
    source_rows: list[dict[str, str]],
    cluster_rows: list[dict[str, str]],
    best_cluster: dict[str, str],
    *,
    issue_count: int,
) -> dict[str, str]:
    source_count = len(source_rows)
    full_coverage = int_value(best_cluster, "source_coverage") == source_count and source_count > 0
    strong_min = int_value(best_cluster, "small_delta_le2_min") >= 30
    verdict = (
        "frontier80_prior_high_row_compact_cluster_ready"
        if full_coverage and strong_min
        else "frontier80_prior_high_row_compact_cluster_weak"
    )
    next_probe = (
        "derive signed-delta byte selector inside dominant prior high-row compact cluster"
        if verdict == "frontier80_prior_high_row_compact_cluster_ready"
        else "expand compact high-row clusters before deriving signed-delta selector"
    )
    return {
        "scope": "total",
        "source_rows": str(source_count),
        "cluster_rows": str(len(cluster_rows)),
        "best_cluster_key": best_cluster.get("cluster_key", ""),
        "best_cluster_source_coverage": best_cluster.get("source_coverage", "0"),
        "best_cluster_support_rows": best_cluster.get("support_rows", "0"),
        "best_cluster_small_delta_le2_min": best_cluster.get("small_delta_le2_min", "0"),
        "best_cluster_small_delta_le2_total": best_cluster.get("small_delta_le2_total", "0"),
        "best_cluster_exact_total": best_cluster.get("exact_total", "0"),
        "best_cluster_known_min": best_cluster.get("known_min", "0"),
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
    cluster_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "clusters": cluster_rows, "selected": selected_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("clusters.csv", output_dir / "clusters.csv"),
            ("selected_support.csv", output_dir / "selected_support.csv"),
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
    <div class="sub">Clusters known prior high-row supports into compact selector candidates.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Best cluster</div><div class="value">{html.escape(summary['best_cluster_key'])}</div></div>
    <div class="stat"><div class="label">Coverage</div><div class="value">{html.escape(summary['best_cluster_source_coverage'])}/{html.escape(summary['source_rows'])}</div></div>
    <div class="stat"><div class="label">Min small delta</div><div class="value">{html.escape(summary['best_cluster_small_delta_le2_min'])}</div></div>
    <div class="stat"><div class="label">Known min</div><div class="value">{html.escape(summary['best_cluster_known_min'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Clusters</h2>{render_table(cluster_rows, CLUSTER_FIELDNAMES)}</section>
  <section class="panel"><h2>Selected support</h2>{render_table(selected_rows, SELECTED_FIELDNAMES)}</section>
</main>
<script type="application/json" id="compact-selector-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    support_path: Path,
    sources_path: Path,
    *,
    bucket_size: int,
    max_support_id: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    source_rows = read_csv(sources_path)
    support_rows = read_csv(support_path)
    if not source_rows:
        issues.append("missing_source_rows")
    if not support_rows:
        issues.append("missing_support_rows")
    source_ids = [row.get("source_id", "") for row in source_rows if row.get("source_id", "")]
    cluster_rows, selected_rows, best_cluster = build_clusters(
        support_rows,
        source_ids,
        bucket_size=bucket_size,
        max_support_id=max_support_id,
    )
    summary = build_summary(source_rows, cluster_rows, best_cluster, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "clusters.csv", CLUSTER_FIELDNAMES, cluster_rows)
    write_csv(output_dir / "selected_support.csv", SELECTED_FIELDNAMES, selected_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, cluster_rows, selected_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster high-row supports into compact selector candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--support", type=Path, default=DEFAULT_SUPPORT)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--bucket-size", type=int, default=8)
    parser.add_argument("--max-support-id", type=int, default=15)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Compact Selector Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.support,
        args.sources,
        bucket_size=args.bucket_size,
        max_support_id=args.max_support_id,
        title=args.title,
    )
    print(f"Best cluster: {summary['best_cluster_key']}")
    print(f"Coverage: {summary['best_cluster_source_coverage']}/{summary['source_rows']}")
    print(f"Min small delta <=2: {summary['best_cluster_small_delta_le2_min']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
