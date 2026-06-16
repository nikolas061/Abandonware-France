#!/usr/bin/env python3
"""Probe local payload grammar for the dominant mixed-value micro-token rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_local_grammar")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "payload_signature_groups",
    "repeated_payload_bytes",
    "byte_value_groups",
    "repeated_byte_value_bytes",
    "dominant_byte_hex",
    "dominant_byte_count",
    "high6_bytes",
    "high6_ratio",
    "byte_shape_groups",
    "repeated_byte_shape_bytes",
    "high_shape_groups",
    "repeated_high_shape_bytes",
    "delta_shape_groups",
    "repeated_delta_shape_bytes",
    "byte_bigram_groups",
    "byte_bigram_repeated_groups",
    "byte_bigram_repeated_entries",
    "byte_bigram_repeated_slots",
    "byte_trigram_groups",
    "byte_trigram_repeated_groups",
    "byte_trigram_repeated_entries",
    "byte_trigram_repeated_slots",
    "byte_ngram8_groups",
    "byte_ngram8_repeated_groups",
    "byte_ngram8_repeated_entries",
    "byte_ngram8_repeated_slots",
    "high_ngram8_groups",
    "high_ngram8_repeated_groups",
    "high_ngram8_repeated_entries",
    "high_ngram8_repeated_slots",
    "delta_ngram4_groups",
    "delta_ngram4_repeated_groups",
    "delta_ngram4_repeated_entries",
    "delta_ngram4_repeated_slots",
    "signed_ngram4_groups",
    "signed_ngram4_repeated_groups",
    "signed_ngram4_repeated_entries",
    "signed_ngram4_repeated_slots",
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
    "payload_signature",
    "unique_bytes",
    "top_byte_hex",
    "top_byte_count",
    "top_byte_ratio",
    "high6_bytes",
    "high6_ratio",
    "repeated_byte_value_bytes",
    "byte_bigram_repeated_slots",
    "byte_trigram_repeated_slots",
    "byte_ngram8_repeated_slots",
    "high_ngram8_repeated_slots",
    "delta_ngram4_repeated_slots",
    "signed_ngram4_repeated_slots",
    "verdict",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "projection",
    "n",
    "ngram_key",
    "entries",
    "covered_rows",
    "covered_slots",
    "sample_pcx",
    "sample_frontier_id",
    "sample_span_index",
    "sample_op_index",
    "sample_offset",
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


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def load_expected_by_fixture(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        if key in expected:
            issues.append(f"duplicate_fixture:{key[0]}:{key[1]}:{key[2]}")
            continue
        path_text = fixture.get("expected_gap_path", "")
        if not path_text:
            issues.append(f"missing_expected_path:{key[0]}:{key[1]}:{key[2]}")
            expected[key] = b""
            continue
        try:
            expected[key] = Path(path_text).read_bytes()
        except OSError as exc:
            issues.append(f"read_expected_failed:{key[0]}:{key[1]}:{key[2]}:{exc}")
            expected[key] = b""
    return expected, issues


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def delta_bucket(delta: int) -> str:
    magnitude = abs(delta)
    if delta == 0:
        return "Z"
    if magnitude <= 4:
        return "S"
    if magnitude <= 31:
        return "M"
    return "J"


def signed_bucket(delta: int) -> str:
    if delta == 0:
        return "0"
    prefix = "+" if delta > 0 else "-"
    magnitude = abs(delta)
    if magnitude <= 4:
        suffix = "s"
    elif magnitude <= 31:
        suffix = "m"
    else:
        suffix = "j"
    return f"{prefix}{suffix}"


def projection_sequence(data: bytes, projection: str) -> list[str]:
    if projection == "byte":
        return [f"{value:02x}" for value in data]
    if projection == "high":
        return [f"{value >> 4:x}" for value in data]
    if projection == "low":
        return [f"{value & 0x0F:x}" for value in data]
    if projection == "band":
        return [band_token(value) for value in data]
    if projection == "delta":
        return [delta_bucket(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]
    if projection == "signed":
        return [signed_bucket(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]
    return []


def projection_byte_offset(projection: str) -> int:
    return 1 if projection in {"delta", "signed"} else 0


def band_token(value: int) -> str:
    high = value >> 4
    if high in {5, 6, 7, 10}:
        return f"{high:x}"
    return "x"


def shape_key(values: list[str]) -> str:
    text = ".".join(values)
    digest = hashlib.sha1(text.encode("ascii")).hexdigest()[:14]
    return f"len={len(text)}|sha1={digest}"


def ngram_key(values: tuple[str, ...]) -> str:
    return " ".join(values)


def build_payload_rows(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[dict[str, object]] = []
    for row in input_rows:
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        expected = expected_by_fixture.get(fixture_key(row), b"")
        if not expected:
            issues.append("missing_expected_fixture")
        start = int_value(row, "start")
        end = int_value(row, "end")
        payload = expected[start:end]
        if not payload:
            issues.append("missing_payload")
        if row.get("length") and int_value(row, "length") != len(payload):
            issues.append(f"length_mismatch:{row.get('length')}:{len(payload)}")
        output.append(
            {
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "op_index": row.get("op_index", ""),
                "length": str(len(payload)),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "control_ref_mod64": row.get("control_ref_mod64", ""),
                "best_signal_key": row.get("best_signal_key", ""),
                "payload_signature": payload_signature(payload) if payload else "",
                "payload": payload,
                "head_hex": payload[:16].hex(),
                "tail_hex": payload[-16:].hex() if payload else "",
                "issues": ";".join(issues),
            }
        )
    return output, fixture_issues


def shape_stats(rows: list[dict[str, object]], projection: str) -> tuple[int, int]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[shape_key(projection_sequence(row["payload"], projection))].append(row)
    repeated_bytes = sum(
        int_value(row, "length")
        for group in grouped.values()
        if len(group) > 1
        for row in group
    )
    return len(grouped), repeated_bytes


def build_ngram_stats(
    rows: list[dict[str, object]],
    projection: str,
    n: int,
) -> tuple[dict[str, int], dict[int, set[int]], list[dict[str, object]]]:
    occurrences: dict[tuple[str, ...], list[tuple[int, int]]] = defaultdict(list)
    for row_index, row in enumerate(rows):
        values = projection_sequence(row["payload"], projection)
        for offset in range(0, max(0, len(values) - n + 1)):
            occurrences[tuple(values[offset : offset + n])].append((row_index, offset))

    repeated = {key: positions for key, positions in occurrences.items() if len(positions) > 1}
    slots_by_row: dict[int, set[int]] = {index: set() for index in range(len(rows))}
    group_rows: list[dict[str, object]] = []
    byte_offset = projection_byte_offset(projection)
    for key, positions in repeated.items():
        covered_rows = {row_index for row_index, _offset in positions}
        covered_slots: set[tuple[int, int]] = set()
        for row_index, offset in positions:
            payload_length = len(rows[row_index]["payload"])
            for byte_index in range(offset + byte_offset, offset + byte_offset + n):
                if 0 <= byte_index < payload_length:
                    slots_by_row[row_index].add(byte_index)
                    covered_slots.add((row_index, byte_index))
        sample_index, sample_offset = positions[0]
        sample = rows[sample_index]
        verdict = "local_byte_repeat" if projection == "byte" else "broad_projection_repeat"
        group_rows.append(
            {
                "rank": 0,
                "projection": projection,
                "n": n,
                "ngram_key": ngram_key(key),
                "entries": len(positions),
                "covered_rows": len(covered_rows),
                "covered_slots": len(covered_slots),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_span_index": sample.get("span_index", ""),
                "sample_op_index": sample.get("op_index", ""),
                "sample_offset": sample_offset,
                "verdict": verdict,
            }
        )
    group_rows.sort(
        key=lambda row: (
            str(row["projection"]),
            int(row["n"]),
            -int(row["covered_slots"]),
            -int(row["entries"]),
            str(row["ngram_key"]),
        )
    )
    stats = {
        "groups": len(occurrences),
        "repeated_groups": len(repeated),
        "repeated_entries": sum(len(positions) for positions in repeated.values()),
        "repeated_slots": sum(len(slots) for slots in slots_by_row.values()),
    }
    return stats, slots_by_row, group_rows


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows, fixture_issues = build_payload_rows(input_rows, fixture_rows)
    payload_counter = Counter(str(row.get("payload_signature", "")) for row in rows)
    byte_counter = Counter(value for row in rows for value in row["payload"])
    target_bytes = sum(len(row["payload"]) for row in rows)
    dominant_byte, dominant_byte_count = byte_counter.most_common(1)[0] if byte_counter else (0, 0)
    high6_bytes = sum(1 for row in rows for value in row["payload"] if value >> 4 == 6)

    stats_to_collect = [
        ("byte", 2),
        ("byte", 3),
        ("byte", 4),
        ("byte", 6),
        ("byte", 8),
        ("high", 8),
        ("delta", 4),
        ("delta", 6),
        ("signed", 4),
    ]
    ngram_stats: dict[tuple[str, int], dict[str, int]] = {}
    row_slots: dict[tuple[str, int], dict[int, set[int]]] = {}
    group_rows: list[dict[str, object]] = []
    for projection, n in stats_to_collect:
        stats, slots, groups = build_ngram_stats(rows, projection, n)
        ngram_stats[(projection, n)] = stats
        row_slots[(projection, n)] = slots
        group_rows.extend(groups)

    for index, group in enumerate(group_rows, start=1):
        group["rank"] = index

    byte_shape_groups, repeated_byte_shape_bytes = shape_stats(rows, "byte")
    high_shape_groups, repeated_high_shape_bytes = shape_stats(rows, "high")
    delta_shape_groups, repeated_delta_shape_bytes = shape_stats(rows, "delta")
    repeated_payload_bytes = sum(
        int_value(row, "length")
        for row in rows
        if payload_counter[str(row.get("payload_signature", ""))] > 1
    )
    repeated_byte_value_bytes = sum(
        1 for row in rows for value in row["payload"] if byte_counter[value] > 1
    )

    row_output: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        payload = row["payload"]
        value_counts = Counter(payload)
        top_byte, top_count = value_counts.most_common(1)[0] if value_counts else (0, 0)
        row_repeated_values = sum(1 for value in payload if byte_counter[value] > 1)
        row_high6 = sum(1 for value in payload if value >> 4 == 6)
        byte_ngram8_slots = len(row_slots[("byte", 8)][index])
        if payload_counter[str(row.get("payload_signature", ""))] > 1:
            verdict = "payload_repeat_review"
        elif byte_ngram8_slots:
            verdict = "long_local_byte_repeat_review"
        else:
            verdict = "short_local_grammar_only"
        row_output.append(
            {
                **{field: row.get(field, "") for field in ROW_FIELDNAMES if field not in {"verdict", "issues"}},
                "unique_bytes": len(value_counts),
                "top_byte_hex": f"{top_byte:02x}" if payload else "",
                "top_byte_count": top_count,
                "top_byte_ratio": ratio(top_count, len(payload)),
                "high6_bytes": row_high6,
                "high6_ratio": ratio(row_high6, len(payload)),
                "repeated_byte_value_bytes": row_repeated_values,
                "byte_bigram_repeated_slots": len(row_slots[("byte", 2)][index]),
                "byte_trigram_repeated_slots": len(row_slots[("byte", 3)][index]),
                "byte_ngram8_repeated_slots": byte_ngram8_slots,
                "high_ngram8_repeated_slots": len(row_slots[("high", 8)][index]),
                "delta_ngram4_repeated_slots": len(row_slots[("delta", 4)][index]),
                "signed_ngram4_repeated_slots": len(row_slots[("signed", 4)][index]),
                "verdict": verdict,
                "issues": row.get("issues", ""),
            }
        )

    summary = {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": target_bytes,
        "payload_signature_groups": len(payload_counter),
        "repeated_payload_bytes": repeated_payload_bytes,
        "byte_value_groups": len(byte_counter),
        "repeated_byte_value_bytes": repeated_byte_value_bytes,
        "dominant_byte_hex": f"{dominant_byte:02x}" if byte_counter else "",
        "dominant_byte_count": dominant_byte_count,
        "high6_bytes": high6_bytes,
        "high6_ratio": ratio(high6_bytes, target_bytes),
        "byte_shape_groups": byte_shape_groups,
        "repeated_byte_shape_bytes": repeated_byte_shape_bytes,
        "high_shape_groups": high_shape_groups,
        "repeated_high_shape_bytes": repeated_high_shape_bytes,
        "delta_shape_groups": delta_shape_groups,
        "repeated_delta_shape_bytes": repeated_delta_shape_bytes,
        "byte_bigram_groups": ngram_stats[("byte", 2)]["groups"],
        "byte_bigram_repeated_groups": ngram_stats[("byte", 2)]["repeated_groups"],
        "byte_bigram_repeated_entries": ngram_stats[("byte", 2)]["repeated_entries"],
        "byte_bigram_repeated_slots": ngram_stats[("byte", 2)]["repeated_slots"],
        "byte_trigram_groups": ngram_stats[("byte", 3)]["groups"],
        "byte_trigram_repeated_groups": ngram_stats[("byte", 3)]["repeated_groups"],
        "byte_trigram_repeated_entries": ngram_stats[("byte", 3)]["repeated_entries"],
        "byte_trigram_repeated_slots": ngram_stats[("byte", 3)]["repeated_slots"],
        "byte_ngram8_groups": ngram_stats[("byte", 8)]["groups"],
        "byte_ngram8_repeated_groups": ngram_stats[("byte", 8)]["repeated_groups"],
        "byte_ngram8_repeated_entries": ngram_stats[("byte", 8)]["repeated_entries"],
        "byte_ngram8_repeated_slots": ngram_stats[("byte", 8)]["repeated_slots"],
        "high_ngram8_groups": ngram_stats[("high", 8)]["groups"],
        "high_ngram8_repeated_groups": ngram_stats[("high", 8)]["repeated_groups"],
        "high_ngram8_repeated_entries": ngram_stats[("high", 8)]["repeated_entries"],
        "high_ngram8_repeated_slots": ngram_stats[("high", 8)]["repeated_slots"],
        "delta_ngram4_groups": ngram_stats[("delta", 4)]["groups"],
        "delta_ngram4_repeated_groups": ngram_stats[("delta", 4)]["repeated_groups"],
        "delta_ngram4_repeated_entries": ngram_stats[("delta", 4)]["repeated_entries"],
        "delta_ngram4_repeated_slots": ngram_stats[("delta", 4)]["repeated_slots"],
        "signed_ngram4_groups": ngram_stats[("signed", 4)]["groups"],
        "signed_ngram4_repeated_groups": ngram_stats[("signed", 4)]["repeated_groups"],
        "signed_ngram4_repeated_entries": ngram_stats[("signed", 4)]["repeated_entries"],
        "signed_ngram4_repeated_slots": ngram_stats[("signed", 4)]["repeated_slots"],
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in rows if row.get("issues")) + len(fixture_issues),
    }
    return summary, row_output, group_rows


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
  <div class="box"><div class="num">{summary['repeated_byte_value_bytes']}</div><div class="muted">repeated byte-value bytes</div></div>
  <div class="box"><div class="num">{summary['byte_trigram_repeated_slots']}</div><div class="muted">byte trigram slots</div></div>
  <div class="box"><div class="num">{summary['byte_ngram8_repeated_slots']}</div><div class="muted">byte ngram8 slots</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Repeated ngrams</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="payload-local-grammar-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local grammar in dominant mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload Local Grammar")
    args = parser.parse_args()

    summary, rows, groups = build(read_csv(args.input_rows), read_csv(args.fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "ngrams.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Repeated byte-value bytes: {summary['repeated_byte_value_bytes']}")
    print(f"Byte trigram repeated slots: {summary['byte_trigram_repeated_slots']}")
    print(f"Byte ngram8 repeated slots: {summary['byte_ngram8_repeated_slots']}")
    print(f"High ngram8 repeated slots: {summary['high_ngram8_repeated_slots']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
