#!/usr/bin/env python3
"""Review terminal/root low transforms after terminal-root context promotion."""

from __future__ import annotations

import argparse
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import strict_prediction
from lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_root_context_review import (
    build_rows as build_context_rows,
    context_for,
    context_key,
    read_csv,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/slots.csv"
)
DEFAULT_ROOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/roots.csv"
)
DEFAULT_TERMINALS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/terminals.csv"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay"
)

FEATURES = [
    "edge_key",
    "edge_target_frontier",
    "root_y_mod8",
    "root_x_mod8",
    "root_prefix_low",
    "root_fragment_low",
    "root_span_index",
    "root_op_index",
    "root_bucket_split_prediction",
    "root_best_template_prediction",
    "root_rel_mod8",
    "root_seq_mod8",
    "root_start_mod32",
    "terminal_fragment_low",
    "terminal_prefix_low",
    "terminal_control_low",
    "terminal_rel_mod8",
    "terminal_source_byte",
    "terminal_source_high",
    "terminal_source_low",
    "terminal_target_low",
    "terminal_seq_mod8",
    "terminal_start_mod32",
    "target_delta_mod8",
    "target_delta_mod16",
    "target_delta_mod32",
    "target_delta_signed",
    "frontier_path",
]

TRANSFORM_BASES = [
    "terminal_target_low",
    "terminal_source_low",
    "terminal_source_high",
    "terminal_fragment_low",
    "terminal_prefix_low",
    "root_fragment_low",
    "root_prefix_low",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "root_rows",
    "known_root_rows",
    "unknown_root_rows",
    "features",
    "transform_bases",
    "max_features",
    "feature_sets",
    "transform_families",
    "candidate_rows",
    "best_context",
    "best_context_key",
    "best_transform",
    "best_transform_param",
    "best_unknown_exact_roots",
    "best_known_exact_roots",
    "best_false_roots",
    "best_unknown_roots",
    "best_precision",
    "selected_contexts",
    "covered_roots",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "context_family",
    "feature_count",
    "context_key",
    "transform_family",
    "transform_param",
    "unknown_exact_roots",
    "known_exact_roots",
    "unknown_false_roots",
    "known_false_roots",
    "unknown_rows",
    "precision",
    "sample_roots",
    "sample_predictions",
    "verdict",
]

ROOT_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "prediction",
    "target_low",
    "path",
    "selected_contexts",
    "known_before",
    "expected_byte",
    "predicted_byte",
    "verdict",
]


def hex_low(value: str) -> int | None:
    try:
        return int(str(value)[-1:], 16)
    except ValueError:
        return None


def transform_families() -> list[tuple[str, str]]:
    output = [("const", "")]
    for base in TRANSFORM_BASES:
        output.append(("add", base))
        output.append(("xor", base))
    return output


def transform_name(transform: tuple[str, str]) -> str:
    kind, base = transform
    return kind if kind == "const" else f"{kind}:{base}"


def transform_param(row: dict[str, str], transform: tuple[str, str]) -> str:
    kind, base = transform
    target = hex_low(row.get("target_low", ""))
    if target is None:
        return ""
    if kind == "const":
        return f"{target:x}"
    base_value = hex_low(row.get(base, ""))
    if base_value is None:
        return ""
    if kind == "add":
        return str((target - base_value) % 16)
    if kind == "xor":
        return f"{target ^ base_value:x}"
    return ""


def apply_transform(row: dict[str, str], transform: tuple[str, str], param: str) -> str:
    kind, base = transform
    try:
        parameter = int(param, 16 if kind in {"const", "xor"} else 10)
    except ValueError:
        return ""
    if kind == "const":
        return f"{parameter & 15:x}"
    base_value = hex_low(row.get(base, ""))
    if base_value is None:
        return ""
    if kind == "add":
        return f"{(base_value + parameter) % 16:x}"
    if kind == "xor":
        return f"{(base_value ^ parameter) & 15:x}"
    return ""


