#!/usr/bin/env python3
"""Review support for the final frontier 80 a3/a3 source dependency."""

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
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_source_support_review")
DEFAULT_OLD_ROOT = Path("/media/niko/niko/Abandonware-France/Lands-of-Lore-II")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slot_rows",
    "target_unknown_rows",
    "target_groups",
    "target_key",
    "target_offsets",
    "target_expected_hex",
    "target_known_mask_bits",
    "exact_context_rows",
    "exact_context_known_non_target_rows",
    "pair_rows",
    "pair_known_rows",
    "pair_right_context_rows",
    "pair_right_context_known_rows",
    "single_a3_rows",
    "single_a3_known_rows",
    "old_media_fixture_csvs",
    "old_media_tex_output_dirs",
    "support_rows",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "review_verdict",
    "next_probe",
    "issue_rows",
]

SUPPORT_FIELDNAMES = [
    "rank",
    "kind",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "offset",
    "length",
    "expected_hex",
    "known_pair_bits",
    "known_context_bits",
    "left_context_hex",
    "right_context_hex",
    "is_target",
    "support_verdict",
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

OLD_MEDIA_FIELDNAMES = [
    "rank",
    "root",
    "fixture_csvs",
    "tex_output_dirs",
    "l4_hj_mix_files",
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


def byte_text(data: bytes, offset: int) -> str:
    if 0 <= offset < len(data):
        return f"{data[offset]:02x}"
    return ""


def mask_bits(mask: bytes, start: int, end: int) -> str:
    return "".join("1" if 0 <= index < len(mask) and mask[index] else "0" for index in range(start, end))


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


def target_group(rows: list[dict[str, str]]) -> tuple[tuple[str, str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(fixture_key(row), []).append(row)
    if not groups:
        return ("", "", ""), []
    return max(groups.items(), key=lambda item: len(item[1]))


def support_verdict(*, is_target: bool, pair_known: bool, context_exact: bool, right_exact: bool) -> str:
    if is_target:
        return "target_unknown_pair"
    if context_exact and pair_known:
        return "known_exact_context_support"
    if right_exact and pair_known:
        return "known_pair_right_context_support"
    if pair_known:
        return "known_pair_different_context"
    if right_exact:
        return "target_context_without_known_pair"
    return "pair_without_known_support"


def scan_support(
    *,
    base_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    target_key: tuple[str, str, str],
    target_offsets: list[int],
    before: int,
    after: int,
) -> tuple[list[dict[str, str]], dict[str, int], list[str]]:
    issues: list[str] = []
    manifests = {fixture_key(row): row for row in manifest_rows}
    bases = {fixture_key(row): row for row in base_rows}
    target_manifest = manifests.get(target_key, {})
    target_base = bases.get(target_key, {})
    target_expected = load_bytes(target_manifest.get("expected_gap_path", ""), issues, "target_expected")
    target_mask = load_bytes(target_base.get("known_mask_path", ""), issues, "target_known_mask")
    if not target_offsets or not target_expected:
        return [], {}, issues

    target_start = min(target_offsets)
    target_end = max(target_offsets) + 1
    pair = target_expected[target_start:target_end]
    context_start = max(0, target_start - before)
    context_end = min(len(target_expected), target_end + after)
    context = target_expected[context_start:context_end]
    context_left_len = target_start - context_start
    target_left = target_expected[max(0, target_start - before) : target_start]
    target_right = target_expected[target_end : min(len(target_expected), target_end + after)]

    support_rows: list[dict[str, str]] = []
    stats = {
        "exact_context_rows": 0,
        "exact_context_known_non_target_rows": 0,
        "pair_rows": 0,
        "pair_known_rows": 0,
        "pair_right_context_rows": 0,
        "pair_right_context_known_rows": 0,
        "single_a3_rows": 0,
        "single_a3_known_rows": 0,
    }

    for base_row in base_rows:
        key = fixture_key(base_row)
        manifest = manifests.get(key, {})
        local_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        known_mask = load_bytes(base_row.get("known_mask_path", ""), local_issues, "known_mask")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
        if not expected or not known_mask:
            continue

        for offset, value in enumerate(expected):
            if value == 0xA3:
                stats["single_a3_rows"] += 1
                if offset < len(known_mask) and known_mask[offset]:
                    stats["single_a3_known_rows"] += 1

        search = 0
        while pair:
            offset = expected.find(pair, search)
            if offset < 0:
                break
            end = offset + len(pair)
            is_target = key == target_key and offset == target_start
            pair_known = all(index < len(known_mask) and known_mask[index] for index in range(offset, end))
            right = expected[end : min(len(expected), end + len(target_right))]
            left = expected[max(0, offset - len(target_left)) : offset]
            right_exact = right == target_right
            aligned_context_start = offset - context_left_len
            context_exact = (
                aligned_context_start >= 0
                and aligned_context_start + len(context) <= len(expected)
                and expected[aligned_context_start : aligned_context_start + len(context)] == context
            )
            if context_exact:
                stats["exact_context_rows"] += 1
                if pair_known and not is_target:
                    stats["exact_context_known_non_target_rows"] += 1
            stats["pair_rows"] += 1
            if pair_known:
                stats["pair_known_rows"] += 1
            if right_exact:
                stats["pair_right_context_rows"] += 1
                if pair_known:
                    stats["pair_right_context_known_rows"] += 1

            support_rows.append(
                {
                    "rank": str(len(support_rows) + 1),
                    "kind": "pair",
                    "archive": key[0],
                    "archive_tag": base_row.get("archive_tag", manifest.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "offset": str(offset),
                    "length": str(len(pair)),
                    "expected_hex": expected[offset:end].hex(),
                    "known_pair_bits": mask_bits(known_mask, offset, end),
                    "known_context_bits": mask_bits(
                        known_mask,
                        max(0, offset - len(target_left)),
                        min(len(expected), end + len(target_right)),
                    ),
                    "left_context_hex": left.hex(),
                    "right_context_hex": right.hex(),
                    "is_target": "1" if is_target else "0",
                    "support_verdict": support_verdict(
                        is_target=is_target,
                        pair_known=pair_known,
                        context_exact=context_exact,
                        right_exact=right_exact,
                    ),
                    "issues": "",
                }
            )
            search = offset + 1

    support_rows.sort(
        key=lambda row: (
            row.get("support_verdict") != "known_exact_context_support",
            row.get("support_verdict") != "known_pair_right_context_support",
            row.get("is_target") != "1",
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "offset"),
        )
    )
    for rank, row in enumerate(support_rows, start=1):
        row["rank"] = str(rank)
    return support_rows, stats, issues


def build_target_rows(
    *,
    target_rows: list[dict[str, str]],
    support_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    has_exact_known_support = any(row.get("support_verdict") == "known_exact_context_support" for row in support_rows)
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in sorted(target_rows, key=lambda item: int_value(item, "source_actual_offset")):
        source_offset = row.get("source_actual_offset", "")
        key = (*fixture_key(row), source_offset)
        if key in seen:
            continue
        seen.add(key)
        issues = [] if has_exact_known_support else ["missing_known_exact_context_support"]
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
                "best_formula": "frontier80_tail_exact_context",
                "best_guard_family": "expected_pair+left_context+right_context",
                "best_guard_key": "exact_context_support",
                "promotion_ready": "1" if not issues else "0",
                "issues": ";".join(issues),
            }
        )
    return output


def old_media_rows(roots: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root in roots:
        issues: list[str] = []
        fixture_csvs = 0
        tex_output_dirs = 0
        l4_hj_mix_files = 0
        if not root.exists():
            issues.append("root_missing")
        else:
            fixture_csvs = sum(1 for _ in root.glob("**/fixtures.csv"))
            tex_output_dirs = sum(1 for path in root.glob("**/tex_*") if path.is_dir())
            l4_hj_mix_files = sum(1 for path in root.glob("**/L4_HJ.MIX") if path.is_file())
        rows.append(
            {
                "rank": str(len(rows) + 1),
                "root": root.as_posix(),
                "fixture_csvs": str(fixture_csvs),
                "tex_output_dirs": str(tex_output_dirs),
                "l4_hj_mix_files": str(l4_hj_mix_files),
                "issues": ";".join(issues),
            }
        )
    return rows


def build_summary(
    *,
    slot_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    target_offsets: list[int],
    target_expected_hex: str,
    target_mask_bits: str,
    support_rows: list[dict[str, str]],
    stats: dict[str, int],
    promotion_rows: list[dict[str, str]],
    old_rows: list[dict[str, str]],
    issue_rows: int,
) -> dict[str, str]:
    ready = sum(1 for row in promotion_rows if row.get("promotion_ready") == "1")
    has_exact_known_support = stats.get("exact_context_known_non_target_rows", 0) > 0
    if ready:
        verdict = "frontier80_tail_known_context_support_ready"
        next_probe = "promote frontier80 source offsets 16-17"
    elif target_rows and not has_exact_known_support:
        verdict = "frontier80_tail_target_only_no_known_support"
        next_probe = "derive opcode producer for frontier80 compact-control tail offsets 16-17"
    else:
        verdict = "frontier80_tail_missing_target"
        next_probe = "rebuild source dependency residual before frontier80 tail review"
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_source_support_review",
        "slot_rows": str(len(slot_rows)),
        "target_unknown_rows": str(len(target_rows)),
        "target_groups": "1" if target_rows else "0",
        "target_key": "|".join(target_key_value),
        "target_offsets": compact_offsets(target_rows),
        "target_expected_hex": target_expected_hex,
        "target_known_mask_bits": target_mask_bits,
        "exact_context_rows": str(stats.get("exact_context_rows", 0)),
        "exact_context_known_non_target_rows": str(stats.get("exact_context_known_non_target_rows", 0)),
        "pair_rows": str(stats.get("pair_rows", 0)),
        "pair_known_rows": str(stats.get("pair_known_rows", 0)),
        "pair_right_context_rows": str(stats.get("pair_right_context_rows", 0)),
        "pair_right_context_known_rows": str(stats.get("pair_right_context_known_rows", 0)),
        "single_a3_rows": str(stats.get("single_a3_rows", 0)),
        "single_a3_known_rows": str(stats.get("single_a3_known_rows", 0)),
        "old_media_fixture_csvs": str(sum(int_value(row, "fixture_csvs") for row in old_rows)),
        "old_media_tex_output_dirs": str(sum(int_value(row, "tex_output_dirs") for row in old_rows)),
        "support_rows": str(len(support_rows)),
        "promotion_candidate_bytes": str(len(promotion_rows)),
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
    *,
    summary: dict[str, str],
    support_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    old_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "support": support_rows, "targets": target_rows, "old_media": old_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("support.csv", output_dir / "support.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("old_media.csv", output_dir / "old_media.csv"),
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
    <div class="stat"><div class="label">Targets</div><div class="value">{html.escape(summary['target_unknown_rows'])}</div></div>
    <div class="stat"><div class="label">Pair known</div><div class="value">{html.escape(summary['pair_known_rows'])}/{html.escape(summary['pair_rows'])}</div></div>
    <div class="stat"><div class="label">Exact known support</div><div class="value">{html.escape(summary['exact_context_known_non_target_rows'])}</div></div>
    <div class="stat"><div class="label">Promotion ready</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(target_rows, TARGET_FIELDNAMES)}
  <h2>Support</h2>
  {render_table(support_rows, SUPPORT_FIELDNAMES)}
  <h2>Old Media</h2>
  {render_table(old_rows, OLD_MEDIA_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--old-root", type=Path, action="append", default=None)
    parser.add_argument("--context-before", type=int, default=16)
    parser.add_argument("--context-after", type=int, default=8)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Source Support Review")
    args = parser.parse_args()

    slot_rows = read_csv(args.slots)
    base_rows = read_csv(args.base_fixtures)
    manifest_rows = read_csv(args.manifest)
    unknown_rows = unknown_source_rows(slot_rows)
    target_key_value, target_members = target_group(unknown_rows)
    target_offsets = sorted({int_value(row, "source_actual_offset", -1) for row in target_members})
    target_offsets = [offset for offset in target_offsets if offset >= 0]

    issues: list[str] = []
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    base_by_key = {fixture_key(row): row for row in base_rows}
    target_expected = load_bytes(manifest_by_key.get(target_key_value, {}).get("expected_gap_path", ""), issues, "target_expected")
    target_mask = load_bytes(base_by_key.get(target_key_value, {}).get("known_mask_path", ""), issues, "target_known_mask")
    target_expected_hex = "".join(byte_text(target_expected, offset) for offset in target_offsets)
    target_mask_bits = "".join(mask_bits(target_mask, offset, offset + 1) for offset in target_offsets)

    support_rows, stats, support_issues = scan_support(
        base_rows=base_rows,
        manifest_rows=manifest_rows,
        target_key=target_key_value,
        target_offsets=target_offsets,
        before=args.context_before,
        after=args.context_after,
    )
    issues.extend(support_issues)
    promotion_rows = build_target_rows(target_rows=target_members, support_rows=support_rows)
    old_rows = old_media_rows(args.old_root if args.old_root else [DEFAULT_OLD_ROOT])
    issue_rows = len(issues)

    summary = build_summary(
        slot_rows=slot_rows,
        target_rows=target_members,
        target_key_value=target_key_value,
        target_offsets=target_offsets,
        target_expected_hex=target_expected_hex,
        target_mask_bits=target_mask_bits,
        support_rows=support_rows,
        stats=stats,
        promotion_rows=promotion_rows,
        old_rows=old_rows,
        issue_rows=issue_rows,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "support.csv", SUPPORT_FIELDNAMES, support_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, promotion_rows)
    write_csv(args.output / "old_media.csv", OLD_MEDIA_FIELDNAMES, old_rows)
    (args.output / "index.html").write_text(
        build_html(
            summary=summary,
            support_rows=support_rows,
            target_rows=promotion_rows,
            old_rows=old_rows,
            output_dir=args.output,
            title=args.title,
        ),
        encoding="utf-8",
    )

    print(
        "Frontier80 tail support review: "
        f"verdict={summary['review_verdict']} "
        f"targets={summary['target_unknown_rows']} "
        f"pair_known={summary['pair_known_rows']}/{summary['pair_rows']} "
        f"exact_known={summary['exact_context_known_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
