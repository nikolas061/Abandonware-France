#!/usr/bin/env python3
"""Replay guarded mixed-value prefix bootstrap plus sequence candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_prefix_bootstrap_probe import DEFAULT_OUTPUT as DEFAULT_PREFIX_OUTPUT
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_OUTPUT as DEFAULT_SEQUENCE_REVIEW_OUTPUT,
)
from lolg_tex_micro_mixed_value_payload_source_profile_probe import fixture_key
from lolg_tex_micro_mixed_value_payload_predictor_probe import int_value, read_csv, write_csv


DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_PREFIX_SLOTS = DEFAULT_PREFIX_OUTPUT / "slots.csv"
DEFAULT_SEQUENCE_REVIEW_ROWS = DEFAULT_SEQUENCE_REVIEW_OUTPUT / "rows.csv"
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_prefix_sequence_replay")

SUMMARY_FIELDNAMES = [
    "scope",
    "prefix_candidate_bytes",
    "prefix_added_bytes",
    "prefix_skipped_known_bytes",
    "prefix_false_bytes",
    "sequence_candidate_bytes",
    "sequence_unlocked_bytes",
    "sequence_added_bytes",
    "sequence_skipped_known_bytes",
    "sequence_false_bytes",
    "total_added_bytes",
    "total_false_bytes",
    "guarded_replay_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "stage",
    "row_index",
    "archive",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "absolute_offset",
    "relative_offset",
    "expected_byte",
    "predicted_byte",
    "already_known",
    "prerequisites",
    "prerequisites_available",
    "verdict",
    "issues",
]


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def byte_at(data: bytes, offset: int) -> str:
    if 0 <= offset < len(data):
        return f"{data[offset]:02x}"
    return "NA"


def load_fixture_data(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], dict[str, bytes]]:
    replay_by_key = {fixture_key(row): row for row in replay_rows}
    output: dict[tuple[str, str, str], dict[str, bytes]] = {}
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        replay = replay_by_key.get(key, {})
        issues: list[str] = []
        output[key] = {
            "expected": read_bytes(fixture.get("expected_gap_path", ""), issues, "expected"),
            "known_mask": read_bytes(replay.get("known_mask_path", ""), issues, "known_mask"),
        }
    return output


def known_or_added(known_mask: bytes, added: dict[int, str], offset: int) -> bool:
    return (0 <= offset < len(known_mask) and bool(known_mask[offset])) or offset in added


def replay(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    prefix_slots: list[dict[str, str]],
    sequence_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    fixture_data = load_fixture_data(fixture_rows, replay_rows)
    added_by_fixture: dict[tuple[str, str, str], dict[int, str]] = {}
    rows: list[dict[str, object]] = []
    issue_rows = 0

    prefix_added = 0
    prefix_skipped_known = 0
    prefix_false = 0
    for slot in prefix_slots:
        key = fixture_key(slot)
        data = fixture_data.get(key, {})
        expected = data.get("expected", b"")
        known_mask = data.get("known_mask", b"")
        offset = int_value(slot, "absolute_offset")
        predicted = slot.get("predicted_values", "")
        local_issues: list[str] = []
        if "|" in predicted or not predicted:
            local_issues.append(f"invalid_prefix_prediction:{predicted}")
        expected_byte = byte_at(expected, offset)
        already_known = 1 if 0 <= offset < len(known_mask) and known_mask[offset] else 0
        if predicted != expected_byte:
            verdict = "prefix_false"
            prefix_false += 1
        elif already_known:
            verdict = "prefix_skipped_known"
            prefix_skipped_known += 1
        else:
            verdict = "prefix_added"
            prefix_added += 1
            added_by_fixture.setdefault(key, {})[offset] = predicted
        if local_issues:
            issue_rows += 1
        rows.append(
            {
                "rank": len(rows) + 1,
                "stage": "prefix",
                "row_index": slot.get("row_index", ""),
                "archive": slot.get("archive", ""),
                "pcx_name": slot.get("pcx_name", ""),
                "frontier_id": slot.get("frontier_id", ""),
                "span_index": slot.get("span_index", ""),
                "op_index": slot.get("op_index", ""),
                "absolute_offset": offset,
                "relative_offset": slot.get("offset", ""),
                "expected_byte": expected_byte,
                "predicted_byte": predicted,
                "already_known": already_known,
                "prerequisites": "",
                "prerequisites_available": "",
                "verdict": verdict,
                "issues": ";".join(local_issues),
            }
        )

    sequence_unlocked = 0
    sequence_added = 0
    sequence_skipped_known = 0
    sequence_false = 0
    for candidate in sequence_rows:
        key = fixture_key(candidate)
        data = fixture_data.get(key, {})
        expected = data.get("expected", b"")
        known_mask = data.get("known_mask", b"")
        added = added_by_fixture.setdefault(key, {})
        offset = int_value(candidate, "start") + int_value(candidate, "offset")
        predicted = candidate.get("predicted_byte", "")
        prereq_offsets = [
            int(part) for part in candidate.get("prerequisite_offsets", "").split("|") if part
        ]
        prerequisites_available = all(known_or_added(known_mask, added, prereq) for prereq in prereq_offsets)
        expected_byte = byte_at(expected, offset)
        already_known = 1 if 0 <= offset < len(known_mask) and known_mask[offset] else 0
        if not prerequisites_available:
            verdict = "sequence_blocked_prerequisites"
        elif predicted != expected_byte:
            verdict = "sequence_false"
            sequence_false += 1
            sequence_unlocked += 1
        elif already_known:
            verdict = "sequence_skipped_known"
            sequence_skipped_known += 1
            sequence_unlocked += 1
        else:
            verdict = "sequence_added"
            sequence_added += 1
            sequence_unlocked += 1
            added[offset] = predicted
        rows.append(
            {
                "rank": len(rows) + 1,
                "stage": "sequence",
                "row_index": candidate.get("row_index", ""),
                "archive": candidate.get("archive", ""),
                "pcx_name": candidate.get("pcx_name", ""),
                "frontier_id": candidate.get("frontier_id", ""),
                "span_index": candidate.get("span_index", ""),
                "op_index": candidate.get("op_index", ""),
                "absolute_offset": offset,
                "relative_offset": candidate.get("offset", ""),
                "expected_byte": expected_byte,
                "predicted_byte": predicted,
                "already_known": already_known,
                "prerequisites": "|".join(str(prereq) for prereq in prereq_offsets),
                "prerequisites_available": 1 if prerequisites_available else 0,
                "verdict": verdict,
                "issues": "",
            }
        )

    total_false = prefix_false + sequence_false
    total_added = prefix_added + sequence_added
    summary = {
        "scope": "total",
        "prefix_candidate_bytes": len(prefix_slots),
        "prefix_added_bytes": prefix_added,
        "prefix_skipped_known_bytes": prefix_skipped_known,
        "prefix_false_bytes": prefix_false,
        "sequence_candidate_bytes": len(sequence_rows),
        "sequence_unlocked_bytes": sequence_unlocked,
        "sequence_added_bytes": sequence_added,
        "sequence_skipped_known_bytes": sequence_skipped_known,
        "sequence_false_bytes": sequence_false,
        "total_added_bytes": total_added,
        "total_false_bytes": total_false,
        "guarded_replay_bytes": total_added if total_false == 0 else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": issue_rows,
    }
    return summary, rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, object], rows: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows}, indent=2, sort_keys=True)
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
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['prefix_added_bytes']}</div><div class="muted">prefix added bytes</div></div>
  <div class="box"><div class="num">{summary['sequence_added_bytes']}</div><div class="muted">sequence added bytes</div></div>
  <div class="box"><div class="num">{summary['total_added_bytes']}</div><div class="muted">total added bytes</div></div>
  <div class="box"><div class="num">{summary['total_false_bytes']}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{summary['guarded_replay_bytes']}</div><div class="muted">guarded replay bytes</div></div>
</div>
<div class="panel"><h2>Replay rows</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-prefix-sequence-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay mixed-value prefix bootstrap plus sequence candidates.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--prefix-slots", type=Path, default=DEFAULT_PREFIX_SLOTS)
    parser.add_argument("--sequence-review-rows", type=Path, default=DEFAULT_SEQUENCE_REVIEW_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Prefix/Sequence Replay")
    args = parser.parse_args()

    summary, rows = replay(
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.prefix_slots),
        read_csv(args.sequence_review_rows),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rows.csv", ROW_FIELDNAMES, rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, args.title))

    print(f"Prefix added bytes: {summary['prefix_added_bytes']}")
    print(f"Sequence added bytes: {summary['sequence_added_bytes']}")
    print(f"Total added bytes: {summary['total_added_bytes']}")
    print(f"False bytes: {summary['total_false_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
