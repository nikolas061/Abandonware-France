#!/usr/bin/env python3
"""Profile generated-sequence evidence for Frontier80 normalized palette-walk runs."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_decoder_frontier80_clean_nonzero_palette_walk_producer_probe import (
    fixture_key,
    key_text,
    normalize_bytes,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_generated_sequence_probe")
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_producer_probe/candidates.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_ROW_WIDTH = 320

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_runs",
    "candidate_bytes",
    "palette_bytes",
    "terminal_sequences",
    "terminal_bytes",
    "palette_delta_pairs",
    "palette_delta_le3_pairs",
    "palette_delta_le3_ratio",
    "large_delta_pairs",
    "value_rows",
    "context_rows",
    "best_insample_context",
    "best_insample_exact",
    "best_insample_missing",
    "best_loo_context",
    "best_loo_exact",
    "best_loo_missing",
    "best_loo_conflicted",
    "terminal_unique_contexts",
    "terminal_near_row_tail",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "row_min",
    "row_max",
    "col_min",
    "col_max",
    "palette_bytes",
    "terminal_sequences",
    "terminal_bytes",
    "palette_unique_hex",
    "palette_delta_pairs",
    "palette_delta_le3_pairs",
    "palette_delta_le3_ratio",
    "large_delta_pairs",
    "largest_abs_delta",
    "head_palette_hex",
    "tail_palette_hex",
    "verdict",
    "next_probe",
]

VALUE_FIELDNAMES = [
    "scope",
    "target_id",
    "value_hex",
    "count",
    "ratio",
]

DELTA_FIELDNAMES = [
    "target_id",
    "transition_index",
    "from_run_offset",
    "to_run_offset",
    "from_abs",
    "to_abs",
    "from_row",
    "to_row",
    "from_col",
    "to_col",
    "from_mode",
    "to_mode",
    "from_value_hex",
    "to_value_hex",
    "delta",
    "abs_delta",
    "small_delta_le3",
]

CONTEXT_FIELDNAMES = [
    "train_mode",
    "context_name",
    "samples",
    "covered_samples",
    "exact_samples",
    "missing_samples",
    "conflicted_samples",
    "context_keys",
    "conflict_keys",
    "exact_ratio",
    "covered_exact_ratio",
    "verdict",
]

TERMINAL_FIELDNAMES = [
    "target_id",
    "terminal_index",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "row",
    "col_start",
    "col_end",
    "length",
    "terminal_hex",
    "prev_palette_hex",
    "next_palette_hex",
    "prev_value_hex",
    "next_value_hex",
    "bridge_delta",
    "col_mod32",
    "near_row_tail",
    "guard_context",
]

PaletteItem = dict[str, object]
Candidate = dict[str, object]
ContextFunc = Callable[[list[PaletteItem], int], tuple[object, ...]]


def manifest_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str, row_id: str) -> bytes:
    if not path_text:
        issues.append(f"{row_id}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{row_id}:read_{label}_failed:{exc}")
        return b""


def signed_delta(left: int, right: int) -> int:
    value = (right - left) & 0xFF
    return value if value < 128 else value - 256


def hex_values(values: list[int]) -> str:
    return " ".join(f"{value:02x}" for value in values)


def terminal_ranges(palette_hits: list[bool]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, hit in enumerate(palette_hits):
        if hit:
            if start is not None:
                ranges.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        ranges.append((start, len(palette_hits)))
    return ranges


def palette_item(
    candidate: dict[str, str],
    offset: int,
    palette_index: int,
    raw_value: int,
    normalized_value: int,
    mode: str,
    row_width: int,
) -> PaletteItem:
    absolute = int_value(candidate, "start") + offset
    return {
        "target_id": candidate.get("target_id", ""),
        "offset": offset,
        "palette_index": palette_index,
        "absolute": absolute,
        "row": absolute // row_width,
        "col": absolute % row_width,
        "raw": raw_value,
        "value": normalized_value,
        "mode": mode,
    }


def load_candidates(
    candidates_path: Path,
    manifest_path: Path,
    issues: list[str],
    *,
    row_width: int,
) -> list[Candidate]:
    manifest_rows = read_csv(manifest_path)
    manifests = {manifest_key(row): row for row in manifest_rows}
    candidates: list[Candidate] = []
    for row in read_csv(candidates_path):
        key = fixture_key(row)
        row_id = row.get("target_id", key_text(key))
        manifest = manifests.get(key)
        if not manifest:
            issues.append(f"{row_id}:missing_manifest")
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", row_id)
        start = int_value(row, "start")
        end = int_value(row, "end")
        data = expected[start:end]
        if len(data) != int_value(row, "length"):
            issues.append(f"{row_id}:target_window_out_of_bounds")
            continue
        normalized, modes, palette_hits = normalize_bytes(data)
        items: list[PaletteItem] = []
        palette_index = 0
        for offset, (raw_value, normalized_value, mode, hit) in enumerate(
            zip(data, normalized, modes, palette_hits)
        ):
            if not hit:
                continue
            items.append(
                palette_item(
                    row,
                    offset,
                    palette_index,
                    raw_value,
                    normalized_value,
                    mode,
                    row_width,
                )
            )
            palette_index += 1
        candidates.append(
            {
                "row": row,
                "manifest": manifest,
                "data": data,
                "normalized": normalized,
                "modes": modes,
                "palette_hits": palette_hits,
                "palette_items": items,
            }
        )
    return candidates


def candidate_record(candidate: Candidate, *, row_width: int) -> dict[str, str]:
    row = candidate["row"]
    data = candidate["data"]
    items = candidate["palette_items"]
    palette_hits = candidate["palette_hits"]
    assert isinstance(row, dict)
    assert isinstance(data, bytes)
    assert isinstance(items, list)
    assert isinstance(palette_hits, list)
    values = [int(item["value"]) for item in items]
    deltas = [signed_delta(left, right) for left, right in zip(values, values[1:])]
    small = sum(1 for delta in deltas if abs(delta) <= 3)
    terminal_spans = terminal_ranges([bool(hit) for hit in palette_hits])
    terminal_bytes = sum(end - start for start, end in terminal_spans)
    rows = [int(item["row"]) for item in items]
    cols = [int(item["col"]) for item in items]
    large_delta_pairs = len(deltas) - small
    if values and small == len(deltas):
        verdict = "palette_walk_generated_local_delta_profile"
    elif values:
        verdict = "palette_walk_generated_delta_profile_with_outliers"
    else:
        verdict = "palette_walk_generated_no_palette_values"
    return {
        "target_id": row.get("target_id", ""),
        "rank": row.get("rank", ""),
        "archive": row.get("archive", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "frontier_id": row.get("frontier_id", ""),
        "start": row.get("start", ""),
        "end": row.get("end", ""),
        "length": str(len(data)),
        "row_min": str(min(rows) if rows else 0),
        "row_max": str(max(rows) if rows else 0),
        "col_min": str(min(cols) if cols else 0),
        "col_max": str(max(cols) if cols else 0),
        "palette_bytes": str(len(values)),
        "terminal_sequences": str(len(terminal_spans)),
        "terminal_bytes": str(terminal_bytes),
        "palette_unique_hex": hex_values(sorted(set(values))),
        "palette_delta_pairs": str(len(deltas)),
        "palette_delta_le3_pairs": str(small),
        "palette_delta_le3_ratio": f"{small / len(deltas):.6f}" if deltas else "0.000000",
        "large_delta_pairs": str(large_delta_pairs),
        "largest_abs_delta": str(max([abs(delta) for delta in deltas] or [0])),
        "head_palette_hex": hex_values(values[:16]),
        "tail_palette_hex": hex_values(values[-16:]),
        "verdict": verdict,
        "next_probe": "derive compact delta-state generator for palette-walk values and terminal marker contexts",
    }


def value_rows(candidates: list[Candidate]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    total_counter: Counter[int] = Counter()
    for candidate in candidates:
        source_row = candidate["row"]
        items = candidate["palette_items"]
        assert isinstance(source_row, dict)
        assert isinstance(items, list)
        counter = Counter(int(item["value"]) for item in items)
        total = sum(counter.values())
        for value, count in sorted(counter.items()):
            rows.append(
                {
                    "scope": "candidate",
                    "target_id": source_row.get("target_id", ""),
                    "value_hex": f"{value:02x}",
                    "count": str(count),
                    "ratio": f"{count / total:.6f}" if total else "0.000000",
                }
            )
        total_counter.update(counter)
    total = sum(total_counter.values())
    for value, count in sorted(total_counter.items()):
        rows.append(
            {
                "scope": "total",
                "target_id": "",
                "value_hex": f"{value:02x}",
                "count": str(count),
                "ratio": f"{count / total:.6f}" if total else "0.000000",
            }
        )
    return rows


def delta_rows(candidates: list[Candidate]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        source_row = candidate["row"]
        items = candidate["palette_items"]
        assert isinstance(source_row, dict)
        assert isinstance(items, list)
        for index, (left, right) in enumerate(zip(items, items[1:])):
            delta = signed_delta(int(left["value"]), int(right["value"]))
            rows.append(
                {
                    "target_id": source_row.get("target_id", ""),
                    "transition_index": str(index),
                    "from_run_offset": str(left["offset"]),
                    "to_run_offset": str(right["offset"]),
                    "from_abs": str(left["absolute"]),
                    "to_abs": str(right["absolute"]),
                    "from_row": str(left["row"]),
                    "to_row": str(right["row"]),
                    "from_col": str(left["col"]),
                    "to_col": str(right["col"]),
                    "from_mode": str(left["mode"]),
                    "to_mode": str(right["mode"]),
                    "from_value_hex": f"{int(left['value']):02x}",
                    "to_value_hex": f"{int(right['value']):02x}",
                    "delta": str(delta),
                    "abs_delta": str(abs(delta)),
                    "small_delta_le3": "1" if abs(delta) <= 3 else "0",
                }
            )
    return rows


def context_specs(row_width: int) -> list[tuple[str, ContextFunc]]:
    def previous_delta(items: list[PaletteItem], index: int) -> int | None:
        if index < 2:
            return None
        return signed_delta(int(items[index - 2]["value"]), int(items[index - 1]["value"]))

    return [
        ("prev_value", lambda items, index: (items[index - 1]["value"],)),
        ("prev_value_mode", lambda items, index: (items[index - 1]["value"], items[index]["mode"])),
        ("prev_value_col_mod8", lambda items, index: (items[index - 1]["value"], int(items[index]["col"]) % 8)),
        ("prev_value_col_mod16", lambda items, index: (items[index - 1]["value"], int(items[index]["col"]) % 16)),
        ("prev_value_col_mod32", lambda items, index: (items[index - 1]["value"], int(items[index]["col"]) % 32)),
        (
            "prev2_values",
            lambda items, index: (
                items[index - 2]["value"] if index >= 2 else None,
                items[index - 1]["value"],
            ),
        ),
        (
            "prev_delta_value",
            lambda items, index: (
                previous_delta(items, index),
                items[index - 1]["value"],
            ),
        ),
        ("abs_col_mod32", lambda items, index: (int(items[index]["col"]) % 32,)),
        ("abs_col_mod64", lambda items, index: (int(items[index]["col"]) % 64,)),
        ("row_col_mod32", lambda items, index: (items[index]["row"], int(items[index]["col"]) % 32)),
        (
            "prev_value_row_col_mod32",
            lambda items, index: (
                items[index - 1]["value"],
                items[index]["row"],
                int(items[index]["col"]) % 32,
            ),
        ),
        (
            "mode_col_mod32",
            lambda items, index: (
                items[index]["mode"],
                int(items[index]["col"]) % 32,
                int(items[index]["absolute"]) // row_width,
            ),
        ),
    ]


def build_context_table(
    candidate_items: list[tuple[str, list[PaletteItem]]],
    context: ContextFunc,
) -> dict[tuple[object, ...], Counter[int]]:
    table: dict[tuple[object, ...], Counter[int]] = defaultdict(Counter)
    for _target_id, items in candidate_items:
        for index in range(1, len(items)):
            table[context(items, index)][int(items[index]["value"])] += 1
    return table


def score_context(
    context_name: str,
    context: ContextFunc,
    all_items: list[tuple[str, list[PaletteItem]]],
    *,
    train_mode: str,
) -> dict[str, str]:
    exact = 0
    missing = 0
    conflicted_samples = 0
    samples = 0
    context_keys = 0
    conflict_keys = 0

    if train_mode == "insample":
        table = build_context_table(all_items, context)
        context_keys = len(table)
        conflict_keys = sum(1 for counter in table.values() if len(counter) > 1)
        holdouts = [(all_items, all_items)]
    else:
        holdouts = []
        for target_id, items in all_items:
            train = [(other_id, other_items) for other_id, other_items in all_items if other_id != target_id]
            holdouts.append((train, [(target_id, items)]))

    for train, held in holdouts:
        if train_mode == "leave_one_run_out":
            table = build_context_table(train, context)
            context_keys += len(table)
            conflict_keys += sum(1 for counter in table.values() if len(counter) > 1)
        for _target_id, items in held:
            for index in range(1, len(items)):
                samples += 1
                counter = table.get(context(items, index))
                if not counter:
                    missing += 1
                    continue
                if len(counter) > 1:
                    conflicted_samples += 1
                predicted = counter.most_common(1)[0][0]
                if predicted == int(items[index]["value"]):
                    exact += 1

    covered = samples - missing
    if exact == samples and samples:
        verdict = "context_deterministic"
    elif train_mode == "leave_one_run_out" and exact >= int(samples * 0.9) and missing == 0:
        verdict = "context_strong"
    elif train_mode == "leave_one_run_out" and exact < int(samples * 0.5):
        verdict = "context_not_predictive"
    else:
        verdict = "context_partial"
    return {
        "train_mode": train_mode,
        "context_name": context_name,
        "samples": str(samples),
        "covered_samples": str(covered),
        "exact_samples": str(exact),
        "missing_samples": str(missing),
        "conflicted_samples": str(conflicted_samples),
        "context_keys": str(context_keys),
        "conflict_keys": str(conflict_keys),
        "exact_ratio": f"{exact / samples:.6f}" if samples else "0.000000",
        "covered_exact_ratio": f"{exact / covered:.6f}" if covered else "0.000000",
        "verdict": verdict,
    }


def context_rows(candidates: list[Candidate], *, row_width: int) -> list[dict[str, str]]:
    all_items: list[tuple[str, list[PaletteItem]]] = []
    for candidate in candidates:
        row = candidate["row"]
        items = candidate["palette_items"]
        assert isinstance(row, dict)
        assert isinstance(items, list)
        all_items.append((row.get("target_id", ""), items))
    rows: list[dict[str, str]] = []
    for context_name, context in context_specs(row_width):
        rows.append(score_context(context_name, context, all_items, train_mode="insample"))
        rows.append(score_context(context_name, context, all_items, train_mode="leave_one_run_out"))
    rows.sort(
        key=lambda row: (
            row.get("train_mode", ""),
            -int_value(row, "exact_samples"),
            int_value(row, "missing_samples"),
            row.get("context_name", ""),
        )
    )
    return rows


def terminal_rows(candidates: list[Candidate], *, row_width: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        source_row = candidate["row"]
        data = candidate["data"]
        palette_hits = candidate["palette_hits"]
        items = candidate["palette_items"]
        assert isinstance(source_row, dict)
        assert isinstance(data, bytes)
        assert isinstance(palette_hits, list)
        assert isinstance(items, list)
        for index, (start, end) in enumerate(terminal_ranges([bool(hit) for hit in palette_hits])):
            absolute_start = int_value(source_row, "start") + start
            absolute_end = int_value(source_row, "start") + end
            previous_values = [
                int(item["value"])
                for item in items
                if int(item["offset"]) < start
            ][-8:]
            next_values = [
                int(item["value"])
                for item in items
                if int(item["offset"]) >= end
            ][:8]
            previous_value = previous_values[-1] if previous_values else None
            next_value = next_values[0] if next_values else None
            bridge_delta = (
                signed_delta(previous_value, next_value)
                if previous_value is not None and next_value is not None
                else None
            )
            previous_context = f"{previous_value:02x}" if previous_value is not None else "none"
            next_context = f"{next_value:02x}" if next_value is not None else "none"
            near_row_tail = (absolute_end % row_width) >= row_width - 16
            guard_context = (
                f"len{end - start}:prev{previous_context}:next{next_context}:"
                f"colmod32_{absolute_start % 32}:tail{1 if near_row_tail else 0}"
            )
            rows.append(
                {
                    "target_id": source_row.get("target_id", ""),
                    "terminal_index": str(index),
                    "rank": source_row.get("rank", ""),
                    "pcx_name": source_row.get("pcx_name", ""),
                    "frontier_id": source_row.get("frontier_id", ""),
                    "run_offset_start": str(start),
                    "run_offset_end": str(end),
                    "absolute_start": str(absolute_start),
                    "absolute_end": str(absolute_end),
                    "row": str(absolute_start // row_width),
                    "col_start": str(absolute_start % row_width),
                    "col_end": str(absolute_end % row_width),
                    "length": str(end - start),
                    "terminal_hex": data[start:end].hex(),
                    "prev_palette_hex": hex_values(previous_values),
                    "next_palette_hex": hex_values(next_values),
                    "prev_value_hex": f"{previous_value:02x}" if previous_value is not None else "",
                    "next_value_hex": f"{next_value:02x}" if next_value is not None else "",
                    "bridge_delta": str(bridge_delta) if bridge_delta is not None else "",
                    "col_mod32": str(absolute_start % 32),
                    "near_row_tail": "1" if near_row_tail else "0",
                    "guard_context": guard_context,
                }
            )
    return rows


def best_context(rows: list[dict[str, str]], train_mode: str) -> dict[str, str]:
    candidates = [row for row in rows if row.get("train_mode") == train_mode]
    if not candidates:
        return {}
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "exact_samples"),
            -int_value(row, "missing_samples"),
            -int_value(row, "conflicted_samples"),
            row.get("context_name", ""),
        ),
    )


def build_summary(
    candidate_rows: list[dict[str, str]],
    value_rows_list: list[dict[str, str]],
    delta_rows_list: list[dict[str, str]],
    context_rows_list: list[dict[str, str]],
    terminal_rows_list: list[dict[str, str]],
    *,
    issue_count: int,
) -> dict[str, str]:
    palette_bytes = sum(int_value(row, "palette_bytes") for row in candidate_rows)
    candidate_bytes = sum(int_value(row, "length") for row in candidate_rows)
    delta_pairs = len(delta_rows_list)
    small_delta_pairs = sum(int_value(row, "small_delta_le3") for row in delta_rows_list)
    large_delta_pairs = delta_pairs - small_delta_pairs
    best_insample = best_context(context_rows_list, "insample")
    best_loo = best_context(context_rows_list, "leave_one_run_out")
    terminal_contexts = {row.get("guard_context", "") for row in terminal_rows_list}
    terminal_near_tail = sum(int_value(row, "near_row_tail") for row in terminal_rows_list)
    if delta_pairs and int_value(best_loo, "exact_samples") == delta_pairs and not large_delta_pairs:
        verdict = "frontier80_clean_nonzero_palette_walk_generated_sequence_ready"
        next_probe = "promote generated palette-walk sequence with contextual terminal marker guard"
    elif delta_pairs and small_delta_pairs / delta_pairs >= 0.95:
        verdict = "frontier80_clean_nonzero_palette_walk_generated_sequence_profiled"
        next_probe = "derive compact delta-state generator for palette-walk values and terminal marker contexts"
    elif candidate_rows:
        verdict = "frontier80_clean_nonzero_palette_walk_generated_sequence_context_partial"
        next_probe = "split palette-walk generator by row and terminal context"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_generated_sequence_no_candidates"
        next_probe = "return to clean-gap nonzero run queue"
    return {
        "scope": "total",
        "candidate_runs": str(len(candidate_rows)),
        "candidate_bytes": str(candidate_bytes),
        "palette_bytes": str(palette_bytes),
        "terminal_sequences": str(len(terminal_rows_list)),
        "terminal_bytes": str(sum(int_value(row, "length") for row in terminal_rows_list)),
        "palette_delta_pairs": str(delta_pairs),
        "palette_delta_le3_pairs": str(small_delta_pairs),
        "palette_delta_le3_ratio": f"{small_delta_pairs / delta_pairs:.6f}" if delta_pairs else "0.000000",
        "large_delta_pairs": str(large_delta_pairs),
        "value_rows": str(len(value_rows_list)),
        "context_rows": str(len(context_rows_list)),
        "best_insample_context": best_insample.get("context_name", ""),
        "best_insample_exact": f"{best_insample.get('exact_samples', '0')}/{best_insample.get('samples', '0')}",
        "best_insample_missing": best_insample.get("missing_samples", "0"),
        "best_loo_context": best_loo.get("context_name", ""),
        "best_loo_exact": f"{best_loo.get('exact_samples', '0')}/{best_loo.get('samples', '0')}",
        "best_loo_missing": best_loo.get("missing_samples", "0"),
        "best_loo_conflicted": best_loo.get("conflicted_samples", "0"),
        "terminal_unique_contexts": str(len(terminal_contexts)),
        "terminal_near_row_tail": str(terminal_near_tail),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 140) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidate_rows_list: list[dict[str, str]],
    value_rows_list: list[dict[str, str]],
    delta_rows_list: list[dict[str, str]],
    context_rows_list: list[dict[str, str]],
    terminal_rows_list: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows_list,
        "values": value_rows_list,
        "deltas": delta_rows_list,
        "contexts": context_rows_list,
        "terminals": terminal_rows_list,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("values.csv", output_dir / "values.csv"),
            ("deltas.csv", output_dir / "deltas.csv"),
            ("context_scores.csv", output_dir / "context_scores.csv"),
            ("terminal_contexts.csv", output_dir / "terminal_contexts.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1260px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Profiles local deltas, leave-one-run-out contexts, and terminal marker guard contexts.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette bytes</div><div class="value">{html.escape(summary['palette_bytes'])}</div></div>
    <div class="stat"><div class="label">Delta <= 3</div><div class="value">{html.escape(summary['palette_delta_le3_pairs'])}/{html.escape(summary['palette_delta_pairs'])}</div></div>
    <div class="stat"><div class="label">Best LOO</div><div class="value warn">{html.escape(summary['best_loo_context'])}: {html.escape(summary['best_loo_exact'])}</div></div>
    <div class="stat"><div class="label">Terminal contexts</div><div class="value">{html.escape(summary['terminal_unique_contexts'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows_list, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Context Scores</h2>{render_table(context_rows_list, CONTEXT_FIELDNAMES)}</section>
  <section class="panel"><h2>Terminal Contexts</h2>{render_table(terminal_rows_list, TERMINAL_FIELDNAMES)}</section>
  <section class="panel"><h2>Values</h2>{render_table(value_rows_list, VALUE_FIELDNAMES)}</section>
  <section class="panel"><h2>Deltas</h2>{render_table(delta_rows_list, DELTA_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-generated-sequence-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    manifest_path: Path,
    *,
    row_width: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    candidates = load_candidates(candidates_path, manifest_path, issues, row_width=row_width)
    candidate_rows_list = [candidate_record(candidate, row_width=row_width) for candidate in candidates]
    value_rows_list = value_rows(candidates)
    delta_rows_list = delta_rows(candidates)
    context_rows_list = context_rows(candidates, row_width=row_width)
    terminal_rows_list = terminal_rows(candidates, row_width=row_width)
    summary = build_summary(
        candidate_rows_list,
        value_rows_list,
        delta_rows_list,
        context_rows_list,
        terminal_rows_list,
        issue_count=len(issues),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows_list)
    write_csv(output_dir / "values.csv", VALUE_FIELDNAMES, value_rows_list)
    write_csv(output_dir / "deltas.csv", DELTA_FIELDNAMES, delta_rows_list)
    write_csv(output_dir / "context_scores.csv", CONTEXT_FIELDNAMES, context_rows_list)
    write_csv(output_dir / "terminal_contexts.csv", TERMINAL_FIELDNAMES, terminal_rows_list)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(
            summary,
            candidate_rows_list,
            value_rows_list,
            delta_rows_list,
            context_rows_list,
            terminal_rows_list,
            output_dir,
            title,
        )
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile generated Frontier80 palette-walk sequences.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--row-width", type=int, default=DEFAULT_ROW_WIDTH)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Generated Sequence Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.candidates,
        args.manifest,
        row_width=args.row_width,
        title=args.title,
    )
    print(f"Palette bytes: {summary['palette_bytes']}")
    print(f"Delta <=3: {summary['palette_delta_le3_pairs']}/{summary['palette_delta_pairs']}")
    print(f"Best LOO context: {summary['best_loo_context']} {summary['best_loo_exact']}")
    print(f"Terminal contexts: {summary['terminal_unique_contexts']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
