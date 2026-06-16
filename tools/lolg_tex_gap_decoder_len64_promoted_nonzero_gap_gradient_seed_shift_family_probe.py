#!/usr/bin/env python3
"""Group gradient seed palette candidates by source-shift family."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe")
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "candidate_rows",
    "candidate_bytes",
    "identity_shift_family_rows",
    "identity_shift_family_bytes",
    "repeated_family_groups",
    "repeated_family_bytes",
    "exact_shift_set_groups",
    "repeated_exact_shift_set_groups",
    "repeated_exact_shift_set_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "covered_palette_values",
    "distinct_shift_deltas",
    "shift_delta_min",
    "shift_delta_max",
    "max_source_offset",
    "max_offset_span",
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
    "payload_signature",
    "candidate_pool",
    "candidate_kind",
    "palette_size",
    "covered_values",
    "base_transforms",
    "shift_deltas",
    "shift_delta_min",
    "shift_delta_max",
    "source_offsets",
    "min_source_offset",
    "max_source_offset",
    "offset_span",
    "family_key",
    "exact_shift_set_key",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "verdict",
    "issues",
]

FAMILY_FIELDNAMES = [
    "family_key",
    "rows",
    "seed_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "covered_palette_values",
    "exact_shift_sets",
    "shift_deltas",
    "source_offset_min",
    "source_offset_max",
    "max_offset_span",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

SHIFT_SET_FIELDNAMES = [
    "exact_shift_set_key",
    "rows",
    "seed_bytes",
    "copy_unlock_rows",
    "copy_unlock_bytes",
    "total_potential_bytes",
    "families",
    "covered_palette_values",
    "source_offset_min",
    "source_offset_max",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def parse_transform(transform: str) -> tuple[str, int]:
    if "_shift" not in transform:
        return transform, 0
    base, delta_text = transform.split("_shift", 1)
    return base, int(delta_text)


def parse_plan(plan: str) -> list[dict[str, str | int]]:
    output: list[dict[str, str | int]] = []
    for token in plan.split():
        if "=" not in token or "@" not in token:
            continue
        value_hex, rest = token.split("=", 1)
        transform, offset_text = rest.rsplit("@", 1)
        try:
            value = int(value_hex, 16)
            offset = int(offset_text)
        except ValueError:
            continue
        try:
            base, delta = parse_transform(transform)
        except ValueError:
            continue
        output.append(
            {
                "value": value,
                "transform": transform,
                "base": base,
                "delta": delta,
                "offset": offset,
            }
        )
    return output


def compact_ints(values: list[int]) -> str:
    return "|".join(str(value) for value in values)


def unique_sorted(values: list[int]) -> list[int]:
    return sorted(set(values))


def family_key(pool: str, bases: list[str], deltas: list[int]) -> str:
    if pool == "control_window" and set(bases) == {"identity"} and deltas:
        return "control_window|identity_shift_family"
    base_text = "+".join(sorted(set(bases))) if bases else "missing"
    return f"{pool or 'missing_pool'}|base={base_text}|shift_family"


def target_verdict(row: dict[str, str]) -> str:
    if not row.get("candidate_pool"):
        return "missing_candidate"
    if row.get("family_key") == "control_window|identity_shift_family":
        return "identity_shift_family_review"
    return "non_identity_shift_family_review"


def build_target_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        plan = parse_plan(row.get("candidate_plan", ""))
        if not plan:
            issues.append("missing_candidate_plan")
        values = [int(item["value"]) for item in plan]
        offsets = [int(item["offset"]) for item in plan]
        deltas = [int(item["delta"]) for item in plan]
        bases = sorted({str(item["base"]) for item in plan})
        shift_values = unique_sorted(deltas)
        min_offset = min(offsets) if offsets else 0
        max_offset = max(offsets) if offsets else 0
        min_delta = min(deltas) if deltas else 0
        max_delta = max(deltas) if deltas else 0
        row_family = family_key(row.get("candidate_pool", ""), bases, deltas)
        exact_key = f"{row_family}|deltas={compact_ints(shift_values)}"
        output_row = {
            "archive": row.get("archive", ""),
            "archive_tag": row.get("archive_tag", ""),
            "pcx_name": row.get("pcx_name", ""),
            "frontier_id": row.get("frontier_id", ""),
            "span_index": row.get("span_index", ""),
            "run_index": row.get("run_index", ""),
            "op_index": row.get("op_index", ""),
            "length": row.get("length", ""),
            "start": row.get("start", ""),
            "end": row.get("end", ""),
            "payload_signature": row.get("payload_signature", ""),
            "candidate_pool": row.get("candidate_pool", ""),
            "candidate_kind": row.get("candidate_kind", ""),
            "palette_size": row.get("palette_size", ""),
            "covered_values": str(len(values)),
            "base_transforms": "|".join(bases),
            "shift_deltas": compact_ints(shift_values),
            "shift_delta_min": str(min_delta),
            "shift_delta_max": str(max_delta),
            "source_offsets": compact_ints(offsets),
            "min_source_offset": str(min_offset),
            "max_source_offset": str(max_offset),
            "offset_span": str(max_offset - min_offset if offsets else 0),
            "family_key": row_family,
            "exact_shift_set_key": exact_key,
            "copy_unlock_rows": row.get("copy_unlock_rows", "0"),
            "copy_unlock_bytes": row.get("copy_unlock_bytes", "0"),
            "total_potential_bytes": row.get("total_potential_bytes", "0"),
            "verdict": "",
            "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
        }
        output_row["verdict"] = target_verdict(output_row)
        output.append(output_row)
    output.sort(key=lambda item: (-int_value(item, "length"), item.get("family_key", ""), item.get("start", "")))
    return output


def build_group_rows(rows: list[dict[str, str]], key_field: str, fields: list[str]) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    values: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        if not key:
            continue
        counters[key]["rows"] += 1
        counters[key]["seed_bytes"] += int_value(row, "length")
        counters[key]["copy_unlock_rows"] += int_value(row, "copy_unlock_rows")
        counters[key]["copy_unlock_bytes"] += int_value(row, "copy_unlock_bytes")
        counters[key]["total_potential_bytes"] += int_value(row, "total_potential_bytes")
        counters[key]["covered_palette_values"] += int_value(row, "covered_values")
        values[key]["families"].add(row.get("family_key", ""))
        values[key]["exact_shift_sets"].add(row.get("exact_shift_set_key", ""))
        values[key]["shift_deltas"].update(value for value in row.get("shift_deltas", "").split("|") if value)
        values[key]["source_offsets"].update(value for value in row.get("source_offsets", "").split("|") if value)
        samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        offsets = sorted(int(value) for value in values[key]["source_offsets"] if value)
        common = {
            key_field: key,
            "rows": str(counter["rows"]),
            "seed_bytes": str(counter["seed_bytes"]),
            "copy_unlock_rows": str(counter["copy_unlock_rows"]),
            "copy_unlock_bytes": str(counter["copy_unlock_bytes"]),
            "total_potential_bytes": str(counter["total_potential_bytes"]),
            "covered_palette_values": str(counter["covered_palette_values"]),
            "source_offset_min": str(min(offsets) if offsets else 0),
            "source_offset_max": str(max(offsets) if offsets else 0),
            "sample_pcx": sample.get("pcx_name", ""),
            "sample_frontier_id": sample.get("frontier_id", ""),
        }
        if key_field == "family_key":
            common.update(
                {
                    "exact_shift_sets": str(len(values[key]["exact_shift_sets"])),
                    "shift_deltas": "|".join(sorted(values[key]["shift_deltas"], key=int)),
                    "max_offset_span": str(max(int_value(row, "offset_span") for row in rows if row.get(key_field) == key)),
                    "verdict": (
                        "repeated_shift_family_needs_delta_selector"
                        if counter["rows"] > 1
                        else "singleton_shift_family_review"
                    ),
                }
            )
        else:
            common.update(
                {
                    "families": "|".join(sorted(values[key]["families"])),
                    "verdict": (
                        "repeated_exact_shift_set_review"
                        if counter["rows"] > 1
                        else "singleton_exact_shift_set_blocks_promotion"
                    ),
                }
            )
        output.append({field: common.get(field, "") for field in fields})
    output.sort(key=lambda row: (-int_value(row, "seed_bytes"), row.get(key_field, "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    shift_set_rows: list[dict[str, str]],
) -> dict[str, str]:
    candidates = [row for row in rows if row.get("candidate_pool")]
    identity_family = [row for row in candidates if row.get("family_key") == "control_window|identity_shift_family"]
    repeated_family = [row for row in family_rows if int_value(row, "rows") > 1]
    repeated_shift_sets = [row for row in shift_set_rows if int_value(row, "rows") > 1]
    all_deltas = sorted({int(value) for row in candidates for value in row.get("shift_deltas", "").split("|") if value})
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "candidate_rows": str(len(candidates)),
        "candidate_bytes": str(sum(int_value(row, "length") for row in candidates)),
        "identity_shift_family_rows": str(len(identity_family)),
        "identity_shift_family_bytes": str(sum(int_value(row, "length") for row in identity_family)),
        "repeated_family_groups": str(len(repeated_family)),
        "repeated_family_bytes": str(sum(int_value(row, "seed_bytes") for row in repeated_family)),
        "exact_shift_set_groups": str(len(shift_set_rows)),
        "repeated_exact_shift_set_groups": str(len(repeated_shift_sets)),
        "repeated_exact_shift_set_bytes": str(sum(int_value(row, "seed_bytes") for row in repeated_shift_sets)),
        "copy_unlock_rows": str(sum(int_value(row, "copy_unlock_rows") for row in candidates)),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in candidates)),
        "total_potential_bytes": str(sum(int_value(row, "total_potential_bytes") for row in candidates)),
        "covered_palette_values": str(sum(int_value(row, "covered_values") for row in candidates)),
        "distinct_shift_deltas": str(len(all_deltas)),
        "shift_delta_min": str(min(all_deltas) if all_deltas else 0),
        "shift_delta_max": str(max(all_deltas) if all_deltas else 0),
        "max_source_offset": str(max((int_value(row, "max_source_offset") for row in candidates), default=0)),
        "max_offset_span": str(max((int_value(row, "offset_span") for row in candidates), default=0)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    targets: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    shift_set_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": targets, "familyRows": family_rows, "shiftSetRows": shift_set_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_family.csv", output_dir / "by_family.csv"),
            ("by_shift_set.csv", output_dir / "by_shift_set.csv"),
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
.wrap {{ width: min(1760px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Groups gradient seed candidates by shared control-window additive shift family.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidate bytes</div><div class="value warn">{summary['candidate_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated family bytes</div><div class="value warn">{summary['repeated_family_bytes']}</div></div>
    <div class="stat"><div class="label">Exact shift-set bytes</div><div class="value">{summary['repeated_exact_shift_set_bytes']}</div></div>
    <div class="stat"><div class="label">Copy unlock bytes</div><div class="value warn">{summary['copy_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Potential bytes</div><div class="value">{summary['total_potential_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Shift sets</h2>{render_table(shift_set_rows, SHIFT_SET_FIELDNAMES)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(targets, TARGET_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_SHIFT_FAMILY_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe shared shift families for .tex gradient seed candidates.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Seed Shift Family Probe",
    )
    args = parser.parse_args()

    targets = build_target_rows(read_csv(args.targets))
    family_rows = build_group_rows(targets, "family_key", FAMILY_FIELDNAMES)
    shift_set_rows = build_group_rows(targets, "exact_shift_set_key", SHIFT_SET_FIELDNAMES)
    summary = build_summary(targets, family_rows, shift_set_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    write_csv(args.output / "by_family.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(args.output / "by_shift_set.csv", SHIFT_SET_FIELDNAMES, shift_set_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, targets, family_rows, shift_set_rows, args.output, args.title))

    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Repeated family bytes: {summary['repeated_family_bytes']}")
    print(f"Repeated exact shift-set bytes: {summary['repeated_exact_shift_set_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
