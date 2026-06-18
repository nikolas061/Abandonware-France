#!/usr/bin/env python3
"""Review terminal/root contexts for residual known-terminal source chains."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_probe import strict_prediction
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/slots.csv"
)
DEFAULT_ROOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/roots.csv"
)
DEFAULT_TERMINALS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/terminals.csv"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay"
)

FEATURES = [
    "root_y_mod8",
    "root_x_mod8",
    "root_prefix_low",
    "root_fragment_low",
    "root_span_index",
    "root_op_index",
    "root_bucket_split_prediction",
    "root_best_template_prediction",
    "terminal_fragment_low",
    "terminal_prefix_low",
    "terminal_control_low",
    "terminal_rel_mod8",
    "terminal_source_byte",
    "terminal_source_low",
    "target_delta_mod16",
    "target_delta_mod32",
    "frontier_path",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "root_rows",
    "known_root_rows",
    "unknown_root_rows",
    "features",
    "max_features",
    "feature_sets",
    "candidate_rows",
    "best_context",
    "best_context_key",
    "best_prediction",
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
    "prediction",
    "unknown_exact_roots",
    "known_exact_roots",
    "unknown_false_roots",
    "known_false_roots",
    "unknown_rows",
    "precision",
    "sample_roots",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def read_bytes(path_text: str) -> bytes:
    return Path(path_text).read_bytes() if path_text else b""


def byte_text(buffer: bytes, offset: int) -> str:
    return f"{buffer[offset]:02x}" if 0 <= offset < len(buffer) else ""


def context_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def context_key(context: tuple[str, ...]) -> str:
    return "|".join(context)


def has_terminal_delta_context(fields: tuple[str, ...]) -> bool:
    return any(field.startswith("terminal_") for field in fields) and any(
        field.startswith("target_delta_") for field in fields
    )


def build_rows(
    slot_rows: list[dict[str, str]],
    root_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    terminals_by_rank = {row["terminal_slot_rank"]: row for row in terminal_rows}
    fixtures = {fixture_key(row): row for row in base_fixture_rows}
    manifests = {fixture_key(row): row for row in manifest_rows}
    buffer_cache: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}
    rows: list[dict[str, str]] = []
    for root_chain in root_rows:
        root = slots_by_rank.get(root_chain.get("root_slot_rank", ""), {})
        terminal_slot = slots_by_rank.get(root_chain.get("terminal_slot_rank", ""), {})
        terminal = terminals_by_rank.get(root_chain.get("terminal_slot_rank", ""), {})
        if not root or not terminal_slot:
            continue
        key = fixture_key(root)
        if key not in buffer_cache:
            fixture = fixtures.get(key, {})
            manifest = manifests.get(key, {})
            buffer_cache[key] = (
                read_bytes(manifest.get("expected_gap_path", "")),
                read_bytes(fixture.get("known_mask_path", "")),
            )
        expected, known_mask = buffer_cache[key]
        offset = int_value(root_chain, "root_target_offset", -1)
        terminal_offset = int_value(root_chain, "terminal_target_offset", -1)
        terminal_source_byte = terminal.get("terminal_source_expected_byte", "")
        path = [rank for rank in root_chain.get("path", "").split("->") if rank]
        row = {
            "row_id": root.get("row_id", ""),
            "root_slot_rank": root_chain.get("root_slot_rank", ""),
            "target_low": root_chain.get("root_target_low", ""),
            "target_high": root.get("target_high", ""),
            "target_offset": root_chain.get("root_target_offset", ""),
            "path": root_chain.get("path", ""),
            "known_before": "1" if 0 <= offset < len(known_mask) and known_mask[offset] else "0",
            "expected_byte": byte_text(expected, offset),
            "root_y_mod8": root.get("y_mod8", ""),
            "root_x_mod8": root.get("x_mod8", ""),
            "root_prefix_low": root.get("prefix_low", ""),
            "root_fragment_low": root.get("fragment_low", ""),
            "root_span_index": root.get("span_index", ""),
            "root_op_index": root.get("op_index", ""),
            "root_bucket_split_prediction": root.get("bucket_split_prediction", ""),
            "root_best_template_prediction": root.get("best_template_prediction", ""),
            "terminal_fragment_low": terminal_slot.get("fragment_low", ""),
            "terminal_prefix_low": terminal_slot.get("prefix_low", ""),
            "terminal_control_low": terminal_slot.get("control_low", ""),
            "terminal_rel_mod8": terminal_slot.get("rel_mod8", ""),
            "terminal_source_byte": terminal_source_byte,
            "terminal_source_low": terminal_source_byte[-1:] if terminal_source_byte else "",
            "target_delta_mod16": str((offset - terminal_offset) % 16) if offset >= 0 and terminal_offset >= 0 else "",
            "target_delta_mod32": str((offset - terminal_offset) % 32) if offset >= 0 and terminal_offset >= 0 else "",
            "frontier_path": "->".join(slots_by_rank.get(rank, {}).get("frontier_id", "") for rank in path),
        }
        rows.append(row)
    return rows


def feature_sets(max_features: int) -> list[tuple[str, ...]]:
    output: list[tuple[str, ...]] = []
    for size in range(1, max_features + 1):
        output.extend(itertools.combinations(FEATURES, size))
    return output


def evaluate_candidate(rows: list[dict[str, str]], fields: tuple[str, ...]) -> list[dict[str, object]]:
    all_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    row_counts: dict[tuple[str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
    grouped_predictions: dict[tuple[tuple[str, ...], str], list[dict[str, str]]] = defaultdict(list)
    grouped_unknowns: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        context = context_for(row, fields)
        all_counts[context][row.get("target_low", "")] += 1
        row_counts[(row.get("row_id", ""), context)][row.get("target_low", "")] += 1

    for row in rows:
        context = context_for(row, fields)
        train_counts = all_counts[context].copy()
        train_counts.subtract(row_counts[(row.get("row_id", ""), context)])
        train_counts += Counter()
        prediction = strict_prediction(train_counts)
        if not prediction:
            grouped_unknowns[context] += 1
            continue
        predicted = dict(row)
        predicted["_prediction"] = prediction
        grouped_predictions[(context, prediction)].append(predicted)

    candidate_rows: list[dict[str, object]] = []
    for (context, prediction), members in grouped_predictions.items():
        verdicts = Counter()
        roots: list[str] = []
        for row in members:
            known = row.get("known_before", "")
            exact = prediction == row.get("target_low", "")
            verdicts[f"{'known' if known == '1' else 'unknown'}_{'exact' if exact else 'false'}"] += 1
            roots.append(row.get("root_slot_rank", ""))
        false_roots = verdicts["unknown_false"] + verdicts["known_false"]
        exact_roots = verdicts["unknown_exact"] + verdicts["known_exact"]
        verdict = "terminal_root_context_reject"
        if false_roots == 0 and verdicts["unknown_exact"] > 0:
            verdict = "false_free_terminal_root_context"
            if verdicts["known_exact"] > 0 and has_terminal_delta_context(fields):
                verdict = "promotion_candidate_terminal_root_context"
        candidate_rows.append(
            {
                "rank": 0,
                "context_family": "+".join(fields),
                "feature_count": len(fields),
                "context_key": context_key(context),
                "prediction": prediction,
                "unknown_exact_roots": verdicts["unknown_exact"],
                "known_exact_roots": verdicts["known_exact"],
                "unknown_false_roots": verdicts["unknown_false"],
                "known_false_roots": verdicts["known_false"],
                "unknown_rows": grouped_unknowns[context],
                "precision": ratio(exact_roots, exact_roots + false_roots),
                "sample_roots": ",".join(roots[:8]),
                "verdict": verdict,
                "_roots": roots,
            }
        )
    return candidate_rows


def evaluate_candidates(rows: list[dict[str, str]], max_features: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for fields in feature_sets(max_features):
        candidates.extend(evaluate_candidate(rows, fields))
    candidates.sort(
        key=lambda row: (
            row.get("verdict") != "promotion_candidate_terminal_root_context",
            -int_value(row, "unknown_exact_roots"),
            -int_value(row, "known_exact_roots"),
            int_value(row, "unknown_false_roots") + int_value(row, "known_false_roots"),
            int_value(row, "feature_count"),
            str(row.get("context_family", "")),
            str(row.get("context_key", "")),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = index
    return candidates


def select_candidate(candidates: list[dict[str, object]]) -> dict[str, object]:
    for row in candidates:
        if row.get("verdict") == "promotion_candidate_terminal_root_context":
            return row
    return {}


def build_root_rows(rows: list[dict[str, str]], selected: dict[str, object]) -> list[dict[str, object]]:
    if not selected:
        return []
    fields = tuple(str(selected.get("context_family", "")).split("+"))
    key = tuple(str(selected.get("context_key", "")).split("|"))
    prediction = str(selected.get("prediction", ""))
    output: list[dict[str, object]] = []
    for row in rows:
        if context_for(row, fields) != key:
            continue
        verdict = "correct" if prediction == row.get("target_low", "") else "false"
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": row.get("root_slot_rank", ""),
                "prediction": prediction,
                "target_low": row.get("target_low", ""),
                "path": row.get("path", ""),
                "selected_contexts": f"{selected.get('context_family', '')}={selected.get('context_key', '')}",
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
    rows = build_rows(slot_rows, root_rows, terminal_rows, base_fixture_rows, manifest_rows)
    candidates = evaluate_candidates(rows, max_features)
    selected = select_candidate(candidates)
    selected_roots = build_root_rows(rows, selected)
    false_roots = sum(1 for row in selected_roots if row.get("verdict") != "correct")
    unknown_exact = sum(1 for row in selected_roots if row.get("verdict") == "correct" and row.get("known_before") == "0")
    known_exact = sum(1 for row in selected_roots if row.get("verdict") == "correct" and row.get("known_before") == "1")
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_root_context_review",
        "root_rows": len(rows),
        "known_root_rows": sum(1 for row in rows if row.get("known_before") == "1"),
        "unknown_root_rows": sum(1 for row in rows if row.get("known_before") == "0"),
        "features": len(FEATURES),
        "max_features": max_features,
        "feature_sets": len(feature_sets(max_features)),
        "candidate_rows": len(candidates),
        "best_context": selected.get("context_family", ""),
        "best_context_key": selected.get("context_key", ""),
        "best_prediction": selected.get("prediction", ""),
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
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
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
  <div class="box"><div class="num">{summary['candidate_rows']}</div><div class="muted">candidate contexts</div></div>
  <div class="box"><div class="num">{summary['best_unknown_exact_roots']}/{summary['best_known_exact_roots']}</div><div class="muted">unknown/known exact roots</div></div>
  <div class="box"><div class="num">{summary['best_false_roots']}</div><div class="muted">false roots</div></div>
  <div class="box"><div class="num">{summary['promotion_candidate_bytes']}</div><div class="muted">candidate bytes</div></div>
</div>
<div class="panel"><h2>Selected roots</h2>{render_table(roots, ROOT_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="terminal-root-context-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review terminal/root contexts for residual known-terminal chains.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--roots", type=Path, default=DEFAULT_ROOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-features", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Source-Terminal Root Context Review",
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
        "Best terminal/root context: "
        f"{summary['best_context']}={summary['best_context_key']} -> {summary['best_prediction']}"
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
