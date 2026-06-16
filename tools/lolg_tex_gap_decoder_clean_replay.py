#!/usr/bin/env python3
"""Replay only promoted .tex gap decoder decisions into clean fixture buffers."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_decoder_seed_replay import (
    TARGET_SIZE,
    exact_byte_count,
    fixture_key,
    fixture_sort_key,
    frontier_lookup,
    load_bytes,
    render_preview,
    safe_stem,
)


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_clean_replay")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_QUEUE = Path("output/tex_gap_decoder_false_risk_queue/queue.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "queue_rows",
    "promoted_ops",
    "rejected_ops",
    "selected_bytes",
    "clean_bytes",
    "rejected_false_bytes",
    "false_bytes",
    "output_exact_bytes",
    "unselected_bytes",
    "native_previews",
    "fullhd_previews",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "queue_ops",
    "promoted_ops",
    "rejected_ops",
    "selected_bytes",
    "clean_bytes",
    "rejected_false_bytes",
    "false_bytes",
    "output_exact_bytes",
    "unselected_bytes",
    "decoded_path",
    "known_mask_path",
    "accepted_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

DECISION_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "op_kind",
    "expected_start",
    "expected_end",
    "length",
    "seed_decision",
    "risk_class",
    "queue_verdict",
    "promotion_selector",
    "promotion_signature",
    "clean_decision",
    "selected_bytes",
    "clean_bytes",
    "rejected_false_bytes",
    "false_bytes",
    "output_exact_bytes",
    "source_offset",
    "source_end",
    "token_value",
    "token_plus3_match",
    "pre4_hex",
    "next2_hex",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def queue_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def selected_output(row: dict[str, str], segment: bytes, issues: list[str]) -> bytes:
    row_length = int_value(row, "length")
    decision = row.get("seed_decision", "") or row.get("decision", "")
    if decision == "zero":
        return b"\x00" * row_length
    if decision != "literal":
        issues.append("unsupported_clean_decision")
        return b""
    source_offset = int_value(row, "source_offset")
    source_end = int_value(row, "source_end")
    if source_end <= source_offset:
        issues.append("invalid_literal_source_range")
        return b""
    output = segment[source_offset:source_end]
    if len(output) != row_length:
        issues.append("literal_source_length_mismatch")
    return output[:row_length]


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    queue_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    queue_by_fixture: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in queue_rows:
        queue_by_fixture[queue_key(row)].append(row)

    frontiers = frontier_lookup(frontier_rows)
    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    all_fixture_rows: list[dict[str, str]] = []
    all_decision_rows: list[dict[str, str]] = []
    issue_rows = 0

    for fixture in sorted(fixture_rows, key=lambda row: fixture_sort_key(fixture_key(row))):
        key = fixture_key(fixture)
        fixture_issues: list[str] = []
        expected = load_bytes(fixture.get("expected_gap_path", ""), fixture_issues, "expected")
        segment = load_bytes(fixture.get("segment_gap_path", ""), fixture_issues, "segment")
        decoded = bytearray(len(expected))
        known_mask = bytearray(len(expected))
        accepted_mask = bytearray(len(expected))
        stats = {
            "queue_ops": 0,
            "promoted_ops": 0,
            "rejected_ops": 0,
            "selected_bytes": 0,
            "clean_bytes": 0,
            "rejected_false_bytes": 0,
            "false_bytes": 0,
            "output_exact_bytes": 0,
        }

        for row in sorted(queue_by_fixture.get(key, []), key=lambda item: int_value(item, "op_index")):
            op_issues: list[str] = []
            verdict = row.get("verdict", "")
            row_length = int_value(row, "length")
            expected_start = int_value(row, "expected_start")
            expected_end = int_value(row, "expected_end")
            expected_slice = expected[expected_start:expected_end]
            if expected_end - expected_start != row_length:
                op_issues.append("expected_range_length_mismatch")
            if len(expected_slice) != row_length:
                op_issues.append("expected_slice_length_mismatch")

            selected_bytes = int_value(row, "selected_bytes")
            clean_bytes = 0
            rejected_false = 0
            false_bytes = 0
            output_exact = 0
            clean_decision = ""
            if verdict == "promoted":
                clean_decision = row.get("decision", "")
                output = selected_output(row, segment, op_issues)
                if len(output) != row_length:
                    output = output + (b"\x00" * max(0, row_length - len(output)))
                output_exact = exact_byte_count(output, expected_slice)
                clean_bytes = row_length
                if expected_start < len(decoded):
                    end = min(expected_end, len(decoded))
                    write_size = max(0, end - expected_start)
                    decoded[expected_start:end] = output[:write_size]
                    known_mask[expected_start:end] = b"\xff" * write_size
                    accepted_mask[expected_start:end] = b"\xff" * write_size
            elif verdict == "reject_false_risk":
                rejected_false = int_value(row, "false_bytes")
            else:
                false_bytes = int_value(row, "false_bytes")
                op_issues.append(f"unexpected_queue_verdict:{verdict}")

            stats["queue_ops"] += 1
            stats["selected_bytes"] += selected_bytes
            stats["clean_bytes"] += clean_bytes
            stats["rejected_false_bytes"] += rejected_false
            stats["false_bytes"] += false_bytes
            stats["output_exact_bytes"] += output_exact
            if verdict == "promoted":
                stats["promoted_ops"] += 1
            if verdict == "reject_false_risk":
                stats["rejected_ops"] += 1
            if op_issues:
                issue_rows += 1

            all_decision_rows.append(
                {
                    "rank": key[0],
                    "archive": fixture.get("archive", ""),
                    "archive_tag": fixture.get("archive_tag", ""),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "op_index": row.get("op_index", ""),
                    "op_kind": row.get("op_kind", ""),
                    "expected_start": row.get("expected_start", ""),
                    "expected_end": row.get("expected_end", ""),
                    "length": row.get("length", ""),
                    "seed_decision": row.get("decision", ""),
                    "risk_class": row.get("risk_class", ""),
                    "queue_verdict": verdict,
                    "promotion_selector": row.get("promotion_selector", ""),
                    "promotion_signature": row.get("promotion_signature", ""),
                    "clean_decision": clean_decision,
                    "selected_bytes": str(selected_bytes),
                    "clean_bytes": str(clean_bytes),
                    "rejected_false_bytes": str(rejected_false),
                    "false_bytes": str(false_bytes),
                    "output_exact_bytes": str(output_exact),
                    "source_offset": row.get("source_offset", ""),
                    "source_end": row.get("source_end", ""),
                    "token_value": row.get("token_value", ""),
                    "token_plus3_match": row.get("token_plus3_match", ""),
                    "pre4_hex": row.get("pre4_hex", ""),
                    "next2_hex": row.get("next2_hex", ""),
                    "issues": ";".join(op_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(key[0]):03d}" if key[0].isdigit() else f"rank{key[0]}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_clean.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        accepted_mask_path = fixture_output_dir / f"{stem}_accepted_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        accepted_mask_path.write_bytes(accepted_mask)
        native_preview_path = native_preview_dir / f"{stem}_clean_replay.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_clean_replay_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(accepted_mask),
            frontier=frontiers.get((fixture.get("archive", ""), key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        fixture_bytes = len(expected)
        all_fixture_rows.append(
            {
                "rank": key[0],
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "queue_ops": str(stats["queue_ops"]),
                "promoted_ops": str(stats["promoted_ops"]),
                "rejected_ops": str(stats["rejected_ops"]),
                "selected_bytes": str(stats["selected_bytes"]),
                "clean_bytes": str(stats["clean_bytes"]),
                "rejected_false_bytes": str(stats["rejected_false_bytes"]),
                "false_bytes": str(stats["false_bytes"]),
                "output_exact_bytes": str(stats["output_exact_bytes"]),
                "unselected_bytes": str(max(0, fixture_bytes - stats["clean_bytes"])),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "accepted_mask_path": accepted_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    summary = {
        "scope": "total",
        "fixture_rows": str(len(all_fixture_rows)),
        "queue_rows": str(len(all_decision_rows)),
        "promoted_ops": str(sum(int_value(row, "promoted_ops") for row in all_fixture_rows)),
        "rejected_ops": str(sum(int_value(row, "rejected_ops") for row in all_fixture_rows)),
        "selected_bytes": str(sum(int_value(row, "selected_bytes") for row in all_fixture_rows)),
        "clean_bytes": str(sum(int_value(row, "clean_bytes") for row in all_fixture_rows)),
        "rejected_false_bytes": str(
            sum(int_value(row, "rejected_false_bytes") for row in all_fixture_rows)
        ),
        "false_bytes": str(sum(int_value(row, "false_bytes") for row in all_fixture_rows)),
        "output_exact_bytes": str(
            sum(int_value(row, "output_exact_bytes") for row in all_fixture_rows)
        ),
        "unselected_bytes": str(sum(int_value(row, "unselected_bytes") for row in all_fixture_rows)),
        "native_previews": str(sum(1 for row in all_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(
            sum(
                1
                for row in all_fixture_rows
                if (row.get("fullhd_width"), row.get("fullhd_height"))
                == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "issue_rows": str(issue_rows),
    }
    return summary, all_fixture_rows, all_decision_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 180) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def render_preview_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="card-body">
    <div class="card-title">#{html.escape(row.get('rank', ''))} {html.escape(row.get('pcx_name', ''))}</div>
    <div class="muted">{html.escape(row.get('clean_bytes', ''))} clean - {html.escape(row.get('rejected_false_bytes', ''))} rejected</div>
    <a href="{image}">Full HD</a>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "decisions": decision_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("decisions.csv", output_dir / "decisions.csv"),
        )
    )
    cards = "\n".join(render_preview_card(row, output_dir) for row in fixture_rows)
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
  --ok: #80df94;
  --risk: #f0a064;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }}
.stat, .panel, .card {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }}
.stat, .panel {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.risk {{ color: var(--risk); }}
.panel {{ overflow-x: auto; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #07090a; border-bottom: 1px solid var(--line); overflow: hidden; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1380px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Only promoted queue decisions are written to clean fixture buffers.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Clean bytes</div><div class="value ok">{html.escape(summary['clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Rejected false-risk</div><div class="value risk">{html.escape(summary['rejected_false_bytes'])}</div></div>
    <div class="stat"><div class="label">False bytes written</div><div class="value">{html.escape(summary['false_bytes'])}</div></div>
    <div class="stat"><div class="label">Full HD previews</div><div class="value">{html.escape(summary['fullhd_previews'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="cards">{cards}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Decisions</h2>{render_table(decision_rows, DECISION_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_CLEAN_REPLAY = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures_path: Path,
    frontiers_path: Path,
    queue_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, decision_rows = build_rows(
        output_dir=output_dir,
        fixture_rows=read_csv(fixtures_path),
        frontier_rows=read_csv(frontiers_path),
        queue_rows=read_csv(queue_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "decisions.csv", DECISION_FIELDNAMES, decision_rows)
    (output_dir / "index.html").write_text(build_html(summary, fixture_rows, decision_rows, output_dir, title))
    return summary, fixture_rows, decision_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay promoted .tex decoder decisions into clean buffers.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Clean Replay")
    args = parser.parse_args()

    summary, _fixtures, _decisions = write_report(
        args.output,
        args.fixtures,
        args.frontiers,
        args.queue,
        title=args.title,
    )
    print(f"Fixtures: {summary['fixture_rows']}")
    print(f"Clean bytes: {summary['clean_bytes']}")
    print(f"Rejected false-risk bytes: {summary['rejected_false_bytes']}")
    print(f"False bytes written: {summary['false_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
