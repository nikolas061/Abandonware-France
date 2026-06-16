#!/usr/bin/env python3
"""Rank direct .tex/CDCACHE chunk matches as decoder seed candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_decoder_seed_report")
DEFAULT_MATCHES = Path("output/tex_exact_chunk_evidence/matches.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "match_rows",
    "seed_rows",
    "strong_seed_rows",
    "medium_seed_rows",
    "weak_seed_rows",
    "unique_pcx",
    "issue_rows",
]

SEED_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "chunk_size",
    "pixel_offset",
    "pixel_offset_hex",
    "pixel_x",
    "pixel_y",
    "segment_offset",
    "segment_offset_hex",
    "extra_segment_occurrences",
    "entropy",
    "zero_ratio",
    "unique_values",
    "score",
    "seed_class",
    "reason",
    "pixel_hex",
    "segment_context_hex",
    "pixel_context_hex",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    value = 0.0
    for count in counts.values():
        p = count / total
        value -= p * math.log2(p)
    return value


def classify_seed(chunk_size: int, value_entropy: float, zero_ratio: float, extra_occurrences: int) -> tuple[str, str]:
    if chunk_size >= 16 and value_entropy >= 2.5 and zero_ratio <= 0.25 and extra_occurrences == 0:
        return "strong", "long_nonzero_unique"
    if chunk_size >= 8 and value_entropy >= 2.4 and zero_ratio <= 0.25 and extra_occurrences <= 1:
        return "medium", "nonzero_low_repeat"
    if zero_ratio >= 0.75:
        return "weak", "zero_heavy"
    if extra_occurrences > 1:
        return "weak", "repeated_chunk"
    return "weak", "short_or_low_entropy"


def score_seed(chunk_size: int, value_entropy: float, zero_ratio: float, extra_occurrences: int) -> float:
    size_weight = math.log2(max(2, chunk_size))
    repeat_penalty = 1.0 / (1.0 + extra_occurrences)
    zero_penalty = 1.0 - min(0.95, zero_ratio)
    return value_entropy * size_weight * repeat_penalty * zero_penalty


def build_seed_rows(match_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in match_rows:
        issues = row.get("issues", "")
        if issues or not row.get("segment_offset"):
            rows.append(
                {
                    "rank": "",
                    "archive": row.get("archive", ""),
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "chunk_size": row.get("chunk_size", ""),
                    "pixel_offset": row.get("pixel_offset", ""),
                    "pixel_offset_hex": row.get("pixel_offset_hex", ""),
                    "pixel_x": row.get("pixel_x", ""),
                    "pixel_y": row.get("pixel_y", ""),
                    "segment_offset": row.get("segment_offset", ""),
                    "segment_offset_hex": row.get("segment_offset_hex", ""),
                    "extra_segment_occurrences": row.get("extra_segment_occurrences", ""),
                    "entropy": "",
                    "zero_ratio": "",
                    "unique_values": "",
                    "score": "0.000000",
                    "seed_class": "invalid",
                    "reason": "source_issue",
                    "pixel_hex": row.get("pixel_hex", ""),
                    "segment_context_hex": row.get("segment_context_hex", ""),
                    "pixel_context_hex": row.get("pixel_context_hex", ""),
                    "issues": issues or "missing_segment_offset",
                }
            )
            continue

        data = bytes.fromhex(row.get("pixel_hex", ""))
        chunk_size = int(row.get("chunk_size") or 0)
        extra_occurrences = int(row.get("extra_segment_occurrences") or 0)
        value_entropy = entropy(data)
        zero_ratio = data.count(0) / len(data) if data else 0.0
        unique_values = len(set(data))
        seed_class, reason = classify_seed(chunk_size, value_entropy, zero_ratio, extra_occurrences)
        score = score_seed(chunk_size, value_entropy, zero_ratio, extra_occurrences)
        rows.append(
            {
                "rank": "",
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "chunk_size": row.get("chunk_size", ""),
                "pixel_offset": row.get("pixel_offset", ""),
                "pixel_offset_hex": row.get("pixel_offset_hex", ""),
                "pixel_x": row.get("pixel_x", ""),
                "pixel_y": row.get("pixel_y", ""),
                "segment_offset": row.get("segment_offset", ""),
                "segment_offset_hex": row.get("segment_offset_hex", ""),
                "extra_segment_occurrences": row.get("extra_segment_occurrences", ""),
                "entropy": f"{value_entropy:.4f}",
                "zero_ratio": f"{zero_ratio:.4f}",
                "unique_values": str(unique_values),
                "score": f"{score:.6f}",
                "seed_class": seed_class,
                "reason": reason,
                "pixel_hex": row.get("pixel_hex", ""),
                "segment_context_hex": row.get("segment_context_hex", ""),
                "pixel_context_hex": row.get("pixel_context_hex", ""),
                "issues": "",
            }
        )

    rows.sort(
        key=lambda row: (
            {"strong": 0, "medium": 1, "weak": 2, "invalid": 3}.get(row["seed_class"], 9),
            -float(row["score"] or 0),
            row["pcx_name"],
            int(row["pixel_offset"] or 0),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def summary_row(source_rows: list[dict[str, str]], seed_rows: list[dict[str, str]]) -> dict[str, str]:
    valid_rows = [row for row in seed_rows if not row.get("issues")]
    class_counts = Counter(row["seed_class"] for row in valid_rows)
    return {
        "scope": "total",
        "match_rows": str(len(source_rows)),
        "seed_rows": str(len(valid_rows)),
        "strong_seed_rows": str(class_counts.get("strong", 0)),
        "medium_seed_rows": str(class_counts.get("medium", 0)),
        "weak_seed_rows": str(class_counts.get("weak", 0)),
        "unique_pcx": str(len({row["pcx_name"] for row in valid_rows if row.get("pcx_name")})),
        "issue_rows": str(sum(1 for row in seed_rows if row.get("issues"))),
    }


def render_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('seed_class', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('chunk_size', ''))}</td>"
        f"<td>{html.escape(row.get('score', ''))}</td>"
        f"<td>{html.escape(row.get('entropy', ''))}</td>"
        f"<td>{html.escape(row.get('zero_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_offset_hex', ''))} ({html.escape(row.get('pixel_x', ''))},{html.escape(row.get('pixel_y', ''))})</td>"
        f"<td>{html.escape(row.get('segment_offset_hex', ''))}</td>"
        f"<td>{html.escape(row.get('reason', ''))}</td>"
        f"<td><code>{html.escape(row.get('pixel_hex', ''))}</code></td>"
        "</tr>"
    )


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "seeds": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(path.name)}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("seeds.csv", output_dir / "seeds.csv"),
        )
    )
    table_rows = "\n".join(render_row(row) for row in rows)
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
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
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
    <div class="stat"><div class="label">Seeds</div><div class="value">{html.escape(summary['seed_rows'])}</div></div>
    <div class="stat"><div class="label">Strong</div><div class="value">{html.escape(summary['strong_seed_rows'])}</div></div>
    <div class="stat"><div class="label">Medium</div><div class="value">{html.escape(summary['medium_seed_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>Rank</th><th>Class</th><th>PCX</th><th>Size</th><th>Score</th><th>Entropy</th><th>Zero</th><th>Pixel</th><th>Segment</th><th>Reason</th><th>Hex</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_DECODER_SEED_REPORT = {data_json};
</script>
</body>
</html>
"""


def write_report(output_dir: Path, matches: Path, title: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = read_rows(matches)
    seed_rows = build_seed_rows(source_rows)
    summary = summary_row(source_rows, seed_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "seeds.csv", SEED_FIELDNAMES, seed_rows)
    (output_dir / "index.html").write_text(build_html(summary, seed_rows, output_dir, title))
    return summary, seed_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank direct .tex chunk matches as decoder seeds.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matches", type=Path, default=DEFAULT_MATCHES)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Seed Report")
    args = parser.parse_args()

    summary, _rows = write_report(args.output, args.matches, args.title)
    print(f"Seed rows: {summary['seed_rows']}")
    print(f"Strong seeds: {summary['strong_seed_rows']}")
    print(f"Medium seeds: {summary['medium_seed_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
