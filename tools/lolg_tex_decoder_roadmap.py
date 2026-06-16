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
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Roadmap")
    args = parser.parse_args()

    decisions = read_rows(args.decisions)
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
