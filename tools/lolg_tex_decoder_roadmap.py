#!/usr/bin/env python3
"""Build a prioritized roadmap from .tex decoder review decisions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_decoder_roadmap")
DEFAULT_DECISIONS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review/decisions.csv")
DEFAULT_REVIEW_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review/summary.csv"
)
DEFAULT_STABLE_WALKS_SUMMARY = Path("output/tex_micro_stable_walks/summary.csv")
DEFAULT_STABLE_WALKS_GROUPS = Path("output/tex_micro_stable_walks/groups.csv")
DEFAULT_STABLE_BACKREFS_SUMMARY = Path("output/tex_micro_stable_backrefs/summary.csv")
DEFAULT_STABLE_SOURCES_SUMMARY = Path("output/tex_micro_stable_sources/summary.csv")
DEFAULT_STABLE_SOURCE_GRAMMAR_SUMMARY = Path("output/tex_micro_stable_source_grammar/summary.csv")
DEFAULT_STABLE_VALUE_CONTEXT_SUMMARY = Path("output/tex_micro_stable_value_context/summary.csv")
DEFAULT_STABLE_CONTEXT_RULES_SUMMARY = Path("output/tex_micro_stable_context_rules/summary.csv")
DEFAULT_STABLE_SEQUENCES_SUMMARY = Path("output/tex_micro_stable_sequences/summary.csv")
DEFAULT_STABLE_ALTERNATION_SUMMARY = Path("output/tex_micro_stable_alternation/summary.csv")

QUEUE_FIELDNAMES = [
    "priority",
    "track",
    "surface",
    "rows",
    "bytes",
    "promotion_ready_bytes",
    "signal_score",
    "status",
    "next_action",
    "positive_evidence",
    "blocking_evidence",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "decision_rows",
    "total_bytes",
    "promotion_ready_bytes",
    "blocked_rows",
    "blocked_bytes",
    "tracks",
    "top_track",
    "top_surface",
    "top_action",
    "issue_rows",
]


TRACK_RULES = [
    ("gradient", ("gradient", "seed", "delta")),
    ("flat_walk", ("flat", "plateau", "palette")),
    ("jump", ("jump", "nibble", "dense", "residual")),
    ("mixed_token", ("mixed_token", "mixed-token", "band")),
    ("control", ("control", "signal", "phase", "payload")),
    ("direction_value", ("direction_value", "direction-value", "value")),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def classify_track(row: dict[str, str]) -> str:
    surface = row.get("surface", "").lower()
    if surface.startswith("mixed_token"):
        return "mixed_token"
    if surface.startswith("jump") or surface.startswith("dense") or surface.startswith("residual"):
        return "jump"
    if surface.startswith("direction_value"):
        return "direction_value"
    if surface.startswith("flat_walk"):
        return "flat_walk"
    if surface.startswith("gradient"):
        return "gradient"
    if "control" in surface or "signal" in surface:
        return "control"

    text = " ".join(
        [
            surface,
            row.get("next_action", ""),
            row.get("positive_evidence", ""),
            row.get("blocking_evidence", ""),
        ]
    ).lower()
    for track, needles in TRACK_RULES:
        if any(needle in text for needle in needles):
            return track
    return "general"


def signal_score(row: dict[str, str]) -> int:
    positive = row.get("positive_evidence", "").lower()
    blocking = row.get("blocking_evidence", "").lower()
    score = 0
    for word, weight in [
        ("repeated", 8),
        ("copy_unlock", 7),
        ("copy_distance", 6),
        ("candidate", 5),
        ("exact", 4),
        ("ge75", 3),
        ("dominant", 2),
    ]:
        score += positive.count(word) * weight
    for word, weight in [
        ("promotion_ready=0", 8),
        ("conflicted", 5),
        ("false", 5),
        ("singleton", 3),
        ("reject", 3),
    ]:
        score -= blocking.count(word) * weight
    return score


def build_queue(decisions: list[dict[str, str]]) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for row in decisions:
        ready = int_value(row, "promotion_ready_bytes")
        bytes_ = int_value(row, "bytes")
        status = "promotion_ready" if ready > 0 else "blocked_review"
        enriched.append(
            {
                "priority": 0,
                "track": classify_track(row),
                "surface": row.get("surface", ""),
                "rows": int_value(row, "rows"),
                "bytes": bytes_,
                "promotion_ready_bytes": ready,
                "signal_score": signal_score(row),
                "status": status,
                "next_action": row.get("next_action", ""),
                "positive_evidence": row.get("positive_evidence", ""),
                "blocking_evidence": row.get("blocking_evidence", ""),
            }
        )

    enriched.sort(
        key=lambda row: (
            str(row["surface"]) != "noisy_all",
            int(row["promotion_ready_bytes"]) > 0,
            int(row["bytes"]),
            int(row["signal_score"]),
            str(row["surface"]),
        ),
        reverse=True,
    )
    for index, row in enumerate(enriched, start=1):
        row["priority"] = index
    return enriched


def build_stable_walk_decision(
    summary: dict[str, str],
    groups: list[dict[str, str]],
    backref_summary: dict[str, str] | None,
    source_summary: dict[str, str] | None,
    source_grammar_summary: dict[str, str] | None,
    value_context_summary: dict[str, str] | None,
    context_rules_summary: dict[str, str] | None,
    sequence_summary: dict[str, str] | None,
    alternation_summary: dict[str, str] | None,
) -> dict[str, str] | None:
    repeated_bytes = int_value(summary, "repeated_signature_bytes")
    copy_bytes = int_value(summary, "copy_distance_320_bytes")
    if repeated_bytes <= 0:
        return None

    strongest = groups[0] if groups else {}
    positive = [
        f"repeated_signature_bytes={repeated_bytes}",
        f"exact_repeat_bytes={int_value(summary, 'exact_repeat_bytes')}",
        f"copy_distance_320_bytes={copy_bytes}",
    ]
    if strongest:
        positive.append(f"top_signature={strongest.get('signed_shape_key', '')}")
        positive.append(f"top_offsets={strongest.get('start_offsets', '')}")

    blocking = ["source_control_unresolved", "promotion_ready=0"]
    if backref_summary:
        positive.append(f"backref_distance={backref_summary.get('best_distance', '')}")
        positive.append(f"backref_exact_bytes={backref_summary.get('distance_320_exact_bytes', '0')}")
        blocking.append(f"backref_known_source_bytes={backref_summary.get('distance_320_known_source_bytes', '0')}")
    if source_summary:
        blocking.append(f"source_probe_best_exact_bytes={source_summary.get('best_exact_bytes_total', '0')}")
        blocking.append(f"source_probe_full_matches={source_summary.get('full_match_rows', '0')}")
    if source_grammar_summary:
        positive.append(f"source_grammar_value_hit_bytes={source_grammar_summary.get('local_value_hit_bytes', '0')}")
        blocking.append(f"source_grammar_literal_run_bytes={source_grammar_summary.get('local_repeated_literal_bytes', '0')}")
    if value_context_summary:
        positive.append(f"value_context_repeated_bytes={value_context_summary.get('repeated_context_bytes', '0')}")
        positive.append(f"value_context_repeated_shape_bytes={value_context_summary.get('repeated_shape_bytes', '0')}")
        blocking.append(
            f"value_context_repeated_value_length_bytes="
            f"{value_context_summary.get('repeated_value_length_context_bytes', '0')}"
        )
        blocking.append(
            f"value_context_repeated_value_length_shape_bytes="
            f"{value_context_summary.get('repeated_value_length_shape_bytes', '0')}"
        )
    if context_rules_summary:
        positive.append(
            f"context_rule_deterministic_exact_bytes="
            f"{context_rules_summary.get('deterministic_context_exact_bytes', '0')}"
        )
        blocking.append(f"context_rule_conflicted_bytes={context_rules_summary.get('conflicted_rule_bytes', '0')}")
    if sequence_summary:
        positive.append(
            f"sequence_shape_step_bytes={sequence_summary.get('deterministic_shape_offset_step_bytes', '0')}"
        )
        blocking.append(f"sequence_transition_bytes={sequence_summary.get('transition_bytes', '0')}")
    if alternation_summary:
        positive.append(f"alternating_suffix_bytes={alternation_summary.get('suffix_alternating_bytes', '0')}")
        blocking.append(f"alternating_run_bytes={alternation_summary.get('run_bytes', '0')}")

    return {
        "surface": "micro_token_stable_walks",
        "rows": summary.get("repeated_signature_rows", "0"),
        "bytes": str(repeated_bytes),
        "promotion_ready_bytes": "0",
        "next_action": "map the +320 exact repeats to a source/control pair before promoting a copy rule",
        "positive_evidence": "; ".join(value for value in positive if value),
        "blocking_evidence": "; ".join(blocking),
    }


def append_optional_stable_walk_decision(
    decisions: list[dict[str, str]],
    summary_path: Path,
    groups_path: Path,
    backrefs_summary_path: Path,
    sources_summary_path: Path,
    source_grammar_summary_path: Path,
    value_context_summary_path: Path,
    context_rules_summary_path: Path,
    sequence_summary_path: Path,
    alternation_summary_path: Path,
) -> list[dict[str, str]]:
    if not summary_path.exists() or not groups_path.exists():
        return decisions
    summary_rows = read_rows(summary_path)
    if not summary_rows:
        return decisions
    backref_summary_rows = read_rows(backrefs_summary_path) if backrefs_summary_path.exists() else []
    backref_summary = backref_summary_rows[0] if backref_summary_rows else None
    source_summary_rows = read_rows(sources_summary_path) if sources_summary_path.exists() else []
    source_summary = source_summary_rows[0] if source_summary_rows else None
    source_grammar_summary_rows = (
        read_rows(source_grammar_summary_path) if source_grammar_summary_path.exists() else []
    )
    source_grammar_summary = source_grammar_summary_rows[0] if source_grammar_summary_rows else None
    value_context_summary_rows = read_rows(value_context_summary_path) if value_context_summary_path.exists() else []
    value_context_summary = value_context_summary_rows[0] if value_context_summary_rows else None
    context_rules_summary_rows = read_rows(context_rules_summary_path) if context_rules_summary_path.exists() else []
    context_rules_summary = context_rules_summary_rows[0] if context_rules_summary_rows else None
    sequence_summary_rows = read_rows(sequence_summary_path) if sequence_summary_path.exists() else []
    sequence_summary = sequence_summary_rows[0] if sequence_summary_rows else None
    alternation_summary_rows = read_rows(alternation_summary_path) if alternation_summary_path.exists() else []
    alternation_summary = alternation_summary_rows[0] if alternation_summary_rows else None
    decision = build_stable_walk_decision(
        summary_rows[0],
        read_rows(groups_path),
        backref_summary,
        source_summary,
        source_grammar_summary,
        value_context_summary,
        context_rules_summary,
        sequence_summary,
        alternation_summary,
    )
    if decision is None:
        return decisions
    return [*decisions, decision]


def build_summary(queue: list[dict[str, object]], review_summary: dict[str, str]) -> dict[str, object]:
    tracks = Counter(str(row["track"]) for row in queue)
    bytes_by_track = Counter()
    for row in queue:
        bytes_by_track[str(row["track"])] += int(row["bytes"])
    top = queue[0] if queue else {}
    blocked = [row for row in queue if row["status"] == "blocked_review"]
    top_track = bytes_by_track.most_common(1)[0][0] if bytes_by_track else ""
    return {
        "scope": "total",
        "decision_rows": len(queue),
        "total_bytes": sum(int(row["bytes"]) for row in queue),
        "promotion_ready_bytes": sum(int(row["promotion_ready_bytes"]) for row in queue),
        "blocked_rows": len(blocked),
        "blocked_bytes": sum(int(row["bytes"]) for row in blocked),
        "tracks": json.dumps(dict(sorted(tracks.items())), sort_keys=True),
        "top_track": top_track,
        "top_surface": top.get("surface", ""),
        "top_action": top.get("next_action", ""),
        "issue_rows": review_summary.get("issue_rows", "0"),
    }


def render_table(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row['priority']))}</td>"
            f"<td>{html.escape(str(row['track']))}</td>"
            f"<td>{html.escape(str(row['surface']))}</td>"
            f"<td>{html.escape(str(row['bytes']))}</td>"
            f"<td>{html.escape(str(row['signal_score']))}</td>"
            f"<td>{html.escape(str(row['status']))}</td>"
            f"<td>{html.escape(str(row['next_action']))}</td>"
            "</tr>"
        )
    return "\n".join(body)


def build_html(summary: dict[str, object], queue: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "queue": queue}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #111; color: #eee; }}
a {{ color: #8bd3ff; }}
table {{ border-collapse: collapse; width: 100%; background: #181818; }}
th, td {{ border: 1px solid #333; padding: .45rem .55rem; vertical-align: top; }}
th {{ background: #222; text-align: left; }}
.metric {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ background: #181818; border: 1px solid #333; padding: .75rem; }}
.num {{ font-size: 1.4rem; font-weight: 700; }}
.muted {{ color: #aaa; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="metric">
  <div class="box"><div class="num">{html.escape(str(summary['decision_rows']))}</div><div class="muted">decisions</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['total_bytes']))}</div><div class="muted">bytes revus</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['promotion_ready_bytes']))}</div><div class="muted">bytes promotables</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['blocked_rows']))}</div><div class="muted">lignes bloquees</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['top_track']))}</div><div class="muted">piste dominante</div></div>
</div>
<p>Prochaine action: <strong>{html.escape(str(summary['top_action']))}</strong></p>
<table>
<thead>
<tr><th>#</th><th>Piste</th><th>Surface</th><th>Bytes</th><th>Signal</th><th>Etat</th><th>Action</th></tr>
</thead>
<tbody>
{render_table(queue)}
</tbody>
</table>
<script type="application/json" id="roadmap-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a prioritized .tex decoder roadmap.")
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--stable-walks-summary", type=Path, default=DEFAULT_STABLE_WALKS_SUMMARY)
    parser.add_argument("--stable-walks-groups", type=Path, default=DEFAULT_STABLE_WALKS_GROUPS)
    parser.add_argument("--stable-backrefs-summary", type=Path, default=DEFAULT_STABLE_BACKREFS_SUMMARY)
    parser.add_argument("--stable-sources-summary", type=Path, default=DEFAULT_STABLE_SOURCES_SUMMARY)
    parser.add_argument("--stable-source-grammar-summary", type=Path, default=DEFAULT_STABLE_SOURCE_GRAMMAR_SUMMARY)
    parser.add_argument("--stable-value-context-summary", type=Path, default=DEFAULT_STABLE_VALUE_CONTEXT_SUMMARY)
    parser.add_argument("--stable-context-rules-summary", type=Path, default=DEFAULT_STABLE_CONTEXT_RULES_SUMMARY)
    parser.add_argument("--stable-sequences-summary", type=Path, default=DEFAULT_STABLE_SEQUENCES_SUMMARY)
    parser.add_argument("--stable-alternation-summary", type=Path, default=DEFAULT_STABLE_ALTERNATION_SUMMARY)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Roadmap")
    args = parser.parse_args()

    decisions = append_optional_stable_walk_decision(
        read_rows(args.decisions),
        args.stable_walks_summary,
        args.stable_walks_groups,
        args.stable_backrefs_summary,
        args.stable_sources_summary,
        args.stable_source_grammar_summary,
        args.stable_value_context_summary,
        args.stable_context_rules_summary,
        args.stable_sequences_summary,
        args.stable_alternation_summary,
    )
    review_summary = read_rows(args.review_summary)[0]
    queue = build_queue(decisions)
    summary = build_summary(queue, review_summary)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "queue.csv", QUEUE_FIELDNAMES, queue)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, queue, args.title))

    print(f"Roadmap decisions: {summary['decision_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Top track: {summary['top_track']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
