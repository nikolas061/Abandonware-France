#!/usr/bin/env python3
"""Probe adjacent-known copies for residual mixed-value sequence prerequisites."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import write_csv
from lolg_tex_micro_mixed_value_payload_external_source_combo_probe import (
    DEFAULT_SOURCE_PROFILE_ROWS,
    add_external_features,
)
from lolg_tex_micro_mixed_value_payload_predictor_probe import (
    DEFAULT_FIXTURES,
    int_value,
    read_csv,
)
from lolg_tex_micro_mixed_value_payload_sequence_candidate_review import (
    DEFAULT_INPUT_ROWS,
    DEFAULT_SELECTED_ROWS,
)
from lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_probe import (
    SLOT_FIELDNAMES,
    currently_known,
    render_table,
    target_prerequisite_entries,
)
from lolg_tex_micro_mixed_value_payload_sequence_state_probe import build_entries


DEFAULT_REPLAY_FIXTURES = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known")

SUMMARY_FIELDNAMES = [
    "scope",
    "selected_high_slots",
    "blocked_sequence_slots",
    "prerequisite_slots",
    "unknown_prerequisite_slots",
    "adjacent_candidate_slots",
    "adjacent_false_slots",
    "adjacent_conflict_slots",
    "unlocked_sequence_slots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rank",
    "source",
    "candidate_slots",
    "false_slots",
    "conflict_slots",
    "predicted_values",
    "sample_candidate_slots",
    "sample_false_slots",
    "verdict",
]


def archive_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row.get("archive", "")), str(row.get("pcx_name", "")), str(row.get("frontier_id", "")))


def load_replay_buffers(replay_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], dict[tuple[str, str, str], bytes], list[str]]:
    decoded_by_key: dict[tuple[str, str, str], bytes] = {}
    mask_by_key: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in replay_rows:
        key = archive_key(row)
        try:
            decoded_by_key[key] = Path(row.get("decoded_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"read_decoded_failed:{key}:{exc}")
            decoded_by_key[key] = b""
        try:
            mask_by_key[key] = Path(row.get("known_mask_path", "")).read_bytes()
        except OSError as exc:
            issues.append(f"read_known_mask_failed:{key}:{exc}")
            mask_by_key[key] = b""
    return decoded_by_key, mask_by_key, issues


def adjacent_predictions(
    target: dict[str, object],
    decoded: bytes,
    known_mask: bytes,
) -> list[tuple[str, str]]:
    absolute_offset = int_value(target, "start") + int_value(target, "offset")
    predictions: list[tuple[str, str]] = []
    for source, index in (("prev", absolute_offset - 1), ("next", absolute_offset + 1)):
        if 0 <= index < len(known_mask) and index < len(decoded) and known_mask[index] and decoded[index] != 0:
            predictions.append((source, f"{decoded[index]:02x}"))
    return predictions


def build(
    input_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
    source_profile_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    entries, issues = build_entries(input_rows, fixture_rows)
    issues.extend(add_external_features(entries, input_rows, source_profile_rows, fixture_rows, replay_rows))
    sequence_slots, targets, slot_issue_rows = target_prerequisite_entries(entries, selected_rows, replay_rows)
    decoded_by_key, mask_by_key, replay_issues = load_replay_buffers(replay_rows)
    issues.extend(replay_issues)

    slot_rows: list[dict[str, object]] = []
    false_rows: list[str] = []
    source_stats: dict[str, Counter[str]] = {"prev": Counter(), "next": Counter(), "prev|next": Counter()}
    candidate_slots: set[tuple[int, int]] = set()
    conflict_slots = 0

    for target in targets:
        key = archive_key(target)
        predictions = adjacent_predictions(target, decoded_by_key.get(key, b""), mask_by_key.get(key, b""))
        values = sorted({prediction for _source, prediction in predictions})
        if not values:
            continue
        source_label = "|".join(source for source, _prediction in predictions)
        if len(values) > 1:
            verdict = "conflicted_prerequisite_candidate"
            conflict_slots += 1
            source_stats[source_label]["conflict"] += 1
        elif values[0] == str(target.get("byte", "")):
            verdict = "prerequisite_candidate"
            candidate_slots.add((int(target["row_index"]), int(target["offset"])))
            source_stats[source_label]["candidate"] += 1
        else:
            verdict = "adjacent_known_false"
            false_rows.append(f"{target.get('row_index')}:{target.get('frontier_id')}:{target.get('offset')}={values[0]}!={target.get('byte')}")
            source_stats[source_label]["false"] += 1

        if verdict == "prerequisite_candidate":
            slot_rows.append(
                {
                    "rank": len(slot_rows) + 1,
                    "row_index": target.get("row_index", ""),
                    "archive": target.get("archive", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "op_index": target.get("op_index", ""),
                    "start": target.get("start", ""),
                    "end": target.get("end", ""),
                    "offset": target.get("offset", ""),
                    "absolute_offset": int_value(target, "start") + int_value(target, "offset"),
                    "byte": target.get("byte", ""),
                    "predicted_values": "|".join(values),
                    "rule_count": len(predictions),
                    "sample_rules": f"adjacent_known:{source_label}",
                    "blocked_sequence_refs": target.get("blocked_sequence_refs", ""),
                    "verdict": verdict,
                }
            )

    blocked_sequence_slots = [slot for slot in sequence_slots if slot.get("state") == "blocked_prerequisites"]
    unlocked_sequence_slots = sum(1 for slot in blocked_sequence_slots if currently_known(slot, candidate_slots))
    rules: list[dict[str, object]] = []
    for source, stats in source_stats.items():
        if not stats:
            continue
        sample_candidates = [
            f"{row['row_index']}:{row['frontier_id']}:{row['offset']}={row['predicted_values']}"
            for row in slot_rows
            if row.get("sample_rules") == f"adjacent_known:{source}"
        ][:8]
        rules.append(
            {
                "rank": len(rules) + 1,
                "source": source,
                "candidate_slots": stats["candidate"],
                "false_slots": stats["false"],
                "conflict_slots": stats["conflict"],
                "predicted_values": "|".join(
                    f"{value}:{count}" for value, count in Counter(row["predicted_values"] for row in slot_rows).most_common()
                ),
                "sample_candidate_slots": "|".join(sample_candidates),
                "sample_false_slots": "|".join(false_rows[:8]),
                "verdict": "adjacent_known_candidate" if stats["candidate"] and not stats["false"] and not stats["conflict"] else "adjacent_known_review",
            }
        )

    prerequisite_slots = {
        (int_value(slot, "row_index"), int(offset) - int_value(slot, "start"))
        for slot in blocked_sequence_slots
        for offset in slot.get("prerequisite_offsets", "").split("|")
        if offset
    }
    summary = {
        "scope": "total",
        "selected_high_slots": len(sequence_slots),
        "blocked_sequence_slots": len(blocked_sequence_slots),
        "prerequisite_slots": len(prerequisite_slots),
        "unknown_prerequisite_slots": len(targets),
        "adjacent_candidate_slots": len(slot_rows),
        "adjacent_false_slots": len(false_rows),
        "adjacent_conflict_slots": conflict_slots,
        "unlocked_sequence_slots": unlocked_sequence_slots,
        "promotion_candidate_bytes": len(slot_rows) if not false_rows and not conflict_slots else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues) + slot_issue_rows,
    }
    return summary, rules, slot_rows


def build_html(
    summary: dict[str, object],
    rules: list[dict[str, object]],
    slots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rules": rules, "slots": slots}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f7f4ee; color: #1f2933; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 1rem; }}
.box, .panel {{ background: white; border: 1px solid #d8d1c4; border-radius: 6px; padding: 1rem; }}
.num {{ font-size: 1.8rem; font-weight: 700; }}
.muted {{ color: #6b7280; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.35rem 0.45rem; text-align: left; vertical-align: top; }}
th {{ background: #f3efe7; position: sticky; top: 0; }}
.panel {{ margin-top: 1rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['unknown_prerequisite_slots']}</div><div class="muted">unknown prerequisites</div></div>
  <div class="box"><div class="num">{summary['adjacent_candidate_slots']}</div><div class="muted">adjacent candidates</div></div>
  <div class="box"><div class="num">{summary['adjacent_false_slots']}</div><div class="muted">false slots</div></div>
  <div class="box"><div class="num">{summary['unlocked_sequence_slots']}</div><div class="muted">unlocked sequence slots</div></div>
</div>
<div class="panel"><h2>Adjacent-known candidates</h2>{render_table(slots, SLOT_FIELDNAMES)}</div>
<div class="panel"><h2>Rules</h2>{render_table(rules, RULE_FIELDNAMES)}</div>
<script type="application/json" id="mixed-value-sequence-prerequisite-adjacent-known-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe adjacent-known prerequisite copies.")
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_SELECTED_ROWS)
    parser.add_argument("--source-profile-rows", type=Path, default=DEFAULT_SOURCE_PROFILE_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Sequence Prerequisite Adjacent-Known Probe")
    args = parser.parse_args()

    summary, rules, slots = build(
        read_csv(args.input_rows),
        read_csv(args.fixtures),
        read_csv(args.replay_fixtures),
        read_csv(args.selected_rows),
        read_csv(args.source_profile_rows),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(args.output / "slots.csv", SLOT_FIELDNAMES, slots)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rules, slots, args.title))

    print(f"Adjacent candidate slots: {summary['adjacent_candidate_slots']}")
    print(f"Adjacent false slots: {summary['adjacent_false_slots']}")
    print(f"Adjacent conflicts: {summary['adjacent_conflict_slots']}")
    print(f"Unlocked sequence slots: {summary['unlocked_sequence_slots']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
