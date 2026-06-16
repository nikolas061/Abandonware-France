#!/usr/bin/env python3
"""Join flat-walk exact backrefs with palette source hypotheses."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import read_csv
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe import (
    DEFAULT_OUTPUT as DEFAULT_BACKREF_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe import (
    DEFAULT_OUTPUT as DEFAULT_MIX_OUTPUT,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_seed_probe import (
    DEFAULT_OUTPUT as DEFAULT_SEED_OUTPUT,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe")
DEFAULT_BACKREF_TARGETS = DEFAULT_BACKREF_OUTPUT / "targets.csv"
DEFAULT_SEED_TARGETS = DEFAULT_SEED_OUTPUT / "targets.csv"
DEFAULT_SEED_GROUPS = DEFAULT_SEED_OUTPUT / "by_pool_transform.csv"
DEFAULT_MIX_TARGETS = DEFAULT_MIX_OUTPUT / "targets.csv"
DEFAULT_MIX_GROUPS = DEFAULT_MIX_OUTPUT / "by_pool_transform_set.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "exact_copy_rows",
    "exact_copy_bytes",
    "seed_source_candidate_rows",
    "seed_source_candidate_bytes",
    "mix_source_candidate_rows",
    "mix_source_candidate_bytes",
    "any_source_candidate_rows",
    "any_source_candidate_bytes",
    "any_source_chain_bytes",
    "repeated_group_rows",
    "repeated_group_chain_bytes",
    "promotion_ready_bytes",
    "blocked_chain_rows",
    "blocked_chain_bytes",
    "issue_rows",
]

CHAIN_FIELDNAMES = [
    "copy_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "copy_span_index",
    "copy_op_index",
    "copy_start",
    "copy_end",
    "source_start",
    "source_end",
    "distance",
    "copy_length",
    "seed_candidate",
    "seed_pool",
    "seed_transform",
    "seed_group_rows",
    "seed_total_potential_bytes",
    "mix_candidate",
    "mix_pool",
    "mix_transform_set",
    "mix_transform_count",
    "mix_group_rows",
    "mix_total_potential_bytes",
    "chain_candidate_bytes",
    "promotion_ready_bytes",
    "verdict",
    "blocker",
]


def target_key(row: dict[str, str], start_field: str = "start", end_field: str = "end") -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get(start_field, ""),
        row.get(end_field, ""),
    )


def source_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return target_key(row, "best_source_start", "best_source_end")


def seed_group_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("candidate_pool", ""), row.get("candidate_transform", "")


def mix_group_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("candidate_pool", ""), row.get("candidate_transform_set", "")


def group_count(groups: dict[tuple[str, str], dict[str, str]], key: tuple[str, str]) -> int:
    if not key[0] or not key[1]:
        return 0
    return int_value(groups.get(key, {}), "rows")


def build_chain_rows(
    backref_rows: list[dict[str, str]],
    seed_rows: list[dict[str, str]],
    seed_group_rows: list[dict[str, str]],
    mix_rows: list[dict[str, str]],
    mix_group_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    seed_by_target = {target_key(row): row for row in seed_rows}
    mix_by_target = {target_key(row): row for row in mix_rows}
    seed_groups = {(row.get("pool", ""), row.get("transform", "")): row for row in seed_group_rows}
    mix_groups = {(row.get("pool", ""), row.get("transform_set", "")): row for row in mix_group_rows}
    chains: list[dict[str, str]] = []

    for backref in backref_rows:
        if backref.get("best_exact") != "1":
            continue
        key = source_key(backref)
        seed = seed_by_target.get(key, {})
        mix = mix_by_target.get(key, {})
        seed_candidate = bool(seed.get("candidate_pool"))
        mix_candidate = bool(mix.get("candidate_pool"))
        seed_group_rows_count = group_count(seed_groups, seed_group_key(seed))
        mix_group_rows_count = group_count(mix_groups, mix_group_key(mix))
        length = int_value(backref, "length")
        chain_candidate_bytes = 0
        if seed_candidate or mix_candidate:
            chain_candidate_bytes = length * 2
        repeated_group = seed_group_rows_count > 1 or mix_group_rows_count > 1
        if chain_candidate_bytes and repeated_group:
            verdict = "repeatable_source_chain_review"
            blocker = "requires value replay validation"
        elif chain_candidate_bytes:
            verdict = "singleton_source_chain_blocked"
            blocker = "source palette cover group is singleton"
        else:
            verdict = "missing_source_candidate"
            blocker = "first occurrence has no palette source candidate"
        chains.append(
            {
                "copy_rank": backref.get("rank", ""),
                "archive": backref.get("archive", ""),
                "archive_tag": backref.get("archive_tag", ""),
                "pcx_name": backref.get("pcx_name", ""),
                "frontier_id": backref.get("frontier_id", ""),
                "copy_span_index": backref.get("span_index", ""),
                "copy_op_index": backref.get("op_index", ""),
                "copy_start": backref.get("start", ""),
                "copy_end": backref.get("end", ""),
                "source_start": backref.get("best_source_start", ""),
                "source_end": backref.get("best_source_end", ""),
                "distance": backref.get("best_distance", ""),
                "copy_length": str(length),
                "seed_candidate": "1" if seed_candidate else "0",
                "seed_pool": seed.get("candidate_pool", ""),
                "seed_transform": seed.get("candidate_transform", ""),
                "seed_group_rows": str(seed_group_rows_count),
                "seed_total_potential_bytes": seed.get("total_potential_bytes", "0"),
                "mix_candidate": "1" if mix_candidate else "0",
                "mix_pool": mix.get("candidate_pool", ""),
                "mix_transform_set": mix.get("candidate_transform_set", ""),
                "mix_transform_count": mix.get("transform_count", "0"),
                "mix_group_rows": str(mix_group_rows_count),
                "mix_total_potential_bytes": mix.get("total_potential_bytes", "0"),
                "chain_candidate_bytes": str(chain_candidate_bytes),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "blocker": blocker,
            }
        )
    chains.sort(
        key=lambda row: (
            -int_value(row, "chain_candidate_bytes"),
            int_value(row, "copy_start"),
            row.get("pcx_name", ""),
        )
    )
    return chains


def build_summary(chains: list[dict[str, str]]) -> dict[str, str]:
    seed_candidates = [row for row in chains if row.get("seed_candidate") == "1"]
    mix_candidates = [row for row in chains if row.get("mix_candidate") == "1"]
    any_candidates = [row for row in chains if int_value(row, "chain_candidate_bytes") > 0]
    repeated = [
        row
        for row in chains
        if int_value(row, "chain_candidate_bytes") > 0
        and (int_value(row, "seed_group_rows") > 1 or int_value(row, "mix_group_rows") > 1)
    ]
    return {
        "scope": "total",
        "exact_copy_rows": str(len(chains)),
        "exact_copy_bytes": str(sum(int_value(row, "copy_length") for row in chains)),
        "seed_source_candidate_rows": str(len(seed_candidates)),
        "seed_source_candidate_bytes": str(sum(int_value(row, "copy_length") for row in seed_candidates)),
        "mix_source_candidate_rows": str(len(mix_candidates)),
        "mix_source_candidate_bytes": str(sum(int_value(row, "copy_length") for row in mix_candidates)),
        "any_source_candidate_rows": str(len(any_candidates)),
        "any_source_candidate_bytes": str(sum(int_value(row, "copy_length") for row in any_candidates)),
        "any_source_chain_bytes": str(sum(int_value(row, "chain_candidate_bytes") for row in any_candidates)),
        "repeated_group_rows": str(len(repeated)),
        "repeated_group_chain_bytes": str(sum(int_value(row, "chain_candidate_bytes") for row in repeated)),
        "promotion_ready_bytes": "0",
        "blocked_chain_rows": str(len([row for row in chains if row.get("promotion_ready_bytes") == "0"])),
        "blocked_chain_bytes": str(sum(int_value(row, "chain_candidate_bytes") for row in chains)),
        "issue_rows": "0",
    }


def build_rows(
    backref_rows: list[dict[str, str]],
    seed_rows: list[dict[str, str]],
    seed_group_rows: list[dict[str, str]],
    mix_rows: list[dict[str, str]],
    mix_group_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    chains = build_chain_rows(backref_rows, seed_rows, seed_group_rows, mix_rows, mix_group_rows)
    return build_summary(chains), chains


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 120) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, str], chains: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "chains": chains}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("chains.csv", output_dir / "chains.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1580px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Links exact flat-walk copies to first-occurrence palette source hypotheses.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Exact copy bytes</div><div class="value">{summary['exact_copy_bytes']}</div></div>
    <div class="stat"><div class="label">Any source chains</div><div class="value warn">{summary['any_source_chain_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated group bytes</div><div class="value">{summary['repeated_group_chain_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Chains</h2>{render_table(chains, CHAIN_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_BACKREF_CHAIN_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Join .tex flat-walk exact backrefs to palette source hypotheses.")
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("--seed-targets", type=Path, default=DEFAULT_SEED_TARGETS)
    parser.add_argument("--seed-groups", type=Path, default=DEFAULT_SEED_GROUPS)
    parser.add_argument("--mix-targets", type=Path, default=DEFAULT_MIX_TARGETS)
    parser.add_argument("--mix-groups", type=Path, default=DEFAULT_MIX_GROUPS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Backref Chain Probe",
    )
    args = parser.parse_args()

    summary, chains = build_rows(
        read_csv(args.backref_targets),
        read_csv(args.seed_targets),
        read_csv(args.seed_groups),
        read_csv(args.mix_targets),
        read_csv(args.mix_groups),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, chains, args.output, args.title))

    print(f"Exact copy bytes: {summary['exact_copy_bytes']}")
    print(f"Any source chain bytes: {summary['any_source_chain_bytes']}")
    print(f"Repeated group chain bytes: {summary['repeated_group_chain_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
