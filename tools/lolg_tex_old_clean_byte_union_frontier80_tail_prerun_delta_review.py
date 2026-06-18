#!/usr/bin/env python3
"""Review repeated pre-run deltas around the final frontier 80 a3/a3 tail."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/slots.csv"
)
DEFAULT_BASE_FIXTURES = Path("output/tex_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/fixtures.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_prerun_delta_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_key",
    "target_offsets",
    "target_expected_hex",
    "target_run_value",
    "target_run_start",
    "target_run_end",
    "target_prerun_delta",
    "candidate_rows",
    "known_pair_rows",
    "known_pair_exact_rows",
    "known_pair_false_rows",
    "same_delta_rows",
    "same_delta_non_target_rows",
    "same_delta_known_rows",
    "same_delta_known_exact_rows",
    "same_delta_known_false_rows",
    "same_delta_target_rows",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "review_verdict",
    "next_probe",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "pair_offset",
    "pair_hex",
    "known_pair_bits",
    "decoded_pair_hex",
    "run_start",
    "run_end",
    "run_length",
    "run_value",
    "delta",
    "delta_hex",
    "left_context_hex",
    "right_context_hex",
    "is_target",
    "verdict",
    "issues",
]

TARGET_FIELDNAMES = [
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "target_offset",
    "source_offset",
    "relative_offset",
    "expected_byte",
    "predicted_byte",
    "root_target_byte",
    "root_target_low",
    "source_slot_rank",
    "source_slot_frontier_id",
    "source_slot_start",
    "source_dependency_edge",
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc.__class__.__name__}")
        return b""


def byte_runs(data: bytes) -> list[tuple[int, int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int, int]] = []
    start = 0
    current = data[0]
    for index, value in enumerate(data[1:], start=1):
        if value == current:
            continue
        runs.append((start, index, current))
        start = index
        current = value
    runs.append((start, len(data), current))
    return runs


def mask_bits(mask: bytes, start: int, end: int) -> str:
    return "".join("1" if 0 <= offset < len(mask) and mask[offset] else "0" for offset in range(start, end))


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def unknown_source_rows(slot_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in slot_rows
        if row.get("source_location") == "outside_highsafe"
        and row.get("source_availability") == "unknown_source"
        and row.get("source_expected_byte")
    ]


def target_group(rows: list[dict[str, str]]) -> tuple[tuple[str, str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(fixture_key(row), []).append(row)
    if not groups:
        return ("", "", ""), []
    return max(groups.items(), key=lambda item: len(item[1]))


def compact_offsets(rows: list[dict[str, str]]) -> str:
    offsets = sorted({int_value(row, "source_actual_offset", -1) for row in rows})
    offsets = [offset for offset in offsets if offset >= 0]
    if not offsets:
        return ""
    ranges: list[str] = []
    start = previous = offsets[0]
    for offset in offsets[1:]:
        if offset == previous + 1:
            previous = offset
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = offset
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def find_target_run(expected: bytes, pair_start: int, pair_len: int) -> tuple[int, int, int]:
    run_start = pair_start + pair_len
    if run_start >= len(expected):
        return -1, -1, -1
    value = expected[run_start]
    run_end = run_start
    while run_end < len(expected) and expected[run_end] == value:
        run_end += 1
    return run_start, run_end, value


def candidate_verdict(is_target: bool, pair_known: bool, pair_exact: bool, same_delta: bool) -> str:
    if is_target:
        return "target_prerun_delta"
    if same_delta and pair_known and pair_exact:
        return "known_same_delta_support"
    if same_delta and pair_known and not pair_exact:
        return "known_same_delta_false"
    if same_delta:
        return "same_delta_without_known_pair"
    if pair_known and pair_exact:
        return "known_other_delta"
    if pair_known:
        return "known_other_delta_false"
    return "other_delta_without_known_pair"


def scan_candidates(
    *,
    manifest_rows: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    target_pair_start: int,
    target_pair_len: int,
    min_run_length: int,
) -> tuple[list[dict[str, str]], dict[str, str], list[str]]:
    manifests = {fixture_key(row): row for row in manifest_rows}
    target_info: dict[str, str] = {}
    issues: list[str] = []
    target_expected = load_bytes(
        manifests.get(target_key_value, {}).get("expected_gap_path", ""),
        issues,
        "target_expected",
    )
    target_run_start, target_run_end, target_run_value = find_target_run(
        target_expected,
        target_pair_start,
        target_pair_len,
    )
    target_pair = target_expected[target_pair_start : target_pair_start + target_pair_len]
    target_delta = ""
    if target_pair_len and len(set(target_pair)) == 1 and target_run_value >= 0:
        target_delta = str((target_pair[0] - target_run_value) & 0xFF)
    target_info.update(
        {
            "target_expected_hex": target_pair.hex(),
            "target_run_value": f"{target_run_value:02x}" if target_run_value >= 0 else "",
            "target_run_start": str(target_run_start) if target_run_start >= 0 else "",
            "target_run_end": str(target_run_end) if target_run_end >= 0 else "",
            "target_prerun_delta": target_delta,
        }
    )

    candidates: list[dict[str, str]] = []
    for base_row in base_rows:
        key = fixture_key(base_row)
        manifest = manifests.get(key, {})
        if manifest.get("rule_type") != "compact_control_stream":
            continue
        local_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        decoded = load_bytes(base_row.get("decoded_path", ""), local_issues, "decoded")
        known_mask = load_bytes(base_row.get("known_mask_path", ""), local_issues, "known_mask")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
        if not expected or not decoded or not known_mask:
            continue
        for run_start, run_end, run_value in byte_runs(expected):
            run_length = run_end - run_start
            if run_length < min_run_length or run_start < target_pair_len:
                continue
            pair_start = run_start - target_pair_len
            pair = expected[pair_start:run_start]
            if len(pair) != target_pair_len or len(set(pair)) != 1:
                continue
            delta = (pair[0] - run_value) & 0xFF
            pair_known = all(offset < len(known_mask) and known_mask[offset] for offset in range(pair_start, run_start))
            pair_exact = all(
                offset < len(decoded) and decoded[offset] == expected[offset]
                for offset in range(pair_start, run_start)
            )
            is_target = key == target_key_value and pair_start == target_pair_start
            same_delta = target_delta != "" and str(delta) == target_delta
            candidates.append(
                {
                    "rank": str(len(candidates) + 1),
                    "archive": key[0],
                    "archive_tag": base_row.get("archive_tag", manifest.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "pair_offset": str(pair_start),
                    "pair_hex": pair.hex(),
                    "known_pair_bits": mask_bits(known_mask, pair_start, run_start),
                    "decoded_pair_hex": decoded[pair_start:run_start].hex(),
                    "run_start": str(run_start),
                    "run_end": str(run_end),
                    "run_length": str(run_length),
                    "run_value": f"{run_value:02x}",
                    "delta": str(delta),
                    "delta_hex": f"{delta:02x}",
                    "left_context_hex": expected[max(0, pair_start - 8) : pair_start].hex(),
                    "right_context_hex": expected[run_start : min(len(expected), run_start + 8)].hex(),
                    "is_target": "1" if is_target else "0",
                    "verdict": candidate_verdict(is_target, pair_known, pair_exact, same_delta),
                    "issues": "",
                }
            )

    candidates.sort(
        key=lambda row: (
            row.get("is_target") != "1",
            row.get("verdict") != "known_same_delta_support",
            row.get("delta") != target_delta,
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "pair_offset"),
        )
    )
    for rank, row in enumerate(candidates, start=1):
        row["rank"] = str(rank)
    return candidates, target_info, issues


def build_target_rows(
    target_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    has_known_support = any(row.get("verdict") == "known_same_delta_support" for row in candidates)
    output: list[dict[str, str]] = []
    for row in sorted(target_rows, key=lambda item: int_value(item, "source_actual_offset")):
        source_offset = row.get("source_actual_offset", "")
        issues = [] if has_known_support else ["missing_known_same_delta_support"]
        output.append(
            {
                "rank": str(len(output) + 1),
                "slot_rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "op_index": row.get("op_index", ""),
                "target_offset": source_offset,
                "source_offset": source_offset,
                "relative_offset": row.get("relative_offset", ""),
                "expected_byte": row.get("source_expected_byte", "").lower(),
                "predicted_byte": row.get("source_expected_byte", "").lower(),
                "root_target_byte": row.get("target_byte", ""),
                "root_target_low": row.get("target_low", ""),
                "source_slot_rank": row.get("source_slot_rank", ""),
                "source_slot_frontier_id": row.get("source_slot_frontier_id", ""),
                "source_slot_start": row.get("source_slot_start", ""),
                "source_dependency_edge": source_dependency_edge(row),
                "best_formula": "following_run_value+target_prerun_delta",
                "best_guard_family": "compact_control_prerun_pair_delta",
                "best_guard_key": "delta=2 before a1 run",
                "promotion_ready": "1" if not issues else "0",
                "issues": ";".join(issues),
            }
        )
    return output


def build_summary(
    *,
    candidates: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    target_offsets: str,
    target_info: dict[str, str],
    issue_rows: int,
) -> dict[str, str]:
    target_delta = target_info.get("target_prerun_delta", "")
    same_delta = [row for row in candidates if row.get("delta") == target_delta]
    same_delta_known = [row for row in same_delta if "1" in row.get("known_pair_bits", "")]
    same_delta_known_exact = [row for row in same_delta if row.get("verdict") == "known_same_delta_support"]
    same_delta_known_false = [row for row in same_delta if row.get("verdict") == "known_same_delta_false"]
    ready = sum(1 for row in target_rows if row.get("promotion_ready") == "1")
    if ready:
        verdict = "frontier80_tail_prerun_delta_support_ready"
        next_probe = "promote frontier80 pre-run delta pair offsets 16-17"
    elif same_delta and not same_delta_known_exact:
        verdict = "frontier80_tail_prerun_delta_target_only_no_known_support"
        next_probe = "derive non-oracle compact-control token for frontier80 pre-run delta +2"
    else:
        verdict = "frontier80_tail_prerun_delta_missing_candidate"
        next_probe = "inspect compact-control tail segmentation around frontier80 offsets 16-17"
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_prerun_delta_review",
        "target_key": "|".join(target_key_value),
        "target_offsets": target_offsets,
        "target_expected_hex": target_info.get("target_expected_hex", ""),
        "target_run_value": target_info.get("target_run_value", ""),
        "target_run_start": target_info.get("target_run_start", ""),
        "target_run_end": target_info.get("target_run_end", ""),
        "target_prerun_delta": target_delta,
        "candidate_rows": str(len(candidates)),
        "known_pair_rows": str(sum(1 for row in candidates if "1" in row.get("known_pair_bits", ""))),
        "known_pair_exact_rows": str(sum(1 for row in candidates if row.get("verdict") in {"known_same_delta_support", "known_other_delta"})),
        "known_pair_false_rows": str(sum(1 for row in candidates if row.get("verdict") in {"known_same_delta_false", "known_other_delta_false"})),
        "same_delta_rows": str(len(same_delta)),
        "same_delta_non_target_rows": str(sum(1 for row in same_delta if row.get("is_target") != "1")),
        "same_delta_known_rows": str(len(same_delta_known)),
        "same_delta_known_exact_rows": str(len(same_delta_known_exact)),
        "same_delta_known_false_rows": str(len(same_delta_known_false)),
        "same_delta_target_rows": str(sum(1 for row in same_delta if row.get("is_target") == "1")),
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(ready),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "issue_rows": str(issue_rows),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #202529; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: white; border: 1px solid #d5dbe0; padding: 10px; }}
    .label {{ color: #68737d; font-size: 12px; }}
    .value {{ font-size: 21px; font-weight: 750; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #d5dbe0; padding: 6px 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    th {{ background: #e9edf0; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>{links}</p>
  <div class="stats">
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
    <div class="stat"><div class="label">Target delta</div><div class="value">{html.escape(summary['target_prerun_delta'])}</div></div>
    <div class="stat"><div class="label">Same delta known</div><div class="value">{html.escape(summary['same_delta_known_exact_rows'])}/{html.escape(summary['same_delta_rows'])}</div></div>
    <div class="stat"><div class="label">Promotion ready</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(targets, TARGET_FIELDNAMES)}
  <h2>Candidates</h2>
  {render_table(candidates, CANDIDATE_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--min-run-length", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Pre-run Delta Review")
    args = parser.parse_args()

    slot_rows = read_csv(args.slots)
    unknown_rows = unknown_source_rows(slot_rows)
    target_key_value, target_members = target_group(unknown_rows)
    target_offsets = sorted({int_value(row, "source_actual_offset", -1) for row in target_members})
    target_offsets = [offset for offset in target_offsets if offset >= 0]
    target_pair_start = min(target_offsets) if target_offsets else -1
    target_pair_len = len(target_offsets)

    candidates, target_info, issues = scan_candidates(
        manifest_rows=read_csv(args.manifest),
        base_rows=read_csv(args.base_fixtures),
        target_key_value=target_key_value,
        target_pair_start=target_pair_start,
        target_pair_len=target_pair_len,
        min_run_length=args.min_run_length,
    )
    targets = build_target_rows(target_members, candidates)
    summary = build_summary(
        candidates=candidates,
        target_rows=targets,
        target_key_value=target_key_value,
        target_offsets=compact_offsets(target_members),
        target_info=target_info,
        issue_rows=len(issues),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, targets, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Frontier80 pre-run delta review: "
        f"verdict={summary['review_verdict']} "
        f"target_delta={summary['target_prerun_delta']} "
        f"same_delta_known={summary['same_delta_known_exact_rows']}/{summary['same_delta_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
