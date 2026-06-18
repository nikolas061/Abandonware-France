#!/usr/bin/env python3
"""Review the external legacy Lands of Lore II worktree without modifying it."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_LEGACY_ROOT = Path("/media/niko/niko/Abandonware-France/Lands-of-Lore-II")
DEFAULT_OUTPUT = Path("output/external_legacy_media_review")
DEFAULT_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_third_expanded_source_byte_guard_promoted_replay/slots.csv"
)
DEFAULT_FIXTURES = Path("output/tex_old_clean_byte_union_third_expanded_source_byte_guard_promoted_replay/fixtures.csv")
DEFAULT_TRACE_REPORT = Path("C/LOLG/reports/te_cmd20_arg_fields_v9_detail.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "legacy_root",
    "legacy_root_exists",
    "legacy_tools",
    "legacy_reports",
    "missing_tools",
    "changed_tools",
    "missing_reports",
    "changed_reports",
    "unknown_highsafe_slots",
    "top_unknown_edge",
    "top_unknown_edge_slots",
    "legacy_trace_clue_rows",
    "legacy_trace_needed_bytes",
    "issue_rows",
]

MIRROR_FIELDNAMES = [
    "category",
    "name",
    "legacy_path",
    "current_path",
    "legacy_size",
    "current_size",
    "status",
    "legacy_sha256",
    "current_sha256",
]

TOP_FIELDNAMES = ["top_path", "files", "bytes"]

CLUE_FIELDNAMES = [
    "level",
    "name",
    "mode",
    "event_index",
    "stream_pos",
    "x",
    "y",
    "action",
    "arg1",
    "arg2",
    "arg3",
    "next8",
    "matched_needed_bytes",
    "related_unknown_slots",
]


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def top_level_inventory(root: Path) -> list[dict[str, str]]:
    grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    skip_names = {".git", ".codex", ".agents"}
    if not root.exists():
        return []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_names]
        directory = Path(dirpath)
        for filename in filenames:
            path = directory / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue
            relative = path.relative_to(root)
            top = relative.parts[0] if len(relative.parts) > 1 else "."
            grouped[top][0] += 1
            grouped[top][1] += size
    rows = [
        {"top_path": top, "files": str(values[0]), "bytes": str(values[1])}
        for top, values in grouped.items()
    ]
    rows.sort(key=lambda row: (-int(row["bytes"]), row["top_path"]))
    return rows


def compare_named_files(legacy_dir: Path, current_dir: Path, pattern: str, category: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not legacy_dir.exists():
        return rows
    for legacy_path in sorted(path for path in legacy_dir.glob(pattern) if path.is_file()):
        current_path = current_dir / legacy_path.name
        legacy_hash = sha256(legacy_path)
        current_size = ""
        current_hash = ""
        status = "missing_current"
        if current_path.exists():
            current_size = str(current_path.stat().st_size)
            current_hash = sha256(current_path)
            status = "identical" if current_hash == legacy_hash else "changed"
        rows.append(
            {
                "category": category,
                "name": legacy_path.name,
                "legacy_path": legacy_path.as_posix(),
                "current_path": current_path.as_posix(),
                "legacy_size": str(legacy_path.stat().st_size),
                "current_size": current_size,
                "status": status,
                "legacy_sha256": legacy_hash,
                "current_sha256": current_hash,
            }
        )
    return rows


def fixture_level_by_name(fixtures: Path) -> dict[str, str]:
    if not fixtures.exists():
        return {}
    levels: dict[str, str] = {}
    for row in read_csv(fixtures):
        pcx_name = row.get("pcx_name", "")
        archive_tag = row.get("archive_tag", "")
        if pcx_name and archive_tag:
            levels.setdefault(pcx_name, archive_tag)
    return levels


def unknown_highsafe_rows(slots: Path) -> list[dict[str, str]]:
    if not slots.exists():
        return []
    return [
        row
        for row in read_csv(slots)
        if row.get("source_location") == "in_highsafe"
        and row.get("source_availability") == "unknown_source"
        and row.get("source_slot_rank")
    ]


def edge(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def extract_trace_clues(
    trace_report: Path,
    unknown_rows: list[dict[str, str]],
    level_by_name: dict[str, str],
) -> list[dict[str, str]]:
    if not trace_report.exists() or not unknown_rows:
        return []
    needed_by_asset: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in unknown_rows:
        name = row.get("pcx_name", "")
        level = row.get("archive_tag") or level_by_name.get(name, "")
        byte = row.get("source_expected_byte", "").lower()
        if not level or not name or len(byte) != 2:
            continue
        needed_by_asset[(level, name)][byte].append(row.get("rank", ""))

    clues: list[dict[str, str]] = []
    with trace_report.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (row.get("level", ""), row.get("name", ""))
            needed = needed_by_asset.get(key)
            if not needed:
                continue
            values = [row.get("arg1", "").lower(), row.get("arg2", "").lower(), row.get("arg3", "").lower()]
            next8 = row.get("next8", "").lower()
            matched = sorted(byte for byte in needed if byte in values or byte in next8)
            if not matched:
                continue
            related = sorted({rank for byte in matched for rank in needed[byte] if rank})
            clues.append(
                {
                    "level": key[0],
                    "name": key[1],
                    "mode": row.get("mode", ""),
                    "event_index": row.get("event_index", ""),
                    "stream_pos": row.get("stream_pos", ""),
                    "x": row.get("x", ""),
                    "y": row.get("y", ""),
                    "action": row.get("action", ""),
                    "arg1": row.get("arg1", ""),
                    "arg2": row.get("arg2", ""),
                    "arg3": row.get("arg3", ""),
                    "next8": row.get("next8", ""),
                    "matched_needed_bytes": ";".join(matched),
                    "related_unknown_slots": ";".join(related),
                }
            )
    clues.sort(key=lambda row: (row["level"], row["name"], int(row["event_index"] or "0")))
    return clues


def render_table(rows: list[dict[str, str]], fieldnames: list[str], limit: int = 200) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fieldnames)
    body = []
    for row in rows[:limit]:
        cells = "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fieldnames)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    top_rows: list[dict[str, str]],
    mirror_rows: list[dict[str, str]],
    clue_rows: list[dict[str, str]],
    output_dir: Path,
) -> str:
    payload = {"summary": summary, "top": top_rows, "mirror": mirror_rows, "clues": clue_rows}
    links = " ".join(
        f'<a href="{html.escape(path.name)}">{html.escape(path.name)}</a>'
        for path in [
            output_dir / "summary.csv",
            output_dir / "top_level.csv",
            output_dir / "mirror.csv",
            output_dir / "trace_clues.csv",
        ]
    )
    changed_total = int(summary["changed_tools"]) + int(summary["changed_reports"])
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lands of Lore II External Legacy Media Review</title>
<style>
body {{ margin: 0; background: #101417; color: #edf3f6; font: 14px/1.45 system-ui, sans-serif; }}
.wrap {{ width: min(1500px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ padding: 18px 0 14px; border-bottom: 1px solid #2c3740; background: #12191d; }}
h1 {{ margin: 0; font-size: 21px; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 14px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, section {{ border: 1px solid #2c3740; border-radius: 8px; background: #171f24; padding: 12px; overflow-x: auto; }}
.label {{ color: #9eacb5; }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 980px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid #2c3740; padding: 7px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }}
th {{ color: #9eacb5; font-weight: 650; }}
a {{ color: #77d3af; text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>Lands of Lore II External Legacy Media Review</h1></div></header>
<main class="wrap">
  <div class="stats">
    <div class="stat"><div class="label">Legacy tools</div><div class="value">{html.escape(summary['legacy_tools'])}</div></div>
    <div class="stat"><div class="label">Legacy reports</div><div class="value">{html.escape(summary['legacy_reports'])}</div></div>
    <div class="stat"><div class="label">Changed mirrors</div><div class="value">{html.escape(str(changed_total))}</div></div>
    <div class="stat"><div class="label">Trace clues</div><div class="value">{html.escape(summary['legacy_trace_clue_rows'])}</div></div>
  </div>
  <section><h2>Files</h2><div>{links}</div></section>
  <section><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES, 1)}</section>
  <section><h2>Top Level Legacy Inventory</h2>{render_table(top_rows, TOP_FIELDNAMES)}</section>
  <section><h2>Mirror Differences</h2>{render_table([row for row in mirror_rows if row['status'] != 'identical'], MIRROR_FIELDNAMES)}</section>
  <section><h2>Residual Trace Clues</h2>{render_table(clue_rows, CLUE_FIELDNAMES)}</section>
</main>
<script>
const EXTERNAL_LEGACY_MEDIA_REVIEW = {json.dumps(payload, ensure_ascii=True, separators=(",", ":"))};
</script>
</body>
</html>
"""


