#!/usr/bin/env python3
"""Summarize the current LOLG Full HD release state without launching the game."""

from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_status")
DEFAULT_RELEASE_SUMMARY = Path("output/hd_release_check/summary.csv")
DEFAULT_MANIFEST_SUMMARY = Path("output/hd_release_manifest/summary.csv")
DEFAULT_MANIFEST_VERIFY_SUMMARY = Path("output/hd_release_manifest_verify/summary.csv")
DEFAULT_RESOLUTION_SUMMARY = Path("output/hd_resolution_check/summary.csv")
DEFAULT_GPU_SUMMARY = Path("output/hd_graphics_check/summary.csv")
DEFAULT_SMOKE_SUMMARY = Path("output/hd_wine_smoke_test/summary.csv")
DEFAULT_SMOKE_1280_SUMMARY = Path("output/hd_wine_smoke_test_1280x1024/summary.csv")
DEFAULT_SIDECAR_CACHE_ROOT = Path("output/vqa_external_sidecar_cache")

CRITICAL_SIDECAR_RESULTS = [
    ("locallng", "LOCALLNG.MIX", "fca4e133"),
    ("movies", "MOVIES.MIX", "4d6efa8e"),
]

SUMMARY_FIELDS = [
    "status",
    "ready_to_launch",
    "hardware_gpu_proven",
    "runtime_active",
    "runtime_processes",
    "release_check_status",
    "release_checks",
    "release_passed",
    "release_info",
    "release_gaps",
    "manifest_status",
    "manifest_rows",
    "manifest_verify_status",
    "manifest_verify_checked",
    "manifest_verify_passed",
    "manifest_verify_info",
    "manifest_verify_gaps",
    "resolution_status",
    "resolution_checks",
    "resolution_passed",
    "resolution_gaps",
    "vqa_mix_files",
    "vqa_mix_bytes",
    "sidecar_critical_ready",
    "sidecar_locallng_ready_frames",
    "sidecar_locallng_frames",
    "sidecar_locallng_full_ready",
    "sidecar_movies_ready_frames",
    "sidecar_movies_frames",
    "sidecar_movies_full_ready",
    "sidecar_critical_issues",
    "sidecar_critical_full_ready",
    "sidecar_critical_full_issues",
    "smoke_status",
    "smoke_resolution",
    "smoke_samples",
    "smoke_matching_samples",
    "smoke_1280_status",
    "smoke_1280_resolution",
    "smoke_1280_samples",
    "smoke_1280_matching_samples",
    "gl_renderer",
    "gl_renderer_kind",
    "gpu_status",
    "gpu_issues",
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


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"status": "invalid_json"}
    return payload if isinstance(payload, dict) else {}


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def count_ready_frames(decode_dir_text: str) -> int:
    if not decode_dir_text:
        return 0
    frames_dir = resolve_project_path(decode_dir_text) / "frames_fullhd"
    if not frames_dir.is_dir():
        return 0
    return len(list(frames_dir.glob("*.png")))


