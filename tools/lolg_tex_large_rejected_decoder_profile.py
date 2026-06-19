#!/usr/bin/env python3
"""Profile rejected large .tex probe segments for the next decoder path."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_rejected_decoder_profile")
DEFAULT_CANDIDATES = Path("output/tex_large_unresolved_probe_review/candidates.csv")
DEFAULT_TEXTURE_SEGMENTS = Path("output/texture_report/texture_segments.csv")
DEFAULT_PROFILE = Path("output/tex_remaining_reference_profile/profile.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
DEFAULT_MAX_SAMPLE_BYTES = 262_144

SUMMARY_FIELDNAMES = [
    "scope",
    "rejected_segment_rows",
    "rejected_candidate_rows",
    "unique_archives",
    "unique_pcx",
    "total_segment_bytes",
    "sampled_bytes",
    "body_first_word_groups",
    "dominant_body_first_word",
    "dominant_body_first_word_rows",
    "lcw_invalid_rows",
    "window_invalid_rows",
    "high_entropy_rows",
    "raw_probe_rejected_rows",
    "control_path_groups",
    "dominant_control_path",
    "dominant_control_path_rows",
    "shifted_2a30_rows",
    "shared_2700302b_rows",
    "llse_signature_rows",
    "shifted_2a30_anchor_rows",
    "shifted_2a30_standard_rows",
    "shifted_2a30_branch_rows",
    "shifted_2a30_selector_values",
    "issue_rows",
    "next_action",
]

SEGMENT_FIELDNAMES = [
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
    "rejected_candidates",
    "widths_tried",
    "skips_tried",
    "best_structure_score",
    "body_first_word",
    "raw_head4_hex",
    "le16_0_hex",
    "le16_1_hex",
    "pair_2a30_offset",
    "pair_2930_offset",
    "control_path",
    "body_first_byte_hex",
    "body_lcw_status",
    "body_window_status",
    "entropy",
    "zero_ratio",
    "ff_ratio",
    "printable_ratio",
    "sample_bytes",
    "sample_entropy",
    "sample_unique_bytes",
    "sample_zero_ratio",
    "sample_ff_ratio",
    "sample_printable_ratio",
    "top_byte_hex",
    "top_byte_ratio",
    "top_word_le_hex",
    "top_word_le_ratio",
    "head32_hex",
    "tail32_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "body_first_word",
    "rows",
    "archives",
    "pcx_names",
    "total_segment_bytes",
    "sampled_bytes",
    "avg_entropy",
    "lcw_statuses",
    "window_statuses",
    "top_bytes",
    "sample_segments",
    "next_probe",
]

CONTROL_FIELDNAMES = [
    "control_path",
    "rows",
    "body_first_words",
    "archives",
    "pcx_names",
    "pair_2a30_rows",
    "pair_2930_rows",
    "total_segment_bytes",
    "sampled_bytes",
    "sample_segments",
    "next_probe",
]

ANCHOR_FIELDNAMES = [
    "segment_id",
    "archive_tag",
    "pcx_name",
    "body_first_word",
    "pair_2a30_offset",
    "selector_byte_hex",
    "post0_hex",
    "post1_hex",
    "post2_hex",
    "post3_hex",
    "anchor_window_hex",
    "anchor_branch",
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


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def ratio(value: float) -> str:
    return f"{value:.6f}"


def normalize_name(value: str) -> str:
    return Path(value.replace("\\", "/")).name.lower()


def safe_name(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return clean.strip("._") or "unnamed"


def segment_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        normalize_name(row.get("pcx_name", "")),
        row.get("segment_index", ""),
        row.get("body_offset_hex", "") or row.get("body_offset", ""),
    )


def segment_id(row: dict[str, str]) -> str:
    return "__".join(
        [
            safe_name(row.get("archive_tag", "")),
            safe_name(normalize_name(row.get("pcx_name", ""))),
            f"seg{safe_name(row.get('segment_index', ''))}",
            safe_name(row.get("body_offset_hex", "") or row.get("body_offset", "")),
        ]
    )


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


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def byte_ratio(data: bytes, value: int) -> float:
    return (data.count(value) / len(data)) if data else 0.0


def printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for value in data if 32 <= value <= 126)
    return printable / len(data)


def top_byte(data: bytes) -> tuple[str, float]:
    if not data:
        return "", 0.0
    value, count = Counter(data).most_common(1)[0]
    return f"0x{value:02x}", count / len(data)


def top_word_le(data: bytes) -> tuple[str, float]:
    if len(data) < 2:
        return "", 0.0
    counts: Counter[int] = Counter()
    limit = len(data) - (len(data) % 2)
    for (word,) in struct.iter_unpack("<H", data[:limit]):
        counts[word] += 1
    word, count = counts.most_common(1)[0]
    return f"0x{word:04x}", count / (limit // 2)


def pair_offset(data: bytes, pair: bytes) -> str:
    offset = data[:16].find(pair)
    return str(offset) if offset >= 0 else ""


def classify_control_path(body: bytes, body_first_word: str) -> str:
    if body.startswith(b"LLSE"):
        return "llse_signature"
    if body_first_word == "2700302b":
        return "shared_2700302b_header"
    if body[:16].find(b"\x2a\x30") >= 0:
        return "shifted_2a30_header"
    if body[:16].find(b"\x29\x30") >= 0:
        return "shifted_2930_header"
    return "unclassified_header"


def byte_at_hex(data: bytes, index: int) -> str:
    return f"0x{data[index]:02x}" if 0 <= index < len(data) else ""


def texture_segment_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("reference_class") == "prefix":
            continue
        lookup[segment_key(row)] = row
    return lookup


def profile_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        archive = row.get("archive", "")
        name = normalize_name(row.get("normalized_pcx_name") or row.get("pcx_name", ""))
        if archive and name:
            lookup[(archive, name)] = row
    return lookup


def build_segment_rows(
    candidates: list[dict[str, str]],
    texture_segments: dict[tuple[str, str, str, str], dict[str, str]],
    profiles: dict[tuple[str, str], dict[str, str]],
    *,
    mix_entry_index: int,
    max_sample_bytes: int,
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[segment_key(row)].append(row)

    payload_cache: dict[Path, bytes] = {}
    rows: list[dict[str, str]] = []
    for key in sorted(grouped):
        group = grouped[key]
        if not any(row.get("review_status") == "rejected" for row in group):
            continue
        first = sorted(group, key=lambda row: int_value(row, "rank"))[0]
        statuses = {row.get("review_status", "") for row in group}
        issues: list[str] = []
        if statuses != {"rejected"}:
            issues.append("segment_not_fully_rejected")

        archive_path = Path(first.get("archive", ""))
        body_offset = int_value(first, "body_offset")
        segment_size = int_value(first, "segment_size")
        profile = profiles.get((first.get("archive", ""), normalize_name(first.get("pcx_name", ""))), {})
        texture_row = texture_segments.get(key, {})
        if not texture_row:
            issues.append("missing_texture_segment_profile")
        body_size = int_value(texture_row, "post_terminator_size")
        if not body_size:
            segment_start = int_value(texture_row, "segment_start")
            prefix_size = max(0, body_offset - segment_start)
            body_size = max(0, segment_size - prefix_size) or segment_size

        sample = b""
        body = b""
        try:
            if archive_path not in payload_cache:
                payload_cache[archive_path] = read_mix_entry(archive_path, mix_entry_index)
            payload = payload_cache[archive_path]
            body = payload[body_offset : body_offset + body_size]
            if len(body) != body_size:
                issues.append("segment_body_short_read")
            sample = body[:max_sample_bytes]
        except Exception as exc:
            issues.append(f"read_failed:{exc}")

        best_score = max((float_value(row, "structure_score") for row in group), default=0.0)
        top_byte_hex, top_byte_value = top_byte(sample)
        top_word_hex, top_word_value = top_word_le(sample)
        body_first_word = first.get("body_first_word", "") or texture_row.get("body_first_word", "")
        raw_head4 = body[:4]
        le16_values = list(struct.unpack("<HH", raw_head4)) if len(raw_head4) == 4 else []
        pair_2a30_offset = pair_offset(body, b"\x2a\x30")
        pair_2930_offset = pair_offset(body, b"\x29\x30")
        control_path = classify_control_path(body, body_first_word)
        rows.append(
            {
                "segment_id": segment_id(first),
                "archive": first.get("archive", ""),
                "archive_tag": first.get("archive_tag", "") or archive_path.stem,
                "texture_path": first.get("texture_path", "") or profile.get("texture_path", ""),
                "pcx_name": first.get("pcx_name", ""),
                "segment_index": first.get("segment_index", ""),
                "body_offset": first.get("body_offset", ""),
                "body_offset_hex": first.get("body_offset_hex", ""),
                "segment_size": str(segment_size),
                "body_size": str(body_size),
                "rejected_candidates": str(sum(1 for row in group if row.get("review_status") == "rejected")),
                "widths_tried": "|".join(sorted({row.get("width", "") for row in group if row.get("width")})),
                "skips_tried": "|".join(sorted({row.get("skip", "") for row in group if row.get("skip")})),
                "best_structure_score": ratio(best_score),
                "body_first_word": body_first_word,
                "raw_head4_hex": raw_head4.hex(),
                "le16_0_hex": f"0x{le16_values[0]:04x}" if le16_values else "",
                "le16_1_hex": f"0x{le16_values[1]:04x}" if len(le16_values) > 1 else "",
                "pair_2a30_offset": pair_2a30_offset,
                "pair_2930_offset": pair_2930_offset,
                "control_path": control_path,
                "body_first_byte_hex": f"0x{body[0]:02x}" if body else "",
                "body_lcw_status": texture_row.get("body_lcw_status", ""),
                "body_window_status": texture_row.get("body_window_status", ""),
                "entropy": texture_row.get("entropy", ""),
                "zero_ratio": texture_row.get("zero_ratio", ""),
                "ff_ratio": texture_row.get("ff_ratio", ""),
                "printable_ratio": texture_row.get("printable_ratio", ""),
                "sample_bytes": str(len(sample)),
                "sample_entropy": ratio(entropy(sample)),
                "sample_unique_bytes": str(len(set(sample))),
                "sample_zero_ratio": ratio(byte_ratio(sample, 0)),
                "sample_ff_ratio": ratio(byte_ratio(sample, 255)),
                "sample_printable_ratio": ratio(printable_ratio(sample)),
                "top_byte_hex": top_byte_hex,
                "top_byte_ratio": ratio(top_byte_value),
                "top_word_le_hex": top_word_hex,
                "top_word_le_ratio": ratio(top_word_value),
                "head32_hex": body[:32].hex(),
                "tail32_hex": body[-32:].hex() if body else "",
                "_body_sample_hex": body[:64].hex(),
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def build_group_rows(segment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in segment_rows:
        grouped[row.get("body_first_word", "")].append(row)

    output: list[dict[str, str]] = []
    for body_first_word, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        entropy_values = [float_value(row, "entropy") for row in rows if row.get("entropy")]
        top_bytes = Counter(row.get("top_byte_hex", "") for row in rows if row.get("top_byte_hex"))
        sample_segments = "|".join(row.get("segment_id", "") for row in rows[:4])
        next_probe = (
            f"trace control/header family {body_first_word or 'unknown'} "
            f"across {len(rows)} rejected large .tex segments"
        )
        output.append(
            {
                "body_first_word": body_first_word,
                "rows": str(len(rows)),
                "archives": str(len({row.get("archive", "") for row in rows if row.get("archive")})),
                "pcx_names": str(len({normalize_name(row.get("pcx_name", "")) for row in rows if row.get("pcx_name")})),
                "total_segment_bytes": str(sum(int_value(row, "segment_size") for row in rows)),
                "sampled_bytes": str(sum(int_value(row, "sample_bytes") for row in rows)),
                "avg_entropy": ratio(sum(entropy_values) / len(entropy_values)) if entropy_values else "",
                "lcw_statuses": "|".join(
                    f"{status}:{count}" for status, count in Counter(row.get("body_lcw_status", "") for row in rows).most_common()
                ),
                "window_statuses": "|".join(
                    f"{status}:{count}"
                    for status, count in Counter(row.get("body_window_status", "") for row in rows).most_common()
                ),
                "top_bytes": "|".join(f"{value}:{count}" for value, count in top_bytes.most_common(4)),
                "sample_segments": sample_segments,
                "next_probe": next_probe,
            }
        )
    return output


def build_control_rows(segment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in segment_rows:
        grouped[row.get("control_path", "")].append(row)

    output: list[dict[str, str]] = []
    for control_path, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        next_probe = f"probe {control_path or 'unknown'} across {len(rows)} rejected large .tex segments"
        output.append(
            {
                "control_path": control_path,
                "rows": str(len(rows)),
                "body_first_words": "|".join(
                    word for word, _count in Counter(row.get("body_first_word", "") for row in rows).most_common()
                ),
                "archives": str(len({row.get("archive", "") for row in rows if row.get("archive")})),
                "pcx_names": str(len({normalize_name(row.get("pcx_name", "")) for row in rows if row.get("pcx_name")})),
                "pair_2a30_rows": str(sum(1 for row in rows if row.get("pair_2a30_offset"))),
                "pair_2930_rows": str(sum(1 for row in rows if row.get("pair_2930_offset"))),
                "total_segment_bytes": str(sum(int_value(row, "segment_size") for row in rows)),
                "sampled_bytes": str(sum(int_value(row, "sample_bytes") for row in rows)),
                "sample_segments": "|".join(row.get("segment_id", "") for row in rows[:4]),
                "next_probe": next_probe,
            }
        )
    return output


def build_anchor_rows(segment_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in segment_rows:
        if row.get("control_path") != "shifted_2a30_header":
            continue
        offset = int_value(row, "pair_2a30_offset")
        sample = bytes.fromhex(row.get("_body_sample_hex", ""))
        post0 = byte_at_hex(sample, offset + 2)
        post1 = byte_at_hex(sample, offset + 3)
        if post0 == "0x00" and post1 == "0x28":
            branch = "standard_zero_28"
            next_probe = "test standard shifted 0x2a30 post-zero field decoder"
        elif post0 == "0x00":
            branch = "zero_other_branch"
            next_probe = "isolate shifted 0x2a30 zero branch variant"
        else:
            branch = "nonzero_branch"
            next_probe = "isolate shifted 0x2a30 nonzero branch variant"
        start = max(0, offset - 4)
        end = min(len(sample), offset + 12)
        output.append(
            {
                "segment_id": row.get("segment_id", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "body_first_word": row.get("body_first_word", ""),
                "pair_2a30_offset": row.get("pair_2a30_offset", ""),
                "selector_byte_hex": byte_at_hex(sample, offset - 1),
                "post0_hex": post0,
                "post1_hex": post1,
                "post2_hex": byte_at_hex(sample, offset + 4),
                "post3_hex": byte_at_hex(sample, offset + 5),
                "anchor_window_hex": sample[start:end].hex(),
                "anchor_branch": branch,
                "next_probe": next_probe,
            }
        )
    return output


def build_summary(
    segment_rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in segment_rows if row.get("issues"))
    body_first_counts = Counter(row.get("body_first_word", "") for row in segment_rows)
    control_path_counts = Counter(row.get("control_path", "") for row in segment_rows)
    dominant_body_first_word, dominant_rows = ("", 0)
    if body_first_counts:
        dominant_body_first_word, dominant_rows = body_first_counts.most_common(1)[0]
    dominant_control_path, dominant_control_path_rows = ("", 0)
    if control_path_counts:
        dominant_control_path, dominant_control_path_rows = control_path_counts.most_common(1)[0]

    high_entropy_rows = sum(1 for row in segment_rows if float_value(row, "entropy") >= 7.0)
    lcw_invalid_rows = sum(1 for row in segment_rows if row.get("body_lcw_status", "").startswith("invalid"))
    window_invalid_rows = sum(
        1
        for row in segment_rows
        if row.get("body_window_status") and row.get("body_window_status") not in {"ok", "decoded"}
    )
    shifted_2a30_rows = control_path_counts["shifted_2a30_header"]
    shared_2700302b_rows = control_path_counts["shared_2700302b_header"]
    llse_signature_rows = control_path_counts["llse_signature"]
    shifted_2a30_standard_rows = sum(1 for row in anchor_rows if row.get("anchor_branch") == "standard_zero_28")
    shifted_2a30_branch_rows = len(anchor_rows) - shifted_2a30_standard_rows
    shifted_2a30_selector_values = len(
        {row.get("selector_byte_hex", "") for row in anchor_rows if row.get("selector_byte_hex")}
    )
    if issue_rows:
        next_action = "fix rejected large .tex decoder profile issues"
    elif shifted_2a30_standard_rows:
        branch_label = "row" if shifted_2a30_branch_rows == 1 else "rows"
        next_action = (
            f"test shifted 0x2a30 standard post-zero decoder on {shifted_2a30_standard_rows} rows "
            f"and isolate {shifted_2a30_branch_rows} branch {branch_label}"
        )
    elif shifted_2a30_rows:
        next_action = f"probe shifted 0x2a30 body-control header across {shifted_2a30_rows} rejected large .tex segments"
    elif segment_rows:
        next_action = (
            f"trace .tex body control grammar for {len(segment_rows)} rejected large segments "
            f"({len(control_rows)} control paths)"
        )
    else:
        next_action = "no rejected large .tex segments to profile"

    return {
        "scope": "total",
        "rejected_segment_rows": str(len(segment_rows)),
        "rejected_candidate_rows": str(sum(int_value(row, "rejected_candidates") for row in segment_rows)),
        "unique_archives": str(len({row.get("archive", "") for row in segment_rows if row.get("archive")})),
        "unique_pcx": str(len({normalize_name(row.get("pcx_name", "")) for row in segment_rows if row.get("pcx_name")})),
        "total_segment_bytes": str(sum(int_value(row, "segment_size") for row in segment_rows)),
        "sampled_bytes": str(sum(int_value(row, "sample_bytes") for row in segment_rows)),
        "body_first_word_groups": str(len(group_rows)),
        "dominant_body_first_word": dominant_body_first_word,
        "dominant_body_first_word_rows": str(dominant_rows),
        "lcw_invalid_rows": str(lcw_invalid_rows),
        "window_invalid_rows": str(window_invalid_rows),
        "high_entropy_rows": str(high_entropy_rows),
        "raw_probe_rejected_rows": str(sum(int_value(row, "rejected_candidates") for row in segment_rows)),
        "control_path_groups": str(len(control_rows)),
        "dominant_control_path": dominant_control_path,
        "dominant_control_path_rows": str(dominant_control_path_rows),
        "shifted_2a30_rows": str(shifted_2a30_rows),
        "shared_2700302b_rows": str(shared_2700302b_rows),
        "llse_signature_rows": str(llse_signature_rows),
        "shifted_2a30_anchor_rows": str(len(anchor_rows)),
        "shifted_2a30_standard_rows": str(shifted_2a30_standard_rows),
        "shifted_2a30_branch_rows": str(shifted_2a30_branch_rows),
        "shifted_2a30_selector_values": str(shifted_2a30_selector_values),
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
    segments: list[dict[str, str]],
    groups: list[dict[str, str]],
    control_rows: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "segments": segments,
        "groups": groups,
        "control_paths": control_rows,
        "shifted_2a30_anchors": anchor_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("segments.csv", output_dir / "segments.csv"),
            ("body_first_word_groups.csv", output_dir / "body_first_word_groups.csv"),
            ("control_paths.csv", output_dir / "control_paths.csv"),
            ("shifted_2a30_anchors.csv", output_dir / "shifted_2a30_anchors.csv"),
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
td {{ max-width: 360px; overflow-wrap: anywhere; }}
code {{ color: #cce7ff; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Rejected visual raw probes are summarized here as byte/control families for the next decoder pass.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Body First Word Groups</h2>
{render_table(groups, GROUP_FIELDNAMES)}
<h2>Control Paths</h2>
{render_table(control_rows, CONTROL_FIELDNAMES)}
<h2>Shifted 2a30 Anchors</h2>
{render_table(anchor_rows, ANCHOR_FIELDNAMES)}
<h2>Rejected Segments</h2>
{render_table(segments, SEGMENT_FIELDNAMES)}
</main>
<script>const TEX_LARGE_REJECTED_DECODER_PROFILE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    texture_segments_path: Path,
    profile_path: Path,
    mix_entry_index: int,
    max_sample_bytes: int,
    title: str,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = read_csv(candidates_path)
    segment_rows = build_segment_rows(
        candidates,
        texture_segment_lookup(read_csv(texture_segments_path)),
        profile_lookup(read_csv(profile_path)),
        mix_entry_index=mix_entry_index,
        max_sample_bytes=max_sample_bytes,
    )
    group_rows = build_group_rows(segment_rows)
    control_rows = build_control_rows(segment_rows)
    anchor_rows = build_anchor_rows(segment_rows)
    summary = build_summary(segment_rows, group_rows, control_rows, anchor_rows)
    public_segment_rows = [{key: value for key, value in row.items() if not key.startswith("_")} for row in segment_rows]
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "segments.csv", SEGMENT_FIELDNAMES, public_segment_rows)
    write_csv(output_dir / "body_first_word_groups.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(output_dir / "control_paths.csv", CONTROL_FIELDNAMES, control_rows)
    write_csv(output_dir / "shifted_2a30_anchors.csv", ANCHOR_FIELDNAMES, anchor_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, public_segment_rows, group_rows, control_rows, anchor_rows, output_dir, title)
    )
    return summary, public_segment_rows, group_rows, control_rows, anchor_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile rejected large .tex probe segments for decoder work.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--texture-segments", type=Path, default=DEFAULT_TEXTURE_SEGMENTS)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--max-sample-bytes", type=int, default=DEFAULT_MAX_SAMPLE_BYTES)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Rejected Decoder Profile")
    args = parser.parse_args()

    summary, segments, groups, control_rows, anchor_rows = write_report(
        args.output,
        args.candidates,
        args.texture_segments,
        args.profile,
        args.mix_entry_index,
        args.max_sample_bytes,
        args.title,
    )
    print(f"Rejected large segments: {summary['rejected_segment_rows']}")
    print(f"Rejected candidates: {summary['rejected_candidate_rows']}")
    print(f"Body-first-word groups: {summary['body_first_word_groups']}")
    print(f"Control paths: {summary['control_path_groups']}")
    print(f"Shifted 2a30 anchors: {summary['shifted_2a30_anchor_rows']}")
    print(f"High entropy rows: {summary['high_entropy_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
