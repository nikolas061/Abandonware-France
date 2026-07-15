#!/usr/bin/env python3
"""Build a lightweight manifest for the local LOLG Full HD release package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import subprocess
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_release_manifest")
DEFAULT_SMALL_HASH_LIMIT = 64 * 1024 * 1024

CORE_FILES = [
    ("launcher", Path("LOLG_HD.sh"), True, True),
    ("launcher", Path("RUN_HD_WINE.sh"), True, True),
    ("launcher", Path("RUN_HD_WINE_GAMESCOPE.sh"), True, True),
    ("launcher", Path("RUN_HD.sh"), True, True),
    ("launcher", Path("PACK_HD_RELEASE.sh"), True, True),
    ("launcher", Path("STOP_HD_WINE.sh"), True, True),
    ("launcher", Path("REPAIR_HD_WINE.sh"), True, True),
    ("launcher", Path("RUN_HD_DESKTOP.sh"), True, True),
    ("launcher", Path("INSTALL_HD_DESKTOP.sh"), True, True),
    ("launcher", Path("UNINSTALL_HD_DESKTOP.sh"), True, True),
    ("launcher", Path("COLLECT_HD_SUPPORT.sh"), True, True),
    ("launcher", Path("VERIFY_HD_MANIFEST.sh"), True, True),
    ("check", Path("CHECK_HD.sh"), True, True),
    ("check", Path("CHECK_HD_GPU.sh"), True, True),
    ("check", Path("TEST_HD_WINE.sh"), True, True),
    ("doc", Path("README"), True, False),
    ("doc", Path("LANCER_HD.txt"), True, False),
    ("doc", Path("LANCER_SAFEVQA_WINDOWS_LINUX.txt"), True, False),
    ("doc", Path("HD_TEXTURES.md"), True, False),
    ("doc", Path("MISE_AU_POINT_PROJET.md"), True, False),
    ("config", Path(".gitattributes"), True, False),
    ("config", Path(".gitignore"), True, False),
    ("desktop", Path("desktop/lolg-hd.desktop"), True, True),
    ("desktop", Path("desktop/lolg-hd-status.desktop"), True, True),
    ("desktop", Path("desktop/lolg-hd-repair.desktop"), True, True),
    ("config", Path("lol2dos.conf"), True, False),
    ("tool", Path("tools/lolg_hd_release_check.py"), True, False),
    ("tool", Path("tools/lolg_hd_wine_smoke_test.py"), True, False),
    ("tool", Path("tools/lolg_hd_graphics_check.py"), True, False),
    ("tool", Path("tools/lolg_hd_release_manifest.py"), True, True),
    ("tool", Path("tools/lolg_hd_manifest_verify.py"), True, True),
    ("tool", Path("tools/lolg_hd_support_manifest_verify.py"), True, False),
    ("tool", Path("tools/lolg_hd_support_archive_verify.py"), True, False),
    ("tool", Path("tools/lolg_hd_git_audit.py"), True, False),
    ("tool", Path("tools/lolg_hd_resolution_check.py"), True, True),
    ("tool", Path("tools/lolg_hd_status.py"), True, False),
    ("tool", Path("tools/analyze_te_pcx_payloads.py"), True, False),
    ("tool", Path("tools/export_shp.py"), True, True),
    ("tool", Path("tools/export_te_guided_decoders.py"), True, False),
    ("tool", Path("tools/export_te_span_previews.py"), True, False),
    ("tool", Path("tools/probe_te_span_decode.py"), True, False),
    ("tool", Path("tools/score_te_raw_layouts.py"), True, False),
    ("tool", Path("tools/trace_te_stream.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_bounded_family_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_guarded_renderer_grammar_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_header_start_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_high_arg2_skip_validation_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_renderer_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_route_previews.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_selector_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_singleton_header_probe.py"), True, False),
    ("tool", Path("tools/lolg_tex_large_shifted_2a30_branch_trace_probe.py"), True, False),
    ("tool", Path("tools/westwood_codecs.py"), True, False),
    ("tool", Path("tools/run_lolg95_runtime_archive_list_probe.py"), True, False),
    ("tool", Path("tools/run_lolg95_sidecar_file_io_trace_attempt.py"), True, False),
    ("tool", Path("tools/run_lolg95_winedbg_attach_pilot_attempt.py"), True, True),
    ("tool", Path("tools/run_lolg95_winedbg_mix_lookup_trace_attempt.py"), True, False),
    ("tool", Path("tools/lolg95_locallng_sidecar_patch_probe.py"), True, True),
    ("tool", Path("tools/lolg_rebuild_locallng_dos_compat.py"), True, True),
    ("tool", Path("tools/lolg_vqa_contract_batch_writer.py"), True, True),
    ("tool", Path("tools/lolg_vqa_contract_preserving_writer.py"), True, True),
    ("tool", Path("tools/lolg_vqa_decode.py"), True, True),
    ("tool", Path("tools/lolg_vqa_fullhd_replacement_writer.py"), True, True),
    ("tool", Path("tools/lolg_vqa_locallng_safe_sidecar.py"), True, True),
    ("tool", Path("tools/lolg_vqa_native_exact_batch_writer.py"), True, False),
    ("tool", Path("tools/lolg_vqa_native_exact_fixture_writer.py"), True, True),
    ("tool", Path("tools/lolg_vqa_runtime_compat_batch_audit.py"), True, False),
    ("tool", Path("tools/lolg_vqa_runtime_compat_audit.py"), True, True),
    ("source_game", Path("C/LOLG/LOLG95.EXE"), True, False),
]

REPORT_FILES = [
    ("report", Path("output/hd_release_check/summary.csv"), False, False),
    ("report", Path("output/hd_release_check/checks.csv"), False, False),
    ("report", Path("output/hd_release_check/index.html"), False, False),
    ("report", Path("output/hd_graphics_check/summary.csv"), False, False),
    ("report", Path("output/hd_wine_smoke_test/summary.csv"), False, False),
    ("report", Path("output/hd_wine_smoke_test_1280x1024/summary.csv"), False, False),
    ("report", Path("output/hd_resolution_check/summary.csv"), False, False),
    ("report", Path("output/hd_resolution_check/checks.csv"), False, False),
    ("report", Path("output/hd_resolution_check/index.html"), False, False),
    ("report", Path("output/vqa_runtime_pack_build/summary.csv"), False, False),
    ("report", Path("output/fullhd_audit/summary.csv"), False, False),
    ("report", Path("output/vqa_runtime_oversize_budget/summary.csv"), False, False),
    ("report", Path("output/vqa_lcw_literal_probe/summary.csv"), False, False),
]

MANIFEST_FIELDS = [
    "category",
    "path",
    "required",
    "status",
    "size_bytes",
    "mtime_ns",
    "executable",
    "sha256",
    "notes",
]

SUMMARY_FIELDS = [
    "status",
    "manifest_rows",
    "required_missing",
    "required_not_executable",
    "vqa_mix_files",
    "vqa_mix_bytes",
    "hash_mode",
    "hashed_files",
    "hash_skipped_files",
    "release_check_status",
    "issues",
    "next_step",
]


def read_csv_first(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_hash(path: Path, args: argparse.Namespace) -> bool:
    if args.hash_mode == "none":
        return False
    if args.hash_mode == "all":
        return True
    return path.stat().st_size <= args.small_hash_limit


def add_file(
    rows: list[dict[str, str]],
    category: str,
    path: Path,
    required: bool,
    must_be_executable: bool,
    args: argparse.Namespace,
) -> tuple[int, int]:
    if not path.exists():
        rows.append(
            {
                "category": category,
                "path": path.as_posix(),
                "required": "1" if required else "0",
                "status": "missing" if required else "optional_missing",
                "size_bytes": "",
                "mtime_ns": "",
                "executable": "0",
                "sha256": "",
                "notes": "required file missing" if required else "optional file missing",
            }
        )
        return 0, 0

    stat = path.stat()
    executable = bool(stat.st_mode & 0o111)
    status = "present"
    notes = ""
    if must_be_executable and not executable:
        status = "not_executable"
        notes = "chmod +x required"

    hash_value = ""
    skipped = 0
    if path.is_file() and should_hash(path, args):
        hash_value = sha256_file(path)
    elif path.is_file() and args.hash_mode != "none":
        skipped = 1
        notes = (notes + "; " if notes else "") + "sha256 skipped by hash mode"

    rows.append(
        {
            "category": category,
            "path": path.as_posix(),
            "required": "1" if required else "0",
            "status": status,
            "size_bytes": str(stat.st_size),
            "mtime_ns": str(stat.st_mtime_ns),
            "executable": "1" if executable else "0",
            "sha256": hash_value,
            "notes": notes,
        }
    )
    return 1 if hash_value else 0, skipped


def run_release_check() -> str:
    result = subprocess.run(
        ["./CHECK_HD.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
        timeout=60,
    )
    return "pass" if result.returncode == 0 else "gap"


def build_html(path: Path, summary: dict[str, str], rows: list[dict[str, str]]) -> None:
    table_rows = []
    for row in rows:
        status = row["status"]
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(row['category'])}</td>"
            f"<td><code>{html.escape(row['path'])}</code></td>"
            f"<td class='{html.escape(status)}'>{html.escape(status)}</td>"
            f"<td>{html.escape(row['size_bytes'])}</td>"
            f"<td>{html.escape(row['sha256'][:16])}</td>"
            f"<td>{html.escape(row['notes'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Release Manifest</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.present {{ color: #106b2f; font-weight: 700; }}
.missing, .not_executable, .gap {{ color: #a22522; font-weight: 700; }}
.optional_missing {{ color: #777; font-weight: 700; }}
code {{ background: #eee; padding: 0.1rem 0.25rem; }}
</style>
<h1>LOLG HD Release Manifest</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>MIX files: {html.escape(summary['vqa_mix_files'])}/66,
bytes={html.escape(summary['vqa_mix_bytes'])},
release_check={html.escape(summary['release_check_status'])}</p>
<table>
<thead><tr><th>Category</th><th>Path</th><th>Status</th><th>Bytes</th><th>SHA256 prefix</th><th>Notes</th></tr></thead>
<tbody>
{''.join(table_rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def write_install_note(path: Path) -> None:
    path.write_text(
        """LOLG HD local release manifest
