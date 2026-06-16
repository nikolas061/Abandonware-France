#!/usr/bin/env python3
"""Probe control signals for the dominant mixed-value micro-token subfamily."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_SUBFAMILY_ROWS = Path("output/tex_micro_mixed_value_subfamily/rows.csv")
DEFAULT_FAMILY_ROWS = Path("output/tex_micro_token_family_split/rows.csv")
DEFAULT_CONTROL_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe/targets.csv"
)
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_dominant_control")
DEFAULT_SUBFAMILY = "0x6|medium|control_known|strong"

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "signal_groups",
    "repeated_signal_rows",
    "repeated_signal_bytes",
    "control_mod_groups",
    "repeated_control_mod_rows",
    "repeated_control_mod_bytes",
    "control_signal_groups",
    "repeated_control_signal_rows",
    "repeated_control_signal_bytes",
    "offset_context_groups",
    "repeated_offset_context_bytes",
    "payload_signature_groups",
    "repeated_payload_bytes",
    "dominant_signal",
    "dominant_signal_bytes",
    "dominant_control_signal",
    "dominant_control_signal_bytes",
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
    "control_ref_mod64",
    "best_signal_key",
    "signal_top_key",
    "offset_context_key",
    "payload_signature",
    "best_signal_ratio",
    "best_signal_exact",
    "best_signal_offset_mod64",
    "dominant_byte_hex",
    "signed_shape_key",
    "transition_profile_key",
    "verdict",
]

GROUP_FIELDNAMES = [
    "rank",
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "payload_signatures",
    "control_mods",
    "signals",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def join_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
        str(row.get("span_index", "")),
        str(row.get("op_index", "")),
        str(row.get("length", "")),
    )


def short_shape(value: str) -> str:
    return value.split("|", 1)[0] if "|" in value else value


def build_groups(rows: list[dict[str, object]], group_kind: str, field: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field, ""))].append(row)
    output: list[dict[str, object]] = []
    for key, group in grouped.items():
        payloads = sorted({str(row.get("payload_signature", "")) for row in group})
        output.append(
            {
                "rank": 0,
                "group_kind": group_kind,
                "group_key": key,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "payload_signatures": str(len(payloads)),
                "control_mods": ";".join(sorted({str(row.get("control_ref_mod64", "")) for row in group})),
                "signals": ";".join(sorted({str(row.get("best_signal_key", "")) for row in group})),
                "sample_pcx": group[0].get("pcx_name", ""),
                "sample_frontier_id": group[0].get("frontier_id", ""),
                "verdict": f"{group_kind}_payload_repeated"
                if len(payloads) < len(group)
                else f"{group_kind}_payload_unique",
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), str(row["group_kind"]), str(row["group_key"])))
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def repeated_bytes(groups: list[dict[str, object]]) -> int:
    return sum(int_value(row, "bytes") for row in groups if int_value(row, "rows") > 1)


def repeated_rows(groups: list[dict[str, object]]) -> int:
    return sum(int_value(row, "rows") for row in groups if int_value(row, "rows") > 1)


def build(
    subfamily_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    *,
    subfamily: str,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    family_by_key = {join_key(row): row for row in family_rows}
    control_by_key = {join_key(row): row for row in control_rows}
    rows: list[dict[str, object]] = []
    issues: list[str] = []

    for sub_row in subfamily_rows:
        if sub_row.get("subfamily_key", "") != subfamily:
            continue
        key = join_key(sub_row)
        family = family_by_key.get(key)
        control = control_by_key.get(key)
        if family is None:
            issues.append(f"missing_family:{key}")
            continue
        if control is None:
            issues.append(f"missing_control:{key}")
            continue
        payload = control.get("payload_signature", "")
        rows.append(
            {
                "rank": len(rows) + 1,
                "archive": sub_row.get("archive", ""),
                "pcx_name": sub_row.get("pcx_name", ""),
                "frontier_id": sub_row.get("frontier_id", ""),
                "span_index": sub_row.get("span_index", ""),
                "op_index": sub_row.get("op_index", ""),
                "length": sub_row.get("length", ""),
                "start": family.get("start", ""),
                "end": family.get("end", ""),
                "control_ref_mod64": control.get("control_ref_mod64", family.get("control_ref_mod64", "")),
                "best_signal_key": control.get("best_signal_key", ""),
                "signal_top_key": control.get("signal_top_key", ""),
                "offset_context_key": control.get("offset_context_key", ""),
                "payload_signature": payload,
                "best_signal_ratio": control.get("best_signal_ratio", ""),
                "best_signal_exact": control.get("best_signal_exact", ""),
                "best_signal_offset_mod64": control.get("best_signal_offset_mod64", ""),
                "dominant_byte_hex": family.get("dominant_byte_hex", ""),
                "signed_shape_key": short_shape(family.get("signed_shape_key", "")),
                "transition_profile_key": short_shape(family.get("transition_profile_key", "")),
                "verdict": "dominant_control_payload_unique",
            }
        )

    signal_groups = build_groups(rows, "signal", "best_signal_key")
    control_groups = build_groups(rows, "control_mod", "control_ref_mod64")
    control_signal_groups = build_groups(
        [
            {
                **row,
                "control_signal_key": f"{row.get('control_ref_mod64', '')}|{row.get('best_signal_key', '')}",
            }
            for row in rows
        ],
        "control_signal",
        "control_signal_key",
    )
    offset_groups = build_groups(rows, "offset_context", "offset_context_key")
    payload_groups = build_groups(rows, "payload", "payload_signature")
    groups = [*signal_groups, *control_groups, *control_signal_groups, *offset_groups, *payload_groups]
    for index, row in enumerate(groups, start=1):
        row["rank"] = index

    dominant_signal = signal_groups[0] if signal_groups else {}
    dominant_control_signal = control_signal_groups[0] if control_signal_groups else {}
    repeated_payload = repeated_bytes([row for row in payload_groups if int_value(row, "rows") > 1])
    summary = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "signal_groups": len(signal_groups),
        "repeated_signal_rows": repeated_rows(signal_groups),
        "repeated_signal_bytes": repeated_bytes(signal_groups),
        "control_mod_groups": len(control_groups),
        "repeated_control_mod_rows": repeated_rows(control_groups),
        "repeated_control_mod_bytes": repeated_bytes(control_groups),
        "control_signal_groups": len(control_signal_groups),
        "repeated_control_signal_rows": repeated_rows(control_signal_groups),
        "repeated_control_signal_bytes": repeated_bytes(control_signal_groups),
        "offset_context_groups": len(offset_groups),
        "repeated_offset_context_bytes": repeated_bytes(offset_groups),
        "payload_signature_groups": len(payload_groups),
        "repeated_payload_bytes": repeated_payload,
        "dominant_signal": dominant_signal.get("group_key", ""),
        "dominant_signal_bytes": dominant_signal.get("bytes", 0),
        "dominant_control_signal": dominant_control_signal.get("group_key", ""),
        "dominant_control_signal_bytes": dominant_control_signal.get("bytes", 0),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, rows, groups


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
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "groups": groups}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
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
  <div class="box"><div class="num">{summary['target_bytes']}</div><div class="muted">target bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_signal_bytes']}</div><div class="muted">repeated signal bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_control_signal_bytes']}</div><div class="muted">control+signal bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_payload_bytes']}</div><div class="muted">repeated payload bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="dominant-control-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe control signals for the dominant mixed-value subfamily.")
    parser.add_argument("--subfamily-rows", type=Path, default=DEFAULT_SUBFAMILY_ROWS)
    parser.add_argument("--family-rows", type=Path, default=DEFAULT_FAMILY_ROWS)
    parser.add_argument("--control-rows", type=Path, default=DEFAULT_CONTROL_ROWS)
    parser.add_argument("--subfamily", default=DEFAULT_SUBFAMILY)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Mixed Value Dominant Control")
    args = parser.parse_args()

    summary, rows, groups = build(
        read_rows(args.subfamily_rows),
        read_rows(args.family_rows),
        read_rows(args.control_rows),
        subfamily=args.subfamily,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Repeated signal bytes: {summary['repeated_signal_bytes']}")
    print(f"Repeated control+signal bytes: {summary['repeated_control_signal_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Dominant control+signal: {summary['dominant_control_signal']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
