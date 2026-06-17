#!/usr/bin/env python3
"""Probe residual gradient macro conflicts against source windows and state bins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_macro_opcode_probe import byte_window_hex, class_window
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import fixture_key, int_value, load_sources, ratio


DEFAULT_MACRO_ROWS = Path("output/tex_gradient_macro_opcode/rows.csv")
DEFAULT_SPLIT_SUMMARY = Path("output/tex_gradient_macro_conflict_split/summary.csv")
DEFAULT_SPLITS = Path("output/tex_gradient_macro_conflict_split/splits.csv")
DEFAULT_TARGET_ROWS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_macro_residual_state")

SUMMARY_FIELDNAMES = [
    "scope",
    "residual_selector_family",
    "residual_selector_key",
    "residual_rows",
    "residual_bytes",
    "selector_families",
    "source_selector_families",
    "state_selector_families",
    "selector_groups",
    "repeated_selector_groups",
    "source_deterministic_repeated_evidence_bytes",
    "source_conflicted_evidence_bytes",
    "state_deterministic_repeated_evidence_bytes",
    "state_conflicted_evidence_bytes",
    "best_source_selector_family",
    "best_source_deterministic_bytes",
    "best_source_conflicted_bytes",
    "best_source_singleton_bytes",
    "best_state_selector_family",
    "best_state_deterministic_bytes",
    "best_state_conflicted_bytes",
    "best_state_singleton_bytes",
    "best_selector_family",
    "best_selector_type",
    "best_deterministic_bytes",
    "best_conflicted_bytes",
    "best_singleton_bytes",
    "best_remaining_conflict_key",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "length",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "start_anchor_offset",
    "dominant_delta",
    "top_nibble",
    "gradient_class",
    "control_window_signature",
    "control_anchor_hex",
    "control_anchor_class",
    "start_anchor_hex",
    "start_anchor_class",
    "source_window_signature",
    "state_signature",
    "payload_signature",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "selector_type",
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "dominant_delta_values",
    "dominant_value",
    "dominant_ratio",
    "deterministic_bytes",
    "conflicted_bytes",
    "singleton_bytes",
    "sample_span_index",
    "sample_op_index",
    "verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "selector_type",
    "selector_family",
    "groups",
    "repeated_groups",
    "deterministic_repeated_groups",
    "deterministic_repeated_bytes",
    "conflicted_groups",
    "conflicted_bytes",
    "singleton_groups",
    "singleton_bytes",
    "best_remaining_conflict_key",
    "best_remaining_conflict_bytes",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha_text(value: str) -> str:
    return hashlib.sha1(value.encode("ascii")).hexdigest()[:14]


def band(value: int, step: int) -> str:
    base = (value // step) * step
    return f"{base}-{base + step - 1}"


def join_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("op_index", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def conflict_group_key(row: dict[str, str]) -> str:
    return f"{row.get('fixture_rule_key', '')}|len={row.get('length_bucket', '')}"


def load_residual_selector(summary_rows: list[dict[str, str]]) -> tuple[str, str]:
    if not summary_rows:
        return "", ""
    summary = summary_rows[0]
    return summary.get("best_split_family", ""), summary.get("best_remaining_conflict_key", "")


def matching_split_group(
    split_rows: list[dict[str, str]],
    selector_family: str,
    selector_key: str,
) -> dict[str, str]:
    for row in split_rows:
        if row.get("selector_family") == selector_family and row.get("selector_key") == selector_key:
            return row
    return {}


def selector_value(row: dict[str, str], selector_family: str) -> str:
    if selector_family == "control_anchor_class":
        return row.get("control_anchor_class_key", "")
    if selector_family == "control_window_class":
        return row.get("control_window_class_key", "")
    if selector_family == "start_anchor_class":
        return row.get("start_anchor_class_key", "")
    return ""


def build_rows(
    macro_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    split_summary_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str], str, str]:
    selector_family, selector_key = load_residual_selector(split_summary_rows)
    split_group = matching_split_group(split_rows, selector_family, selector_key)
    target_by_key = {join_key(row): row for row in target_rows}
    sources_by_fixture, fixture_issues = load_sources(fixture_rows)
    output: list[dict[str, object]] = []
    issues = list(fixture_issues)

    for macro_row in macro_rows:
        if selector_value(macro_row, selector_family) != selector_key:
            continue
        if split_group and conflict_group_key(macro_row) != split_group.get("conflict_group_key", ""):
            continue
        target = target_by_key.get(join_key(macro_row), {})
        local_issues = [issue for issue in macro_row.get("issues", "").split(";") if issue]
        if not target:
            local_issues.append("missing_target_join")

        sources = sources_by_fixture.get(fixture_key(macro_row), {})
        segment = sources.get("segment_gap", b"")
        control_ref_offset = int_value(target, "control_ref_offset", -1)
        control_ref_mod64 = int_value(target, "control_ref_mod64", -1)
        start_mod64 = int_value(target, "start_mod64", -1)
        start_anchor = (
            control_ref_offset - control_ref_mod64 + start_mod64
            if control_ref_offset >= 0 and control_ref_mod64 >= 0 and start_mod64 >= 0
            else -1
        )
        control_hex = byte_window_hex(segment, control_ref_offset, 6)
        start_hex = byte_window_hex(segment, start_anchor, 6)
        control_class = class_window(segment, control_ref_offset, 6)
        start_class = class_window(segment, start_anchor, 6)
        source_signature = f"cw={target.get('control_window_signature', '')}|ctrl={control_hex}|start={start_hex}"
        state_signature = (
            f"span={macro_row.get('span_index', '')}|op={macro_row.get('op_index', '')}|"
            f"start={macro_row.get('start', '')}|len={macro_row.get('length', '')}"
        )
        output.append(
            {
                "rank": len(output) + 1,
                "archive": macro_row.get("archive", ""),
                "pcx_name": macro_row.get("pcx_name", ""),
                "frontier_id": macro_row.get("frontier_id", ""),
                "span_index": macro_row.get("span_index", ""),
                "op_index": macro_row.get("op_index", ""),
                "length": macro_row.get("length", ""),
                "start": macro_row.get("start", ""),
                "end": macro_row.get("end", ""),
                "start_mod64": target.get("start_mod64", ""),
                "control_ref_offset": target.get("control_ref_offset", ""),
                "control_ref_mod64": target.get("control_ref_mod64", ""),
                "start_anchor_offset": start_anchor,
                "dominant_delta": macro_row.get("dominant_delta", ""),
                "top_nibble": macro_row.get("top_nibble", ""),
                "gradient_class": macro_row.get("gradient_class", ""),
                "control_window_signature": target.get("control_window_signature", ""),
                "control_anchor_hex": control_hex,
                "control_anchor_class": control_class,
                "start_anchor_hex": start_hex,
                "start_anchor_class": start_class,
                "source_window_signature": f"sha1={sha_text(source_signature)}",
                "state_signature": state_signature,
                "payload_signature": macro_row.get("payload_signature", ""),
                "issues": ";".join(local_issues),
            }
        )
    return output, issues, selector_family, selector_key


def selector_values(row: dict[str, object]) -> dict[str, tuple[str, str]]:
    span = int_value(row, "span_index")
    op = int_value(row, "op_index")
    start = int_value(row, "start")
    length = int_value(row, "length")
    return {
        "control_window_signature": ("source", str(row["control_window_signature"])),
        "control_anchor_hex": ("source", str(row["control_anchor_hex"])),
        "start_anchor_hex": ("source", str(row["start_anchor_hex"])),
        "source_window_signature": ("source", str(row["source_window_signature"])),
        "start_mod64": ("source", f"start_mod64={row['start_mod64']}"),
        "span_index_band4": ("state", band(span, 4)),
        "op_index_band8": ("state", band(op, 8)),
        "start_offset_band128": ("state", band(start, 128)),
        "length_band8": ("state", band(length, 8)),
        "exact_length": ("state", f"length={length}"),
        "span_op_band": ("state", f"span={band(span, 4)}|op={band(op, 8)}"),
        "source_length": ("state", f"source={row['source_window_signature']}|len={band(length, 8)}"),
    }


def build_group_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    families = selector_values(rows[0]).keys() if rows else []
    for selector_family in families:
        selector_type = selector_values(rows[0])[selector_family][0]
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[selector_values(row)[selector_family][1]].append(row)
        for selector_key, members in grouped.items():
            values = Counter(str(row["dominant_delta"]) for row in members)
            dominant_value, dominant_count = values.most_common(1)[0]
            rows_count = len(members)
            bytes_count = sum(int_value(row, "length") for row in members)
            deterministic = len(values) == 1
            repeated = rows_count > 1
            output.append(
                {
                    "rank": 0,
                    "selector_type": selector_type,
                    "selector_family": selector_family,
                    "selector_key": selector_key,
                    "rows": rows_count,
                    "bytes": bytes_count,
                    "dominant_delta_values": "|".join(
                        f"{value}:{count}" for value, count in values.most_common()
                    ),
                    "dominant_value": dominant_value,
                    "dominant_ratio": ratio(dominant_count, rows_count),
                    "deterministic_bytes": bytes_count if deterministic and repeated else 0,
                    "conflicted_bytes": bytes_count if not deterministic and repeated else 0,
                    "singleton_bytes": bytes_count if rows_count == 1 else 0,
                    "sample_span_index": members[0].get("span_index", ""),
                    "sample_op_index": members[0].get("op_index", ""),
                    "verdict": (
                        "residual_deterministic_repeat"
                        if deterministic and repeated
                        else "residual_conflicted_repeat"
                        if repeated
                        else "residual_singleton"
                    ),
                }
            )

    output.sort(
        key=lambda row: (
            str(row["selector_type"]),
            str(row["selector_family"]),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            str(row["selector_key"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_family_rows(group_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in group_rows:
        grouped[(str(row["selector_type"]), str(row["selector_family"]))].append(row)

    output: list[dict[str, object]] = []
    for (selector_type, selector_family), members in grouped.items():
        repeated = [row for row in members if int_value(row, "rows") > 1]
        deterministic = [row for row in repeated if int_value(row, "deterministic_bytes") > 0]
        conflicted = [row for row in repeated if int_value(row, "conflicted_bytes") > 0]
        singleton = [row for row in members if int_value(row, "rows") == 1]
        best_remaining = max(conflicted, key=lambda row: int_value(row, "conflicted_bytes"), default={})
        deterministic_bytes = sum(int_value(row, "deterministic_bytes") for row in deterministic)
        conflicted_bytes = sum(int_value(row, "conflicted_bytes") for row in conflicted)
        singleton_bytes = sum(int_value(row, "singleton_bytes") for row in singleton)
        output.append(
            {
                "rank": 0,
                "selector_type": selector_type,
                "selector_family": selector_family,
                "groups": len(members),
                "repeated_groups": len(repeated),
                "deterministic_repeated_groups": len(deterministic),
                "deterministic_repeated_bytes": deterministic_bytes,
                "conflicted_groups": len(conflicted),
                "conflicted_bytes": conflicted_bytes,
                "singleton_groups": len(singleton),
                "singleton_bytes": singleton_bytes,
                "best_remaining_conflict_key": best_remaining.get("selector_key", ""),
                "best_remaining_conflict_bytes": best_remaining.get("conflicted_bytes", 0),
                "verdict": (
                    "state_phase_candidate"
                    if selector_type == "state" and deterministic_bytes and not conflicted_bytes
                    else "source_still_conflicted"
                    if selector_type == "source" and conflicted_bytes
                    else "residual_partial_split"
                    if deterministic_bytes
                    else "residual_singleton_only"
                ),
            }
        )

    output.sort(
        key=lambda row: (
            str(row["selector_type"]) != "state",
            -int_value(row, "deterministic_repeated_bytes"),
            int_value(row, "conflicted_bytes"),
            int_value(row, "singleton_bytes"),
            str(row["selector_family"]),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def family_bytes(family_rows: list[dict[str, object]], selector_type: str, field: str) -> int:
    return sum(int_value(row, field) for row in family_rows if row.get("selector_type") == selector_type)


def best_family(family_rows: list[dict[str, object]], selector_type: str) -> dict[str, object]:
    candidates = [row for row in family_rows if row.get("selector_type") == selector_type]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "deterministic_repeated_bytes"),
            -int_value(row, "conflicted_bytes"),
            -int_value(row, "singleton_bytes"),
        ),
        default={},
    )


def build_summary(
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    issues: list[str],
    residual_selector_family: str,
    residual_selector_key: str,
) -> dict[str, object]:
    best = max(
        family_rows,
        key=lambda row: (
            int_value(row, "deterministic_repeated_bytes"),
            -int_value(row, "conflicted_bytes"),
            -int_value(row, "singleton_bytes"),
            str(row["selector_type"]) == "state",
        ),
        default={},
    )
    best_source = best_family(family_rows, "source")
    best_state = best_family(family_rows, "state")
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    return {
        "scope": "total",
        "residual_selector_family": residual_selector_family,
        "residual_selector_key": residual_selector_key,
        "residual_rows": len(rows),
        "residual_bytes": sum(int_value(row, "length") for row in rows),
        "selector_families": len(family_rows),
        "source_selector_families": sum(1 for row in family_rows if row.get("selector_type") == "source"),
        "state_selector_families": sum(1 for row in family_rows if row.get("selector_type") == "state"),
        "selector_groups": len(group_rows),
        "repeated_selector_groups": len(repeated),
        "source_deterministic_repeated_evidence_bytes": family_bytes(
            family_rows, "source", "deterministic_repeated_bytes"
        ),
        "source_conflicted_evidence_bytes": family_bytes(family_rows, "source", "conflicted_bytes"),
        "state_deterministic_repeated_evidence_bytes": family_bytes(
            family_rows, "state", "deterministic_repeated_bytes"
        ),
        "state_conflicted_evidence_bytes": family_bytes(family_rows, "state", "conflicted_bytes"),
        "best_source_selector_family": best_source.get("selector_family", ""),
        "best_source_deterministic_bytes": best_source.get("deterministic_repeated_bytes", 0),
        "best_source_conflicted_bytes": best_source.get("conflicted_bytes", 0),
        "best_source_singleton_bytes": best_source.get("singleton_bytes", 0),
        "best_state_selector_family": best_state.get("selector_family", ""),
        "best_state_deterministic_bytes": best_state.get("deterministic_repeated_bytes", 0),
        "best_state_conflicted_bytes": best_state.get("conflicted_bytes", 0),
        "best_state_singleton_bytes": best_state.get("singleton_bytes", 0),
        "best_selector_family": best.get("selector_family", ""),
        "best_selector_type": best.get("selector_type", ""),
        "best_deterministic_bytes": best.get("deterministic_repeated_bytes", 0),
        "best_conflicted_bytes": best.get("conflicted_bytes", 0),
        "best_singleton_bytes": best.get("singleton_bytes", 0),
        "best_remaining_conflict_key": best.get("best_remaining_conflict_key", ""),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + sum(1 for row in rows if row.get("issues")),
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    group_rows: list[dict[str, object]],
    family_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "groups": group_rows, "families": family_rows},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['residual_bytes']}</div><div class="muted">residual bytes</div></div>
  <div class="box"><div class="num">{summary['best_source_conflicted_bytes']}</div><div class="muted">best source conflict</div></div>
  <div class="box"><div class="num">{summary['best_state_deterministic_bytes']}</div><div class="muted">best state deterministic</div></div>
  <div class="box"><div class="num">{summary['best_selector_family']}</div><div class="muted">best selector</div></div>
  <div class="box"><div class="num">{summary['best_singleton_bytes']}</div><div class="muted">best singleton bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Families</h2>{render_table(family_rows, FAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(group_rows, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="gradient-macro-residual-state-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe residual gradient macro conflicts by state bins.")
    parser.add_argument("--macro-rows", type=Path, default=DEFAULT_MACRO_ROWS)
    parser.add_argument("--split-summary", type=Path, default=DEFAULT_SPLIT_SUMMARY)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--target-rows", type=Path, default=DEFAULT_TARGET_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Gradient Macro Residual State")
    args = parser.parse_args()

    rows, issues, selector_family, selector_key = build_rows(
        read_csv(args.macro_rows),
        read_csv(args.target_rows),
        read_csv(args.fixtures),
        read_csv(args.split_summary),
        read_csv(args.splits),
    )
    group_rows = build_group_rows(rows)
    family_rows = build_family_rows(group_rows)
    summary = build_summary(rows, group_rows, family_rows, issues, selector_family, selector_key)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, family_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, family_rows, args.title))

    print(f"Residual rows: {summary['residual_rows']}")
    print(f"Residual bytes: {summary['residual_bytes']}")
    print(
        f"Best source selector: {summary['best_source_selector_family']} "
        f"{summary['best_source_deterministic_bytes']} deterministic, "
        f"{summary['best_source_conflicted_bytes']} conflicted, "
        f"{summary['best_source_singleton_bytes']} singleton"
    )
    print(
        f"Best state selector: {summary['best_state_selector_family']} "
        f"{summary['best_state_deterministic_bytes']} deterministic, "
        f"{summary['best_state_conflicted_bytes']} conflicted, "
        f"{summary['best_state_singleton_bytes']} singleton"
    )
    print(
        f"Best selector: {summary['best_selector_type']} / {summary['best_selector_family']} "
        f"{summary['best_deterministic_bytes']} deterministic, "
        f"{summary['best_conflicted_bytes']} conflicted, "
        f"{summary['best_singleton_bytes']} singleton"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
