#!/usr/bin/env python3
"""Rank exploratory .tex probe previews by simple image-structure metrics."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
from collections import Counter
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_unresolved_material_probe_render")

SUMMARY_FIELDNAMES = [
    "scope",
    "preview_rows",
    "analyzed_rows",
    "best_candidate_rows",
    "unique_pcx",
    "segments",
    "issue_rows",
    "best_score",
    "median_score",
]

ANALYSIS_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "material_clean_text",
    "segment_index",
    "body_offset",
    "body_offset_hex",
    "body_first_word",
    "segment_size",
    "skip",
    "width",
    "height",
    "native_path",
    "fullhd_path",
    "entropy",
    "dominant_ratio",
    "zero_ratio",
    "horizontal_equal_ratio",
    "vertical_equal_ratio",
    "row_repeat_ratio",
    "horizontal_absdiff",
    "vertical_absdiff",
    "structure_score",
    "issues",
]

BEST_FIELDNAMES = ["rank"] + ANALYSIS_FIELDNAMES


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def ratio(value: float) -> str:
    return f"{value:.6f}"


def entropy_from_counts(counts: Counter[int], total: int) -> float:
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def mean_absdiff(pairs: list[tuple[int, int]]) -> float:
    if not pairs:
        return 0.0
    return sum(abs(left - right) for left, right in pairs) / (len(pairs) * 255.0)


def analyze_pixels(data: bytes, width: int, height: int) -> dict[str, float]:
    total = len(data)
    counts = Counter(data)
    dominant = max(counts.values()) / total if total else 0.0
    zero = counts.get(0, 0) / total if total else 0.0
    entropy = entropy_from_counts(counts, total)

    horizontal_pairs: list[tuple[int, int]] = []
    horizontal_equal = 0
    if width > 1:
        for y in range(height):
            row_start = y * width
            row = data[row_start : row_start + width]
            for x in range(width - 1):
                left = row[x]
                right = row[x + 1]
                horizontal_pairs.append((left, right))
                if left == right:
                    horizontal_equal += 1

    vertical_pairs: list[tuple[int, int]] = []
    vertical_equal = 0
    repeated_rows = 0
    if height > 1:
        for y in range(height - 1):
            row_a = data[y * width : (y + 1) * width]
            row_b = data[(y + 1) * width : (y + 2) * width]
            if row_a == row_b:
                repeated_rows += 1
            for x in range(width):
                top = row_a[x]
                bottom = row_b[x]
                vertical_pairs.append((top, bottom))
                if top == bottom:
                    vertical_equal += 1

    horizontal_ratio = horizontal_equal / len(horizontal_pairs) if horizontal_pairs else 0.0
    vertical_ratio = vertical_equal / len(vertical_pairs) if vertical_pairs else 0.0
    row_repeat_ratio = repeated_rows / (height - 1) if height > 1 else 0.0
    horizontal_absdiff = mean_absdiff(horizontal_pairs)
    vertical_absdiff = mean_absdiff(vertical_pairs)
    normalized_entropy = min(1.0, entropy / 8.0)
    score = (
        vertical_ratio * 0.34
        + horizontal_ratio * 0.24
        + row_repeat_ratio * 0.18
        + dominant * 0.12
        + (1.0 - normalized_entropy) * 0.12
    )
    return {
        "entropy": entropy,
        "dominant_ratio": dominant,
        "zero_ratio": zero,
        "horizontal_equal_ratio": horizontal_ratio,
        "vertical_equal_ratio": vertical_ratio,
        "row_repeat_ratio": row_repeat_ratio,
        "horizontal_absdiff": horizontal_absdiff,
        "vertical_absdiff": vertical_absdiff,
        "structure_score": score,
    }


def load_native_bytes(path: Path) -> tuple[bytes, int, int, str]:
    with Image.open(path) as image:
        if image.mode not in {"1", "L", "P"}:
            image = image.convert("L")
        return image.tobytes(), image.width, image.height, image.mode


def analyze_row(row: dict[str, str]) -> dict[str, str]:
    issues: list[str] = []
    native_path = Path(row.get("native_path", ""))
    expected_width = int(row.get("width") or 0)
    expected_height = int(row.get("height") or 0)
    metrics = {
        "entropy": 0.0,
        "dominant_ratio": 0.0,
        "zero_ratio": 0.0,
        "horizontal_equal_ratio": 0.0,
        "vertical_equal_ratio": 0.0,
        "row_repeat_ratio": 0.0,
        "horizontal_absdiff": 0.0,
        "vertical_absdiff": 0.0,
        "structure_score": 0.0,
    }
    if not native_path.exists():
        issues.append("missing_native_path")
    else:
        try:
            data, width, height, _mode = load_native_bytes(native_path)
            if (width, height) != (expected_width, expected_height):
                issues.append("native_dimensions_mismatch")
            metrics = analyze_pixels(data, width, height)
        except Exception as exc:
            issues.append(f"analysis_failed:{exc}")

    return {
        "archive": row.get("archive", ""),
        "archive_tag": row.get("archive_tag", ""),
        "pcx_name": row.get("pcx_name", ""),
        "material_clean_text": row.get("material_clean_text", ""),
        "segment_index": row.get("segment_index", ""),
        "body_offset": row.get("body_offset", ""),
        "body_offset_hex": row.get("body_offset_hex", ""),
        "body_first_word": row.get("body_first_word", ""),
        "segment_size": row.get("segment_size", ""),
        "skip": row.get("skip", ""),
        "width": row.get("width", ""),
        "height": row.get("height", ""),
        "native_path": row.get("native_path", ""),
        "fullhd_path": row.get("fullhd_path", ""),
        "entropy": ratio(metrics["entropy"]),
        "dominant_ratio": ratio(metrics["dominant_ratio"]),
        "zero_ratio": ratio(metrics["zero_ratio"]),
        "horizontal_equal_ratio": ratio(metrics["horizontal_equal_ratio"]),
        "vertical_equal_ratio": ratio(metrics["vertical_equal_ratio"]),
        "row_repeat_ratio": ratio(metrics["row_repeat_ratio"]),
        "horizontal_absdiff": ratio(metrics["horizontal_absdiff"]),
        "vertical_absdiff": ratio(metrics["vertical_absdiff"]),
        "structure_score": ratio(metrics["structure_score"]),
        "issues": ";".join(issues),
    }


def segment_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", ""),
        row.get("segment_index", ""),
        row.get("body_offset", ""),
    )


def select_best(rows: list[dict[str, str]], top_per_segment: int) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(segment_key(row), []).append(row)

    best_rows: list[dict[str, str]] = []
    for group in grouped.values():
        ranked = sorted(
            group,
            key=lambda row: (
                float(row.get("structure_score") or 0),
                -float(row.get("entropy") or 0),
                row.get("width", ""),
                row.get("skip", ""),
            ),
            reverse=True,
        )
        for rank, row in enumerate(ranked[:top_per_segment], start=1):
            best_rows.append({"rank": str(rank), **row})
    return sorted(
        best_rows,
        key=lambda row: (
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            row.get("segment_index", ""),
            int(row.get("rank") or 0),
        ),
    )


def summary_row(rows: list[dict[str, str]], best_rows: list[dict[str, str]]) -> dict[str, str]:
    scores = sorted(float(row.get("structure_score") or 0) for row in rows if not row.get("issues"))
    if scores:
        median = scores[len(scores) // 2]
        best = scores[-1]
    else:
        median = 0.0
        best = 0.0
    return {
        "scope": "total",
        "preview_rows": str(len(rows)),
        "analyzed_rows": str(sum(1 for row in rows if not row.get("issues"))),
        "best_candidate_rows": str(len(best_rows)),
        "unique_pcx": str(len({row["pcx_name"].lower() for row in rows if row["pcx_name"]})),
        "segments": str(len({segment_key(row) for row in rows})),
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
        "best_score": ratio(best),
        "median_score": ratio(median),
    }


def render_best_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_path", ""), output_dir))
    title = f"{row.get('pcx_name', '')} rank {row.get('rank', '')}"
    details = (
        f"{row.get('archive_tag', '')} seg {row.get('segment_index', '')} "
        f"w{row.get('width', '')} skip {row.get('skip', '')}"
    )
    metrics = (
        f"score {row.get('structure_score', '')} / h {row.get('horizontal_equal_ratio', '')} "
        f"/ v {row.get('vertical_equal_ratio', '')}"
    )
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="muted">{html.escape(details)}</div>
    <div class="muted">{html.escape(metrics)}</div>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "analysis": rows, "best": best_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_best_card(row, output_dir) for row in best_rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("analysis_summary.csv", output_dir / "analysis_summary.csv"),
            ("analysis.csv", output_dir / "analysis.csv"),
            ("best_candidates.csv", output_dir / "best_candidates.csv"),
            ("probe gallery", output_dir / "index.html"),
        )
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
  --ok: #78d98f;
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
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
}}
.preview {{
  display: block;
  aspect-ratio: 16 / 9;
  background: #060708;
  border-bottom: 1px solid var(--line);
}}
.preview img {{ width: 100%; height: 100%; object-fit: contain; }}
.body {{ padding: 10px; display: grid; gap: 5px; }}
.title {{ font-weight: 700; overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Previews analysees</div><div class="value">{html.escape(summary['analyzed_rows'])}</div></div>
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segments'])}</div></div>
    <div class="stat"><div class="label">Candidats</div><div class="value">{html.escape(summary['best_candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <div>{links}</div>
  </section>
  <section class="grid">{cards}</section>
</main>
<script>
const TEX_PROBE_ANALYSIS = {data_json};
</script>
</body>
</html>
"""


def write_analysis(output_dir: Path, title: str, top_per_segment: int) -> tuple[dict[str, str], list[dict[str, str]]]:
    rows = [analyze_row(row) for row in read_rows(output_dir / "gallery_manifest.csv")]
    best_rows = select_best(rows, top_per_segment)
    summary = summary_row(rows, best_rows)
    write_csv(output_dir / "analysis_summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "analysis.csv", ANALYSIS_FIELDNAMES, rows)
    write_csv(output_dir / "best_candidates.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "analysis.html").write_text(build_html(summary, rows, best_rows, output_dir, title))
    return summary, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank .tex probe previews by image structure.")
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-per-segment", type=int, default=3)
    parser.add_argument("--title", default="Lands of Lore II .tex Probe Analysis")
    args = parser.parse_args()

    summary, _best_rows = write_analysis(args.output, args.title, args.top_per_segment)
    print(f"Analyzed previews: {summary['analyzed_rows']}/{summary['preview_rows']}")
    print(f"Segments: {summary['segments']}")
    print(f"Best candidates: {summary['best_candidate_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'analysis.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
