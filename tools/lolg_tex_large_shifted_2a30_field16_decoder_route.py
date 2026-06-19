#!/usr/bin/env python3
"""Route integrated shifted 0x2a30 field16 decoder rows to rejected large segments."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_field16_decoder_route")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_DECODER_ROWS = Path("output/tex_large_shifted_2a30_field16_decoder_integration/decoder_rows.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "profile_segment_rows",
    "shifted_2a30_segment_rows",
    "integrated_decoder_rows",
    "integrated_large_rows",
    "routed_large_rows",
    "routed_exact_rows",
    "branch_rows",
    "branch_blocked_rows",
    "non_2a30_rows",
    "missing_segment_rows",
    "route_rows",
    "issue_rows",
    "review_verdict",
    "next_action",
]

ROUTE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "segment_size",
    "body_first_word",
    "control_path",
    "pair_2a30_offset",
    "decoder_rule",
    "decoder_extra",
    "decoder_status",
    "decoder_exact",
    "target_promoted",
    "route_status",
    "route_priority",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("archive_tag", ""), row.get("pcx_name", "").lower()


def segment_is_shifted_2a30(row: dict[str, str]) -> bool:
    return row.get("control_path") == "shifted_2a30_header"


def build_route_rows(
    segment_rows: list[dict[str, str]],
    decoder_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    integrated_large = {
        row_key(row): row
        for row in decoder_rows
        if row.get("large_rejected") == "yes" and row.get("decoder_status") == "decoded_exact"
    }
    rows: list[dict[str, str]] = []
    seen_integrated: set[tuple[str, str]] = set()
    for segment in segment_rows:
        key = row_key(segment)
        decoder = integrated_large.get(key, {})
        issues: list[str] = []
        if decoder:
            seen_integrated.add(key)
            route_status = "routed_field16_decoder"
            route_priority = "materialize_shifted_2a30_preview"
            if not segment_is_shifted_2a30(segment):
                issues.append("routed_non_shifted_2a30_segment")
            if decoder.get("exact_match") != "yes":
                issues.append("decoder_not_exact")
        elif segment_is_shifted_2a30(segment):
            route_status = "blocked_shifted_2a30_branch"
            route_priority = "derive_shifted_2a30_branch_decoder"
        else:
            route_status = "outside_field16_decoder_scope"
            route_priority = "profile_other_large_decoder_family"

        rows.append(
            {
                "archive": segment.get("archive", ""),
                "archive_tag": segment.get("archive_tag", ""),
                "texture_path": segment.get("texture_path", ""),
                "pcx_name": segment.get("pcx_name", ""),
                "segment_index": segment.get("segment_index", ""),
                "body_offset": segment.get("body_offset", ""),
                "body_offset_hex": segment.get("body_offset_hex", ""),
                "segment_size": segment.get("segment_size", ""),
                "body_first_word": segment.get("body_first_word", ""),
                "control_path": segment.get("control_path", ""),
                "pair_2a30_offset": segment.get("pair_2a30_offset", ""),
                "decoder_rule": decoder.get("decoder_rule", ""),
                "decoder_extra": decoder.get("decoder_extra", ""),
                "decoder_status": decoder.get("decoder_status", ""),
                "decoder_exact": decoder.get("exact_match", ""),
                "target_promoted": decoder.get("target_promoted", ""),
                "route_status": route_status,
                "route_priority": route_priority,
                "issues": "|".join(issues),
            }
        )

    missing = sorted(set(integrated_large) - seen_integrated)
    for archive_tag, pcx_name in missing:
        decoder = integrated_large[(archive_tag, pcx_name)]
        rows.append(
            {
                "archive": "",
                "archive_tag": archive_tag,
                "texture_path": "",
                "pcx_name": decoder.get("pcx_name", pcx_name),
                "segment_index": "",
                "body_offset": "",
                "body_offset_hex": "",
                "segment_size": "",
                "body_first_word": "",
                "control_path": "",
                "pair_2a30_offset": "",
                "decoder_rule": decoder.get("decoder_rule", ""),
                "decoder_extra": decoder.get("decoder_extra", ""),
                "decoder_status": decoder.get("decoder_status", ""),
                "decoder_exact": decoder.get("exact_match", ""),
                "target_promoted": decoder.get("target_promoted", ""),
                "route_status": "missing_profile_segment",
                "route_priority": "fix_profile_join",
                "issues": "missing_profile_segment",
            }
        )

    return sorted(rows, key=lambda row: (row["route_priority"], row["archive_tag"], row["pcx_name"].lower()))


def build_summary(
    segment_rows: list[dict[str, str]],
    decoder_rows: list[dict[str, str]],
    route_rows: list[dict[str, str]],
) -> dict[str, str]:
    shifted_rows = [row for row in segment_rows if segment_is_shifted_2a30(row)]
    integrated_rows = [row for row in decoder_rows if row.get("decoder_status") == "decoded_exact"]
    integrated_large_rows = [row for row in integrated_rows if row.get("large_rejected") == "yes"]
    routed_rows = [row for row in route_rows if row.get("route_status") == "routed_field16_decoder"]
    routed_exact = [row for row in routed_rows if row.get("decoder_exact") == "yes"]
    branch_rows = [row for row in route_rows if row.get("route_status") == "blocked_shifted_2a30_branch"]
    non_2a30_rows = [row for row in route_rows if row.get("route_status") == "outside_field16_decoder_scope"]
    missing_rows = [row for row in route_rows if row.get("route_status") == "missing_profile_segment"]
    issue_rows = [row for row in route_rows if row.get("issues")]
    clean = (
        len(segment_rows) == 9
        and len(shifted_rows) == 5
        and len(integrated_rows) == 6
        and len(integrated_large_rows) == 4
        and len(routed_rows) == 4
        and len(routed_exact) == 4
        and len(branch_rows) == 1
        and len(non_2a30_rows) == 4
        and not missing_rows
        and not issue_rows
    )
    if clean:
        verdict = "field16_decoder_route_ready"
        next_action = "materialize routed shifted 0x2a30 field16 decoder previews for 4 large .tex segments"
    elif issue_rows:
        verdict = "field16_decoder_route_issues"
        next_action = "fix shifted 0x2a30 field16 decoder route issues"
    else:
        verdict = "field16_decoder_route_incomplete"
        next_action = "complete shifted 0x2a30 field16 decoder route coverage"
    return {
        "scope": "total",
        "profile_segment_rows": str(len(segment_rows)),
        "shifted_2a30_segment_rows": str(len(shifted_rows)),
        "integrated_decoder_rows": str(len(integrated_rows)),
        "integrated_large_rows": str(len(integrated_large_rows)),
        "routed_large_rows": str(len(routed_rows)),
        "routed_exact_rows": str(len(routed_exact)),
        "branch_rows": str(len(branch_rows)),
        "branch_blocked_rows": str(len(branch_rows)),
        "non_2a30_rows": str(len(non_2a30_rows)),
        "missing_segment_rows": str(len(missing_rows)),
        "route_rows": str(len(route_rows)),
        "issue_rows": str(len(issue_rows)),
        "review_verdict": verdict,
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    route_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "routes": route_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("routes.csv", output_dir / "routes.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 420px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Routes integrated shifted 0x2a30 field16 decoder rows onto rejected large .tex profile segments.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Routes</h2>
{render_table(route_rows, ROUTE_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_ROUTE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    segments_path: Path,
    decoder_rows_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    segment_rows = read_csv(segments_path)
    decoder_rows = read_csv(decoder_rows_path)
    route_rows = build_route_rows(segment_rows, decoder_rows)
    summary = build_summary(segment_rows, decoder_rows, route_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "routes.csv", ROUTE_FIELDNAMES, route_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, route_rows, output_dir, title),
        encoding="utf-8",
    )
    return summary, route_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Route shifted 0x2a30 field16 decoder rows.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--decoder-rows", type=Path, default=DEFAULT_DECODER_ROWS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Field16 Decoder Route",
    )
    args = parser.parse_args()

    summary, _route_rows = write_report(args.output, args.segments, args.decoder_rows, args.title)
    print(f"Profile segment rows: {summary['profile_segment_rows']}")
    print(f"Routed exact rows: {summary['routed_exact_rows']}/{summary['routed_large_rows']}")
    print(f"Branch blocked rows: {summary['branch_blocked_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
