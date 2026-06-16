#!/usr/bin/env python3
"""Inventory historical project-added files without copying large assets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


DEFAULT_OUTPUT = Path("output/project_legacy_inventory")
DEFAULT_SINCE = "2026-05-01"
DEFAULT_BEFORE = "2026-06-15"

MANIFEST_FIELDNAMES = [
    "priority",
    "category",
    "path",
    "mtime",
    "size",
    "extension",
    "role",
    "integration",
]

SUMMARY_FIELDNAMES = [
    "category",
    "files",
    "bytes",
    "first_mtime",
    "last_mtime",
]

CORE_PATHS = {
    "lol2fix.conf",
    "tools/lolg_mix_extract.py",
    "tools/lolg_fullhd_export.py",
    "C/LOLG/run_lolg_hd.sh",
    "C/LOLG/ENGINE_HD_PATCH_NOTES.md",
    "C/LOLG/TEST_PCX_MOD.md",
    "C/LOLG/HD_ASSETS_NOTES.md",
    "C/LOLG/QWEN3_HANDOFF.md",
    "C/LOLG/lolg_hd_viewport.conf",
    "C/LOLG/dgVoodoo.conf",
    "C/LOLG/tools/restore_original_mix.sh",
    "C/LOLG/tools/check_pcx_mod.sh",
    "C/LOLG/tools/install_pcx_mod.sh",
    "C/LOLG/tools/build_hd_assets.sh",
    "C/LOLG/mod_mix/LOCAL.MIX",
    "C/LOLG/mod_mix/GLOBAL.MIX",
    "C/LOLG/mod_mix_pcx4x/LOCAL.MIX",
    "C/LOLG/mod_mix_pcx4x/GLOBAL.MIX",
}

SKIP_NAMES = {
    ".git",
    ".agents",
    ".codex",
    "__pycache__",
    "output",
}

DOC_SUFFIXES = {".md", ".txt"}
SCRIPT_SUFFIXES = {".py", ".sh", ".pl", ".bat"}
CONFIG_SUFFIXES = {".conf", ".ini", ".cfg"}
IMAGE_SUFFIXES = {".png", ".pcx", ".ico"}


def parse_date(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"invalid date: {value}")


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return any(part in SKIP_NAMES or part.startswith(".") for part in rel.parts)


def classify(rel_path: str) -> tuple[str, str, str]:
    path = Path(rel_path)
    parts = path.parts
    suffix = path.suffix.lower()

    if rel_path in CORE_PATHS:
        return (
            "core_project_file",
            "Tracked handoff, launcher, config, or mod pack from earlier HD work.",
            "Keep in place and expose through project documentation/reporting.",
        )
    if suffix in DOC_SUFFIXES:
        return (
            "project_doc",
            "Historical notes or handoff document.",
            "Keep as project memory and link from the inventory.",
        )
    if suffix in SCRIPT_SUFFIXES:
        return (
            "project_script",
            "Project automation or extraction/build helper.",
            "Keep executable workflow visible in the inventory.",
        )
    if suffix in CONFIG_SUFFIXES:
        return (
            "project_config",
            "Configuration used by the HD or diagnostic path.",
            "Keep in place and track as runtime/build context.",
        )
    if len(parts) >= 3 and parts[0] == "C" and parts[1] == "LOLG":
        tree = parts[2]
        if tree in {"mod_mix", "mod_mix_pcx4x"}:
            return (
                "mod_archive",
                "Generated or curated MIX archive pack.",
                "Keep as deployable project artifact; do not duplicate.",
            )
        if tree in {"hd", "hd_clean", "hd_font", "hd_shp", "hd_wsa"} or tree.startswith("hd_"):
            return (
                "hd_asset_tree",
                "Generated HD asset tree retained from earlier work.",
                "Track location and size; regenerate only from source scripts.",
            )
        if tree.startswith("replacements") or tree == "original_clean":
            return (
                "replacement_asset_tree",
                "Replacement or cleaned source asset tree.",
                "Keep as source material for rebuilds.",
            )
        if tree == "runtime_overrides":
            return (
                "runtime_override",
                "Runtime override payload from previous HD experiments.",
                "Keep in place and document as optional runtime material.",
            )
        if tree == "extracted":
            return (
                "extracted_reference",
                "Bulk extracted reference material.",
                "Track as generated reference data; avoid hand editing.",
            )
        if tree == "reports":
            return (
                "diagnostic_report",
                "Historical TSV/CSV analysis output.",
                "Keep as evidence for decoder decisions.",
            )
        if tree.startswith("probe") or tree.startswith("previews") or tree == "te_segments_pcx":
            return (
                "diagnostic_preview",
                "Historical probe or preview output.",
                "Track as visual evidence; avoid copying into docs.",
            )
    if suffix in IMAGE_SUFFIXES:
        return (
            "image_asset",
            "Image asset or preview outside the standard output tree.",
            "Keep path tracked for manual review.",
        )
    return (
        "other_project_file",
        "Project-era file outside known buckets.",
        "Review manually before moving or deleting.",
    )


def iter_files(root: Path, since: datetime, before: datetime) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        stat = path.stat()
        mtime_dt = datetime.fromtimestamp(stat.st_mtime)
        if mtime_dt < since or mtime_dt >= before:
            continue
        rel_path = relative_to_root(path, root)
        category, role, integration = classify(rel_path)
        rows.append(
            {
                "priority": "core" if rel_path in CORE_PATHS else "support",
                "category": category,
                "path": rel_path,
                "mtime": mtime_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "size": str(stat.st_size),
                "extension": path.suffix.lower(),
                "role": role,
                "integration": integration,
            }
        )
    rows.sort(key=lambda row: (row["priority"] != "core", row["category"], row["path"]))
    return rows


def summarize(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)

    summary: list[dict[str, str]] = []
    total_bytes = 0
    for category, group_rows in sorted(grouped.items()):
        byte_count = sum(int(row["size"]) for row in group_rows)
        total_bytes += byte_count
        mtimes = [row["mtime"] for row in group_rows]
        summary.append(
            {
                "category": category,
                "files": str(len(group_rows)),
                "bytes": str(byte_count),
                "first_mtime": min(mtimes),
                "last_mtime": max(mtimes),
            }
        )
    if rows:
        summary.insert(
            0,
            {
                "category": "total",
                "files": str(len(rows)),
                "bytes": str(total_bytes),
                "first_mtime": min(row["mtime"] for row in rows),
                "last_mtime": max(row["mtime"] for row in rows),
            },
        )
    return summary


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return Path(os.path.relpath(path, base_dir)).as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: list[dict[str, str]],
    rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
    since: str,
    before: str,
) -> str:
    payload = {"summary": summary, "files": rows, "since": since, "before": before}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    total = summary[0] if summary else {"files": "0", "bytes": "0", "first_mtime": "", "last_mtime": ""}
    core_rows = [row for row in rows if row["priority"] == "core"]
    support_rows = [row for row in rows if row["priority"] != "core"][:400]
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in [
            ("manifest.csv", output_dir / "manifest.csv"),
            ("summary.csv", output_dir / "summary.csv"),
        ]
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
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
.sub {{ margin-top: 4px; color: var(--muted); }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}}
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 980px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Fichiers ajoutes au projet entre {html.escape(since)} et {html.escape(before)}.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fichiers</div><div class="value">{html.escape(total['files'])}</div></div>
    <div class="stat"><div class="label">Octets</div><div class="value">{html.escape(total['bytes'])}</div></div>
    <div class="stat"><div class="label">Premier</div><div class="value">{html.escape(total['first_mtime'][:10])}</div></div>
    <div class="stat"><div class="label">Dernier</div><div class="value">{html.escape(total['last_mtime'][:10])}</div></div>
  </section>
  <section class="panel">
    <h2>Fichiers</h2>
    <div>{links}</div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table(summary, SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Fichiers coeur</h2>
    {render_table(core_rows, MANIFEST_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Autres fichiers classes</h2>
    {render_table(support_rows, MANIFEST_FIELDNAMES)}
  </section>
</main>
<script>
const PROJECT_LEGACY_INVENTORY = {data_json};
</script>
</body>
</html>
"""


def write_report(
    root: Path,
    output_dir: Path,
    since: datetime,
    before: datetime,
    title: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = iter_files(root, since, before)
    summary = summarize(rows)
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, summary)
    (output_dir / "index.html").write_text(
        build_html(
            summary,
            rows,
            output_dir,
            title,
            since.strftime("%Y-%m-%d"),
            before.strftime("%Y-%m-%d"),
        )
    )
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory historical project-added files.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--since", type=parse_date, default=parse_date(DEFAULT_SINCE))
    parser.add_argument("--before", type=parse_date, default=parse_date(DEFAULT_BEFORE))
    parser.add_argument("--title", default="Lands of Lore II Project Legacy File Inventory")
    args = parser.parse_args()

    summary, rows = write_report(args.root.resolve(), args.output, args.since, args.before, args.title)
    total = summary[0] if summary else {"files": "0", "bytes": "0"}
    core_files = sum(1 for row in rows if row["priority"] == "core")
    print(f"Project files: {total['files']}")
    print(f"Core files: {core_files}")
    print(f"Bytes: {total['bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