def has_terminal_transform_context(fields: tuple[str, ...], transform: tuple[str, str]) -> bool:
    _, base = transform
    terminal_signal = base.startswith("terminal_") or any(field.startswith("terminal_") for field in fields)
    root_signal = any(
        field.startswith("root_")
        or field.startswith("target_delta_")
        or field in {"edge_key", "edge_target_frontier", "frontier_path"}
        for field in fields
    )
    return terminal_signal and root_signal


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def seq_mod8(row: dict[str, str]) -> str:
    value = row.get("seq_index", "")
    return str(int(value) % 8) if value.isdigit() else ""


def start_mod32(row: dict[str, str]) -> str:
    value = row.get("start", "")
    return str(int(value) % 32) if value.isdigit() else ""


def enriched_rows(
    slot_rows: list[dict[str, str]],
    root_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = build_context_rows(slot_rows, root_rows, terminal_rows, base_fixture_rows, manifest_rows)
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    terminals_by_rank = {row["terminal_slot_rank"]: row for row in terminal_rows}
    roots_by_rank = {row["root_slot_rank"]: row for row in root_rows}
    for row in rows:
        chain = roots_by_rank.get(row.get("root_slot_rank", ""), {})
        root_slot = slots_by_rank.get(row.get("root_slot_rank", ""), {})
        terminal_slot = slots_by_rank.get(chain.get("terminal_slot_rank", ""), {})
        terminal = terminals_by_rank.get(chain.get("terminal_slot_rank", ""), {})
        terminal_source_byte = terminal.get("terminal_source_expected_byte", "")
        terminal_source_value = int(terminal_source_byte, 16) if terminal_source_byte else 0
        root_offset = int_value(chain, "root_target_offset", -1)
        terminal_offset = int_value(chain, "terminal_target_offset", -1)
        row.update(
            {
                "edge_key": chain.get("edge_key", ""),
                "edge_target_frontier": chain.get("source_frontier_id", ""),
                "root_rel_mod8": root_slot.get("rel_mod8", ""),
                "root_seq_mod8": seq_mod8(root_slot),
                "root_start_mod32": start_mod32(root_slot),
                "terminal_source_byte": terminal_source_byte,
                "terminal_source_high": f"{terminal_source_value >> 4:x}" if terminal_source_byte else "",
                "terminal_source_low": f"{terminal_source_value & 15:x}" if terminal_source_byte else "",
                "terminal_target_low": chain.get("terminal_target_low", ""),
                "terminal_seq_mod8": seq_mod8(terminal_slot),
                "terminal_start_mod32": start_mod32(terminal_slot),
                "target_delta_mod8": str((root_offset - terminal_offset) % 8)
                if root_offset >= 0 and terminal_offset >= 0
                else "",
                "target_delta_signed": str(root_offset - terminal_offset)
                if root_offset >= 0 and terminal_offset >= 0
                else "",
            }
        )
    return rows


def evaluate_candidate(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
    transform: tuple[str, str],
) -> list[dict[str, object]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    grouped_predictions: dict[tuple[tuple[str, ...], str], list[dict[str, str]]] = defaultdict(list)
    grouped_unknowns: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        context = context_for(row, fields)
        parameter = transform_param(row, transform)
        if not parameter:
            continue
        all_counts[context][parameter] += 1
        row_counts[(row.get("row_id", ""), context)][parameter] += 1

    for row in rows:
        context = context_for(row, fields)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(row.get("row_id", ""), context)])
        train_counts += Counter()
        parameter = strict_prediction(train_counts)
        if not parameter:
            grouped_unknowns[context] += 1
            continue
        prediction = apply_transform(row, transform, parameter)
        if not prediction:
            grouped_unknowns[context] += 1
            continue
        predicted = dict(row)
        predicted["_prediction"] = prediction
        grouped_predictions[(context, parameter)].append(predicted)

    candidate_rows: list[dict[str, object]] = []
    for (context, parameter), members in grouped_predictions.items():
        verdicts = Counter()
        roots: list[str] = []
        predictions: list[str] = []
        for row in members:
            exact = row.get("_prediction") == row.get("target_low", "")
            verdicts[f"{'known' if row.get('known_before') == '1' else 'unknown'}_{'exact' if exact else 'false'}"] += 1
            roots.append(row.get("root_slot_rank", ""))
            predictions.append(str(row.get("_prediction", "")))
        false_roots = verdicts["unknown_false"] + verdicts["known_false"]
        exact_roots = verdicts["unknown_exact"] + verdicts["known_exact"]
        verdict = "terminal_root_transform_reject"
        if false_roots == 0 and verdicts["unknown_exact"] > 0:
            verdict = "false_free_terminal_root_transform"
            if verdicts["known_exact"] > 0 and has_terminal_transform_context(fields, transform):
                verdict = "promotion_candidate_terminal_root_transform"
        candidate_rows.append(
            {
                "rank": 0,
                "context_family": "+".join(fields),
                "feature_count": len(fields),
                "context_key": context_key(context),
                "transform_family": transform_name(transform),
                "transform_param": parameter,
                "unknown_exact_roots": verdicts["unknown_exact"],
                "known_exact_roots": verdicts["known_exact"],
                "unknown_false_roots": verdicts["unknown_false"],
                "known_false_roots": verdicts["known_false"],
                "unknown_rows": grouped_unknowns[context],
                "precision": ratio(exact_roots, exact_roots + false_roots),
                "sample_roots": ",".join(roots[:8]),
                "sample_predictions": ",".join(predictions[:8]),
                "verdict": verdict,
                "_transform": transform,
                "_roots": roots,
            }
        )
    return candidate_rows


