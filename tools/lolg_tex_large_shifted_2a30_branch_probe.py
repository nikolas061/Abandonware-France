#!/usr/bin/env python3
"""Profile non-standard shifted 0x2a30 branch anchors in rejected large .tex bodies."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_probe")
DEFAULT_ANCHORS = Path("output/tex_large_shifted_2a30_standard_probe/anchors.csv")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
DEFAULT_HEAD_BYTES = 64

SUMMARY_FIELDNAMES = [
    "scope",
    "branch_rows",
    "unique_archives",
    "unique_pcx",
    "branch_key_groups",
    "dominant_branch_key",
    "dominant_branch_key_rows",
    "zero_other_branch_rows",
    "nonzero_branch_rows",
    "post_zero_rows",
    "selector_values",
    "selector_mod8_values",
    "post_field16_values",
    "post_field16_min",
    "post_field16_max",
    "next_word16_values",
    "body_first_word_groups",
    "byte_rows",
    "rule_rows",
    "issue_rows",
    "next_action",
]

BRANCH_FIELDNAMES = [
    "branch_id",
    "segment_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "segment_size",
    "body_size",
    "body_first_word",
    "anchor_branch",
    "branch_key",
    "pair_2a30_offset",
    "selector_byte_hex",
    "selector_byte_dec",
    "selector_mod8",
    "post0_hex",
    "post1_hex",
    "post_field16_le_hex",
    "post_field16_le_dec",
    "post_field16_mod64",
    "next_word16_le_hex",
    "control_word16_le_hex",
    "anchor_words_le_hex",
    "head64_hex",
    "tail64_hex",
    "entropy",
    "next_probe",
    "issues",
]

BYTE_FIELDNAMES = [
    "branch_id",
    "byte_offset",
    "byte_hex",
    "role",
]

RULE_FIELDNAMES = [
    "rule_id",
    "scope",
    "rows",
    "distinct_values",
    "values",
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


def branch_id(anchor: dict[str, str]) -> str:
    return anchor.get("segment_id", "") or "__".join(
        [
            anchor.get("archive_tag", ""),
            anchor.get("pcx_name", "").lower(),
            anchor.get("branch_key", ""),
        ]
    )


def anchor_words(data: bytes, pair_offset: int, count: int = 8) -> str:
    words: list[str] = []
    for index in range(count):
        offset = pair_offset + index * 2
        value = word_at(data, offset)
        if value is not None:
            words.append(f"{offset}:{hex_word(value)}")
    return "|".join(words)


def byte_role(offset: int, pair_offset: int) -> str:
    roles = {
        pair_offset - 1: "selector",
        pair_offset: "control_2a",
        pair_offset + 1: "control_30",
        pair_offset + 2: "branch_post0",
        pair_offset + 3: "branch_post1",
        pair_offset + 4: "post_field16_lo",
        pair_offset + 5: "post_field16_hi",
        pair_offset + 6: "next_word16_lo",
        pair_offset + 7: "next_word16_hi",
    }
    return roles.get(offset, "context")


def build_rows(
    segments: dict[str, dict[str, str]],
    anchors: list[dict[str, str]],
    mix_entry_index: int,
    head_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    payload_cache: dict[Path, bytes] = {}
    branch_rows: list[dict[str, str]] = []
    byte_rows: list[dict[str, str]] = []

    for anchor in anchors:
        if anchor.get("is_standard") == "yes":
            continue

        issues: list[str] = []
        segment = segments.get(anchor.get("segment_id", ""), {})
        if not segment:
            issues.append("missing_segment_profile")

        archive = Path(segment.get("archive", ""))
        body_offset = int_value(segment, "body_offset")
        body_size = int_value(segment, "body_size")
        body = b""
        try:
            if archive and archive not in payload_cache:
                payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
            payload = payload_cache.get(archive, b"")
            body = payload[body_offset : body_offset + body_size]
            if len(body) != body_size:
                issues.append("segment_body_short_read")
        except Exception as exc:
            issues.append(f"read_failed:{exc}")

        pair_offset = int_value(anchor, "pair_2a30_offset")
        if body[pair_offset : pair_offset + 2] != b"\x2a\x30":
            issues.append("missing_2a30_anchor")

        sample = body[: max(0, head_bytes)]
        selector = byte_at(body, pair_offset - 1)
        post0 = byte_at(body, pair_offset + 2)
        post1 = byte_at(body, pair_offset + 3)
        post_field16 = word_at(body, pair_offset + 4)
        next_word16 = word_at(body, pair_offset + 6)
        control_word16 = word_at(body, pair_offset)
        branch_key = anchor.get("branch_key", "") or f"{hex_byte(post0)}_{hex_byte(post1)}"
        bid = branch_id(anchor)
        next_probe = (
            f"derive shifted 0x2a30 branch {branch_key or 'unknown'} decoder "
            f"for {anchor.get('archive_tag', '')}/{anchor.get('pcx_name', '')}"
        )

        branch_rows.append(
            {
                "branch_id": bid,
                "segment_id": anchor.get("segment_id", ""),
                "archive": segment.get("archive", ""),
                "archive_tag": anchor.get("archive_tag", ""),
                "texture_path": segment.get("texture_path", ""),
                "pcx_name": anchor.get("pcx_name", ""),
                "segment_index": segment.get("segment_index", ""),
                "body_offset": segment.get("body_offset", ""),
                "body_offset_hex": segment.get("body_offset_hex", ""),
                "segment_size": segment.get("segment_size", ""),
                "body_size": segment.get("body_size", ""),
                "body_first_word": anchor.get("body_first_word", "") or segment.get("body_first_word", ""),
                "anchor_branch": anchor.get("anchor_branch", ""),
                "branch_key": branch_key,
                "pair_2a30_offset": str(pair_offset),
                "selector_byte_hex": hex_byte(selector),
                "selector_byte_dec": str(selector) if selector is not None else "",
                "selector_mod8": str(selector % 8) if selector is not None else "",
                "post0_hex": hex_byte(post0),
                "post1_hex": hex_byte(post1),
                "post_field16_le_hex": hex_word(post_field16),
                "post_field16_le_dec": str(post_field16) if post_field16 is not None else "",
                "post_field16_mod64": str(post_field16 % 64) if post_field16 is not None else "",
                "next_word16_le_hex": hex_word(next_word16),
                "control_word16_le_hex": hex_word(control_word16),
                "anchor_words_le_hex": anchor_words(body, pair_offset),
                "head64_hex": sample[:64].hex(),
                "tail64_hex": body[-64:].hex() if body else "",
                "entropy": segment.get("entropy", ""),
                "next_probe": next_probe,
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )

        for offset, value in enumerate(sample[:64]):
            byte_rows.append(
                {
                    "branch_id": bid,
                    "byte_offset": str(offset),
                    "byte_hex": f"0x{value:02x}",
                    "role": byte_role(offset, pair_offset),
                }
            )

    return branch_rows, byte_rows


def rule_row(rule_id: str, field: str, rows: list[dict[str, str]], next_probe: str) -> dict[str, str]:
    values = Counter(row.get(field, "") for row in rows if row.get(field, ""))
    if not values:
        verdict = "missing_values"
    elif len(values) == 1:
        verdict = "single_value"
    else:
        verdict = "multiple_values"
    return {
        "rule_id": rule_id,
        "scope": field,
        "rows": str(len(rows)),
        "distinct_values": str(len(values)),
        "values": "|".join(f"{value}:{count}" for value, count in values.most_common()),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def build_rule_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        rule_row("branch_key", "branch_key", rows, "use branch key as the first decoder split"),
        rule_row("anchor_branch", "anchor_branch", rows, "keep standard and non-standard branches separate"),
        rule_row("selector_byte", "selector_byte_hex", rows, "test selector byte as branch-local control"),
        rule_row("selector_mod8", "selector_mod8", rows, "test selector mod8 as compact branch-local control"),
        rule_row("post_field16", "post_field16_le_hex", rows, "decode post-branch field16 semantics"),
        rule_row("next_word16", "next_word16_le_hex", rows, "test next word as branch payload length/control"),
        rule_row("body_first_word", "body_first_word", rows, "validate body header family for branch reuse"),
    ]


def build_summary(
    branch_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    rule_rows: list[dict[str, str]],
) -> dict[str, str]:
    branch_key_counts = Counter(row.get("branch_key", "") for row in branch_rows if row.get("branch_key"))
    dominant_branch_key, dominant_branch_key_rows = ("", 0)
    if branch_key_counts:
        dominant_branch_key, dominant_branch_key_rows = branch_key_counts.most_common(1)[0]
    post_field16_values = [
        int_value(row, "post_field16_le_dec")
        for row in branch_rows
        if row.get("post_field16_le_dec")
    ]
    issue_rows = sum(1 for row in branch_rows if row.get("issues"))
    if issue_rows:
        next_action = "fix shifted 0x2a30 non-standard branch probe issues"
    elif len(branch_rows) == 1:
        row = branch_rows[0]
        next_action = (
            f"derive shifted 0x2a30 branch {row.get('branch_key') or 'unknown'} decoder "
            f"for {row.get('archive_tag', '')}/{row.get('pcx_name', '')}"
        )
    elif branch_rows:
        next_action = f"cluster {len(branch_rows)} shifted 0x2a30 non-standard branch rows by branch key"
    else:
        next_action = "no shifted 0x2a30 non-standard branch rows"

    return {
        "scope": "total",
        "branch_rows": str(len(branch_rows)),
        "unique_archives": str(len({row.get("archive", "") for row in branch_rows if row.get("archive")})),
        "unique_pcx": str(len({row.get("pcx_name", "").lower() for row in branch_rows if row.get("pcx_name")})),
        "branch_key_groups": str(len(branch_key_counts)),
        "dominant_branch_key": dominant_branch_key,
        "dominant_branch_key_rows": str(dominant_branch_key_rows),
        "zero_other_branch_rows": str(sum(1 for row in branch_rows if row.get("anchor_branch") == "zero_other_branch")),
        "nonzero_branch_rows": str(sum(1 for row in branch_rows if row.get("anchor_branch") == "nonzero_branch")),
        "post_zero_rows": str(sum(1 for row in branch_rows if row.get("post0_hex") == "0x00")),
        "selector_values": str(len({row.get("selector_byte_hex", "") for row in branch_rows if row.get("selector_byte_hex")})),
        "selector_mod8_values": str(len({row.get("selector_mod8", "") for row in branch_rows if row.get("selector_mod8")})),
        "post_field16_values": str(len(set(post_field16_values))),
        "post_field16_min": str(min(post_field16_values)) if post_field16_values else "0",
        "post_field16_max": str(max(post_field16_values)) if post_field16_values else "0",
        "next_word16_values": str(len({row.get("next_word16_le_hex", "") for row in branch_rows if row.get("next_word16_le_hex")})),
        "body_first_word_groups": str(len({row.get("body_first_word", "") for row in branch_rows if row.get("body_first_word")})),
        "byte_rows": str(len(byte_rows)),
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
    branches: list[dict[str, str]],
    bytes_rows: list[dict[str, str]],
    rules: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "branches": branches, "bytes": bytes_rows, "rules": rules}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("branches.csv", output_dir / "branches.csv"),
            ("bytes.csv", output_dir / "bytes.csv"),
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
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Non-standard shifted 0x2a30 branch anchors are isolated from the already-promoted field16 path.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Rules</h2>
{render_table(rules, RULE_FIELDNAMES)}
<h2>Branches</h2>
{render_table(branches, BRANCH_FIELDNAMES)}
<h2>Head Bytes</h2>
{render_table(bytes_rows, BYTE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    anchors_path: Path,
    segments_path: Path,
    mix_entry_index: int,
    head_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    branches, bytes_rows = build_rows(
        segment_lookup(read_csv(segments_path)),
        read_csv(anchors_path),
        mix_entry_index,
        head_bytes,
    )
    rules = build_rule_rows(branches)
    summary = build_summary(branches, bytes_rows, rules)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "branches.csv", BRANCH_FIELDNAMES, branches)
    write_csv(output_dir / "bytes.csv", BYTE_FIELDNAMES, bytes_rows)
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rules)
    (output_dir / "index.html").write_text(build_html(summary, branches, bytes_rows, rules, output_dir, title))
    return summary, branches, bytes_rows, rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile non-standard shifted 0x2a30 branches.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--head-bytes", type=int, default=DEFAULT_HEAD_BYTES)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Probe")
    args = parser.parse_args()

    summary, branches, bytes_rows, rules = write_report(
        args.output,
        args.anchors,
        args.segments,
        args.mix_entry_index,
        args.head_bytes,
        args.title,
    )
    print(f"Branch rows: {summary['branch_rows']}")
    print(f"Branch keys: {summary['branch_key_groups']}")
    print(f"Byte rows: {summary['byte_rows']}")
    print(f"Rule rows: {summary['rule_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
