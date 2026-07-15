#!/usr/bin/env python3
"""Diagnose whether the Wine Full HD path is using hardware graphics."""

from __future__ import annotations

import argparse
import csv
import html
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_graphics_check")
DEFAULT_WINE_SMOKE_SUMMARY = Path("output/hd_wine_smoke_test/summary.csv")

SUMMARY_FIELDS = [
    "status",
    "checks",
    "pass_checks",
    "gap_checks",
    "info_checks",
    "wine_gl_renderer",
    "wine_gl_renderer_kind",
    "display",
    "gpu_summary",
    "issues",
    "next_step",
]
CHECK_FIELDS = ["check", "status", "evidence", "next_step"]


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


def run_command(command: list[str], timeout: int = 5) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}:{exc}"
    return result.returncode, result.stdout, result.stderr


def add_check(
    rows: list[dict[str, str]],
    check: str,
    status: str,
    evidence: str,
    next_step: str,
) -> None:
    rows.append(
        {
            "check": check,
            "status": status,
            "evidence": evidence,
            "next_step": next_step,
        }
    )


def classify_renderer(renderer: str) -> str:
    lowered = renderer.lower()
    if not renderer:
        return "unknown"
    if any(token in lowered for token in ("llvmpipe", "softpipe", "software rasterizer", "swrast")):
        return "software"
    return "hardware_or_driver"


def detect_display() -> str:
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    x11_dir = Path("/tmp/.X11-unix")
    for socket in sorted(x11_dir.glob("X*")):
        suffix = socket.name[1:]
        if suffix.isdigit():
            return f":{suffix}"
    return ""


def build_html(path: Path, summary: dict[str, str], checks: list[dict[str, str]]) -> None:
    rows_html = []
    for row in checks:
        status = row["status"]
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(row['check'])}</td>"
            f"<td class='{html.escape(status)}'>{html.escape(status)}</td>"
            f"<td>{html.escape(row['evidence'])}</td>"
            f"<td>{html.escape(row['next_step'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Graphics Check</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
