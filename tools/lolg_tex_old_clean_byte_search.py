#!/usr/bin/env python3
"""Search older .tex replay artifacts for clean bytes not in the current replay."""

from __future__ import annotations

import argparse
import csv
import html
import os
from pathlib import Path


DEFAULT_ROOT = Path(".")
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_search")
DEFAULT_CURRENT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_eleventh_terminal_source_byte_guard_after_terminal_root_source_byte_cascade_promoted/fixtures.csv"
)
DEFAULT_CURRENT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_eleventh_terminal_source_byte_guard_after_terminal_root_source_byte_cascade_promoted/summary.csv"
)
DEFAULT_EXPECTED_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_EXCLUDED_DIRS = ("C/LOLG",)
GENERATED_OUTPUT_DIR_NAMES = {
    "tex_old_clean_byte_search",
    "tex_old_clean_byte_seed_union_promoted_replay",
    "tex_old_clean_byte_union_promoted_replay",
}

SUMMARY_FIELDNAMES = [
    "scope",
    "excluded_dirs",
    "current_fixture_rows",
    "expected_fixture_rows",
    "candidate_fixture_csvs",
    "candidate_fixture_rows",
    "matching_candidate_rows",
    "candidate_new_known_bytes",
    "candidate_new_clean_bytes",
    "candidate_new_false_bytes",
    "zero_false_candidates_with_new_clean",
    "best_candidate_fixture_csv",
    "best_candidate_new_clean_bytes",
    "best_candidate_new_false_bytes",
    "current_total_clean_bytes",
    "current_remaining_unresolved_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "fixtures_csv",
    "summary_csv",
    "summary_total_clean_bytes",
    "summary_remaining_unresolved_bytes",
    "fixture_rows",
    "matching_rows",
    "candidate_known_bytes",
    "candidate_clean_bytes",
    "candidate_false_bytes",
    "shared_known_conflict_bytes",
    "candidate_new_known_bytes",
    "candidate_new_clean_bytes",
    "candidate_new_false_bytes",
    "issue_rows",
    "issues",
]

BYTE_FIELDNAMES = [
    "candidate_rank",
    "fixtures_csv",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "offset",
    "expected_hex",
    "candidate_hex",
    "verdict",
    "candidate_decoded_path",
    "candidate_known_mask_path",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(str(row.get(field, "")).strip())
    except ValueError:
        return default


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("archive_tag", "").strip(),
        row.get("pcx_name", "").strip(),
        row.get("frontier_id", "").strip(),
    )


def is_under(path: Path, parent: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
        resolved_parent = parent.resolve(strict=False)
    except OSError:
        return False
    return resolved == resolved_parent or resolved_parent in resolved.parents


def resolve_workspace_path(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def safe_read_bytes(
    path_text: str,
    *,
    root: Path,
    excluded_dirs: list[Path],
    issues: list[str],
    label: str,
) -> bytes | None:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return None
    path = resolve_workspace_path(path_text, root)
    if not is_under(path, root):
        issues.append(f"{label}:outside_workspace:{path_text}")
        return None
    for excluded_dir in excluded_dirs:
        if is_under(path, excluded_dir):
            issues.append(f"{label}:excluded_path:{path_text}")
            return None
    try:
        return path.read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_error:{path_text}:{exc.__class__.__name__}")
        return None


def summary_stats(summary_csv: Path) -> dict[str, str]:
    if not summary_csv.exists():
        return {}
    try:
        rows = read_csv(summary_csv)
    except OSError:
        return {}
    if not rows:
        return {}
    total = next((row for row in rows if row.get("scope") == "total"), rows[0])
    return {
        "total_clean_bytes": total.get("total_clean_bytes", total.get("clean_bytes", "")),
        "remaining_unresolved_bytes": total.get("remaining_unresolved_bytes", total.get("unresolved_bytes", "")),
    }


def load_expected(
    manifest_csv: Path,
    *,
    root: Path,
    excluded_dirs: list[Path],
) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    expected: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for row in read_csv(manifest_csv):
        key = fixture_key(row)
        if not all(key):
            continue
        data = safe_read_bytes(
            row.get("expected_gap_path", ""),
            root=root,
            excluded_dirs=excluded_dirs,
            issues=issues,
            label="expected",
        )
        if data is not None:
            expected[key] = data
    return expected, issues


def load_current(
    fixtures_csv: Path,
    *,
    root: Path,
    excluded_dirs: list[Path],
) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[dict[str, str]], list[str]]:
    current: dict[tuple[str, str, str], dict[str, bytes]] = {}
    rows = read_csv(fixtures_csv)
    issues: list[str] = []
    for row in rows:
        key = fixture_key(row)
        if not all(key):
            continue
        decoded = safe_read_bytes(
            row.get("decoded_path", ""),
            root=root,
            excluded_dirs=excluded_dirs,
            issues=issues,
            label="current_decoded",
        )
        mask = safe_read_bytes(
            row.get("known_mask_path", ""),
            root=root,
            excluded_dirs=excluded_dirs,
            issues=issues,
            label="current_known_mask",
        )
        if decoded is None or mask is None:
            continue
        current[key] = {"decoded": decoded, "mask": mask}
    return current, rows, issues


def iter_fixture_csvs(root: Path, excluded_dirs: list[Path]) -> list[Path]:
    skip_names = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "fixtures",
        "fullhd",
        "native",
    } | GENERATED_OUTPUT_DIR_NAMES
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath).resolve(strict=False)
        if any(is_under(directory, excluded_dir) for excluded_dir in excluded_dirs):
            dirnames[:] = []
            continue
        dirnames[:] = [name for name in dirnames if name not in skip_names]
        if "fixtures.csv" in filenames:
            paths.append(directory / "fixtures.csv")
    return sorted(paths)


