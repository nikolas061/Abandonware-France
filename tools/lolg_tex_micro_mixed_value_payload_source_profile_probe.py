#!/usr/bin/env python3
"""Probe external source profiles for dominant mixed-value payloads."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_INPUT_ROWS = Path("output/tex_micro_mixed_value_dominant_control/rows.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_source_profile")

COMPRESSED_POOLS = ("segment_gap", "control_prefix", "fragment")
SOURCE_POOLS = (*COMPRESSED_POOLS, "decoded_replay")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "known_target_bytes",
    "source_pools",
    "best_exact_bytes",
    "best_prefix_bytes",
    "compressed_best_exact_bytes",
    "decoded_replay_best_rows",
    "decoded_replay_best_bytes",
    "decoded_replay_best_exact_bytes",
    "decoded_zero_bias_rows",
    "decoded_zero_bias_bytes",
    "profile_overlap_ge50_rows",
    "profile_overlap_ge50_bytes",
    "profile_overlap_ge75_rows",
    "profile_overlap_ge75_bytes",
    "positional_ge50_rows",
    "positional_ge50_bytes",
    "exact_profile_match_rows",
    "exact_profile_match_bytes",
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
    "known_target_bytes",
    "best_pool",
    "best_offset",
    "best_offset_delta",
    "best_transform",
    "best_parameter",
    "best_exact_bytes",
    "best_prefix_bytes",
    "best_source_zero_ratio",
    "best_source_known_bytes",
    "compressed_best_pool",
    "compressed_best_offset",
    "compressed_best_transform",
    "compressed_best_exact_bytes",
    "profile_best_pool",
    "profile_best_offset",
    "profile_overlap_exact",
    "profile_overlap_ratio",
    "profile_positional_exact",
    "profile_positional_ratio",
    "exact_profile_match",
    "verdict",
    "expected_head_hex",
    "best_source_head_hex",
    "best_output_head_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "rank",
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "exact_bytes",
    "prefix_bytes",
    "known_source_bytes",
    "decoded_zero_bias_rows",
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


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def fixture_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("archive", "")),
        str(row.get("pcx_name", "")),
        str(row.get("frontier_id", "")),
    )


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
        pools = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment_gap": read_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap"),
            "control_prefix": read_bytes(fixture.get("control_prefix_path", ""), local_issues, "control_prefix"),
            "fragment": read_bytes(fixture.get("fragment_path", ""), local_issues, "fragment"),
            "decoded_replay": read_bytes(replay.get("decoded_path", ""), local_issues, "decoded_replay"),
            "known_mask": read_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask"),
        }
        sources[key] = pools
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return sources, issues


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def common_prefix(left: bytes, right: bytes) -> int:
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        if left_value != right_value:
            return index
    return min(len(left), len(right))


def zero_ratio(data: bytes) -> str:
    return ratio(sum(1 for value in data if value == 0), len(data))


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


def profile_values(data: bytes) -> list[str]:
    return [signed_bucket(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]


def profile_overlap(wanted: list[str], candidate: list[str]) -> tuple[int, int]:
    wanted_counts = Counter(wanted)
    candidate_counts = Counter(candidate)
    return sum(min(wanted_counts[key], candidate_counts[key]) for key in wanted_counts), len(wanted)


def positional_score(wanted: list[str], candidate: list[str]) -> tuple[int, int]:
    total = min(len(wanted), len(candidate))
    return sum(1 for index in range(total) if wanted[index] == candidate[index]), total


def profile_key(values: list[str]) -> str:
    counts = Counter(values)
    order = ["0", "+s", "-s", "+m", "-m", "+j", "-j"]
    return ";".join(f"{label}:{counts[label]}" for label in order if counts[label])


def transforms(source: bytes, expected: bytes) -> list[tuple[str, str, bytes]]:
    rows = [
        ("identity", "", source),
        ("low7", "", bytes(value & 0x7F for value in source)),
        ("highbit_set", "", bytes(value | 0x80 for value in source)),
        ("bit_not", "", bytes(value ^ 0xFF for value in source)),
        ("nibble_swap", "", bytes(((value & 0x0F) << 4) | (value >> 4) for value in source)),
    ]
    if source and expected:
        xor_value = source[0] ^ expected[0]
        add_value = (expected[0] - source[0]) & 0xFF
        rows.extend(
            [
                ("xor_prefix", f"0x{xor_value:02x}", bytes(value ^ xor_value for value in source)),
                ("add_prefix", f"0x{add_value:02x}", bytes((value + add_value) & 0xFF for value in source)),
            ]
        )
    return rows


def iter_slices(data: bytes, length: int):
    if length <= 0 or len(data) < length:
        return
    for offset in range(len(data) - length + 1):
        yield offset, data[offset : offset + length]


def source_known_bytes(mask: bytes, offset: int, length: int) -> int:
    if offset < 0 or len(mask) < offset + length:
        return 0
    return sum(1 for value in mask[offset : offset + length] if value)


def target_known_bytes(mask: bytes, start: int, end: int) -> int:
    if start < 0 or len(mask) < end:
        return 0
    return sum(1 for value in mask[start:end] if value)


def score_exact_candidate(
    expected: bytes,
    pool_name: str,
    offset: int,
    source: bytes,
    transform: str,
    parameter: str,
    output: bytes,
    known_mask: bytes,
) -> dict[str, object]:
    return {
        "pool": pool_name,
        "offset": offset,
        "transform": transform,
        "parameter": parameter,
        "exact": exact_count(output, expected),
        "prefix": common_prefix(output, expected),
        "source_zero_ratio": zero_ratio(source),
        "source_known_bytes": source_known_bytes(known_mask, offset, len(source)) if pool_name == "decoded_replay" else 0,
        "source_head_hex": source[:16].hex(),
        "output_head_hex": output[:16].hex(),
    }


def better_exact(left: dict[str, object] | None, right: dict[str, object]) -> dict[str, object]:
    if left is None:
        return right
    left_score = (
        int(left["exact"]),
        int(left["prefix"]),
        1 if left.get("pool") != "decoded_replay" else 0,
        int(left.get("source_known_bytes", 0)),
    )
    right_score = (
        int(right["exact"]),
        int(right["prefix"]),
        1 if right.get("pool") != "decoded_replay" else 0,
        int(right.get("source_known_bytes", 0)),
    )
    return right if right_score > left_score else left


def best_exact_source(
    expected: bytes,
    pools: dict[str, bytes],
    known_mask: bytes,
    pool_names: tuple[str, ...],
) -> dict[str, object]:
    best: dict[str, object] | None = None
    for pool_name in pool_names:
        pool = pools.get(pool_name, b"")
        for offset, source in iter_slices(pool, len(expected)) or []:
            for transform, parameter, output in transforms(source, expected):
                candidate = score_exact_candidate(
                    expected,
                    pool_name,
                    offset,
                    source,
                    transform,
                    parameter,
                    output,
                    known_mask,
                )
                best = better_exact(best, candidate)
    return best or {
        "pool": "",
        "offset": "",
        "transform": "",
        "parameter": "",
        "exact": 0,
        "prefix": 0,
        "source_zero_ratio": "0.000000",
        "source_known_bytes": 0,
        "source_head_hex": "",
        "output_head_hex": "",
    }


def best_profile_source(expected: bytes, pools: dict[str, bytes]) -> dict[str, object]:
    wanted = profile_values(expected)
    wanted_key = profile_key(wanted)
    best: dict[str, object] | None = None
    for pool_name in COMPRESSED_POOLS:
        pool = pools.get(pool_name, b"")
        for offset, source in iter_slices(pool, len(expected)) or []:
            candidate_values = profile_values(source)
            overlap_exact, overlap_total = profile_overlap(wanted, candidate_values)
            positional_exact, positional_total = positional_score(wanted, candidate_values)
            current = {
                "pool": pool_name,
                "offset": offset,
                "overlap_exact": overlap_exact,
                "overlap_ratio": ratio(overlap_exact, overlap_total),
                "positional_exact": positional_exact,
                "positional_ratio": ratio(positional_exact, positional_total),
                "exact_profile_match": "1" if profile_key(candidate_values) == wanted_key else "0",
            }
            if best is None:
                best = current
                continue
            current_score = (
                float_value(current, "overlap_ratio"),
                float_value(current, "positional_ratio"),
                int_value(current, "overlap_exact"),
                int_value(current, "positional_exact"),
            )
            best_score = (
                float_value(best, "overlap_ratio"),
                float_value(best, "positional_ratio"),
                int_value(best, "overlap_exact"),
                int_value(best, "positional_exact"),
            )
            if current_score > best_score:
                best = current
    return best or {
        "pool": "",
        "offset": "",
        "overlap_exact": 0,
        "overlap_ratio": "0.000000",
        "positional_exact": 0,
        "positional_ratio": "0.000000",
        "exact_profile_match": "0",
    }


def is_decoded_zero_bias(row: dict[str, object]) -> bool:
    return (
        row.get("best_pool") == "decoded_replay"
        and row.get("best_transform") in {"xor_prefix", "add_prefix"}
        and float_value(row, "best_source_zero_ratio") >= 0.75
    )


def classify(row: dict[str, object]) -> str:
    if is_decoded_zero_bias(row):
        return "decoded_zero_bias_reject"
    if float_value(row, "profile_overlap_ratio") >= 0.75:
        return "source_profile_review"
    if int_value(row, "compressed_best_exact_bytes") >= max(8, int_value(row, "length") // 4):
        return "compressed_exact_review"
    if float_value(row, "profile_overlap_ratio") >= 0.50:
        return "weak_profile_hint"
    return "external_source_reject"


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    sources_by_fixture, fixture_issues = load_sources(fixture_rows, replay_rows)
    output_rows: list[dict[str, object]] = []
    for input_row in input_rows:
        issues = [issue for issue in input_row.get("issues", "").split(";") if issue]
        pools = sources_by_fixture.get(fixture_key(input_row), {})
        expected_all = pools.get("expected", b"")
        known_mask = pools.get("known_mask", b"")
        start = int_value(input_row, "start")
        end = int_value(input_row, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_payload")
        if input_row.get("length") and int_value(input_row, "length") != len(expected):
            issues.append(f"length_mismatch:{input_row.get('length')}:{len(expected)}")
        known_target = target_known_bytes(known_mask, start, end)
        best = best_exact_source(expected, pools, known_mask, SOURCE_POOLS)
        compressed_best = best_exact_source(expected, pools, known_mask, COMPRESSED_POOLS)
        profile_best = best_profile_source(expected, pools)
        row = {
            "rank": input_row.get("rank", ""),
            "archive": input_row.get("archive", ""),
            "pcx_name": input_row.get("pcx_name", ""),
            "frontier_id": input_row.get("frontier_id", ""),
            "span_index": input_row.get("span_index", ""),
            "op_index": input_row.get("op_index", ""),
            "length": str(len(expected)),
            "start": input_row.get("start", ""),
            "end": input_row.get("end", ""),
            "control_ref_mod64": input_row.get("control_ref_mod64", ""),
            "best_signal_key": input_row.get("best_signal_key", ""),
            "known_target_bytes": known_target,
            "best_pool": best.get("pool", ""),
            "best_offset": best.get("offset", ""),
            "best_offset_delta": int(best.get("offset") or 0) - start if best.get("offset") != "" else "",
            "best_transform": best.get("transform", ""),
            "best_parameter": best.get("parameter", ""),
            "best_exact_bytes": best.get("exact", 0),
            "best_prefix_bytes": best.get("prefix", 0),
            "best_source_zero_ratio": best.get("source_zero_ratio", "0.000000"),
            "best_source_known_bytes": best.get("source_known_bytes", 0),
            "compressed_best_pool": compressed_best.get("pool", ""),
            "compressed_best_offset": compressed_best.get("offset", ""),
            "compressed_best_transform": compressed_best.get("transform", ""),
            "compressed_best_exact_bytes": compressed_best.get("exact", 0),
            "profile_best_pool": profile_best.get("pool", ""),
            "profile_best_offset": profile_best.get("offset", ""),
            "profile_overlap_exact": profile_best.get("overlap_exact", 0),
            "profile_overlap_ratio": profile_best.get("overlap_ratio", "0.000000"),
            "profile_positional_exact": profile_best.get("positional_exact", 0),
            "profile_positional_ratio": profile_best.get("positional_ratio", "0.000000"),
            "exact_profile_match": profile_best.get("exact_profile_match", "0"),
            "verdict": "",
            "expected_head_hex": expected[:16].hex(),
            "best_source_head_hex": best.get("source_head_hex", ""),
            "best_output_head_hex": best.get("output_head_hex", ""),
            "issues": ";".join(issues),
        }
        row["verdict"] = classify(row)
        output_rows.append(row)

    groups = build_groups(output_rows)
    summary = build_summary(output_rows, fixture_issues)
    return summary, output_rows, groups


def build_groups(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    group_specs = [
        ("best_pool", lambda row: str(row.get("best_pool", ""))),
        ("best_transform", lambda row: str(row.get("best_transform", ""))),
        ("profile_pool", lambda row: str(row.get("profile_best_pool", ""))),
        ("verdict", lambda row: str(row.get("verdict", ""))),
    ]
    groups: list[dict[str, object]] = []
    for kind, key_func in group_specs:
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[key_func(row)].append(row)
        for key, group in grouped.items():
            sample = group[0]
            groups.append(
                {
                    "rank": 0,
                    "group_kind": kind,
                    "group_key": key,
                    "rows": len(group),
                    "bytes": sum(int_value(row, "length") for row in group),
                    "exact_bytes": sum(int_value(row, "best_exact_bytes") for row in group),
                    "prefix_bytes": sum(int_value(row, "best_prefix_bytes") for row in group),
                    "known_source_bytes": sum(int_value(row, "best_source_known_bytes") for row in group),
                    "decoded_zero_bias_rows": sum(1 for row in group if is_decoded_zero_bias(row)),
                    "sample_pcx": sample.get("pcx_name", ""),
                    "sample_frontier_id": sample.get("frontier_id", ""),
                    "verdict": "repeated_group" if len(group) > 1 else "singleton_group",
                }
            )
    groups.sort(key=lambda row: (str(row["group_kind"]), -int_value(row, "bytes"), str(row["group_key"])))
    for index, row in enumerate(groups, start=1):
        row["rank"] = index
    return groups


def build_summary(rows: list[dict[str, object]], fixture_issues: list[str]) -> dict[str, object]:
    decoded_best = [row for row in rows if row.get("best_pool") == "decoded_replay"]
    decoded_zero_bias = [row for row in rows if is_decoded_zero_bias(row)]
    overlap_ge50 = [row for row in rows if float_value(row, "profile_overlap_ratio") >= 0.50]
    overlap_ge75 = [row for row in rows if float_value(row, "profile_overlap_ratio") >= 0.75]
    positional_ge50 = [row for row in rows if float_value(row, "profile_positional_ratio") >= 0.50]
    exact_profile = [row for row in rows if row.get("exact_profile_match") == "1"]
    return {
        "scope": "total",
        "target_rows": len(rows),
        "target_bytes": sum(int_value(row, "length") for row in rows),
        "known_target_bytes": sum(int_value(row, "known_target_bytes") for row in rows),
        "source_pools": len(SOURCE_POOLS),
        "best_exact_bytes": sum(int_value(row, "best_exact_bytes") for row in rows),
        "best_prefix_bytes": sum(int_value(row, "best_prefix_bytes") for row in rows),
        "compressed_best_exact_bytes": sum(int_value(row, "compressed_best_exact_bytes") for row in rows),
        "decoded_replay_best_rows": len(decoded_best),
        "decoded_replay_best_bytes": sum(int_value(row, "length") for row in decoded_best),
        "decoded_replay_best_exact_bytes": sum(int_value(row, "best_exact_bytes") for row in decoded_best),
        "decoded_zero_bias_rows": len(decoded_zero_bias),
        "decoded_zero_bias_bytes": sum(int_value(row, "length") for row in decoded_zero_bias),
        "profile_overlap_ge50_rows": len(overlap_ge50),
        "profile_overlap_ge50_bytes": sum(int_value(row, "length") for row in overlap_ge50),
        "profile_overlap_ge75_rows": len(overlap_ge75),
        "profile_overlap_ge75_bytes": sum(int_value(row, "length") for row in overlap_ge75),
        "positional_ge50_rows": len(positional_ge50),
        "positional_ge50_bytes": sum(int_value(row, "length") for row in positional_ge50),
        "exact_profile_match_rows": len(exact_profile),
        "exact_profile_match_bytes": sum(int_value(row, "length") for row in exact_profile),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in rows if row.get("issues")) + len(fixture_issues),
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
table {{ border-collapse: collapse; width: 100%; min-width: 1550px; }}
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
  <div class="box"><div class="num">{summary['compressed_best_exact_bytes']}</div><div class="muted">compressed exact bytes</div></div>
  <div class="box"><div class="num">{summary['decoded_zero_bias_bytes']}</div><div class="muted">decoded zero-bias bytes</div></div>
  <div class="box"><div class="num">{summary['profile_overlap_ge75_bytes']}</div><div class="muted">profile overlap >=75 bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="payload-source-profile-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe external source profiles for mixed-value payloads.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Payload Source Profile")
    args = parser.parse_args()

    summary, rows, groups = build(read_csv(args.input_rows), read_csv(args.fixtures), read_csv(args.replay_fixtures))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.title))

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Compressed best exact bytes: {summary['compressed_best_exact_bytes']}")
    print(f"Decoded zero-bias bytes: {summary['decoded_zero_bias_bytes']}")
    print(f"Profile overlap >=75 bytes: {summary['profile_overlap_ge75_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