def sidecar_critical_status(cache_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    issues: list[str] = []
    full_issues: list[str] = []
    for label, archive, file_id in CRITICAL_SIDECAR_RESULTS:
        result_path = cache_root / archive / file_id / "result.json"
        result = read_json(result_path)
        ready_frames = count_ready_frames(str(result.get("decode_dir", "")))
        frames = str(result.get("frames", ""))
        try:
            frame_count = int(frames)
        except ValueError:
            frame_count = 0
        width = str(result.get("width", ""))
        height = str(result.get("height", ""))
        status = str(result.get("status", "missing"))
        ready = status == "decoded" and width == "1920" and height == "1080" and ready_frames > 0
        full_ready = ready and frame_count > 0 and ready_frames >= frame_count
        if not ready:
            issues.append(label)
        if not full_ready:
            full_issues.append(label)
        values[f"sidecar_{label}_ready_frames"] = str(ready_frames)
        values[f"sidecar_{label}_frames"] = frames
        values[f"sidecar_{label}_full_ready"] = "1" if full_ready else "0"
    values["sidecar_critical_ready"] = "1" if not issues else "0"
    values["sidecar_critical_issues"] = ";".join(issues)
    values["sidecar_critical_full_ready"] = "1" if not full_issues else "0"
    values["sidecar_critical_full_issues"] = ";".join(full_issues)
    return values


def build_html(path: Path, summary: dict[str, str]) -> None:
    rows = []
    for key in SUMMARY_FIELDS:
        rows.append(
            "<tr>"
            f"<th>{html.escape(key)}</th>"
            f"<td>{html.escape(summary.get(key, ''))}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Status</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; background: white; min-width: 50rem; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
</style>
<h1>LOLG HD Status</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<table>
<tbody>
{''.join(rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def detect_runtime_processes() -> str:
    root = Path.cwd()
    pattern = "|".join(
        [
            str(root / "RUN_HD_WINE.sh"),
            str(root / "output/lolg95_fullhd_wine_runtime"),
            r"D:\\WESTWOOD\\LOLG",
        ]
    )
    try:
        result = subprocess.run(
            ["pgrep", "-af", pattern],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode not in {0, 1}:
        return ""
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return " | ".join(lines)


def refresh_manifest_verify(args: argparse.Namespace) -> None:
    if not args.refresh_manifest_verify:
        return
    manifest_path = args.manifest_summary.with_name("manifest.csv")
    output_path = args.manifest_verify_summary.parent
    try:
        subprocess.run(
            [
                "python3",
                "tools/lolg_hd_manifest_verify.py",
                "--manifest",
                str(manifest_path),
                "-o",
                str(output_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def refresh_resolution_check(args: argparse.Namespace) -> None:
    if not args.refresh_resolution_check:
        return
    output_path = args.resolution_summary.parent
    try:
        subprocess.run(
            [
                "python3",
                "tools/lolg_hd_resolution_check.py",
                "-o",
                str(output_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def format_sample_summary(matching_samples: str, samples: str) -> str:
    if not samples:
        return "not run"
    return f"{matching_samples or '0'} match / {samples} samples"


def build_status(args: argparse.Namespace) -> dict[str, str]:
    refresh_resolution_check(args)
    refresh_manifest_verify(args)
    release = read_csv_first(args.release_summary)
    manifest = read_csv_first(args.manifest_summary)
    manifest_verify = read_csv_first(args.manifest_verify_summary)
    resolution = read_csv_first(args.resolution_summary)
    gpu = read_csv_first(args.gpu_summary)
    smoke = read_csv_first(args.smoke_summary)
    smoke_1280 = read_csv_first(args.smoke_1280_summary)
    sidecar_critical = sidecar_critical_status(args.sidecar_cache_root)

    issues = []
    if release.get("status") != "pass":
        issues.append("release_check")
    if manifest.get("status") != "pass":
        issues.append("manifest")
    if manifest_verify.get("status") != "pass":
        issues.append("manifest_verify")
    if resolution.get("status") != "pass":
        issues.append("resolution_check")
    if sidecar_critical.get("sidecar_critical_ready") != "1":
        issues.append("sidecar_critical")
    ready_to_launch = not issues
    gpu_status = gpu.get("status", "")
    gl_renderer_kind = smoke.get("gl_renderer_kind") or gpu.get("wine_gl_renderer_kind", "")
    hardware_gpu_proven = gpu_status == "pass" and gl_renderer_kind == "hardware"
    runtime_processes = detect_runtime_processes()
    runtime_active = bool(runtime_processes)

    summary = {
        "status": "pass" if ready_to_launch else "gap",
        "ready_to_launch": "1" if ready_to_launch else "0",
        "hardware_gpu_proven": "1" if hardware_gpu_proven else "0",
        "runtime_active": "1" if runtime_active else "0",
        "runtime_processes": runtime_processes,
        "release_check_status": release.get("status", ""),
        "release_checks": release.get("checks", ""),
        "release_passed": release.get("passed", ""),
        "release_info": release.get("info", ""),
        "release_gaps": release.get("gaps", ""),
        "manifest_status": manifest.get("status", ""),
        "manifest_rows": manifest.get("manifest_rows", ""),
        "manifest_verify_status": manifest_verify.get("status", ""),
        "manifest_verify_checked": manifest_verify.get("checked", ""),
        "manifest_verify_passed": manifest_verify.get("passed", ""),
        "manifest_verify_info": manifest_verify.get("info", ""),
        "manifest_verify_gaps": manifest_verify.get("gaps", ""),
        "resolution_status": resolution.get("status", ""),
        "resolution_checks": resolution.get("checks", ""),
        "resolution_passed": resolution.get("passed", ""),
        "resolution_gaps": resolution.get("gaps", ""),
        "vqa_mix_files": manifest.get("vqa_mix_files", ""),
        "vqa_mix_bytes": manifest.get("vqa_mix_bytes", ""),
        **sidecar_critical,
        "smoke_status": smoke.get("status", ""),
        "smoke_resolution": smoke.get("resolution", ""),
        "smoke_samples": smoke.get("samples", ""),
        "smoke_matching_samples": smoke.get("matching_samples", ""),
        "smoke_1280_status": smoke_1280.get("status", ""),
        "smoke_1280_resolution": smoke_1280.get("resolution", ""),
        "smoke_1280_samples": smoke_1280.get("samples", ""),
        "smoke_1280_matching_samples": smoke_1280.get("matching_samples", ""),
        "gl_renderer": smoke.get("gl_renderer") or gpu.get("wine_gl_renderer", ""),
        "gl_renderer_kind": gl_renderer_kind,
        "gpu_status": gpu_status,
        "gpu_issues": gpu.get("issues", ""),
        "issues": ";".join(issues),
        "next_step": (
            "runtime already active; use ./LOLG_HD.sh stop if it is stuck"
            if ready_to_launch and runtime_active
            else "predecode all critical VQA frames with ./LOLG_HD.sh sidecar-critical-warmup"
            if ready_to_launch and sidecar_critical.get("sidecar_critical_full_ready") != "1"
            else "launch with ./LOLG_HD.sh; hardware GPU still needs a real GPU session"
            if ready_to_launch and not hardware_gpu_proven
            else "launch with ./LOLG_HD.sh sidecar-hd"
            if ready_to_launch
            else "run ./LOLG_HD.sh check, ./LOLG_HD.sh resolutions, ./LOLG_HD.sh manifest and ./LOLG_HD.sh verify-manifest"
        ),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(args.output / "index.html", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize the current LOLG HD release status.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--release-summary", type=Path, default=DEFAULT_RELEASE_SUMMARY)
    parser.add_argument("--manifest-summary", type=Path, default=DEFAULT_MANIFEST_SUMMARY)
    parser.add_argument("--manifest-verify-summary", type=Path, default=DEFAULT_MANIFEST_VERIFY_SUMMARY)
    parser.add_argument("--resolution-summary", type=Path, default=DEFAULT_RESOLUTION_SUMMARY)
    parser.add_argument("--skip-manifest-verify-refresh", dest="refresh_manifest_verify", action="store_false")
    parser.add_argument("--skip-resolution-refresh", dest="refresh_resolution_check", action="store_false")
    parser.set_defaults(refresh_manifest_verify=True, refresh_resolution_check=True)
    parser.add_argument("--gpu-summary", type=Path, default=DEFAULT_GPU_SUMMARY)
    parser.add_argument("--smoke-summary", type=Path, default=DEFAULT_SMOKE_SUMMARY)
    parser.add_argument("--smoke-1280-summary", type=Path, default=DEFAULT_SMOKE_1280_SUMMARY)
    parser.add_argument("--sidecar-cache-root", type=Path, default=DEFAULT_SIDECAR_CACHE_ROOT)
    args = parser.parse_args()

    summary = build_status(args)
    print(f"LOLG HD status: {summary['status']}")
    print(
        "Ready to launch: "
        f"{'yes' if summary['ready_to_launch'] == '1' else 'no'} "
        f"(release {summary['release_passed']} pass"
        f" + {summary['release_info']} info"
        f" / {summary['release_checks']}, "
        f"gaps={summary['release_gaps']}, "
        f"manifest {summary['manifest_status']}, "
        f"verify {summary['manifest_verify_status']}, "
        f"resolutions {summary['resolution_status']}, "
        f"smoke_diag 1920={summary['smoke_status'] or 'missing'} "
        f"1280={summary['smoke_1280_status'] or 'missing'})"
    )
    print(
        "VQA MIX pack: "
        f"{summary['vqa_mix_files']} files / 66 expected, {summary['vqa_mix_bytes']} bytes"
    )
    print(
        "Manifest verify: "
        f"{summary['manifest_verify_passed']} pass"
        f" + {summary['manifest_verify_info']} info"
        f" / {summary['manifest_verify_checked']} rows, "
        f"gaps={summary['manifest_verify_gaps']}"
    )
    print(
        "Resolution check: "
        f"{summary['resolution_passed']} pass / {summary['resolution_checks']} checks, "
        f"gaps={summary['resolution_gaps']}"
    )
    print(
        "Sidecar critical: "
        f"{'ready' if summary['sidecar_critical_ready'] == '1' else 'gap'} "
        f"(LOCALLNG {summary['sidecar_locallng_ready_frames']}/{summary['sidecar_locallng_frames']} frames, "
        f"MOVIES {summary['sidecar_movies_ready_frames']}/{summary['sidecar_movies_frames']} frames)"
    )
    print(
        "Sidecar critical full cache: "
        f"{'ready' if summary['sidecar_critical_full_ready'] == '1' else 'gap'}"
    )
    print(
        "Wine smoke 1920x1080 (diagnostic): "
        f"{format_sample_summary(summary['smoke_matching_samples'], summary['smoke_samples'])}, "
        f"renderer={summary['gl_renderer_kind']}"
    )
    print(
        "Wine smoke 1280x1024 (diagnostic): "
        f"{format_sample_summary(summary['smoke_1280_matching_samples'], summary['smoke_1280_samples'])}"
    )
    print(
        "Hardware GPU: "
        f"{'proven' if summary['hardware_gpu_proven'] == '1' else 'not proven'} "
        f"(gpu check {summary['gpu_status']})"
    )
    print(
        "Runtime Wine HD: "
        f"{'active' if summary['runtime_active'] == '1' else 'not active'}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