==============================

This directory is a lightweight release manifest. It does not copy the 19 GB
VQA MIX pack. The real files stay in the project tree.

Useful commands from the project root:

  ./LOLG_HD.sh              Launch Wine HD at 1920x1080
  desktop/lolg-hd.desktop   Desktop shortcut for Wine HD
  ./LOLG_HD.sh install-desktop --dry-run  Preview menu shortcut install
  ./LOLG_HD.sh uninstall-desktop  Preview menu shortcut removal
  ./LOLG_HD.sh support      Collect lightweight diagnostic bundle
  ./LOLG_HD.sh wine-1280    Launch Wine HD at 1280x1024
  ./LOLG_HD.sh status       Summarize release state without launching Wine
  ./LOLG_HD.sh stop         Stop the project HD Wine runtime
  ./LOLG_HD.sh repair       Stop, prepare, check, and summarize
  ./LOLG_HD.sh check        Validate the HD release
  ./LOLG_HD.sh smoke        Run the bounded Wine runtime smoke test
  ./LOLG_HD.sh gpu          Diagnose Wine/OpenGL GPU exposure
  ./LOLG_HD.sh resolutions  Check Wine HD resolutions without launching
  ./LOLG_HD.sh manifest     Regenerate this manifest
  ./LOLG_HD.sh verify-manifest  Verify manifest without hashing large MIX files
  ./LOLG_HD.sh git-audit    Check Git tracking and ignored heavy payloads
  ./LOLG_HD.sh notice       Print the short French launch notice

