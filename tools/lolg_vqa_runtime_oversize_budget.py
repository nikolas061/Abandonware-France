#!/usr/bin/env python3
"""Quantify the remaining VQA runtime MIX body-size oversize budget."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_PACK_BUILD = Path("output/vqa_runtime_pack_build")
DEFAULT_OUTPUT = Path("output/vqa_runtime_oversize_budget")
MAX_MIX_FIELD = 0xFFFFFFFF

SUMMARY_FIELDS = [
    "status",
    "archives",
    "oversize_archives",
    "deferred_replacements",
    "projected_body_bytes",
    "max_body_bytes",
    "headroom_bytes",
    "deferred_source_bytes",
    "deferred_replacement_bytes",
    "deferred_delta_bytes",
    "required_reduction_bytes",
    "largest_deferred_replacement_bytes",
    "largest_deferred_delta_bytes",
    "issues",
    "next_step",
]

ARCHIVE_FIELDS = [
    "archive",
    "deferred_replacements",
    "applied_replacements",
    "missing_replacements",
    "projected_body_bytes",
    "max_body_bytes",
    "headroom_bytes",
    "output_bytes",
    "deferred_source_bytes",
    "deferred_replacement_bytes",
    "deferred_delta_bytes",
    "required_reduction_bytes",
    "required_reduction_ratio",
    "largest_entry",
    "largest_deferred_replacement_bytes",
    "largest_deferred_delta_bytes",
    "issues",
    "next_step",
]

ENTRY_FIELDS = [
    "archive",
    "index",
    "file_id",
    "source_size",
    "replacement_size",
    "size_delta",
    "projected_body_bytes",
    "max_body_bytes",
    "headroom_bytes",
    "archive_required_reduction_bytes",
    "replacement_path",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "0") or 0)
    except ValueError:
        return 0


def parse_issue_number(issue_text: str, field: str, default: int = 0) -> int:
    for issue in issue_text.split(";"):
        parts = issue.split(":")
        for index, part in enumerate(parts[:-1]):
            if part != field:
                continue
            try:
                return int(parts[index + 1])
            except ValueError:
                return default
    return default


def ratio_text(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000"
    return f"{numerator / denominator:.6f}"


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    archive_source_rows = read_csv(args.archives)
    entry_source_rows = read_csv(args.entries)
    archive_by_name = {row.get("archive", ""): row for row in archive_source_rows if row.get("archive")}
    deferred_by_archive: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in entry_source_rows:
        if row.get("status") != "replacement_deferred_oversize":
            continue
        archive = row.get("archive", "")
        if archive:
            deferred_by_archive[archive].append(row)

    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    issues: list[str] = []

    for archive, deferred_rows in sorted(deferred_by_archive.items()):
        archive_info = archive_by_name.get(archive, {})
        issue_text = archive_info.get("issues", "") or ";".join(row.get("issues", "") for row in deferred_rows)
        projected_body = parse_issue_number(issue_text, "projected_body")
        max_body = parse_issue_number(issue_text, "max", MAX_MIX_FIELD) or MAX_MIX_FIELD
        headroom = max_body - projected_body if projected_body else 0
        deferred_source = sum(int_value(row, "source_size") for row in deferred_rows)
        deferred_replacement = sum(int_value(row, "replacement_size") for row in deferred_rows)
        deferred_delta = sum(int_value(row, "size_delta") for row in deferred_rows)
        required_reduction = max(0, deferred_delta - max(0, headroom))
        largest_row = max(deferred_rows, key=lambda row: int_value(row, "replacement_size"))
        largest_replacement = int_value(largest_row, "replacement_size")
        largest_delta = int_value(largest_row, "size_delta")
        largest_entry = f"{largest_row.get('index', '')}:{largest_row.get('file_id', '')}"
        if required_reduction:
            issues.append(f"{Path(archive).name}:required_reduction:{required_reduction}")

        archive_row = {
            "archive": archive,
            "deferred_replacements": str(len(deferred_rows)),
            "applied_replacements": archive_info.get("applied_replacements", ""),
            "missing_replacements": archive_info.get("missing_replacements", ""),
            "projected_body_bytes": str(projected_body),
            "max_body_bytes": str(max_body),
            "headroom_bytes": str(max(0, headroom)),
            "output_bytes": archive_info.get("output_bytes", ""),
            "deferred_source_bytes": str(deferred_source),
            "deferred_replacement_bytes": str(deferred_replacement),
            "deferred_delta_bytes": str(deferred_delta),
            "required_reduction_bytes": str(required_reduction),
            "required_reduction_ratio": ratio_text(required_reduction, deferred_replacement),
            "largest_entry": largest_entry,
            "largest_deferred_replacement_bytes": str(largest_replacement),
            "largest_deferred_delta_bytes": str(largest_delta),
            "issues": issue_text,
            "next_step": "re-encode deferred WVQA payloads smaller or provide a runtime override that avoids the 32-bit MIX body limit",
        }
        archive_rows.append(archive_row)

        for row in sorted(deferred_rows, key=lambda item: int_value(item, "replacement_size"), reverse=True):
            entry_rows.append(
                {
                    "archive": archive,
                    "index": row.get("index", ""),
                    "file_id": row.get("file_id", ""),
                    "source_size": row.get("source_size", ""),
                    "replacement_size": row.get("replacement_size", ""),
                    "size_delta": row.get("size_delta", ""),
                    "projected_body_bytes": str(projected_body),
                    "max_body_bytes": str(max_body),
                    "headroom_bytes": str(max(0, headroom)),
                    "archive_required_reduction_bytes": str(required_reduction),
                    "replacement_path": row.get("replacement_path", ""),
                    "issues": row.get("issues", ""),
                }
            )

    total_deferred_source = sum(int_value(row, "deferred_source_bytes") for row in archive_rows)
    total_deferred_replacement = sum(int_value(row, "deferred_replacement_bytes") for row in archive_rows)
    total_deferred_delta = sum(int_value(row, "deferred_delta_bytes") for row in archive_rows)
    total_required_reduction = sum(int_value(row, "required_reduction_bytes") for row in archive_rows)
    total_headroom = sum(int_value(row, "headroom_bytes") for row in archive_rows)
    total_projected_body = sum(int_value(row, "projected_body_bytes") for row in archive_rows)
    largest_replacement = max((int_value(row, "largest_deferred_replacement_bytes") for row in archive_rows), default=0)
    largest_delta = max((int_value(row, "largest_deferred_delta_bytes") for row in archive_rows), default=0)

    if not archive_source_rows or not entry_source_rows:
        issues.append("missing_runtime_pack_build_csv")

    summary = {
        "status": "pass" if not deferred_by_archive and not issues else "gap",
        "archives": str(len(archive_source_rows)),
        "oversize_archives": str(len(archive_rows)),
        "deferred_replacements": str(sum(int_value(row, "deferred_replacements") for row in archive_rows)),
        "projected_body_bytes": str(total_projected_body),
        "max_body_bytes": str(MAX_MIX_FIELD * len(archive_rows)),
        "headroom_bytes": str(total_headroom),
        "deferred_source_bytes": str(total_deferred_source),
        "deferred_replacement_bytes": str(total_deferred_replacement),
        "deferred_delta_bytes": str(total_deferred_delta),
        "required_reduction_bytes": str(total_required_reduction),
        "largest_deferred_replacement_bytes": str(largest_replacement),
        "largest_deferred_delta_bytes": str(largest_delta),
        "issues": ";".join(issues),
        "next_step": "reduce deferred WVQA payload sizes by at least required_reduction_bytes, or implement a runtime loader/pack strategy that does not depend on one 32-bit MIX body",
    }
    return summary, archive_rows, entry_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(
    path: Path,
    summary: dict[str, str],
    archives: list[dict[str, str]],
    entries: list[dict[str, str]],
) -> None:
    payload = {
        "summary": summary,
        "archives": archives,
        "entries_sample": entries[:200],
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOLG VQA Runtime Oversize Budget</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; overflow-wrap: anywhere; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1040px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>LOLG VQA Runtime Oversize Budget</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Archives oversized</div><div class="value">{html.escape(summary['oversize_archives'])}</div></div>
    <div class="stat"><div class="label">Remplacements differes</div><div class="value">{html.escape(summary['deferred_replacements'])}</div></div>
    <div class="stat"><div class="label">Reduction requise</div><div class="value">{html.escape(summary['required_reduction_bytes'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Archives</h2>{render_table(archives, ARCHIVE_FIELDS)}</section>
  <section class="panel"><h2>Entrees oversized</h2>{render_table(entries, ENTRY_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-runtime-oversize-budget">{html.escape(data_json)}</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantify VQA runtime MIX oversize deferrals.")
    parser.add_argument("--archives", type=Path, default=DEFAULT_PACK_BUILD / "archives.csv")
    parser.add_argument("--entries", type=Path, default=DEFAULT_PACK_BUILD / "entries.csv")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    summary, archives, entries = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "archives.csv", ARCHIVE_FIELDS, archives)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entries)
    write_html(args.output / "index.html", summary, archives, entries)

    print(
        "VQA runtime oversize budget: "
        f"{summary['status']} "
        f"oversize_archives={summary['oversize_archives']} "
        f"deferred={summary['deferred_replacements']} "
        f"required_reduction_bytes={summary['required_reduction_bytes']} "
        f"output={args.output / 'index.html'}"
    )
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
