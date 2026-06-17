#!/usr/bin/env python3
"""Probe repeated jump-mixed micro-token payloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_MICRO_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/targets.csv")
DEFAULT_SPLIT_BUCKETS = Path("output/tex_micro_jump_split/buckets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_jump_mixed_payload")

SOURCE_POOLS = ("segment_gap", "control_prefix", "fragment", "decoded_replay")
TRANSFORMS = ("identity", "xor80", "xorff", "add1", "sub1", "add2", "sub2")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "bucket_rows",
    "repeated_bucket_rows",
    "repeated_bucket_bytes",
    "payload_signature_groups",
    "repeated_payload_signature_rows",
    "repeated_payload_signature_bytes",
    "value_histogram_groups",
    "repeated_value_histogram_rows",
    "repeated_value_histogram_bytes",
    "signed_profile_groups",
    "repeated_signed_profile_rows",
    "repeated_signed_profile_bytes",
    "pair_overlap_ge50_rows",
    "pair_overlap_ge50_bytes",
    "source_profile_ge50_rows",
    "source_profile_ge50_bytes",
    "source_profile_ge75_rows",
    "source_profile_ge75_bytes",
    "external_best_exact_bytes",
    "external_best_prefix_bytes",
    "spatial_best_distance",
    "spatial_best_rows",
    "spatial_best_bytes",
    "spatial_best_correct_bytes",
    "spatial_best_false_bytes",
    "spatial_exact_copy_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "bucket_rank",
    "bucket_key",
    "archive",
    "pcx_name",
    "frontier_id",
    "length",
    "start",
    "end",
    "control_window_signature",
    "top_nibble",
    "jump_delta_count",
    "jump_delta_ratio",
    "small_delta_count",
    "small_delta_ratio",
    "payload_signature",
    "value_histogram_key",
    "signed_profile_key",
    "best_bucket_peer_exact",
    "best_bucket_peer_ratio",
    "best_source_pool",
    "best_source_offset",
    "best_source_transform",
    "best_source_exact",
    "best_source_prefix",
    "best_source_known_bytes",
    "best_source_profile_pool",
    "best_source_profile_offset",
    "best_source_profile_overlap",
    "best_source_profile_ratio",
    "best_spatial_distance",
    "best_spatial_correct",
    "best_spatial_false",
    "verdict",
    "head_hex",
    "source_head_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]

DISTANCE_FIELDNAMES = [
    "distance",
    "rows",
    "bytes",
    "correct_bytes",
    "false_bytes",
    "exact_rows",
    "sample_pcx",
    "sample_frontier_id",
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


def float_value(row: dict[str, str] | dict[str, object], field: str) -> float:
    try:
        return float(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0.0


def ratio(numerator: int | float, denominator: int | float) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def short_sha1(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha1(data).hexdigest()[:14]


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


def bucket_key(row: dict[str, str] | dict[str, object]) -> str:
    return f"nibble={row.get('top_nibble', '')}|control={row.get('control_window_signature', '')}"


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_sources(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    replay_by_key = {fixture_key(row): row for row in replay_rows}
    sources: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        replay = replay_by_key.get(key, {})
        local_issues: list[str] = []
        sources[key] = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap"),
            "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), local_issues, "control_prefix"),
            "fragment": read_bytes(fixture.get("fragment_path", ""), local_issues, "fragment"),
            "decoded_replay": read_bytes(replay.get("decoded_path", ""), local_issues, "decoded_replay"),
            "known_mask": read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask"),
        }
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return sources, issues


def transform_byte(value: int, transform: str) -> int:
    if transform == "identity":
        return value
    if transform == "xor80":
        return value ^ 0x80
    if transform == "xorff":
        return value ^ 0xFF
    if transform == "add1":
        return (value + 1) & 0xFF
    if transform == "sub1":
        return (value - 1) & 0xFF
    if transform == "add2":
        return (value + 2) & 0xFF
    if transform == "sub2":
        return (value - 2) & 0xFF
    raise ValueError(transform)


def apply_transform(data: bytes, transform: str) -> bytes:
    if transform == "identity":
        return data
    return bytes(transform_byte(value, transform) for value in data)


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def common_prefix(left: bytes, right: bytes) -> int:
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        if left_value != right_value:
            return index
    return min(len(left), len(right))


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


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


def signed_profile(data: bytes) -> list[str]:
    return [signed_bucket(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]


def profile_overlap(wanted: list[str], candidate: list[str]) -> tuple[int, int]:
    wanted_counts = Counter(wanted)
    candidate_counts = Counter(candidate)
    return sum(min(wanted_counts[key], candidate_counts[key]) for key in wanted_counts), len(wanted)


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={short_sha1(data)}"


def value_histogram_key(data: bytes) -> str:
    counts = Counter(data)
    text = ";".join(f"{value:02x}:{count}" for value, count in sorted(counts.items()))
    return f"unique={len(counts)}|sha1={short_sha1(text)}"


def signed_profile_key(data: bytes) -> str:
    profile = signed_profile(data)
    text = ";".join(f"{key}:{value}" for key, value in sorted(Counter(profile).items()))
    return f"len={len(profile)}|sha1={short_sha1(text)}"


def best_peer_score(data: bytes, peers: list[bytes]) -> tuple[int, str]:
    best = 0
    skipped_self = False
    for peer in peers:
        if peer == data and not skipped_self:
            skipped_self = True
            continue
        length = min(len(data), len(peer))
        if not length:
            continue
        best = max(best, exact_count(data[:length], peer[:length]))
    return best, ratio(best, len(data))


def best_source_match(target: bytes, sources: dict[str, bytes], known_mask: bytes) -> dict[str, object]:
    best: dict[str, object] = {
        "pool": "",
        "offset": "",
        "transform": "",
        "exact": 0,
        "prefix": 0,
        "known": 0,
        "source_head_hex": "",
    }
    for pool in SOURCE_POOLS:
        source = sources.get(pool, b"")
        if len(source) < len(target) or not target:
            continue
        for offset in range(0, len(source) - len(target) + 1):
            window = source[offset : offset + len(target)]
            for transform in TRANSFORMS:
                output = apply_transform(window, transform)
                exact = exact_count(target, output)
                prefix = common_prefix(target, output)
                known = 0
                if pool == "decoded_replay" and len(known_mask) >= offset + len(target):
                    known = sum(1 for value in known_mask[offset : offset + len(target)] if value)
                score = (exact, prefix, known, -offset, -SOURCE_POOLS.index(pool), transform == "identity")
                best_score = (
                    int(best["exact"]),
                    int(best["prefix"]),
                    int(best["known"]),
                    -int(best["offset"] or 0),
                    -SOURCE_POOLS.index(str(best["pool"])) if best["pool"] in SOURCE_POOLS else -99,
                    best["transform"] == "identity",
                )
                if score > best_score:
                    best = {
                        "pool": pool,
                        "offset": offset,
                        "transform": transform,
                        "exact": exact,
                        "prefix": prefix,
                        "known": known,
                        "source_head_hex": window[:16].hex(),
                    }
    return best


def best_source_profile(target: bytes, sources: dict[str, bytes]) -> dict[str, object]:
    wanted = signed_profile(target)
    best: dict[str, object] = {
        "pool": "",
        "offset": "",
        "overlap": 0,
        "ratio": "0.000000",
    }
    if not wanted:
        return best
    for pool in SOURCE_POOLS:
        source = sources.get(pool, b"")
        if len(source) < len(target):
            continue
        for offset in range(0, len(source) - len(target) + 1):
            candidate = signed_profile(source[offset : offset + len(target)])
            overlap, denominator = profile_overlap(wanted, candidate)
            score = (overlap, -offset, -SOURCE_POOLS.index(pool))
            best_score = (
                int(best["overlap"]),
                -int(best["offset"] or 0),
                -SOURCE_POOLS.index(str(best["pool"])) if best["pool"] in SOURCE_POOLS else -99,
            )
            if score > best_score:
                best = {
                    "pool": pool,
                    "offset": offset,
                    "overlap": overlap,
                    "ratio": ratio(overlap, denominator),
                }
    return best


def best_spatial_match(expected_all: bytes, start: int, end: int, max_distance: int) -> dict[str, object]:
    target = expected_all[start:end]
    best: dict[str, object] = {"distance": "", "correct": 0, "false": len(target)}
    if not target:
        return best
    for distance in range(1, min(max_distance, start) + 1):
        source = expected_all[start - distance : end - distance]
        if len(source) != len(target):
            continue
        correct = exact_count(target, source)
        false = len(target) - correct
        score = (correct, -false, -distance)
        best_score = (int(best["correct"]), -int(best["false"]), -int(best["distance"] or 0))
        if score > best_score:
            best = {"distance": distance, "correct": correct, "false": false}
    return best


def repeated_row_stats(rows: list[dict[str, object]], key: str) -> tuple[int, int, int]:
    counter = Counter(str(row.get(key, "")) for row in rows if row.get(key, ""))
    repeated_rows = [row for row in rows if row.get(key, "") and counter[str(row.get(key, ""))] > 1]
    return len(counter), len(repeated_rows), sum(int_value(row, "length") for row in repeated_rows)


def build_groups(rows: list[dict[str, object]], fields: list[tuple[str, str]]) -> list[dict[str, object]]:
    group_rows: list[dict[str, object]] = []
    for group_kind, field in fields:
        by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            key = str(row.get(field, ""))
            if key:
                by_key[key].append(row)
        for key, members in by_key.items():
            sample = members[0]
            verdict = "repeated_group" if len(members) > 1 else "singleton_group"
            group_rows.append(
                {
                    "rank": 0,
                    "group_kind": group_kind,
                    "group_key": key,
                    "rows": len(members),
                    "bytes": sum(int_value(row, "length") for row in members),
                    "sample_pcx": sample.get("pcx_name", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                    "verdict": verdict,
                }
            )
    group_rows.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), str(row["group_kind"])))
    for index, row in enumerate(group_rows, start=1):
        row["rank"] = index
    return group_rows


def build(
    micro_rows: list[dict[str, str]],
    split_buckets: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    max_distance: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    source_by_fixture, fixture_issues = load_sources(fixture_rows, replay_rows)
    repeated_buckets = {
        row.get("bucket_key", ""): int_value(row, "rank")
        for row in split_buckets
        if int_value(row, "rows") > 1
    }
    source_rows = [
        row
        for row in micro_rows
        if row.get("micro_class") == "jump_mixed_walk" and bucket_key(row) in repeated_buckets
    ]
    source_rows.sort(key=lambda row: (repeated_buckets[bucket_key(row)], int_value(row, "rank")))

    payload_by_bucket: dict[str, list[bytes]] = defaultdict(list)
    prepared: list[tuple[dict[str, str], bytes, dict[str, bytes], list[str]]] = []
    issues: list[str] = []
    for row in source_rows:
        row_issues = [issue for issue in row.get("issues", "").split(";") if issue]
        sources = source_by_fixture.get(fixture_key(row), {})
        expected_all = sources.get("expected", b"")
        start = int_value(row, "start")
        end = int_value(row, "end")
        target = expected_all[start:end]
        if not target:
            row_issues.append("missing_expected_payload")
        if row.get("length") and int_value(row, "length") != len(target):
            row_issues.append(f"length_mismatch:{row.get('length')}:{len(target)}")
        prepared.append((row, target, sources, row_issues))
        payload_by_bucket[bucket_key(row)].append(target)
        issues.extend(row_issues)
    issues.extend(fixture_issues)

    row_outputs: list[dict[str, object]] = []
    distance_counters: dict[int, Counter[str]] = defaultdict(Counter)
    distance_samples: dict[int, dict[str, str]] = {}
    for row, target, sources, row_issues in prepared:
        start = int_value(row, "start")
        end = int_value(row, "end")
        expected_all = sources.get("expected", b"")
        peers = payload_by_bucket[bucket_key(row)]
        peer_exact, peer_ratio = best_peer_score(target, peers)
        source_match = best_source_match(target, sources, sources.get("known_mask", b""))
        source_profile = best_source_profile(target, sources)
        spatial = best_spatial_match(expected_all, start, end, max_distance)
        for distance in range(1, min(max_distance, start) + 1):
            source = expected_all[start - distance : end - distance]
            if len(source) != len(target):
                continue
            correct = exact_count(target, source)
            counter = distance_counters[distance]
            counter["rows"] += 1
            counter["bytes"] += len(target)
            counter["correct"] += correct
            counter["false"] += len(target) - correct
            counter["exact_rows"] += 1 if correct == len(target) else 0
            distance_samples.setdefault(distance, row)
        profile_ratio = float_value(source_profile, "ratio")
        if int(source_match["exact"]) == len(target) and int(source_match["known"]) == len(target):
            verdict = "known_source_exact_review"
        elif int(source_match["exact"]) == len(target):
            verdict = "oracle_source_exact_review"
        elif int(spatial["correct"]) == len(target):
            verdict = "oracle_spatial_exact_review"
        elif float(peer_ratio) >= 0.5:
            verdict = "peer_overlap_review"
        elif profile_ratio >= 0.75:
            verdict = "source_profile_review"
        else:
            verdict = "jump_payload_blocked"
        row_outputs.append(
            {
                "rank": len(row_outputs) + 1,
                "bucket_rank": repeated_buckets[bucket_key(row)],
                "bucket_key": bucket_key(row),
                "archive": row.get("archive", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "length": len(target),
                "start": start,
                "end": end,
                "control_window_signature": row.get("control_window_signature", ""),
                "top_nibble": row.get("top_nibble", ""),
                "jump_delta_count": row.get("jump_delta_count", ""),
                "jump_delta_ratio": row.get("jump_delta_ratio", ""),
                "small_delta_count": row.get("small_delta_count", ""),
                "small_delta_ratio": row.get("small_delta_ratio", ""),
                "payload_signature": payload_signature(target),
                "value_histogram_key": value_histogram_key(target),
                "signed_profile_key": signed_profile_key(target),
                "best_bucket_peer_exact": peer_exact,
                "best_bucket_peer_ratio": peer_ratio,
                "best_source_pool": source_match["pool"],
                "best_source_offset": source_match["offset"],
                "best_source_transform": source_match["transform"],
                "best_source_exact": source_match["exact"],
                "best_source_prefix": source_match["prefix"],
                "best_source_known_bytes": source_match["known"],
                "best_source_profile_pool": source_profile["pool"],
                "best_source_profile_offset": source_profile["offset"],
                "best_source_profile_overlap": source_profile["overlap"],
                "best_source_profile_ratio": source_profile["ratio"],
                "best_spatial_distance": spatial["distance"],
                "best_spatial_correct": spatial["correct"],
                "best_spatial_false": spatial["false"],
                "verdict": verdict,
                "head_hex": target[:16].hex(),
                "source_head_hex": source_match["source_head_hex"],
                "issues": ";".join(row_issues),
            }
        )

    distance_rows: list[dict[str, object]] = []
    for distance, counter in distance_counters.items():
        sample = distance_samples[distance]
        if counter["exact_rows"]:
            verdict = "oracle_spatial_exact_review"
        elif counter["correct"] >= counter["false"]:
            verdict = "partial_spatial_review"
        else:
            verdict = "spatial_reject"
        distance_rows.append(
            {
                "distance": distance,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "correct_bytes": counter["correct"],
                "false_bytes": counter["false"],
                "exact_rows": counter["exact_rows"],
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "verdict": verdict,
            }
        )
    distance_rows.sort(
        key=lambda row: (-int_value(row, "correct_bytes"), int_value(row, "false_bytes"), int_value(row, "distance"))
    )
    groups = build_groups(
        row_outputs,
        [
            ("bucket", "bucket_key"),
            ("payload_signature", "payload_signature"),
            ("value_histogram", "value_histogram_key"),
            ("signed_profile", "signed_profile_key"),
            ("source_profile_pool", "best_source_profile_pool"),
            ("verdict", "verdict"),
        ],
    )
    payload_groups, repeated_payload_rows, repeated_payload_bytes = repeated_row_stats(row_outputs, "payload_signature")
    value_groups, repeated_value_rows, repeated_value_bytes = repeated_row_stats(row_outputs, "value_histogram_key")
    signed_groups, repeated_signed_rows, repeated_signed_bytes = repeated_row_stats(row_outputs, "signed_profile_key")
    pair_overlap_rows = [row for row in row_outputs if float_value(row, "best_bucket_peer_ratio") >= 0.5]
    profile_ge50_rows = [row for row in row_outputs if float_value(row, "best_source_profile_ratio") >= 0.5]
    profile_ge75_rows = [row for row in row_outputs if float_value(row, "best_source_profile_ratio") >= 0.75]
    best_distance = distance_rows[0] if distance_rows else {}
    spatial_exact_rows = [row for row in row_outputs if int_value(row, "best_spatial_correct") == int_value(row, "length")]
    summary = {
        "scope": "total",
        "target_rows": len(row_outputs),
        "target_bytes": sum(int_value(row, "length") for row in row_outputs),
        "bucket_rows": len({row.get("bucket_key", "") for row in row_outputs}),
        "repeated_bucket_rows": len(repeated_buckets),
        "repeated_bucket_bytes": sum(int_value(row, "length") for row in row_outputs),
        "payload_signature_groups": payload_groups,
        "repeated_payload_signature_rows": repeated_payload_rows,
        "repeated_payload_signature_bytes": repeated_payload_bytes,
        "value_histogram_groups": value_groups,
        "repeated_value_histogram_rows": repeated_value_rows,
        "repeated_value_histogram_bytes": repeated_value_bytes,
        "signed_profile_groups": signed_groups,
        "repeated_signed_profile_rows": repeated_signed_rows,
        "repeated_signed_profile_bytes": repeated_signed_bytes,
        "pair_overlap_ge50_rows": len(pair_overlap_rows),
        "pair_overlap_ge50_bytes": sum(int_value(row, "length") for row in pair_overlap_rows),
        "source_profile_ge50_rows": len(profile_ge50_rows),
        "source_profile_ge50_bytes": sum(int_value(row, "length") for row in profile_ge50_rows),
        "source_profile_ge75_rows": len(profile_ge75_rows),
        "source_profile_ge75_bytes": sum(int_value(row, "length") for row in profile_ge75_rows),
        "external_best_exact_bytes": sum(int_value(row, "best_source_exact") for row in row_outputs),
        "external_best_prefix_bytes": sum(int_value(row, "best_source_prefix") for row in row_outputs),
        "spatial_best_distance": best_distance.get("distance", ""),
        "spatial_best_rows": best_distance.get("rows", 0),
        "spatial_best_bytes": best_distance.get("bytes", 0),
        "spatial_best_correct_bytes": best_distance.get("correct_bytes", 0),
        "spatial_best_false_bytes": best_distance.get("false_bytes", 0),
        "spatial_exact_copy_bytes": sum(int_value(row, "length") for row in spatial_exact_rows),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, row_outputs, groups, distance_rows


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
    distances: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "rows": rows, "groups": groups, "distances": distances},
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
table {{ border-collapse: collapse; width: 100%; min-width: 1600px; }}
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
  <div class="box"><div class="num">{summary['repeated_payload_signature_bytes']}</div><div class="muted">repeated payload bytes</div></div>
  <div class="box"><div class="num">{summary['pair_overlap_ge50_bytes']}</div><div class="muted">peer overlap >= 50%</div></div>
  <div class="box"><div class="num">{summary['source_profile_ge75_bytes']}</div><div class="muted">source profile >= 75%</div></div>
  <div class="box"><div class="num">{summary['spatial_exact_copy_bytes']}</div><div class="muted">spatial exact copy bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Distances</h2>{render_table(distances, DISTANCE_FIELDNAMES)}</div>
<script type="application/json" id="jump-mixed-payload-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe repeated .tex micro-token jump-mixed payloads.")
    parser.add_argument("--micro-targets", type=Path, default=DEFAULT_MICRO_TARGETS)
    parser.add_argument("--split-buckets", type=Path, default=DEFAULT_SPLIT_BUCKETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=700)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Jump-Mixed Payload Probe")
    args = parser.parse_args()

    summary, rows, groups, distances = build(
        read_csv(args.micro_targets),
        read_csv(args.split_buckets),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        max_distance=args.max_distance,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    write_csv(args.output / "distances.csv", DISTANCE_FIELDNAMES, distances)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, distances, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Repeated payload signature bytes: {summary['repeated_payload_signature_bytes']}")
    print(f"Pair overlap >=50 bytes: {summary['pair_overlap_ge50_bytes']}")
    print(f"Source profile >=75 bytes: {summary['source_profile_ge75_bytes']}")
    print(f"Spatial exact copy bytes: {summary['spatial_exact_copy_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