For full SHA256 checksums of the 19 GB MIX pack, run:

  ./LOLG_HD.sh manifest --hash-mode all
""",
        encoding="utf-8",
    )


def build_manifest(args: argparse.Namespace) -> dict[str, str]:
    if args.run_check:
        release_check_status = run_release_check()
    else:
        release_check_status = read_csv_first(Path("output/hd_release_check/summary.csv")).get("status", "")

    rows: list[dict[str, str]] = []
    hashed_files = 0
    hash_skipped_files = 0

    for category, path, required, must_be_executable in CORE_FILES + REPORT_FILES:
        hashed, skipped = add_file(rows, category, path, required, must_be_executable, args)
        hashed_files += hashed
        hash_skipped_files += skipped

    mix_files = sorted(Path("mod_mix_vqa_fullhd").glob("*.MIX"))
    mix_bytes = 0
    for mix in mix_files:
        mix_bytes += mix.stat().st_size
        hashed, skipped = add_file(rows, "vqa_mix", mix, True, False, args)
        hashed_files += hashed
        hash_skipped_files += skipped

    required_missing = [
        row["path"]
        for row in rows
        if row["required"] == "1" and row["status"] == "missing"
    ]
    required_not_executable = [
        row["path"]
        for row in rows
        if row["required"] == "1" and row["status"] == "not_executable"
    ]
    issues = []
    if required_missing:
        issues.append("required_missing")
    if required_not_executable:
        issues.append("required_not_executable")
    if len(mix_files) != 66:
        issues.append("vqa_mix_count")
    if release_check_status != "pass":
        issues.append("release_check")

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "manifest_rows": str(len(rows)),
        "required_missing": str(len(required_missing)),
        "required_not_executable": str(len(required_not_executable)),
        "vqa_mix_files": str(len(mix_files)),
        "vqa_mix_bytes": str(mix_bytes),
        "hash_mode": args.hash_mode,
        "hashed_files": str(hashed_files),
        "hash_skipped_files": str(hash_skipped_files),
        "release_check_status": release_check_status,
        "issues": ";".join(issues),
        "next_step": "manifest passed" if not issues else "fix release manifest issues",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "manifest.csv", MANIFEST_FIELDS, rows)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    checksum_rows = [row for row in rows if row["sha256"]]
    with (args.output / "checksums.sha256").open("w", encoding="utf-8") as handle:
        for row in checksum_rows:
            handle.write(f"{row['sha256']}  {row['path']}\n")
    write_install_note(args.output / "README_INSTALL.txt")
    build_html(args.output / "index.html", summary, rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a lightweight LOLG HD release manifest.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--hash-mode",
        choices=["none", "small", "all"],
        default="small",
        help="Hash no files, only files under the small limit, or every file.",
    )
    parser.add_argument(
        "--small-hash-limit",
        type=int,
        default=DEFAULT_SMALL_HASH_LIMIT,
        help="Maximum byte size hashed by --hash-mode small.",
    )
    parser.add_argument("--skip-check", dest="run_check", action="store_false")
    parser.set_defaults(run_check=True)
    args = parser.parse_args()

    summary = build_manifest(args)
    print(
        "HD release manifest: "
        f"{summary['status']} rows={summary['manifest_rows']} "
        f"mix={summary['vqa_mix_files']} files / 66 expected "
        f"hashed={summary['hashed_files']} skipped={summary['hash_skipped_files']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Manifest: {args.output / 'manifest.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
