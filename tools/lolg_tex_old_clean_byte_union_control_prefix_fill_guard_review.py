#!/usr/bin/env python3
"""Review control-prefix fill runs after post-union terminal source-byte promotion."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_control_prefix_fill_guard_review")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_BASE_FIXTURES = Path("output/tex_old_clean_byte_union_third_terminal_source_byte_guard_promoted_replay/fixtures.csv")
DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_third_terminal_source_byte_guard_promoted_replay/slots.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "fixture_rows",
    "control_index",
    "min_run_length",
    "run_rows",
    "known_run_rows",
    "unknown_run_rows",
    "known_exact_bytes",
    "known_false_bytes",
    "unknown_candidate_bytes",
    "unknown_false_bytes",
    "highsafe_unknown_target_bytes",
    "extra_run_target_bytes",
    "best_guard_family",
    "best_guard_key",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RUN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "control_index",
    "control_byte",
    "run_start",
    "run_end",
    "run_length",
    "known_bytes",
    "unknown_bytes",
    "known_exact_bytes",
    "known_false_bytes",
    "highsafe_unknown_bytes",
    "extra_unknown_bytes",
    "guard_family",
    "guard_key",
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
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def source_dependency_edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def highsafe_unknown_slot_map(slot_rows: list[dict[str, str]]) -> dict[tuple[str, str, str, int], list[dict[str, str]]]:
    slots: dict[tuple[str, str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in slot_rows:
        if row.get("source_location") != "in_highsafe":
            continue
        if row.get("source_availability") != "unknown_source":
            continue
        if not row.get("source_slot_rank") or not row.get("source_actual_offset", "").isdigit():
            continue
        key = (
            row.get("archive", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            int(row.get("source_actual_offset", "0")),
        )
        slots[key].append(row)
    return slots


def byte_runs(data: bytes) -> list[tuple[int, int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int, int]] = []
    start = 0
    current = data[0]
    for index, value in enumerate(data[1:], start=1):
        if value != current:
            runs.append((start, index, current))
            start = index
            current = value
    runs.append((start, len(data), current))
    return runs


def join_unique(values: list[str]) -> str:
    return ";".join(sorted({value for value in values if value}))


def representative_slot(slots: list[dict[str, str]]) -> dict[str, str]:
    if not slots:
        return {}
    return sorted(slots, key=lambda row: int(row.get("rank", "0") or "0"))[0]


def target_row(
    rank: int,
    fixture: dict[str, str],
    offset: int,
    value: int,
    guard_family: str,
    guard_key: str,
    slots: list[dict[str, str]],
) -> dict[str, str]:
    slot = representative_slot(slots)
    return {
        "rank": str(rank),
        "slot_rank": join_unique([row.get("rank", "") for row in slots]),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "span_index": slot.get("span_index", ""),
        "op_index": slot.get("op_index", ""),
        "target_offset": str(offset),
        "source_offset": str(offset),
        "relative_offset": slot.get("relative_offset", str(offset)),
        "expected_byte": f"{value:02x}",
        "predicted_byte": f"{value:02x}",
        "root_target_byte": slot.get("target_byte", ""),
        "root_target_low": slot.get("target_low", ""),
        "source_slot_rank": join_unique([row.get("source_slot_rank", "") for row in slots]),
        "source_slot_frontier_id": slot.get("source_slot_frontier_id", ""),
        "source_slot_start": slot.get("source_slot_start", ""),
        "source_dependency_edge": source_dependency_edge(slot) if slot else "",
        "best_formula": "control_prefix_byte",
        "best_guard_family": guard_family,
        "best_guard_key": guard_key,
        "promotion_ready": "1",
        "issues": "",
    }


def build(
    manifest_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    slot_rows: list[dict[str, str]],
    control_index: int,
    min_run_length: int,
    target_scope: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    highsafe_slots = highsafe_unknown_slot_map(slot_rows)
    run_rows: list[dict[str, str]] = []
    target_rows: list[dict[str, str]] = []
    counters: Counter[str] = Counter()
    guard_family = "control_prefix_index+expected_value_run"
    guard_key = f"control_index={control_index}+min_run_length={min_run_length}"

    for fixture in fixture_rows:
        key = fixture_key(fixture)
        manifest = manifest_by_key.get(key, {})
        issues: list[str] = []
        expected = read_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        control_prefix = read_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix")
        decoded = read_bytes(fixture.get("decoded_path", ""), issues, "decoded")
        known_mask = read_bytes(fixture.get("known_mask_path", ""), issues, "known_mask")
        if len(decoded) != len(expected):
            issues.append("decoded_size_mismatch")
        if len(known_mask) != len(expected):
            issues.append("known_mask_size_mismatch")
        if issues:
            counters["issue_rows"] += 1
            continue
        if control_index < 0 or control_index >= len(control_prefix):
            continue
        control_byte = control_prefix[control_index]
        for start, end, value in byte_runs(expected):
            length = end - start
            if value != control_byte or length < min_run_length:
                continue
            known_bytes = 0
            unknown_offsets: list[int] = []
            known_exact = 0
            known_false = 0
            highsafe_unknown = 0
            extra_unknown = 0
            for offset in range(start, end):
                if known_mask[offset]:
                    known_bytes += 1
                    if decoded[offset] == value:
                        known_exact += 1
                    else:
                        known_false += 1
                else:
                    unknown_offsets.append(offset)
                    if (key[0], key[1], key[2], offset) in highsafe_slots:
                        highsafe_unknown += 1
                    else:
                        extra_unknown += 1
            counters["known_exact_bytes"] += known_exact
            counters["known_false_bytes"] += known_false
            counters["unknown_candidate_bytes"] += len(unknown_offsets)
            counters["highsafe_unknown_target_bytes"] += highsafe_unknown
            counters["extra_run_target_bytes"] += extra_unknown
            verdict = "known_support_run"
            if known_false:
                verdict = "rejected_known_false"
            elif unknown_offsets:
                verdict = "promotion_ready_run"
            run_rows.append(
                {
                    "rank": str(len(run_rows) + 1),
                    "archive": fixture.get("archive", ""),
                    "archive_tag": fixture.get("archive_tag", ""),
                    "pcx_name": fixture.get("pcx_name", ""),
                    "frontier_id": fixture.get("frontier_id", ""),
                    "control_index": str(control_index),
                    "control_byte": f"{control_byte:02x}",
                    "run_start": str(start),
                    "run_end": str(end),
                    "run_length": str(length),
                    "known_bytes": str(known_bytes),
                    "unknown_bytes": str(len(unknown_offsets)),
                    "known_exact_bytes": str(known_exact),
                    "known_false_bytes": str(known_false),
                    "highsafe_unknown_bytes": str(highsafe_unknown),
                    "extra_unknown_bytes": str(extra_unknown),
                    "guard_family": guard_family,
                    "guard_key": guard_key,
                    "verdict": verdict,
                    "issues": "",
                }
            )
            if known_false:
                continue
            for offset in unknown_offsets:
                slot_hits = highsafe_slots.get((key[0], key[1], key[2], offset), [])
                if target_scope == "highsafe" and not slot_hits:
                    continue
                target_rows.append(
                    target_row(
                        len(target_rows) + 1,
                        fixture,
                        offset,
                        value,
                        guard_family,
                        guard_key,
                        slot_hits,
                    )
                )

    run_rows.sort(
        key=lambda row: (
            row["verdict"] != "promotion_ready_run",
            -int(row["unknown_bytes"]),
            row["archive"],
            row["pcx_name"],
            int(row["frontier_id"] or "0"),
            int(row["run_start"]),
        )
    )
    for index, row in enumerate(run_rows, start=1):
        row["rank"] = str(index)

    promotion_ready = (
        len(target_rows)
        if counters["known_exact_bytes"] > 0 and counters["known_false_bytes"] == 0 and counters["unknown_false_bytes"] == 0
        else 0
    )
    if promotion_ready:
        verdict = "control_prefix_fill_guard_promotion_ready"
        next_probe = "promote control-prefix fill run after terminal source-byte cascade"
    elif counters["known_false_bytes"]:
        verdict = "control_prefix_fill_guard_known_false"
        next_probe = "split control-prefix fill guard by false known runs"
    else:
        verdict = "missing_control_prefix_fill_guard"
        next_probe = "derive narrower control-prefix fill guard"
    summary = {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_control_prefix_fill_guard_review",
        "fixture_rows": str(len(fixture_rows)),
        "control_index": str(control_index),
        "min_run_length": str(min_run_length),
        "run_rows": str(len(run_rows)),
        "known_run_rows": str(sum(1 for row in run_rows if row["unknown_bytes"] == "0")),
        "unknown_run_rows": str(sum(1 for row in run_rows if row["unknown_bytes"] != "0")),
        "known_exact_bytes": str(counters["known_exact_bytes"]),
        "known_false_bytes": str(counters["known_false_bytes"]),
        "unknown_candidate_bytes": str(counters["unknown_candidate_bytes"]),
        "unknown_false_bytes": str(counters["unknown_false_bytes"]),
        "highsafe_unknown_target_bytes": str(counters["highsafe_unknown_target_bytes"]),
        "extra_run_target_bytes": str(counters["extra_run_target_bytes"]),
        "best_guard_family": guard_family,
        "best_guard_key": guard_key,
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": str(len(target_rows)),
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(counters["issue_rows"]),
    }
    return summary, run_rows, target_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    run_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "runs": run_rows, "targets": target_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("runs.csv", output_dir / "runs.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
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
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['review_verdict']}</div><div class="muted">verdict</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
  <div class="box"><div class="num">{summary['known_exact_bytes']}/{summary['known_false_bytes']}</div><div class="muted">known exact/false</div></div>
  <div class="box"><div class="num">{summary['highsafe_unknown_target_bytes']}</div><div class="muted">high-safe target bytes</div></div>
</div>
<p>{links}</p>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Runs</h2>{render_table(run_rows, RUN_FIELDNAMES)}</div>
<script type="application/json" id="control-prefix-fill-guard-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--control-index", type=int, default=8)
    parser.add_argument("--min-run-length", type=int, default=4)
    parser.add_argument("--target-scope", choices=("all", "highsafe"), default="all")
    parser.add_argument("--title", default="Lands of Lore II .tex Old Clean Union Control Prefix Fill Guard Review")
    args = parser.parse_args()

    summary, run_rows, target_rows = build(
        read_csv(args.manifest),
        read_csv(args.base_fixtures),
        read_csv(args.slots),
        args.control_index,
        args.min_run_length,
        args.target_scope,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "runs.csv", RUN_FIELDNAMES, run_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    (args.output / "index.html").write_text(
        build_html(summary, run_rows, target_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "Control-prefix fill guard review: "
        f"verdict={summary['review_verdict']} "
        f"guard={summary['best_guard_key']} "
        f"known={summary['known_exact_bytes']}/{summary['known_false_bytes']} "
        f"unknown={summary['unknown_candidate_bytes']}/{summary['unknown_false_bytes']} "
        f"highsafe={summary['highsafe_unknown_target_bytes']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