def build_report(
    legacy_root: Path,
    output_dir: Path,
    slots: Path,
    fixtures: Path,
    trace_report: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    current_root = Path.cwd()
    legacy_tools = legacy_root / "C" / "LOLG" / "tools"
    legacy_reports = legacy_root / "C" / "LOLG" / "reports"

    top_rows = top_level_inventory(legacy_root)
    mirror_rows: list[dict[str, str]] = []
    mirror_rows.extend(compare_named_files(legacy_tools, current_root / "tools", "*.py", "tool"))
    mirror_rows.extend(compare_named_files(legacy_reports, current_root / "reports", "*", "report"))

    unknown_rows = unknown_highsafe_rows(slots)
    level_by_name = fixture_level_by_name(fixtures)
    clues = extract_trace_clues(legacy_root / trace_report, unknown_rows, level_by_name)
    edge_counts = Counter(edge(row) for row in unknown_rows)
    top_edge, top_edge_slots = ("", 0)
    if edge_counts:
        top_edge, top_edge_slots = edge_counts.most_common(1)[0]

    statuses = Counter(row["status"] for row in mirror_rows)
    needed_bytes = sorted({row.get("source_expected_byte", "") for row in unknown_rows if row.get("source_expected_byte")})
    issues = []
    if not legacy_root.exists():
        issues.append("missing_legacy_root")
    if statuses["missing_current"]:
        issues.append("missing_current_mirror_files")
    if statuses["changed"]:
        issues.append("changed_mirror_files")

    summary = {
        "scope": "external_legacy_media",
        "legacy_root": legacy_root.as_posix(),
        "legacy_root_exists": "1" if legacy_root.exists() else "0",
        "legacy_tools": str(sum(1 for row in mirror_rows if row["category"] == "tool")),
        "legacy_reports": str(sum(1 for row in mirror_rows if row["category"] == "report")),
        "missing_tools": str(sum(1 for row in mirror_rows if row["category"] == "tool" and row["status"] == "missing_current")),
        "changed_tools": str(sum(1 for row in mirror_rows if row["category"] == "tool" and row["status"] == "changed")),
        "missing_reports": str(sum(1 for row in mirror_rows if row["category"] == "report" and row["status"] == "missing_current")),
        "changed_reports": str(sum(1 for row in mirror_rows if row["category"] == "report" and row["status"] == "changed")),
        "unknown_highsafe_slots": str(len(unknown_rows)),
        "top_unknown_edge": top_edge,
        "top_unknown_edge_slots": str(top_edge_slots),
        "legacy_trace_clue_rows": str(len(clues)),
        "legacy_trace_needed_bytes": ";".join(needed_bytes),
        "issue_rows": str(len(issues)),
    }

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "top_level.csv", TOP_FIELDNAMES, top_rows)
    write_csv(output_dir / "mirror.csv", MIRROR_FIELDNAMES, mirror_rows)
    write_csv(output_dir / "trace_clues.csv", CLUE_FIELDNAMES, clues)
    (output_dir / "index.html").write_text(
        build_html(summary, top_rows, mirror_rows, clues, output_dir),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Review external legacy Lands of Lore II media work.")
    parser.add_argument("--legacy-root", type=Path, default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--trace-report", type=Path, default=DEFAULT_TRACE_REPORT)
    args = parser.parse_args()

    summary = build_report(
        args.legacy_root.resolve(strict=False),
        args.output,
        args.slots,
        args.fixtures,
        args.trace_report,
    )
    print(f"Legacy root exists: {summary['legacy_root_exists']}")
    print(f"Tools mirrored: {summary['legacy_tools']} changed={summary['changed_tools']}")
    print(f"Reports mirrored: {summary['legacy_reports']} changed={summary['changed_reports']}")
    print(f"Unknown high-safe slots: {summary['unknown_highsafe_slots']}")
    print(f"Trace clues: {summary['legacy_trace_clue_rows']}")
    print(f"Issues: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