.info {{ color: #555; font-weight: 700; }}
</style>
<h1>LOLG HD Graphics Check</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Checks: {html.escape(summary['pass_checks'])} pass + {html.escape(summary['info_checks'])} info /
{html.escape(summary['checks'])}, gaps={html.escape(summary['gap_checks'])}</p>
<p>Wine renderer: {html.escape(summary['wine_gl_renderer'] or 'unknown')} ({html.escape(summary['wine_gl_renderer_kind'])})</p>
<p>Display: {html.escape(summary['display'])}</p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Evidence</th><th>Next step</th></tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_check(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, str]] = []

    smoke = read_csv_first(args.wine_smoke_summary)
    wine_renderer = smoke.get("gl_renderer", "")
    wine_renderer_kind = smoke.get("gl_renderer_kind") or classify_renderer(wine_renderer)
    add_check(
        checks,
        "wine_smoke_renderer",
        "pass" if wine_renderer_kind == "hardware_or_driver" else "gap",
        f"renderer={wine_renderer};kind={wine_renderer_kind};source={args.wine_smoke_summary}",
        "run TEST_HD_WINE.sh from a session with hardware OpenGL if this reports software",
    )

    display = args.display or smoke.get("display") or detect_display()
    add_check(
        checks,
        "display",
        "pass" if display else "gap",
        display,
        "start from an X11/Wayland session with DISPLAY set",
    )

    glxinfo = shutil.which("glxinfo")
    if glxinfo:
        env = os.environ.copy()
        if display:
            env["DISPLAY"] = display
        try:
            result = subprocess.run(
                [glxinfo, "-B"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                check=False,
                timeout=8,
                env=env,
            )
            glx_text = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            glx_text = "glxinfo_timeout"
            result_code = 124
        else:
            result_code = result.returncode
        renderer = ""
        for line in glx_text.splitlines():
            if "OpenGL renderer string:" in line:
                renderer = line.split(":", 1)[1].strip()
                break
        kind = classify_renderer(renderer)
        add_check(
            checks,
            "glxinfo_renderer",
            "pass" if result_code == 0 and kind == "hardware_or_driver" else "gap",
            f"returncode={result_code};renderer={renderer};kind={kind}",
            "install/use a hardware OpenGL stack if glxinfo also reports software",
        )
    else:
        add_check(
            checks,
            "glxinfo_renderer",
            "info",
            "glxinfo not installed",
            "install mesa-utils for an independent OpenGL renderer check",
        )

    code, xdpyinfo_out, xdpyinfo_err = run_command(["xdpyinfo"], timeout=8)
    glx_present = "GLX" in xdpyinfo_out
    dimensions = ""
    for line in xdpyinfo_out.splitlines():
        if "dimensions:" in line:
            dimensions = line.strip()
            break
    add_check(
        checks,
        "x11_glx",
        "pass" if code == 0 and glx_present else "gap",
        f"returncode={code};glx={glx_present};{dimensions};stderr={xdpyinfo_err.strip()}",
        "fix DISPLAY/X11 GLX availability",
    )

    dri = Path("/dev/dri")
    dri_entries = sorted(path.name for path in dri.iterdir()) if dri.is_dir() else []
    render_nodes = [name for name in dri_entries if name.startswith("renderD")]
    add_check(
        checks,
        "dri_render_nodes",
        "pass" if render_nodes else "gap",
        "entries=" + ";".join(dri_entries),
        "hardware Mesa usually exposes /dev/dri/renderD*; check VM/driver/session permissions",
    )

    code, id_out, _id_err = run_command(["id", "-nG"], timeout=5)
    groups = id_out.strip().split() if code == 0 else []
    add_check(
        checks,
        "user_graphics_groups",
        "pass" if "render" in groups or "video" in groups else "gap",
        "groups=" + ";".join(groups),
        "add the user to render/video groups if direct rendering devices require it",
    )

    code, lspci_out, lspci_err = run_command(["lspci", "-nn"], timeout=8)
    gpu_lines = [
        line
        for line in lspci_out.splitlines()
        if any(token in line.lower() for token in ("vga", "3d", "display", "nvidia", "amd", "radeon", "intel"))
    ]
    gpu_summary = " | ".join(gpu_lines)
    virtual_gpu = any(token in gpu_summary.lower() for token in ("qxl", "virtio", "vmware", "bochs", "virtualbox"))
    add_check(
        checks,
        "pci_gpu",
        "gap" if virtual_gpu else ("pass" if gpu_lines else "info"),
        gpu_summary or f"returncode={code};stderr={lspci_err.strip()}",
        "use a host/session exposing the physical GPU if this is a virtual adapter",
    )

    code, xrandr_out, xrandr_err = run_command(["xrandr", "--listproviders"], timeout=8)
    provider_line = xrandr_out.strip().replace("\n", " | ")
    no_provider = "Providers: number : 0" in xrandr_out
    add_check(
        checks,
        "xrandr_providers",
        "gap" if no_provider else ("pass" if code == 0 else "info"),
        provider_line or f"returncode={code};stderr={xrandr_err.strip()}",
        "configure XRandR/driver providers if no GPU provider is exposed",
    )

    pass_checks = sum(1 for row in checks if row["status"] == "pass")
    gap_checks = [row["check"] for row in checks if row["status"] == "gap"]
    info_checks = sum(1 for row in checks if row["status"] == "info")
    status = "pass" if wine_renderer_kind == "hardware_or_driver" and not gap_checks else "gap"
    summary = {
        "status": status,
        "checks": str(len(checks)),
        "pass_checks": str(pass_checks),
        "gap_checks": str(len(gap_checks)),
        "info_checks": str(info_checks),
        "wine_gl_renderer": wine_renderer,
        "wine_gl_renderer_kind": wine_renderer_kind,
        "display": display,
        "gpu_summary": gpu_summary,
        "issues": ";".join(gap_checks),
        "next_step": (
            "hardware OpenGL renderer detected"
            if status == "pass"
            else "Wine HD runs, but hardware GPU acceleration is not proven in this session"
        ),
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose graphics acceleration for the LOLG HD Wine path.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--wine-smoke-summary", type=Path, default=DEFAULT_WINE_SMOKE_SUMMARY)
    parser.add_argument("--display", default="")
    args = parser.parse_args()

    summary = run_check(args)
    print(
        "HD graphics check: "
        f"{summary['status']} checks={summary['pass_checks']} pass + "
        f"{summary['info_checks']} info / {summary['checks']} "
        f"gaps={summary['gap_checks']} renderer={summary['wine_gl_renderer'] or 'unknown'} "
        f"kind={summary['wine_gl_renderer_kind']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
