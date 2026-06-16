#!/usr/bin/env python3
"""Compare direction/value payload profiles with fixture source profiles."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    read_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_micro_token_probe import (
    deltas,
    preview_text,
    shape_key,
    signed_bucket,
    transition_profile,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe"
)
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe/targets.csv"
)

SOURCE_POOLS = ("segment_gap", "control_prefix", "fragment")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "fixture_keys",
    "source_pools",
    "best_segment_gap_rows",
    "best_segment_gap_bytes",
    "profile_overlap_ge50_rows",
    "profile_overlap_ge50_bytes",
    "profile_overlap_ge75_rows",
    "profile_overlap_ge75_bytes",
    "profile_overlap_ge90_rows",
    "profile_overlap_ge90_bytes",
    "exact_profile_match_rows",
    "exact_profile_match_bytes",
    "positional_ge50_rows",
    "positional_ge50_bytes",
    "positional_ge75_rows",
    "positional_ge75_bytes",
    "source_profile_groups",
    "repeated_source_profile_groups",
    "repeated_source_profile_bytes",
    "best_offset_groups",
    "repeated_best_offset_groups",
    "repeated_best_offset_bytes",
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
    "offset_delta",
    "top_token",
    "top_nibble",
    "payload_profile_key",
    "payload_profile_preview",
    "best_pool",
    "best_offset",
    "best_profile_key",
    "best_profile_preview",
    "profile_overlap_exact",
    "profile_overlap_ratio",
    "positional_exact",
    "positional_ratio",
    "exact_profile_match",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "surfaces",
    "direction_value_keys",
    "payload_profile_keys",
    "best_pools",
    "best_offsets",
    "exact_profile_match_rows",
    "profile_overlap_ge75_rows",
    "positional_ge50_rows",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
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


def profile_values(data: bytes) -> tuple[list[str], str, str]:
    signed_values = [signed_bucket(value) for value in deltas(data)]
    profile = transition_profile(signed_values)
    return signed_values, shape_key(profile), profile


def positional_score(wanted: list[str], candidate: list[str]) -> tuple[int, int]:
    total = min(len(wanted), len(candidate))
    return sum(1 for index in range(total) if wanted[index] == candidate[index]), total


def profile_overlap(wanted: list[str], candidate: list[str]) -> tuple[int, int]:
    wanted_counts = Counter(wanted)
    candidate_counts = Counter(candidate)
    return sum(min(wanted_counts[key], candidate_counts[key]) for key in wanted_counts), len(wanted)


def iter_candidate_slices(pool: bytes, length: int):
    if not pool or length <= 0 or len(pool) < length:
        return
    for offset in range(len(pool) - length + 1):
        yield offset, pool[offset : offset + length]


def best_source_profile(
    payload: bytes,
    pools: dict[str, bytes],
) -> dict[str, str]:
    wanted_values, wanted_key, wanted_profile = profile_values(payload)
    best: dict[str, str] | None = None
    for pool in SOURCE_POOLS:
        for offset, candidate in iter_candidate_slices(pools.get(pool, b""), len(payload)):
            candidate_values, candidate_key, candidate_profile = profile_values(candidate)
            overlap_exact, overlap_total = profile_overlap(wanted_values, candidate_values)
            positional_exact, positional_total = positional_score(wanted_values, candidate_values)
            current = {
                "best_pool": pool,
                "best_offset": str(offset),
                "best_profile_key": candidate_key,
                "best_profile_preview": preview_text(candidate_profile),
                "profile_overlap_exact": str(overlap_exact),
                "profile_overlap_ratio": ratio(overlap_exact, overlap_total),
                "positional_exact": str(positional_exact),
                "positional_ratio": ratio(positional_exact, positional_total),
                "exact_profile_match": "1" if candidate_key == wanted_key else "0",
            }
            if best is None:
                best = current
                continue
            current_score = (
                float_value(current, "profile_overlap_ratio"),
                float_value(current, "positional_ratio"),
                int_value(current, "profile_overlap_exact"),
                int_value(current, "positional_exact"),
                1 if current["best_pool"] == "segment_gap" else 0,
            )
            best_score = (
                float_value(best, "profile_overlap_ratio"),
                float_value(best, "positional_ratio"),
                int_value(best, "profile_overlap_exact"),
                int_value(best, "positional_exact"),
                1 if best["best_pool"] == "segment_gap" else 0,
            )
            if current_score > best_score:
                best = current
    if best is None:
        return {
            "best_pool": "",
            "best_offset": "",
            "best_profile_key": "",
            "best_profile_preview": "",
            "profile_overlap_exact": "0",
            "profile_overlap_ratio": "0.000000",
            "positional_exact": "0",
            "positional_ratio": "0.000000",
            "exact_profile_match": "0",
        }
    return best


def classify(row: dict[str, str]) -> str:
    if row.get("exact_profile_match") == "1" and float_value(row, "positional_ratio") >= 0.75:
        return "exact_profile_position_review"
    if row.get("exact_profile_match") == "1":
        return "exact_profile_multiset_review"
    if float_value(row, "profile_overlap_ratio") >= 0.75:
        return "high_profile_overlap_review"
    if float_value(row, "profile_overlap_ratio") >= 0.50:
        return "medium_profile_overlap_review"
    return "weak_source_profile"


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
        payload = expected_all[start:end]
        if not payload:
            issues.append("missing_expected_chunk")
            continue
        wanted_values, wanted_key, wanted_profile = profile_values(payload)
        best = best_source_profile(payload, pools)
        fixture = metadata.get(key, {})
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
            "length": str(len(payload)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "direction_value_key": target.get("direction_value_key", ""),
            "offset_delta": target.get("offset_delta", ""),
            "top_token": target.get("top_token", ""),
            "top_nibble": target.get("top_nibble", ""),
            "payload_profile_key": wanted_key,
            "payload_profile_preview": preview_text(wanted_profile),
            **best,
            "verdict": "",
            "issues": ";".join(issues),
        }
        row["verdict"] = classify(row)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("verdict", ""),
            -float_value(row, "profile_overlap_ratio"),
            -float_value(row, "positional_ratio"),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return rows, fixture_issues


def group_rows(rows: list[dict[str, str]], kind: str, key_func) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[key_func(row)].append(row)
    output: list[dict[str, str]] = []
    for key, group in grouped.items():
        sample = group[0]
        exact_rows = [row for row in group if row.get("exact_profile_match") == "1"]
        overlap_rows = [row for row in group if float_value(row, "profile_overlap_ratio") >= 0.75]
        positional_rows = [row for row in group if float_value(row, "positional_ratio") >= 0.50]
        if len(group) > 1:
            verdict = "repeated_source_profile_review" if kind == "source_profile" else "repeated_offset_review"
        else:
            verdict = "singleton"
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "rows": str(len(group)),
                "bytes": str(sum(int_value(row, "length") for row in group)),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group})),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group})),
                "payload_profile_keys": "|".join(sorted({row.get("payload_profile_key", "") for row in group})),
                "best_pools": "|".join(sorted({row.get("best_pool", "") for row in group})),
                "best_offsets": "|".join(sorted({row.get("best_offset", "") for row in group})),
                "exact_profile_match_rows": str(len(exact_rows)),
                "profile_overlap_ge75_rows": str(len(overlap_rows)),
                "positional_ge50_rows": str(len(positional_rows)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("group_kind", ""),
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("group_key", ""),
        )
    )
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "bytes") for row in repeated)


def build_summary(
    rows: list[dict[str, str]],
    source_profile_groups: list[dict[str, str]],
    offset_groups: list[dict[str, str]],
) -> dict[str, str]:
    best_segment_gap = [row for row in rows if row.get("best_pool") == "segment_gap"]
    overlap_ge50 = [row for row in rows if float_value(row, "profile_overlap_ratio") >= 0.50]
    overlap_ge75 = [row for row in rows if float_value(row, "profile_overlap_ratio") >= 0.75]
    overlap_ge90 = [row for row in rows if float_value(row, "profile_overlap_ratio") >= 0.90]
    exact_profile = [row for row in rows if row.get("exact_profile_match") == "1"]
    positional_ge50 = [row for row in rows if float_value(row, "positional_ratio") >= 0.50]
    positional_ge75 = [row for row in rows if float_value(row, "positional_ratio") >= 0.75]
    repeated_profile = repeated_stats(source_profile_groups)
    repeated_offset = repeated_stats(offset_groups)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "fixture_keys": str(len({fixture_key(row) for row in rows})),
        "source_pools": str(len(SOURCE_POOLS)),
        "best_segment_gap_rows": str(len(best_segment_gap)),
        "best_segment_gap_bytes": str(sum(int_value(row, "length") for row in best_segment_gap)),
        "profile_overlap_ge50_rows": str(len(overlap_ge50)),
        "profile_overlap_ge50_bytes": str(sum(int_value(row, "length") for row in overlap_ge50)),
        "profile_overlap_ge75_rows": str(len(overlap_ge75)),
        "profile_overlap_ge75_bytes": str(sum(int_value(row, "length") for row in overlap_ge75)),
        "profile_overlap_ge90_rows": str(len(overlap_ge90)),
        "profile_overlap_ge90_bytes": str(sum(int_value(row, "length") for row in overlap_ge90)),
        "exact_profile_match_rows": str(len(exact_profile)),
        "exact_profile_match_bytes": str(sum(int_value(row, "length") for row in exact_profile)),
        "positional_ge50_rows": str(len(positional_ge50)),
        "positional_ge50_bytes": str(sum(int_value(row, "length") for row in positional_ge50)),
        "positional_ge75_rows": str(len(positional_ge75)),
        "positional_ge75_bytes": str(sum(int_value(row, "length") for row in positional_ge75)),
        "source_profile_groups": str(len(source_profile_groups)),
        "repeated_source_profile_groups": str(repeated_profile[0]),
        "repeated_source_profile_bytes": str(repeated_profile[1]),
        "best_offset_groups": str(len(offset_groups)),
        "repeated_best_offset_groups": str(repeated_offset[0]),
        "repeated_best_offset_bytes": str(repeated_offset[1]),
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
    source_profile_groups: list[dict[str, str]],
    offset_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "sourceProfileGroups": source_profile_groups,
        "offsetGroups": offset_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_source_profile.csv", output_dir / "by_source_profile.csv"),
            ("by_best_offset.csv", output_dir / "by_best_offset.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1280px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #26363b; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #1d292d; z-index: 1; }}
td {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Direction/value payload transition profiles compared against fixture source pools.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target rows</div><div class="value">{html.escape(summary['target_rows'])}</div></div>
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Overlap >=75% bytes</div><div class="value">{html.escape(summary['profile_overlap_ge75_bytes'])}</div></div>
    <div class="stat"><div class="label">Exact profile bytes</div><div class="value">{html.escape(summary['exact_profile_match_bytes'])}</div></div>
    <div class="stat"><div class="label">Positional >=50% bytes</div><div class="value">{html.escape(summary['positional_ge50_bytes'])}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </section>
  <section class="panel">
    <h2>Files</h2>
    <div class="links">{links}</div>
  </section>
  <section class="panel">
    <h2>Source Profile Groups</h2>
    <div class="table-wrap">{render_table(source_profile_groups, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Best Offset Groups</h2>
    <div class="table-wrap">{render_table(offset_groups, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Targets</h2>
    <div class="table-wrap">{render_table(rows, TARGET_FIELDNAMES)}</div>
  </section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_SOURCE_PROFILE_PROBE = {data_json};
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
        default="Lands of Lore II .tex Direction/Value Source Profile Probe",
    )
    args = parser.parse_args()

    rows, fixture_issues = build_target_rows(read_csv(args.targets), read_csv(args.fixtures))
    if fixture_issues:
        fixture_issue_text = ";".join(sorted(set(fixture_issues)))
        for row in rows:
            row["issues"] = ";".join(issue for issue in (row.get("issues", ""), fixture_issue_text) if issue)
    source_profile_groups = group_rows(rows, "source_profile", lambda row: row.get("best_profile_key", ""))
    offset_groups = group_rows(rows, "best_offset", lambda row: f"{row.get('best_pool', '')}:{row.get('best_offset', '')}")
    summary = build_summary(rows, source_profile_groups, offset_groups)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_source_profile.csv", GROUP_FIELDNAMES, source_profile_groups)
    write_csv(args.output / "by_best_offset.csv", GROUP_FIELDNAMES, offset_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, source_profile_groups, offset_groups, args.output, args.title))

    print(f"Source profile rows: {summary['target_rows']}")
    print(f"Best segment-gap bytes: {summary['best_segment_gap_bytes']}")
    print(f"Profile overlap >=75% bytes: {summary['profile_overlap_ge75_bytes']}")
    print(f"Exact profile match bytes: {summary['exact_profile_match_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
