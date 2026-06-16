#!/usr/bin/env python3
"""Link repeated gradient seeds to palette candidates and copy-unlock potential."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe")
DEFAULT_GRADIENT_REPEAT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe/targets.csv"
)
DEFAULT_PALETTE_SEED_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe/targets.csv"
)
DEFAULT_PALETTE_MIX_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "seed_rows",
    "seed_bytes",
    "candidate_seed_rows",
    "candidate_seed_bytes",
    "control_seed_rows",
    "control_seed_bytes",
    "single_transform_seed_rows",
    "single_transform_seed_bytes",
    "mixed_transform_seed_rows",
    "mixed_transform_seed_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_seed_plus_unlock_bytes",
    "payload_pair_groups",
    "payload_pair_rows",
    "payload_pair_bytes",
    "copy_distance_320_pair_groups",
    "copy_distance_320_pair_bytes",
    "transform_set_groups",
    "repeated_transform_set_groups",
    "repeated_transform_set_bytes",
    "blocked_seed_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
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
    "shape_context_key",
    "payload_signature",
    "copy_target_start",
    "copy_target_end",
    "copy_target_span_index",
    "copy_target_op_index",
    "copy_distance",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "evidence_sources",
    "candidate_pool",
    "candidate_kind",
    "transform_count",
    "candidate_transform_set",
    "candidate_plan",
    "palette_size",
    "unique_values_hex",
    "total_potential_bytes",
    "verdict",
    "issues",
]

TRANSFORM_FIELDNAMES = [
    "candidate_pool",
    "candidate_transform_set",
    "rows",
    "seed_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "candidate_kinds",
    "palette_sizes",
    "evidence_sources",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

PAYLOAD_PAIR_FIELDNAMES = [
    "payload_signature",
    "shape_context_key",
    "rows",
    "bytes",
    "seed_start",
    "copy_start",
    "copy_distance",
    "seed_bytes",
    "copy_bytes",
    "candidate_pool",
    "candidate_transform_set",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def seed_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("run_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def copy_source_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("copy_source_start", ""),
    )


def palette_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("run_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def normalize_seed_candidate(row: dict[str, str]) -> dict[str, str]:
    return {
        "source": "palette_seed",
        "candidate_pool": row.get("candidate_pool", ""),
        "candidate_kind": "single_transform" if row.get("candidate_pool") else "",
        "transform_count": "1" if row.get("candidate_pool") else "0",
        "candidate_transform_set": row.get("candidate_transform", ""),
        "candidate_plan": row.get("candidate_offsets", ""),
        "palette_size": row.get("palette_size", ""),
        "unique_values_hex": row.get("unique_values_hex", ""),
        "issues": row.get("issues", ""),
    }


def normalize_mix_candidate(row: dict[str, str]) -> dict[str, str]:
    return {
        "source": "palette_mix",
        "candidate_pool": row.get("candidate_pool", ""),
        "candidate_kind": row.get("candidate_kind", ""),
        "transform_count": row.get("transform_count", "0"),
        "candidate_transform_set": row.get("candidate_transform_set", ""),
        "candidate_plan": row.get("candidate_plan", ""),
        "palette_size": row.get("palette_size", ""),
        "unique_values_hex": row.get("unique_values_hex", ""),
        "issues": row.get("issues", ""),
    }


def build_candidate_map(
    palette_seed_rows: list[dict[str, str]],
    palette_mix_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str, str, str, str, str], list[dict[str, str]]]:
    candidates: dict[tuple[str, str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in palette_seed_rows:
        if row.get("candidate_pool"):
            candidates[palette_key(row)].append(normalize_seed_candidate(row))
    for row in palette_mix_rows:
        if row.get("candidate_pool"):
            candidates[palette_key(row)].append(normalize_mix_candidate(row))
    return candidates


def candidate_score(row: dict[str, str]) -> tuple[int, int, int, str, str]:
    source_rank = 0 if row.get("source") == "palette_mix" else 1
    pool_rank = 0 if row.get("candidate_pool") == "control_window" else 1
    return (
        pool_rank,
        int_value(row, "transform_count"),
        source_rank,
        row.get("candidate_transform_set", ""),
        row.get("source", ""),
    )


def pick_candidate(candidates: list[dict[str, str]]) -> dict[str, str]:
    usable = [row for row in candidates if row.get("candidate_pool")]
    if not usable:
        return {}
    return min(usable, key=candidate_score)


def build_copy_map(gradient_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    copies: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in gradient_rows:
        if row.get("copy_unlock") != "1":
            continue
        copies[copy_source_key(row)].append(row)
    return copies


def build_target_rows(
    gradient_rows: list[dict[str, str]],
    palette_seed_rows: list[dict[str, str]],
    palette_mix_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    candidate_map = build_candidate_map(palette_seed_rows, palette_mix_rows)
    copy_map = build_copy_map(gradient_rows)
    seed_rows = [row for row in gradient_rows if row.get("copy_unlock") != "1"]
    output: list[dict[str, str]] = []

    for seed in sorted(seed_rows, key=lambda row: (row.get("shape_context_key", ""), int_value(row, "start"))):
        key = seed_key(seed)
        candidates = candidate_map.get(key, [])
        candidate = pick_candidate(candidates)
        copy_targets = copy_map.get(
            (seed.get("archive", ""), seed.get("pcx_name", ""), seed.get("frontier_id", ""), seed.get("start", "")),
            [],
        )
        copy_targets.sort(key=lambda row: int_value(row, "start"))
        copy_unlock_bytes = sum(int_value(row, "length") for row in copy_targets)
        copy_distances = sorted({row.get("copy_distance", "") for row in copy_targets if row.get("copy_distance")})
        issues = [issue for issue in seed.get("issues", "").split(";") if issue]
        for row in candidates:
            issues.extend(issue for issue in row.get("issues", "").split(";") if issue)
        if not candidate:
            issues.append("missing_palette_seed_candidate")
        if not copy_targets:
            issues.append("missing_copy_unlock_target")
        evidence_sources = ",".join(sorted({row.get("source", "") for row in candidates if row.get("source")}))
        candidate_kind = candidate.get("candidate_kind", "")
        if not candidate:
            verdict = "seed_without_candidate"
        elif copy_unlock_bytes <= 0:
            verdict = f"{candidate_kind or 'candidate'}_seed_review"
        else:
            verdict = f"{candidate_kind or 'candidate'}_seed_unlocks_gradient_copy"
        first_copy = copy_targets[0] if copy_targets else {}
        output.append(
            {
                "archive": seed.get("archive", ""),
                "archive_tag": seed.get("archive_tag", ""),
                "pcx_name": seed.get("pcx_name", ""),
                "frontier_id": seed.get("frontier_id", ""),
                "span_index": seed.get("span_index", ""),
                "run_index": seed.get("run_index", ""),
                "op_index": seed.get("op_index", ""),
                "length": seed.get("length", ""),
                "start": seed.get("start", ""),
                "end": seed.get("end", ""),
                "start_mod64": seed.get("start_mod64", ""),
                "control_ref_mod64": seed.get("control_ref_mod64", ""),
                "shape_context_key": seed.get("shape_context_key", ""),
                "payload_signature": seed.get("payload_signature", ""),
                "copy_target_start": first_copy.get("start", ""),
                "copy_target_end": first_copy.get("end", ""),
                "copy_target_span_index": first_copy.get("span_index", ""),
                "copy_target_op_index": first_copy.get("op_index", ""),
                "copy_distance": "|".join(copy_distances),
                "copy_unlock_rows": str(len(copy_targets)),
                "copy_unlock_bytes": str(copy_unlock_bytes),
                "evidence_sources": evidence_sources,
                "candidate_pool": candidate.get("candidate_pool", ""),
                "candidate_kind": candidate_kind,
                "transform_count": candidate.get("transform_count", "0"),
                "candidate_transform_set": candidate.get("candidate_transform_set", ""),
                "candidate_plan": candidate.get("candidate_plan", ""),
                "palette_size": candidate.get("palette_size", ""),
                "unique_values_hex": candidate.get("unique_values_hex", ""),
                "total_potential_bytes": str(int_value(seed, "length") + copy_unlock_bytes if candidate else 0),
                "verdict": verdict,
                "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
            }
        )
    return output


def build_transform_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    values: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    samples: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if not row.get("candidate_pool"):
            continue
        key = row.get("candidate_pool", ""), row.get("candidate_transform_set", "")
        counters[key]["rows"] += 1
        counters[key]["seed_bytes"] += int_value(row, "length")
        counters[key]["copy_unlock_rows"] += int_value(row, "copy_unlock_rows")
        counters[key]["copy_unlock_bytes"] += int_value(row, "copy_unlock_bytes")
        counters[key]["total_potential_bytes"] += int_value(row, "total_potential_bytes")
        values[key]["candidate_kinds"].add(row.get("candidate_kind", ""))
        values[key]["palette_sizes"].add(row.get("palette_size", ""))
        values[key]["evidence_sources"].update(row.get("evidence_sources", "").split(","))
        samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        rows_count = counter["rows"]
        output.append(
            {
                "candidate_pool": key[0],
                "candidate_transform_set": key[1],
                "rows": str(rows_count),
                "seed_bytes": str(counter["seed_bytes"]),
                "copy_unlock_rows": str(counter["copy_unlock_rows"]),
                "copy_unlock_bytes": str(counter["copy_unlock_bytes"]),
                "total_potential_bytes": str(counter["total_potential_bytes"]),
                "candidate_kinds": "|".join(sorted(value for value in values[key]["candidate_kinds"] if value)),
                "palette_sizes": "|".join(sorted(value for value in values[key]["palette_sizes"] if value)),
                "evidence_sources": "|".join(sorted(value for value in values[key]["evidence_sources"] if value)),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": "repeated_transform_review" if rows_count > 1 else "singleton_transform_blocks_promotion",
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "total_potential_bytes"),
            -int_value(row, "seed_bytes"),
            row.get("candidate_pool", ""),
            row.get("candidate_transform_set", ""),
        )
    )
    return output


def build_payload_pair_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        pair_rows = 1 + int_value(row, "copy_unlock_rows")
        seed_bytes = int_value(row, "length")
        copy_bytes = int_value(row, "copy_unlock_bytes")
        output.append(
            {
                "payload_signature": row.get("payload_signature", ""),
                "shape_context_key": row.get("shape_context_key", ""),
                "rows": str(pair_rows),
                "bytes": str(seed_bytes + copy_bytes),
                "seed_start": row.get("start", ""),
                "copy_start": row.get("copy_target_start", ""),
                "copy_distance": row.get("copy_distance", ""),
                "seed_bytes": str(seed_bytes),
                "copy_bytes": str(copy_bytes),
                "candidate_pool": row.get("candidate_pool", ""),
                "candidate_transform_set": row.get("candidate_transform_set", ""),
                "copy_unlock_bytes": str(copy_bytes),
                "total_potential_bytes": row.get("total_potential_bytes", "0"),
                "verdict": row.get("verdict", ""),
                "sample_pcx": row.get("pcx_name", ""),
                "sample_frontier_id": row.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), row.get("payload_signature", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    transform_rows: list[dict[str, str]],
    payload_pair_rows: list[dict[str, str]],
) -> dict[str, str]:
    candidates = [row for row in rows if row.get("candidate_pool")]
    control = [row for row in candidates if row.get("candidate_pool") == "control_window"]
    single = [row for row in candidates if row.get("candidate_kind") == "single_transform"]
    mixed = [row for row in candidates if row.get("candidate_kind") == "mixed_transform"]
    repeated_transform_rows = [row for row in transform_rows if int_value(row, "rows") > 1]
    copy_distance_320 = [row for row in payload_pair_rows if row.get("copy_distance") == "320"]
    repeated_transform_seed_bytes = sum(int_value(row, "seed_bytes") for row in repeated_transform_rows)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "seed_rows": str(len(rows)),
        "seed_bytes": str(sum(int_value(row, "length") for row in rows)),
        "candidate_seed_rows": str(len(candidates)),
        "candidate_seed_bytes": str(sum(int_value(row, "length") for row in candidates)),
        "control_seed_rows": str(len(control)),
        "control_seed_bytes": str(sum(int_value(row, "length") for row in control)),
        "single_transform_seed_rows": str(len(single)),
        "single_transform_seed_bytes": str(sum(int_value(row, "length") for row in single)),
        "mixed_transform_seed_rows": str(len(mixed)),
        "mixed_transform_seed_bytes": str(sum(int_value(row, "length") for row in mixed)),
        "copy_unlock_rows": str(sum(int_value(row, "copy_unlock_rows") for row in candidates)),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in candidates)),
        "total_seed_plus_unlock_bytes": str(sum(int_value(row, "total_potential_bytes") for row in candidates)),
        "payload_pair_groups": str(len(payload_pair_rows)),
        "payload_pair_rows": str(sum(int_value(row, "rows") for row in payload_pair_rows)),
        "payload_pair_bytes": str(sum(int_value(row, "bytes") for row in payload_pair_rows)),
        "copy_distance_320_pair_groups": str(len(copy_distance_320)),
        "copy_distance_320_pair_bytes": str(sum(int_value(row, "bytes") for row in copy_distance_320)),
        "transform_set_groups": str(len(transform_rows)),
        "repeated_transform_set_groups": str(len(repeated_transform_rows)),
        "repeated_transform_set_bytes": str(repeated_transform_seed_bytes),
        "blocked_seed_bytes": str(sum(int_value(row, "length") for row in candidates) - repeated_transform_seed_bytes),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    transform_rows: list[dict[str, str]],
    payload_pair_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": targets,
        "transformRows": transform_rows,
        "payloadPairRows": payload_pair_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_transform_set.csv", output_dir / "by_transform_set.csv"),
            ("by_payload_pair.csv", output_dir / "by_payload_pair.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1760px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Links repeated gradient first occurrences to palette seed candidates and distance-320 copy unlocks.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Seed rows</div><div class="value">{summary['seed_rows']}</div></div>
    <div class="stat"><div class="label">Seed bytes</div><div class="value warn">{summary['seed_bytes']}</div></div>
    <div class="stat"><div class="label">Candidate seed bytes</div><div class="value warn">{summary['candidate_seed_bytes']}</div></div>
    <div class="stat"><div class="label">Copy unlock bytes</div><div class="value warn">{summary['copy_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Total potential bytes</div><div class="value">{summary['total_seed_plus_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Transform sets</h2>{render_table(transform_rows, TRANSFORM_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Payload pairs</h2>{render_table(payload_pair_rows, PAYLOAD_PAIR_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Seed targets</h2>{render_table(targets, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_UNLOCK_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe gradient seed candidates that unlock repeated payload copies.")
    parser.add_argument("--gradient-repeat-targets", type=Path, default=DEFAULT_GRADIENT_REPEAT_TARGETS)
    parser.add_argument("--palette-seed-targets", type=Path, default=DEFAULT_PALETTE_SEED_TARGETS)
    parser.add_argument("--palette-mix-targets", type=Path, default=DEFAULT_PALETTE_MIX_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Unlock Probe",
    )
    args = parser.parse_args()

    targets = build_target_rows(
        read_csv(args.gradient_repeat_targets),
        read_csv(args.palette_seed_targets),
        read_csv(args.palette_mix_targets),
    )
    transform_rows = build_transform_rows(targets)
    payload_pair_rows = build_payload_pair_rows(targets)
    summary = build_summary(targets, transform_rows, payload_pair_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_transform_set.csv", TRANSFORM_FIELDNAMES, transform_rows)
    write_csv(args.output / "by_payload_pair.csv", PAYLOAD_PAIR_FIELDNAMES, payload_pair_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, transform_rows, payload_pair_rows, args.output, args.title))

    print(f"Gradient seed rows: {summary['seed_rows']}")
    print(f"Candidate seed bytes: {summary['candidate_seed_bytes']}")
    print(f"Copy-unlock bytes: {summary['copy_unlock_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
