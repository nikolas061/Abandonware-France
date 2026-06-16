#!/usr/bin/env python3
"""Probe subfamilies inside the mixed-value micro-token class."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_ROWS = Path("output/tex_micro_token_family_split/rows.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_subfamily")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "clean_rows",
    "clean_bytes",
    "ambiguous_rows",
    "ambiguous_bytes",
    "subfamily_rows",
    "repeated_subfamily_rows",
    "repeated_subfamily_bytes",
    "dominant_subfamily",
    "dominant_subfamily_bytes",
    "control_known_bytes",
    "control_missing_bytes",
    "top_nibble_6_bytes",
    "small_len_bytes",
    "medium_len_bytes",
    "large_len_bytes",
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
    "top_nibble",
    "top_nibble_ratio",
    "length_band",
    "control_state",
    "source_classification",
    "confidence",
    "subfamily_key",
    "signal_key",
    "verdict",
]

SUBFAMILY_FIELDNAMES = [
    "rank",
    "subfamily_key",
    "rows",
    "bytes",
    "clean_rows",
    "clean_bytes",
    "control_states",
    "source_classes",
    "top_nibbles",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

SIGNAL_FIELDNAMES = [
    "rank",
    "signal_key",
    "rows",
    "bytes",
    "subfamilies",
    "control_states",
    "top_nibbles",
    "length_bands",
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


def length_band(length: int) -> str:
    if length < 32:
        return "small"
    if length < 64:
        return "medium"
    return "large"


def control_state(row: dict[str, str]) -> str:
    return "control_missing" if row.get("control_ref_offset", "") == "missing" else "control_known"


def signal_key(row: dict[str, str], band: str, state: str) -> str:
    top = row.get("top_nibble", "")
    source = row.get("source_classification", "")
    return f"top={top}|band={band}|control={state}|source={source}"


def subfamily_key(row: dict[str, str], band: str, state: str) -> str:
    top = row.get("top_nibble", "")
    confidence = int_value(row, "confidence")
    confidence_band = "strong" if confidence >= 2 else "weak"
    return f"{top}|{band}|{state}|{confidence_band}"


def build(source_rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    mixed_rows = [row for row in source_rows if row.get("split_family", "") == "mixed_value"]
    for row in mixed_rows:
        length = int_value(row, "length")
        band = length_band(length)
        state = control_state(row)
        key = subfamily_key(row, band, state)
        sig = signal_key(row, band, state)
        clean = row.get("verdict", "") == "split_family_clean" and int_value(row, "confidence") >= 2
        rows.append(
            {
                "rank": len(rows) + 1,
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "op_index": row.get("op_index", ""),
                "length": length,
                "top_nibble": row.get("top_nibble", ""),
                "top_nibble_ratio": row.get("top_nibble_ratio", ""),
                "length_band": band,
                "control_state": state,
                "source_classification": row.get("source_classification", ""),
                "confidence": row.get("confidence", ""),
                "subfamily_key": key,
                "signal_key": sig,
                "verdict": "mixed_value_subfamily_clean" if clean else "mixed_value_subfamily_review",
            }
        )

    by_subfamily: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_subfamily[str(row["subfamily_key"])].append(row)
    subfamilies: list[dict[str, object]] = []
    for key, group in by_subfamily.items():
        clean = [row for row in group if row["verdict"] == "mixed_value_subfamily_clean"]
        subfamilies.append(
            {
                "rank": 0,
                "subfamily_key": key,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "clean_rows": len(clean),
                "clean_bytes": sum(int_value(row, "length") for row in clean),
                "control_states": ";".join(sorted({str(row["control_state"]) for row in group})),
                "source_classes": ";".join(sorted({str(row["source_classification"]) for row in group})),
                "top_nibbles": ";".join(f"{key}:{value}" for key, value in Counter(str(row["top_nibble"]) for row in group).most_common()),
                "sample_pcx": group[0]["pcx_name"],
                "sample_frontier_id": group[0]["frontier_id"],
                "verdict": "mixed_value_repeated_subfamily" if len(group) > 1 else "mixed_value_singleton_subfamily",
            }
        )
    subfamilies.sort(key=lambda row: (-int_value(row, "bytes"), str(row["subfamily_key"])))
    for index, row in enumerate(subfamilies, start=1):
        row["rank"] = index

    by_signal: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_signal[str(row["signal_key"])].append(row)
    signals: list[dict[str, object]] = []
    for key, group in by_signal.items():
        if len(group) < 2:
            continue
        subfamily_set = sorted({str(row["subfamily_key"]) for row in group})
        signals.append(
            {
                "rank": 0,
                "signal_key": key,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "subfamilies": ";".join(subfamily_set),
                "control_states": ";".join(sorted({str(row["control_state"]) for row in group})),
                "top_nibbles": ";".join(sorted({str(row["top_nibble"]) for row in group})),
                "length_bands": ";".join(sorted({str(row["length_band"]) for row in group})),
                "verdict": "mixed_value_stable_signal" if len(subfamily_set) == 1 else "mixed_value_split_signal",
            }
        )
    signals.sort(key=lambda row: (-int_value(row, "bytes"), str(row["signal_key"])))
    for index, row in enumerate(signals, start=1):
        row["rank"] = index

    clean_rows = [row for row in rows if row["verdict"] == "mixed_value_subfamily_clean"]
    ambiguous_rows = [row for row in rows if row["verdict"] != "mixed_value_subfamily_clean"]
    repeated_subfamilies = [row for row in subfamilies if row["verdict"] == "mixed_value_repeated_subfamily"]
    dominant = subfamilies[0] if subfamilies else {}
    summary = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "clean_rows": len(clean_rows),
        "clean_bytes": sum(int_value(row, "length") for row in clean_rows),
        "ambiguous_rows": len(ambiguous_rows),
        "ambiguous_bytes": sum(int_value(row, "length") for row in ambiguous_rows),
        "subfamily_rows": len(subfamilies),
        "repeated_subfamily_rows": len(repeated_subfamilies),
        "repeated_subfamily_bytes": sum(int_value(row, "bytes") for row in repeated_subfamilies),
        "dominant_subfamily": dominant.get("subfamily_key", ""),
        "dominant_subfamily_bytes": dominant.get("bytes", 0),
        "control_known_bytes": sum(int_value(row, "length") for row in rows if row["control_state"] == "control_known"),
        "control_missing_bytes": sum(int_value(row, "length") for row in rows if row["control_state"] == "control_missing"),
        "top_nibble_6_bytes": sum(int_value(row, "length") for row in rows if row["top_nibble"] == "0x6"),
        "small_len_bytes": sum(int_value(row, "length") for row in rows if row["length_band"] == "small"),
        "medium_len_bytes": sum(int_value(row, "length") for row in rows if row["length_band"] == "medium"),
        "large_len_bytes": sum(int_value(row, "length") for row in rows if row["length_band"] == "large"),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, rows, subfamilies, signals


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
    subfamilies: list[dict[str, object]],
    signals: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "subfamilies": subfamilies, "signals": signals},
        indent=2,
        sort_keys=True,
    )
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
  <div class="box"><div class="num">{summary['clean_bytes']}</div><div class="muted">clean bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_subfamily_bytes']}</div><div class="muted">repeated subfamily bytes</div></div>
  <div class="box"><div class="num">{summary['dominant_subfamily']}</div><div class="muted">dominant subfamily</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Subfamilies</h2>{render_table(subfamilies, SUBFAMILY_FIELDNAMES)}</div>
<div class="panel"><h2>Signals</h2>{render_table(signals, SIGNAL_FIELDNAMES)}</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="micro-mixed-value-subfamily-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe mixed-value micro-token subfamilies.")
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Mixed Value Subfamily")
    args = parser.parse_args()

    summary, rows, subfamilies, signals = build(read_rows(args.rows))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "subfamilies.csv", SUBFAMILY_FIELDNAMES, subfamilies)
    write_csv(args.output / "signals.csv", SIGNAL_FIELDNAMES, signals)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, subfamilies, signals, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Clean bytes: {summary['clean_bytes']}")
    print(f"Repeated subfamily bytes: {summary['repeated_subfamily_bytes']}")
    print(f"Dominant subfamily: {summary['dominant_subfamily']}")
    print(f"Ambiguous bytes: {summary['ambiguous_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
