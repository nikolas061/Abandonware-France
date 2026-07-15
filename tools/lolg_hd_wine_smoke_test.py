#!/usr/bin/env python3
"""Run a bounded Wine launch smoke test for the Full HD LOLG95 launcher."""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_wine_smoke_test")
DEFAULT_LAUNCHER = Path("RUN_HD_WINE.sh")
DEFAULT_WINEPREFIX = Path("output/lolg95_fullhd_wine_prefix")
ERROR_WINDOW_RE = re.compile(
    r"(Application Error|Program Error|Wine Debugger|Unhandled Exception|Fatal Error|Assertion failed)",
    re.IGNORECASE,
)
SUMMARY_FIELDS = [
    "status",
    "resolution",
    "display",
    "timeout_seconds",
    "sample_times",
    "samples",
    "matching_samples",
    "process_seen",
    "window_seen",
    "error_window_seen",
    "launcher_returncode",
    "cleaned_wineprefix",
    "gl_renderer",
    "gl_renderer_kind",
    "stdout",
    "stderr",
    "samples_csv",
    "issues",
    "next_step",
]
SAMPLE_FIELDS = [
    "sample_index",
    "elapsed_seconds",
    "window_id",
    "x",
    "y",
    "width",
    "height",
    "matches_resolution",
    "process_seen",
    "issues",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compact_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return "\n".join(value.splitlines()[-80:])


def run_command(command: list[str], env: dict[str, str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
        timeout=timeout,
        env=env,
    )


def detect_display() -> str:
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    x11_dir = Path("/tmp/.X11-unix")
    for socket in sorted(x11_dir.glob("X*")):
        suffix = socket.name[1:]
        if suffix.isdigit():
            return f":{suffix}"
    return ""


def parse_resolution(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"([0-9]+)x([0-9]+)", value)
    if not match:
        raise SystemExit(f"invalid resolution: {value}")
    return int(match.group(1)), int(match.group(2))


def get_lolg_window(env: dict[str, str], window_name: str) -> dict[str, str]:
    xdotool = shutil.which("xdotool")
    if not xdotool:
        return {"issues": "missing_xdotool"}
    deadline = time.monotonic() + 0.8
    search = None
    while True:
        try:
            search = run_command([xdotool, "search", "--name", window_name], env, timeout=5)
        except subprocess.TimeoutExpired:
            return {"issues": "xdotool_search_timeout"}
        if search.returncode == 0 and search.stdout.strip():
            break
        if time.monotonic() >= deadline:
            return {"issues": "window_not_found"}
        time.sleep(0.1)
    window_id = search.stdout.strip().splitlines()[-1].strip()
    try:
        geometry = run_command([xdotool, "getwindowgeometry", "--shell", window_id], env, timeout=5)
    except subprocess.TimeoutExpired:
        return {"window_id": window_id, "issues": "xdotool_geometry_timeout"}
    values = {"window_id": window_id, "issues": ""}
    for line in geometry.stdout.splitlines():
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        values[key.lower()] = raw_value.strip()
    if geometry.returncode != 0:
        values["issues"] = "geometry_failed"
    return values


def visible_window_names(env: dict[str, str]) -> str:
    xdotool = shutil.which("xdotool")
    if not xdotool:
        return "missing_xdotool"
    try:
        result = run_command(
            [xdotool, "search", "--onlyvisible", "--name", ".", "getwindowname", "%@"],
            env,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return "xdotool_visible_windows_timeout"
    text = compact_text(result.stdout + result.stderr)
    return text or f"xdotool_visible_windows_returncode={result.returncode}"


def error_window_names(visible_windows: str) -> list[str]:
    names: list[str] = []
    for line in visible_windows.splitlines():
        name = line.strip()
        if name and ERROR_WINDOW_RE.search(name):
            names.append(name)
    return names


def parse_gl_renderer(*paths: Path) -> tuple[str, str]:
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'GL_RENDERER "([^"]+)"', text)
        if not match:
            continue
        renderer = match.group(1)
        lowered = renderer.lower()
        if any(token in lowered for token in ("llvmpipe", "softpipe", "software rasterizer", "swrast")):
            return renderer, "software"
        return renderer, "hardware_or_driver"
    return "", "unknown"


def process_seen() -> bool:
    pgrep = shutil.which("pgrep")
    if not pgrep:
        return False
    result = subprocess.run(
        [pgrep, "-af", "LOLG95"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        check=False,
    )
    return "LOLG95" in result.stdout


def cleanup(process: subprocess.Popen[str], env: dict[str, str]) -> tuple[str, str]:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=6)

    wineserver = shutil.which("wineserver")
    if not wineserver:
        return "0", "missing_wineserver"
    try:
        result = run_command([wineserver, "-k"], env, timeout=10)
    except subprocess.TimeoutExpired:
        return "0", "wineserver_kill_timeout"
    return ("1" if result.returncode == 0 else "0"), compact_text(result.stderr)


def build_html(path: Path, summary: dict[str, str], samples: list[dict[str, str]]) -> None:
    sample_rows = []
    for row in samples:
        cls = "pass" if row["matches_resolution"] == "1" else "gap"
        sample_rows.append(
            "<tr>"
            f"<td>{html.escape(row['sample_index'])}</td>"
            f"<td>{html.escape(row['elapsed_seconds'])}</td>"
            f"<td>{html.escape(row['window_id'])}</td>"
            f"<td>{html.escape(row['width'])}x{html.escape(row['height'])}</td>"
            f"<td class='{cls}'>{html.escape(row['matches_resolution'])}</td>"
            f"<td>{html.escape(row['process_seen'])}</td>"
            f"<td>{html.escape(row['issues'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Wine Smoke Test</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
</style>
<h1>LOLG HD Wine Smoke Test</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Resolution: {html.escape(summary['resolution'])}; display: {html.escape(summary['display'])}</p>
<p>GL renderer: {html.escape(summary.get('gl_renderer', '') or 'unknown')} ({html.escape(summary.get('gl_renderer_kind', 'unknown'))})</p>
<p>Samples matching target: {html.escape(summary['matching_samples'])} match /
{html.escape(summary['samples'])} samples</p>
<table>
<thead><tr><th>#</th><th>Elapsed</th><th>Window</th><th>Geometry</th><th>Match</th><th>Process</th><th>Issues</th></tr></thead>
<tbody>
{''.join(sample_rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_smoke(args: argparse.Namespace) -> dict[str, str]:
    width, height = parse_resolution(args.resolution)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    stdout_path = output / "runtime_stdout.txt"
    stderr_path = output / "runtime_stderr.txt"
    samples_path = output / "samples.csv"
    windows_path = output / "visible_windows.txt"

    issues: list[str] = []
    display = args.display or detect_display()
    if not display:
        issues.append("missing_display")
    for tool in ("wine", "wineserver", "xdotool", "xwininfo"):
        if not shutil.which(tool):
            issues.append(f"missing_{tool}")
    if not args.launcher.is_file():
        issues.append("missing_launcher")

    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    env["WINEPREFIX"] = str(args.wineprefix.resolve())
    env["WINEDEBUG"] = args.winedebug
    env["LOLG_HD_RESOLUTION"] = args.resolution
    env["LOLG_HD_WINE_WAIT"] = "1"
    env["LOLG_HD_AUTO_RESIZE"] = "1" if args.auto_resize else "0"
    env["LOLG_HD_RESIZE_GAME_WINDOW"] = "1" if args.resize_game_window else "0"

    samples: list[dict[str, str]] = []
    visible_errors: list[str] = []
    launcher_returncode = ""
    cleaned = "0"
    cleanup_issue = ""

    if issues:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
    else:
        launcher = args.launcher
        if not launcher.is_absolute():
            launcher = Path.cwd() / launcher
        command = [str(launcher), *args.launcher_arg]
        if args.skip_wine_setup:
            command.append("--skip-wine-setup")
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            process = subprocess.Popen(
                command,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                cwd=Path.cwd(),
                env=env,
                start_new_session=True,
            )
            started = time.monotonic()
            try:
                for index, sample_time in enumerate(args.sample_at, start=1):
                    remaining = sample_time - (time.monotonic() - started)
                    if remaining > 0:
                        time.sleep(remaining)
                    geometry = get_lolg_window(env, args.window_name)
                    seen = process_seen()
                    visible_windows = visible_window_names(env)
                    sample_error_windows = error_window_names(visible_windows)
                    visible_errors.extend(sample_error_windows)
                    with windows_path.open("a", encoding="utf-8", errors="replace") as handle:
                        handle.write(f"\n--- sample {index} elapsed={time.monotonic() - started:.2f} ---\n")
                        handle.write(visible_windows)
                        handle.write("\n")
                    sample_width = geometry.get("width", "")
                    sample_height = geometry.get("height", "")
                    matches = sample_width == str(width) and sample_height == str(height)
                    sample_issues = [geometry.get("issues", "")]
                    if sample_error_windows:
                        sample_issues.append("error_window:" + "|".join(sample_error_windows))
                    samples.append(
                        {
                            "sample_index": str(index),
                            "elapsed_seconds": f"{time.monotonic() - started:.2f}",
                            "window_id": geometry.get("window_id", ""),
                            "x": geometry.get("x", ""),
                            "y": geometry.get("y", ""),
                            "width": sample_width,
                            "height": sample_height,
                            "matches_resolution": "1" if matches else "0",
                            "process_seen": "1" if seen else "0",
                            "issues": ";".join(issue for issue in sample_issues if issue),
                        }
                    )
                    if process.poll() is not None and not seen:
                        break
                timeout_remaining = args.timeout - (time.monotonic() - started)
                if timeout_remaining > 0:
                    time.sleep(min(2.0, timeout_remaining))
            finally:
                cleaned, cleanup_issue = cleanup(process, env)
                launcher_returncode = "" if process.returncode is None else str(process.returncode)

    matching_samples = sum(1 for row in samples if row["matches_resolution"] == "1")
    process_samples = sum(1 for row in samples if row["process_seen"] == "1")
    window_samples = sum(1 for row in samples if row["window_id"])
    unique_visible_errors = sorted(dict.fromkeys(visible_errors))
    gl_renderer, gl_renderer_kind = parse_gl_renderer(stderr_path, stdout_path)

    if cleanup_issue:
        issues.append(cleanup_issue)
    if not samples:
        issues.append("no_samples")
    if matching_samples != len(args.sample_at):
        issues.append("resolution_mismatch")
    if process_samples == 0:
        issues.append("process_not_seen")
    if window_samples == 0:
        issues.append("window_not_seen")
    if unique_visible_errors:
        issues.append("error_window_seen:" + "|".join(unique_visible_errors))

    # A bounded test normally terminates the launcher, so 143/SIGTERM is acceptable.
    acceptable_returncodes = {"", "0", "-15", "-9", "124", "143"}
    if launcher_returncode not in acceptable_returncodes:
        issues.append(f"launcher_returncode:{launcher_returncode}")

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "resolution": args.resolution,
        "display": display,
        "timeout_seconds": str(args.timeout),
        "sample_times": ";".join(str(value) for value in args.sample_at),
        "samples": str(len(samples)),
        "matching_samples": str(matching_samples),
        "process_seen": "1" if process_samples else "0",
        "window_seen": "1" if window_samples else "0",
        "error_window_seen": "1" if unique_visible_errors else "0",
        "launcher_returncode": launcher_returncode,
        "cleaned_wineprefix": cleaned,
        "gl_renderer": gl_renderer,
        "gl_renderer_kind": gl_renderer_kind,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "samples_csv": str(samples_path),
        "issues": ";".join(dict.fromkeys(issue for issue in issues if issue)),
        "next_step": "runtime smoke passed" if status == "pass" else "inspect smoke logs and rerun",
    }
    write_csv(samples_path, SAMPLE_FIELDS, samples)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, samples)
    return summary


def parse_sample_times(value: str) -> list[float]:
    times = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not times:
        raise argparse.ArgumentTypeError("at least one sample time is required")
    return sorted(times)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded LOLG95 Wine Full HD smoke test.")
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument("--display", default="")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sample-at", type=parse_sample_times, default=parse_sample_times("8,16"))
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument(
        "--launcher-arg",
        action="append",
        default=[],
        help="Argument inserted between the launcher path and --skip-wine-setup; repeat for multiple arguments.",
    )
    parser.add_argument("--wineprefix", type=Path, default=DEFAULT_WINEPREFIX)
    parser.add_argument("--window-name", default="Lands Of Lore Guardians")
    parser.add_argument("--skip-wine-setup", action="store_true", default=True)
    parser.add_argument("--no-skip-wine-setup", action="store_false", dest="skip_wine_setup")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--winedebug", default="fixme+d3d")
    parser.add_argument("--auto-resize", action="store_true", default=True)
    parser.add_argument("--no-auto-resize", action="store_false", dest="auto_resize")
    parser.add_argument("--resize-game-window", action="store_true", default=True)
    parser.add_argument("--no-resize-game-window", action="store_false", dest="resize_game_window")
    args = parser.parse_args()

    summary = run_smoke(args)
    print(
        "HD Wine smoke test: "
        f"{summary['status']} resolution={summary['resolution']} "
        f"samples={summary['matching_samples']} match / {summary['samples']} samples"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