def evaluate_candidates(rows: list[dict[str, str]], max_features: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    transforms = transform_families()
    for fields in feature_sets(max_features):
        if not any(
            field.startswith("terminal_")
            or field.startswith("target_delta_")
            or field in {"edge_key", "edge_target_frontier"}
            for field in fields
        ):
            continue
        for transform in transforms:
            candidates.extend(evaluate_candidate(rows, fields, transform))
    candidates.sort(
        key=lambda row: (
            row.get("verdict") != "promotion_candidate_terminal_root_transform",
            -int_value(row, "unknown_exact_roots"),
            -int_value(row, "known_exact_roots"),
            int_value(row, "unknown_false_roots") + int_value(row, "known_false_roots"),
            int_value(row, "feature_count"),
            str(row.get("transform_family", "")),
            str(row.get("context_family", "")),
            str(row.get("context_key", "")),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates


def select_candidate(candidates: list[dict[str, object]]) -> dict[str, object]:
    for row in candidates:
        if row.get("verdict") == "promotion_candidate_terminal_root_transform":
            return row
    return {}


def build_root_rows(rows: list[dict[str, str]], selected: dict[str, object]) -> list[dict[str, object]]:
    if not selected:
        return []
    fields = tuple(str(selected.get("context_family", "")).split("+"))
    key = tuple(str(selected.get("context_key", "")).split("|"))
    transform = selected.get("_transform", ("const", ""))
    if not isinstance(transform, tuple):
        return []
    parameter = str(selected.get("transform_param", ""))
    output: list[dict[str, object]] = []
    for row in rows:
        if context_for(row, fields) != key:
            continue
        prediction = apply_transform(row, transform, parameter)
        verdict = "correct" if prediction == row.get("target_low", "") else "false"
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": row.get("root_slot_rank", ""),
                "prediction": prediction,
                "target_low": row.get("target_low", ""),
                "path": row.get("path", ""),
                "selected_contexts": (
                    f"{selected.get('context_family', '')}={selected.get('context_key', '')};"
                    f"{selected.get('transform_family', '')}={parameter}"
                ),
                "known_before": row.get("known_before", ""),
                "expected_byte": row.get("expected_byte", ""),
                "predicted_byte": f"{row.get('target_high', '')}{prediction}" if prediction else "",
                "verdict": verdict,
            }
        )
    return output


def public_candidates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{field: row.get(field, "") for field in CANDIDATE_FIELDNAMES} for row in rows]