def compare_candidate(
    fixtures_csv: Path,
    *,
    root: Path,
    excluded_dirs: list[Path],
    expected: dict[tuple[str, str, str], bytes],
    current: dict[tuple[str, str, str], dict[str, bytes]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    issues: list[str] = []
    try:
        rows = read_csv(fixtures_csv)
    except OSError as exc:
        return (
            {
                "fixtures_csv": fixtures_csv.relative_to(root).as_posix(),
                "summary_csv": "",
                "summary_total_clean_bytes": "",
                "summary_remaining_unresolved_bytes": "",
                "fixture_rows": "0",
                "matching_rows": "0",
                "candidate_known_bytes": "0",
                "candidate_clean_bytes": "0",
                "candidate_false_bytes": "0",
                "shared_known_conflict_bytes": "0",
                "candidate_new_known_bytes": "0",
                "candidate_new_clean_bytes": "0",
                "candidate_new_false_bytes": "0",
                "issue_rows": "1",
                "issues": f"read_error:{exc.__class__.__name__}",
            },
            [],
        )

    stats = summary_stats(fixtures_csv.with_name("summary.csv"))
    matching_rows = 0
    candidate_known_bytes = 0
    candidate_clean_bytes = 0
    candidate_false_bytes = 0
    shared_known_conflict_bytes = 0
    candidate_new_known_bytes = 0
    candidate_new_clean_bytes = 0
    candidate_new_false_bytes = 0
    byte_rows: list[dict[str, str]] = []

    for row in rows:
        key = fixture_key(row)
        if key not in current or key not in expected:
            continue
        matching_rows += 1
        expected_bytes = expected[key]
        current_data = current[key]
        decoded = safe_read_bytes(
            row.get("decoded_path", ""),
            root=root,
            excluded_dirs=excluded_dirs,
            issues=issues,
            label="candidate_decoded",
        )
        mask = safe_read_bytes(
            row.get("known_mask_path", ""),
            root=root,
            excluded_dirs=excluded_dirs,
            issues=issues,
            label="candidate_known_mask",
        )
        if decoded is None or mask is None:
            continue
        current_mask = current_data["mask"]
        current_decoded = current_data["decoded"]
        limit = min(len(expected_bytes), len(decoded), len(mask), len(current_mask), len(current_decoded))
        if limit != len(expected_bytes):
            issues.append(f"{key}:length_mismatch")
        for offset in range(limit):
            candidate_known = mask[offset] != 0
            if not candidate_known:
                continue
            candidate_known_bytes += 1
            clean = decoded[offset] == expected_bytes[offset]
            if clean:
                candidate_clean_bytes += 1
            else:
                candidate_false_bytes += 1
            current_known = current_mask[offset] != 0
            if current_known:
                if decoded[offset] != current_decoded[offset]:
                    shared_known_conflict_bytes += 1
                continue
            candidate_new_known_bytes += 1
            if clean:
                candidate_new_clean_bytes += 1
                verdict = "clean"
            else:
                candidate_new_false_bytes += 1
                verdict = "false"
            byte_rows.append(
                {
                    "candidate_rank": "",
                    "fixtures_csv": fixtures_csv.relative_to(root).as_posix(),
                    "archive_tag": key[0],
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "offset": str(offset),
                    "expected_hex": f"{expected_bytes[offset]:02x}",
                    "candidate_hex": f"{decoded[offset]:02x}",
                    "verdict": verdict,
                    "candidate_decoded_path": row.get("decoded_path", ""),
                    "candidate_known_mask_path": row.get("known_mask_path", ""),
                }
            )

    candidate_row = {
        "fixtures_csv": fixtures_csv.relative_to(root).as_posix(),
        "summary_csv": fixtures_csv.with_name("summary.csv").relative_to(root).as_posix(),
        "summary_total_clean_bytes": stats.get("total_clean_bytes", ""),
        "summary_remaining_unresolved_bytes": stats.get("remaining_unresolved_bytes", ""),
        "fixture_rows": str(len(rows)),
        "matching_rows": str(matching_rows),
        "candidate_known_bytes": str(candidate_known_bytes),
        "candidate_clean_bytes": str(candidate_clean_bytes),
        "candidate_false_bytes": str(candidate_false_bytes),
        "shared_known_conflict_bytes": str(shared_known_conflict_bytes),
        "candidate_new_known_bytes": str(candidate_new_known_bytes),
        "candidate_new_clean_bytes": str(candidate_new_clean_bytes),
        "candidate_new_false_bytes": str(candidate_new_false_bytes),
        "issue_rows": str(len(issues)),
        "issues": ";".join(issues[:25]),
    }
    return candidate_row, byte_rows


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        return html.escape(os.path.relpath(path, base_dir))
    except ValueError:
        return html.escape(path.as_posix())


def render_html(output: Path, summary: dict[str, str], candidates: list[dict[str, str]], byte_rows: list[dict[str, str]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in candidates[:80]:
        row_class = "ok" if int_value(row, "candidate_new_clean_bytes") and int_value(row, "candidate_new_false_bytes") == 0 else ""
        rows.append(
            "<tr class='{row_class}'>"
            f"<td>{html.escape(row['rank'])}</td>"
            f"<td><a href='{relative_href(row['fixtures_csv'], output)}'>{html.escape(row['fixtures_csv'])}</a></td>"
            f"<td>{html.escape(row['summary_total_clean_bytes'])}</td>"
            f"<td>{html.escape(row['summary_remaining_unresolved_bytes'])}</td>"
            f"<td>{html.escape(row['matching_rows'])}</td>"
            f"<td>{html.escape(row['candidate_new_clean_bytes'])}</td>"
            f"<td>{html.escape(row['candidate_new_false_bytes'])}</td>"
            f"<td>{html.escape(row['shared_known_conflict_bytes'])}</td>"
            f"<td>{html.escape(row['issue_rows'])}</td>"
            "</tr>"
        )
    byte_preview = []
    for row in byte_rows[:120]:
        byte_preview.append(
            "<tr>"
            f"<td>{html.escape(row['candidate_rank'])}</td>"
            f"<td>{html.escape(row['archive_tag'])}</td>"
            f"<td>{html.escape(row['pcx_name'])}</td>"
            f"<td>{html.escape(row['frontier_id'])}</td>"
            f"<td>{html.escape(row['offset'])}</td>"
            f"<td>{html.escape(row['expected_hex'])}</td>"
            f"<td>{html.escape(row['candidate_hex'])}</td>"
            f"<td>{html.escape(row['verdict'])}</td>"
            "</tr>"
        )
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Lands of Lore II .tex Old Clean Byte Search</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f4; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 13px; text-align: left; }}
    th {{ background: #ecebe4; }}
    .ok {{ background: #eaf7ea; }}
    code {{ background: #eee; padding: 1px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Lands of Lore II .tex Old Clean Byte Search</h1>
  <p>Recherche dans les anciens artefacts, avec exclusion physique de <code>{html.escape(summary['excluded_dirs'])}</code>.</p>
  <table>
    <tbody>
      {''.join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in summary.items())}
    </tbody>
  </table>
  <h2>Candidats</h2>
  <table>
    <thead><tr><th>rang</th><th>fixtures</th><th>clean summary</th><th>unresolved summary</th><th>rows</th><th>nouveaux clean</th><th>nouveaux false</th><th>conflits connus</th><th>issues</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Nouveaux octets vus</h2>
  <table>
    <thead><tr><th>rang</th><th>archive</th><th>pcx</th><th>frontier</th><th>offset</th><th>attendu</th><th>candidat</th><th>verdict</th></tr></thead>
    <tbody>{''.join(byte_preview)}</tbody>
  </table>
</body>
</html>
"""
    (output / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--current-fixtures", type=Path, default=DEFAULT_CURRENT_FIXTURES)
    parser.add_argument("--current-summary", type=Path, default=DEFAULT_CURRENT_SUMMARY)
    parser.add_argument("--expected-manifest", type=Path, default=DEFAULT_EXPECTED_MANIFEST)
    parser.add_argument(
        "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDED_DIRS),
        help="Workspace-relative directory to exclude from physical reads and scans.",
    )
    args = parser.parse_args()

    root = args.root.resolve(strict=False)
    output = args.output
    if not output.is_absolute():
        output = root / output
    current_fixtures = resolve_workspace_path(args.current_fixtures.as_posix(), root)
    current_summary = resolve_workspace_path(args.current_summary.as_posix(), root)
    expected_manifest = resolve_workspace_path(args.expected_manifest.as_posix(), root)
    excluded_dirs = [resolve_workspace_path(path_text, root) for path_text in args.exclude]

    expected, expected_issues = load_expected(expected_manifest, root=root, excluded_dirs=excluded_dirs)
    current, current_rows, current_issues = load_current(current_fixtures, root=root, excluded_dirs=excluded_dirs)
    candidate_paths = iter_fixture_csvs(root, excluded_dirs)

    candidate_rows: list[dict[str, str]] = []
    byte_rows: list[dict[str, str]] = []
    for fixtures_csv in candidate_paths:
        candidate_row, rows = compare_candidate(
            fixtures_csv,
            root=root,
            excluded_dirs=excluded_dirs,
            expected=expected,
            current=current,
        )
        candidate_rows.append(candidate_row)
        byte_rows.extend(rows)

    candidate_rows.sort(
        key=lambda row: (
            int_value(row, "candidate_new_false_bytes") != 0,
            -int_value(row, "candidate_new_clean_bytes"),
            -int_value(row, "summary_total_clean_bytes"),
            row["fixtures_csv"],
        )
    )
    for rank, row in enumerate(candidate_rows, start=1):
        row["rank"] = str(rank)
    rank_by_path = {row["fixtures_csv"]: row["rank"] for row in candidate_rows}
    for row in byte_rows:
        row["candidate_rank"] = rank_by_path.get(row["fixtures_csv"], "")
    byte_rows.sort(
        key=lambda row: (
            int(row["candidate_rank"] or "999999"),
            row["archive_tag"],
            row["pcx_name"],
            int(row["frontier_id"] or "0"),
            int(row["offset"] or "0"),
        )
    )

    clean_zero_false = [
        row
        for row in candidate_rows
        if int_value(row, "candidate_new_clean_bytes") > 0
        and int_value(row, "candidate_new_false_bytes") == 0
    ]
    actionable_candidate_issue_rows = sum(
        int_value(row, "issue_rows")
        for row in candidate_rows
        if int_value(row, "candidate_new_clean_bytes") > 0 or int_value(row, "candidate_new_false_bytes") > 0
    )
    best = candidate_rows[0] if candidate_rows else {}
    current_stats = summary_stats(current_summary)
    summary = {
        "scope": "old_artifacts_excluding_game_dir",
        "excluded_dirs": ";".join(str(path.relative_to(root)) for path in excluded_dirs),
        "current_fixture_rows": str(len(current_rows)),
        "expected_fixture_rows": str(len(expected)),
        "candidate_fixture_csvs": str(len(candidate_rows)),
        "candidate_fixture_rows": str(sum(int_value(row, "fixture_rows") for row in candidate_rows)),
        "matching_candidate_rows": str(sum(int_value(row, "matching_rows") for row in candidate_rows)),
        "candidate_new_known_bytes": str(sum(int_value(row, "candidate_new_known_bytes") for row in candidate_rows)),
        "candidate_new_clean_bytes": str(sum(int_value(row, "candidate_new_clean_bytes") for row in candidate_rows)),
        "candidate_new_false_bytes": str(sum(int_value(row, "candidate_new_false_bytes") for row in candidate_rows)),
        "zero_false_candidates_with_new_clean": str(len(clean_zero_false)),
        "best_candidate_fixture_csv": best.get("fixtures_csv", ""),
        "best_candidate_new_clean_bytes": best.get("candidate_new_clean_bytes", "0"),
        "best_candidate_new_false_bytes": best.get("candidate_new_false_bytes", "0"),
        "current_total_clean_bytes": current_stats.get("total_clean_bytes", ""),
        "current_remaining_unresolved_bytes": current_stats.get("remaining_unresolved_bytes", ""),
        "issue_rows": str(len(expected_issues) + len(current_issues) + actionable_candidate_issue_rows),
    }

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output / "candidate_bytes.csv", BYTE_FIELDNAMES, byte_rows)
    render_html(output, summary, candidate_rows, byte_rows)

    print(f"summary={output / 'summary.csv'}")
    print(f"candidates={output / 'candidates.csv'}")
    print(f"candidate_bytes={output / 'candidate_bytes.csv'}")
    print(f"html={output / 'index.html'}")
    print(
        "best="
        f"{summary['best_candidate_fixture_csv']} "
        f"new_clean={summary['best_candidate_new_clean_bytes']} "
        f"new_false={summary['best_candidate_new_false_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
