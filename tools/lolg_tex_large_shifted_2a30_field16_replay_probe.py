#!/usr/bin/env python3
"""Test direct replay hypotheses for shifted 0x2a30 field16 units."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import struct
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_replay_probe")
DEFAULT_FIELD16 = Path("output/tex_large_shifted_2a30_field16_probe/field16.csv")
DEFAULT_ANCHORS = Path("output/tex_large_shifted_2a30_standard_probe/anchors.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
WINDOW_SIZE = 32

SUMMARY_FIELDNAMES = [
    "scope",
    "standard_rows",
    "candidate_rows",
    "unit_relation_rows",
    "candidate_labels",
    "target_rows",
    "best_exact_prefix_bytes",
    "exact_prefix_ge4_rows",
    "exact_prefix_ge2_rows",
    "zero_prefix_rows",
    "transform_needed_rows",
    "rule_rows",
    "issue_rows",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "field16_hex",
    "field16_low_dec",
    "field16_low_div4",
    "anchor_offset",
    "target_offset",
    "target_head_hex",
    "candidate_label",
    "candidate_offset",
    "candidate_head_hex",
    "exact_prefix_bytes",
    "candidate_entropy",
    "candidate_zero_ratio",
    "target_entropy",
    "target_zero_ratio",
    "verdict",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_id",
    "scope",
    "rows",
    "matched_rows",
    "best_prefix",
    "verdict",
    "next_probe",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def ratio(value: float) -> str:
    return f"{value:.6f}"


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def zero_ratio(data: bytes) -> float:
    return (data.count(0) / len(data)) if data else 0.0


def common_prefix(left: bytes, right: bytes) -> int:
    count = 0
    for left_byte, right_byte in zip(left, right):
        if left_byte != right_byte:
            break
        count += 1
    return count


def read_mix_entry(path: Path, index: int) -> bytes:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        raise ValueError(f"{path}: invalid MIX entry index {index}")
    _file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared body size")
    return data[table_end + offset : table_end + offset + size]


def row_lookup(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def candidate_offsets(anchor_offset: int, unit: int, low: int, selector: int) -> list[tuple[str, int]]:
    return [
        ("unit", unit),
        ("low", low),
        ("anchor_plus_unit", anchor_offset + unit),
        ("anchor_plus_low", anchor_offset + low),
        ("selector", selector),
    ]


def build_candidate_rows(
    field_rows: list[dict[str, str]],
    anchors: dict[str, dict[str, str]],
    segments: dict[str, dict[str, str]],
    mix_entry_index: int,
) -> list[dict[str, str]]:
    payload_cache: dict[Path, bytes] = {}
    output: list[dict[str, str]] = []
    for field in field_rows:
        issues: list[str] = []
        segment_id = field.get("segment_id", "")
        anchor = anchors.get(segment_id, {})
        segment = segments.get(segment_id, {})
        if not anchor:
            issues.append("missing_anchor")
        if not segment:
            issues.append("missing_segment")

        body = b""
        archive = Path(segment.get("archive", ""))
        body_offset = int_value(segment, "body_offset")
        body_size = int_value(segment, "body_size")
        try:
            if archive and archive not in payload_cache:
                payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
            payload = payload_cache.get(archive, b"")
            body = payload[body_offset : body_offset + min(body_size, 2048)]
        except Exception as exc:
            issues.append(f"read_failed:{exc}")

        anchor_offset = int_value(anchor, "pair_2a30_offset")
        low = int_value(field, "field16_low_dec")
        unit = int_value(field, "field16_low_div4")
        selector = int_value(field, "selector_byte_dec")
        if low != unit * 4:
            issues.append("unit_relation_mismatch")
        target_offset = anchor_offset + 8
        target = body[target_offset : target_offset + WINDOW_SIZE]
        if len(target) < WINDOW_SIZE:
            issues.append("short_target_window")

        for label, offset in candidate_offsets(anchor_offset, unit, low, selector):
            candidate = body[offset : offset + WINDOW_SIZE] if offset >= 0 else b""
            row_issues = list(issues)
            if len(candidate) < WINDOW_SIZE:
                row_issues.append("short_candidate_window")
            prefix = common_prefix(candidate, target)
            if prefix >= 4:
                verdict = "direct_replay_candidate"
            elif prefix:
                verdict = "weak_prefix_only"
            else:
                verdict = "no_direct_prefix"
            output.append(
                {
                    "segment_id": segment_id,
                    "archive": segment.get("archive", ""),
                    "archive_tag": field.get("archive_tag", ""),
                    "pcx_name": field.get("pcx_name", ""),
                    "field16_hex": field.get("field16_hex", ""),
                    "field16_low_dec": field.get("field16_low_dec", ""),
                    "field16_low_div4": field.get("field16_low_div4", ""),
                    "anchor_offset": str(anchor_offset),
                    "target_offset": str(target_offset),
                    "target_head_hex": target[:12].hex(),
                    "candidate_label": label,
                    "candidate_offset": str(offset),
                    "candidate_head_hex": candidate[:12].hex(),
                    "exact_prefix_bytes": str(prefix),
                    "candidate_entropy": ratio(entropy(candidate)),
                    "candidate_zero_ratio": ratio(zero_ratio(candidate)),
                    "target_entropy": ratio(entropy(target)),
                    "target_zero_ratio": ratio(zero_ratio(target)),
                    "verdict": verdict,
                    "issues": ";".join(dict.fromkeys(row_issues)),
                }
            )
    return output


def build_rule_rows(candidate_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    standard_segments = {row.get("segment_id", "") for row in candidate_rows if row.get("segment_id")}
    unit_rows = [row for row in candidate_rows if row.get("candidate_label") == "unit"]
    low_rows = [row for row in candidate_rows if row.get("candidate_label") == "low"]
    direct_rows = [row for row in candidate_rows if int_value(row, "exact_prefix_bytes") >= 4]
    weak_rows = [row for row in candidate_rows if int_value(row, "exact_prefix_bytes") > 0]
    best_prefix = max((int_value(row, "exact_prefix_bytes") for row in candidate_rows), default=0)
    return [
        {
            "rule_id": "field16_low_unit_relation",
            "scope": "standard_rows",
            "rows": str(len(standard_segments)),
            "matched_rows": str(
                len(
                    {
                        row.get("segment_id", "")
                        for row in candidate_rows
                        if int_value(row, "field16_low_dec") == int_value(row, "field16_low_div4") * 4
                    }
                )
            ),
            "best_prefix": "",
            "verdict": "all_standard_rows",
            "next_probe": "use low-byte /4 as a unit parameter, not as proof of direct replay",
        },
        {
            "rule_id": "unit_offset_direct_replay",
            "scope": "unit",
            "rows": str(len(unit_rows)),
            "matched_rows": str(sum(1 for row in unit_rows if int_value(row, "exact_prefix_bytes") >= 4)),
            "best_prefix": str(max((int_value(row, "exact_prefix_bytes") for row in unit_rows), default=0)),
            "verdict": "no_direct_replay",
            "next_probe": "derive a transform before treating unit offset as a source pointer",
        },
        {
            "rule_id": "low_offset_direct_replay",
            "scope": "low",
            "rows": str(len(low_rows)),
            "matched_rows": str(sum(1 for row in low_rows if int_value(row, "exact_prefix_bytes") >= 4)),
            "best_prefix": str(max((int_value(row, "exact_prefix_bytes") for row in low_rows), default=0)),
            "verdict": "no_direct_replay",
            "next_probe": "derive a transform before treating low byte as a byte offset",
        },
        {
            "rule_id": "all_candidates_direct_replay",
            "scope": "all_candidates",
            "rows": str(len(candidate_rows)),
            "matched_rows": str(len(direct_rows)),
            "best_prefix": str(best_prefix),
            "verdict": "no_direct_replay" if not direct_rows else "has_direct_replay_candidates",
            "next_probe": "derive shifted 0x2a30 field16 transform after direct replay miss",
        },
        {
            "rule_id": "weak_prefix_noise",
            "scope": "all_candidates",
            "rows": str(len(candidate_rows)),
            "matched_rows": str(len(weak_rows)),
            "best_prefix": str(best_prefix),
            "verdict": "weak_only" if weak_rows and not direct_rows else "none",
            "next_probe": "ignore one-byte prefixes as insufficient replay evidence",
        },
    ]


def build_summary(candidate_rows: list[dict[str, str]], rule_rows: list[dict[str, str]]) -> dict[str, str]:
    segments = {row.get("segment_id", "") for row in candidate_rows if row.get("segment_id")}
    candidate_labels = {row.get("candidate_label", "") for row in candidate_rows if row.get("candidate_label")}
    best_prefix = max((int_value(row, "exact_prefix_bytes") for row in candidate_rows), default=0)
    exact_ge4 = sum(1 for row in candidate_rows if int_value(row, "exact_prefix_bytes") >= 4)
    issue_rows = sum(1 for row in candidate_rows if row.get("issues"))
    transform_needed_rows = len(segments) if exact_ge4 == 0 and segments else 0
    if issue_rows:
        next_action = "fix shifted 0x2a30 field16 replay probe issues"
    elif transform_needed_rows:
        next_action = (
            f"derive shifted 0x2a30 field16 transform after direct replay miss on "
            f"{transform_needed_rows} standard rows"
        )
    elif exact_ge4:
        next_action = f"review {exact_ge4} shifted 0x2a30 field16 direct replay candidates"
    else:
        next_action = "no shifted 0x2a30 field16 replay rows"
    return {
        "scope": "total",
        "standard_rows": str(len(segments)),
        "candidate_rows": str(len(candidate_rows)),
        "unit_relation_rows": str(
            len(
                {
                    row.get("segment_id", "")
                    for row in candidate_rows
                    if int_value(row, "field16_low_dec") == int_value(row, "field16_low_div4") * 4
                }
            )
        ),
        "candidate_labels": str(len(candidate_labels)),
        "target_rows": str(len({(row.get("segment_id", ""), row.get("target_offset", "")) for row in candidate_rows})),
        "best_exact_prefix_bytes": str(best_prefix),
        "exact_prefix_ge4_rows": str(exact_ge4),
        "exact_prefix_ge2_rows": str(sum(1 for row in candidate_rows if int_value(row, "exact_prefix_bytes") >= 2)),
        "zero_prefix_rows": str(sum(1 for row in candidate_rows if int_value(row, "exact_prefix_bytes") == 0)),
        "transform_needed_rows": str(transform_needed_rows),
        "rule_rows": str(len(rule_rows)),
        "issue_rows": str(issue_rows),
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("rules.csv", output_dir / "rules.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Direct replay windows from field16 units are tested before any transform is promoted.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rules, RULE_FIELDNAMES)}
<h2>Candidates</h2>
{render_table(candidates, CANDIDATE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_REPLAY_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    field16_path: Path,
    anchors_path: Path,
    segments_path: Path,
    mix_entry_index: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = build_candidate_rows(
        read_csv(field16_path),
        row_lookup(read_csv(anchors_path), "segment_id"),
        row_lookup(read_csv(segments_path), "segment_id"),
        mix_entry_index,
    )
    rule_rows = build_rule_rows(candidate_rows)
    summary = build_summary(candidate_rows, rule_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rule_rows)
    (output_dir / "index.html").write_text(build_html(summary, candidate_rows, rule_rows, output_dir, title))
    return summary, candidate_rows, rule_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Test direct replay hypotheses for shifted 0x2a30 field16 units.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--field16", type=Path, default=DEFAULT_FIELD16)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Field16 Replay Probe")
    args = parser.parse_args()

    summary, candidates, rules = write_report(
        args.output,
        args.field16,
        args.anchors,
        args.segments,
        args.mix_entry_index,
        args.title,
    )
    print(f"Standard rows: {summary['standard_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Best exact prefix bytes: {summary['best_exact_prefix_bytes']}")
    print(f"Exact prefix >=4 rows: {summary['exact_prefix_ge4_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
