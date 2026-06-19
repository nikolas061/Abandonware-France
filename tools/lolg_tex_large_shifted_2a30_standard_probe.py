#!/usr/bin/env python3
"""Probe the standard shifted 0x2a30 control branch in rejected large .tex bodies."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_standard_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_ANCHORS = Path("output/tex_large_rejected_decoder_profile/shifted_2a30_anchors.csv")
DEFAULT_MIX_ENTRY_INDEX = 2

SUMMARY_FIELDNAMES = [
    "scope",
    "anchor_rows",
    "standard_rows",
    "branch_rows",
    "branch_key_groups",
    "standard_branch_key",
    "branch_only_keys",
    "standard_selector_values",
    "branch_selector_values",
    "selector_collision_rows",
    "standard_field16_values",
    "standard_field16_min",
    "standard_field16_max",
    "post_zero_rows",
    "post_28_rows",
    "rule_rows",
    "issue_rows",
    "next_action",
]

ANCHOR_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "body_first_word",
    "anchor_branch",
    "is_standard",
    "pair_2a30_offset",
    "selector_byte_hex",
    "selector_byte_dec",
    "selector_mod8",
    "post0_hex",
    "post1_hex",
    "branch_key",
    "post_field16_le_hex",
    "post_field16_le_dec",
    "post_field16_mod64",
    "next_word16_le_hex",
    "control_word16_le_hex",
    "anchor_window_hex",
    "body_size",
    "segment_size",
    "entropy",
    "issues",
]

RULE_FIELDNAMES = [
    "rule_id",
    "scope",
    "rows",
    "standard_rows",
    "branch_rows",
    "distinct_values",
    "values",
    "standard_values",
    "branch_values",
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


def hex_byte(value: int | None) -> str:
    return f"0x{value:02x}" if value is not None else ""


def hex_word(value: int | None) -> str:
    return f"0x{value:04x}" if value is not None else ""


def byte_at(data: bytes, index: int) -> int | None:
    return data[index] if 0 <= index < len(data) else None


def word_at(data: bytes, index: int) -> int | None:
    if 0 <= index <= len(data) - 2:
        return struct.unpack_from("<H", data, index)[0]
    return None


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


def segment_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("segment_id", ""): row for row in rows if row.get("segment_id")}


def build_anchor_rows(
    segments: dict[str, dict[str, str]],
    anchors: list[dict[str, str]],
    mix_entry_index: int,
) -> list[dict[str, str]]:
    payload_cache: dict[Path, bytes] = {}
    output: list[dict[str, str]] = []
    for anchor in anchors:
        issues: list[str] = []
        segment = segments.get(anchor.get("segment_id", ""), {})
        if not segment:
            issues.append("missing_segment_profile")

        body = b""
        archive = Path(segment.get("archive", ""))
        body_offset = int_value(segment, "body_offset")
        body_size = int_value(segment, "body_size")
        try:
            if archive and archive not in payload_cache:
                payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
            payload = payload_cache.get(archive, b"")
            body = payload[body_offset : body_offset + min(body_size, 128)]
        except Exception as exc:
            issues.append(f"read_failed:{exc}")

        pair_offset = int_value(anchor, "pair_2a30_offset")
        if body[pair_offset : pair_offset + 2] != b"\x2a\x30":
            issues.append("missing_2a30_anchor")

        selector = byte_at(body, pair_offset - 1)
        post0 = byte_at(body, pair_offset + 2)
        post1 = byte_at(body, pair_offset + 3)
        post_field16 = word_at(body, pair_offset + 4)
        next_word16 = word_at(body, pair_offset + 6)
        control_word16 = word_at(body, pair_offset)
        branch_key = f"{hex_byte(post0)}_{hex_byte(post1)}"
        is_standard = branch_key == "0x00_0x28"
        output.append(
            {
                "segment_id": anchor.get("segment_id", ""),
                "archive": segment.get("archive", ""),
                "archive_tag": anchor.get("archive_tag", ""),
                "pcx_name": anchor.get("pcx_name", ""),
                "body_first_word": anchor.get("body_first_word", ""),
                "anchor_branch": anchor.get("anchor_branch", ""),
                "is_standard": "yes" if is_standard else "no",
                "pair_2a30_offset": str(pair_offset),
                "selector_byte_hex": hex_byte(selector),
                "selector_byte_dec": str(selector) if selector is not None else "",
                "selector_mod8": str(selector % 8) if selector is not None else "",
                "post0_hex": hex_byte(post0),
                "post1_hex": hex_byte(post1),
                "branch_key": branch_key,
                "post_field16_le_hex": hex_word(post_field16),
                "post_field16_le_dec": str(post_field16) if post_field16 is not None else "",
                "post_field16_mod64": str(post_field16 % 64) if post_field16 is not None else "",
                "next_word16_le_hex": hex_word(next_word16),
                "control_word16_le_hex": hex_word(control_word16),
                "anchor_window_hex": body[max(0, pair_offset - 4) : min(len(body), pair_offset + 16)].hex(),
                "body_size": segment.get("body_size", ""),
                "segment_size": segment.get("segment_size", ""),
                "entropy": segment.get("entropy", ""),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return output


def rule_row(rule_id: str, field: str, rows: list[dict[str, str]], next_probe: str) -> dict[str, str]:
    standard = [row for row in rows if row.get("is_standard") == "yes"]
    branch = [row for row in rows if row.get("is_standard") != "yes"]
    values = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    standard_values = Counter(row.get(field, "") for row in standard if row.get(field, ""))
    branch_values = Counter(row.get(field, "") for row in branch if row.get(field, ""))
    branch_collisions = set(standard_values) & set(branch_values)
    if len(values) == 1:
        verdict = "constant"
    elif not branch_collisions:
        verdict = "separates_current_branch"
    else:
        verdict = "collides_with_branch"
    return {
        "rule_id": rule_id,
        "scope": field,
        "rows": str(len(rows)),
        "standard_rows": str(len(standard)),
        "branch_rows": str(len(branch)),
        "distinct_values": str(len(values)),
        "values": "|".join(f"{value}:{count}" for value, count in values.most_common()),
        "standard_values": "|".join(f"{value}:{count}" for value, count in standard_values.most_common()),
        "branch_values": "|".join(f"{value}:{count}" for value, count in branch_values.most_common()),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def build_rule_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        rule_row(
            "branch_key",
            "branch_key",
            rows,
            "treat 0x00_0x28 as the standard shifted 0x2a30 branch key",
        ),
        rule_row(
            "selector_byte",
            "selector_byte_hex",
            rows,
            "do not use selector byte alone because it collides with the branch row",
        ),
        rule_row(
            "pair_offset",
            "pair_2a30_offset",
            rows,
            "treat anchor offset as context, not final branch semantics",
        ),
        rule_row(
            "post_field16",
            "post_field16_le_hex",
            rows,
            "derive standard 0x2a30 post-field16 semantics before replay",
        ),
    ]


def build_summary(rows: list[dict[str, str]], rule_rows: list[dict[str, str]]) -> dict[str, str]:
    standard = [row for row in rows if row.get("is_standard") == "yes"]
    branch = [row for row in rows if row.get("is_standard") != "yes"]
    branch_keys = Counter(row.get("branch_key", "") for row in rows if row.get("branch_key"))
    standard_branch_key = Counter(row.get("branch_key", "") for row in standard if row.get("branch_key"))
    branch_only_keys = [
        key
        for key in sorted({row.get("branch_key", "") for row in branch if row.get("branch_key")})
        if key not in standard_branch_key
    ]
    standard_selectors = {row.get("selector_byte_hex", "") for row in standard if row.get("selector_byte_hex")}
    branch_selectors = {row.get("selector_byte_hex", "") for row in branch if row.get("selector_byte_hex")}
    selector_collisions = standard_selectors & branch_selectors
    standard_fields = [int_value(row, "post_field16_le_dec") for row in standard if row.get("post_field16_le_dec")]
    issue_rows = sum(1 for row in rows if row.get("issues"))

    if issue_rows:
        next_action = "fix shifted 0x2a30 standard probe issues"
    elif standard:
        branch_label = "row" if len(branch) == 1 else "rows"
        next_action = (
            f"derive shifted 0x2a30 post-field16 semantics for {len(standard)} standard rows "
            f"with {len(branch)} isolated branch {branch_label}"
        )
    else:
        next_action = "no shifted 0x2a30 standard rows"

    return {
        "scope": "total",
        "anchor_rows": str(len(rows)),
        "standard_rows": str(len(standard)),
        "branch_rows": str(len(branch)),
        "branch_key_groups": str(len(branch_keys)),
        "standard_branch_key": standard_branch_key.most_common(1)[0][0] if standard_branch_key else "",
        "branch_only_keys": "|".join(branch_only_keys),
        "standard_selector_values": str(len(standard_selectors)),
        "branch_selector_values": str(len(branch_selectors)),
        "selector_collision_rows": str(
            sum(1 for row in rows if row.get("selector_byte_hex") in selector_collisions)
        ),
        "standard_field16_values": str(len(set(standard_fields))),
        "standard_field16_min": str(min(standard_fields)) if standard_fields else "0",
        "standard_field16_max": str(max(standard_fields)) if standard_fields else "0",
        "post_zero_rows": str(sum(1 for row in rows if row.get("post0_hex") == "0x00")),
        "post_28_rows": str(sum(1 for row in rows if row.get("post1_hex") == "0x28")),
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
    anchors: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "anchors": anchors, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("anchors.csv", output_dir / "anchors.csv"),
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
<p class="muted">Standard shifted 0x2a30 anchors are split from the isolated branch row before decoder replay.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rules, RULE_FIELDNAMES)}
<h2>Anchors</h2>
{render_table(anchors, ANCHOR_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_STANDARD_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    segments_path: Path,
    anchors_path: Path,
    mix_entry_index: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    anchors = build_anchor_rows(
        segment_lookup(read_csv(segments_path)),
        read_csv(anchors_path),
        mix_entry_index,
    )
    rules = build_rule_rows(anchors)
    summary = build_summary(anchors, rules)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "anchors.csv", ANCHOR_FIELDNAMES, anchors)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rules)
    (output_dir / "index.html").write_text(build_html(summary, anchors, rules, output_dir, title))
    return summary, anchors, rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe standard shifted 0x2a30 branches in large rejected .tex bodies.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Standard Probe")
    args = parser.parse_args()

    summary, anchors, rules = write_report(
        args.output,
        args.segments,
        args.anchors,
        args.mix_entry_index,
        args.title,
    )
    print(f"Anchors: {summary['anchor_rows']}")
    print(f"Standard rows: {summary['standard_rows']}")
    print(f"Branch rows: {summary['branch_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