def build(
    slot_rows: list[dict[str, str]],
    root_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    max_features: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    rows = enriched_rows(slot_rows, root_rows, terminal_rows, base_fixture_rows, manifest_rows)
    candidates = evaluate_candidates(rows, max_features)
    selected = select_candidate(candidates)
    selected_roots = build_root_rows(rows, selected)
    false_roots = sum(1 for row in selected_roots if row.get("verdict") != "correct")
    unknown_exact = sum(1 for row in selected_roots if row.get("verdict") == "correct" and row.get("known_before") == "0")
    known_exact = sum(1 for row in selected_roots if row.get("verdict") == "correct" and row.get("known_before") == "1")
    feature_set_count = len(feature_sets(max_features))
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_root_transform_review",
        "root_rows": len(rows),
        "known_root_rows": sum(1 for row in rows if row.get("known_before") == "1"),
        "unknown_root_rows": sum(1 for row in rows if row.get("known_before") == "0"),
        "features": len(FEATURES),
        "transform_bases": len(TRANSFORM_BASES),
        "max_features": max_features,
        "feature_sets": feature_set_count,
        "transform_families": len(transform_families()),
        "candidate_rows": len(candidates),
        "best_context": selected.get("context_family", ""),
        "best_context_key": selected.get("context_key", ""),
        "best_transform": selected.get("transform_family", ""),
        "best_transform_param": selected.get("transform_param", ""),
        "best_unknown_exact_roots": unknown_exact,
        "best_known_exact_roots": known_exact,
        "best_false_roots": false_roots,
        "best_unknown_roots": selected.get("unknown_rows", "0"),
        "best_precision": selected.get("precision", "0.000000"),
        "selected_contexts": 1 if selected else 0,
        "covered_roots": len(selected_roots),
        "promotion_candidate_bytes": len(selected_roots),
        "promotion_ready_bytes": 0,
        "issue_rows": false_roots,
    }
    return summary, public_candidates(candidates), selected_roots


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    candidates: list[dict[str, object]],
    roots: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "roots": roots, "candidates": candidates[:220]},
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1800px; }}
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
  <div class="box"><div class="num">{summary['root_rows']}</div><div class="muted">root rows</div></div>
  <div class="box"><div class="num">{summary['candidate_rows']}</div><div class="muted">candidate transforms</div></div>
  <div class="box"><div class="num">{summary['best_unknown_exact_roots']}/{summary['best_known_exact_roots']}</div><div class="muted">unknown/known exact roots</div></div>
  <div class="box"><div class="num">{summary['best_false_roots']}</div><div class="muted">false roots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">candidate bytes</div></div>
</div>
<div class="panel"><h2>Selected roots</h2>{render_table(roots, ROOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="terminal-root-transform-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review terminal/root low transforms for residual known-terminal chains.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--roots", type=Path, default=DEFAULT_ROOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Source-Terminal Root Transform Review",
    )
    args = parser.parse_args()

    summary, candidates, roots = build(
        read_csv(args.slots),
        read_csv(args.roots),
        read_csv(args.terminals),
        read_csv(args.base_fixtures),
        read_csv(args.manifest),
        args.max_features,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "roots.csv", ROOT_FIELDNAMES, roots)
    (args.output / "index.html").write_text(build_html(summary, candidates, roots, args.title))

    print(
        "Best terminal/root transform: "
        f"{summary['best_context']}={summary['best_context_key']} "
        f"{summary['best_transform']}={summary['best_transform_param']}"
    )
    print(
        "Exact roots: "
        f"{summary['best_unknown_exact_roots']} unknown + {summary['best_known_exact_roots']} known / "
        f"{summary['best_false_roots']} false"
    )
    print(f"Promotion candidate bytes: {summary['promotion_candidate_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
