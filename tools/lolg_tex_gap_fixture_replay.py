#!/usr/bin/env python3
"""Replay prioritized .tex gap fixtures with small decoder-rule hypotheses."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_rle_probe import (
    decode_count_value,
    decode_hibit_repeat,
    decode_packbits,
    decode_packbits_inverse,
    decode_pcx_rle,
)


DEFAULT_OUTPUT = Path("output/tex_gap_fixture_replay")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "candidate_rows",
    "tested_variants",
    "exact_match_rows",
    "exact_match_fixtures",
    "best_prefix_bytes",
    "best_prefix_variant",
    "best_prefix_rank",
    "best_prefix_pcx",
    "best_prefix_frontier_id",
    "best_exact_bytes",
    "best_exact_variant",
    "best_exact_rank",
    "issue_rows",
]

REPLAY_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "variant",
    "parameter",
    "pixel_gap",
    "segment_gap_bytes",
    "input_bytes",
    "consumed_bytes",
    "produced_bytes",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "first_mismatch_at",
    "output_head_hex",
    "expected_head_hex",
    "notes",
    "issues",
]

BEST_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "best_variant",
    "best_parameter",
    "best_prefix_bytes",
    "best_prefix_ratio",
    "best_exact_bytes",
    "best_exact_ratio",
    "full_match",
    "first_mismatch_at",
    "notes",
    "issues",
]


@dataclass(frozen=True)
class Candidate:
    variant: str
    parameter: str
    output: bytes
    consumed: int
    notes: str = ""


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    path = Path(path_text)
    try:
        return path.read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    count = 0
    while count < limit and left[count] == right[count]:
        count += 1
    return count


def exact_byte_count(left: bytes, right: bytes) -> int:
    return sum(1 for index in range(min(len(left), len(right))) if left[index] == right[index])


def first_mismatch(prefix: int, output: bytes, expected: bytes) -> str:
    if prefix >= len(expected):
        return ""
    if prefix >= len(output):
        return f"output_short_at:{prefix}"
    return str(prefix)


def clamp(data: bytes, limit: int) -> bytes:
    return data[:limit]


def repeat_fragment(fragment: bytes, limit: int) -> bytes:
    if not fragment or limit <= 0:
        return b""
    repeats = (limit + len(fragment) - 1) // len(fragment)
    return (fragment * repeats)[:limit]


def zero_count_from_prefix(segment: bytes, byteorder: str) -> int:
    if len(segment) < 2:
        return 0
    return int.from_bytes(segment[:2], byteorder=byteorder, signed=False)


def decoder_candidate(
    name: str,
    data: bytes,
    limit: int,
) -> tuple[bytes, int, str]:
    if name == "pcx_rle":
        output, consumed, notes = decode_pcx_rle(data, limit)
    elif name == "packbits":
        output, consumed, notes = decode_packbits(data, limit)
    elif name == "packbits_inverse":
        output, consumed, notes = decode_packbits_inverse(data, limit)
    elif name == "hibit_repeat":
        output, consumed, notes = decode_hibit_repeat(data, limit)
    elif name == "count_value":
        output, consumed, notes = decode_count_value(data, limit, 0)
    elif name == "count1_value":
        output, consumed, notes = decode_count_value(data, limit, 1)
    else:
        raise ValueError(f"unknown decoder candidate: {name}")
    return clamp(output, limit), consumed, ";".join(notes)


def build_candidates(
    segment: bytes,
    expected: bytes,
    fragment: bytes,
    *,
    best_skip: int,
) -> list[Candidate]:
    limit = len(expected)
    after_skip = segment[best_skip:] if 0 <= best_skip <= len(segment) else b""
    candidates = [
        Candidate("segment_identity", "offset=0", clamp(segment, limit), min(len(segment), limit)),
        Candidate(
            "raw_after_best_skip",
            f"skip={best_skip}",
            clamp(after_skip, limit),
            min(max(0, len(segment) - best_skip), limit),
        ),
        Candidate("fragment_only", f"bytes={len(fragment)}", clamp(fragment, limit), len(fragment)),
        Candidate(
            "fragment_repeat",
            f"bytes={len(fragment)}",
            repeat_fragment(fragment, limit),
            len(fragment),
            "fragment cycled to expected length",
        ),
        Candidate("zero_fill", f"bytes={limit}", b"\x00" * limit, 0),
        Candidate(
            "zero_prefix_then_fragment",
            f"zeros={best_skip}",
            clamp((b"\x00" * max(0, best_skip)) + fragment, limit),
            len(fragment),
        ),
    ]

    for byteorder in ("little", "big"):
        count = zero_count_from_prefix(segment, byteorder)
        output = clamp((b"\x00" * count) + segment[2:], limit)
        candidates.append(
            Candidate(
                f"u16_{byteorder}_zero_run_then_tail",
                f"count={count}",
                output,
                min(2, len(segment)),
                "first two segment bytes interpreted as zero-run length",
            )
        )

    if segment:
        low7_count = (segment[0] & 0x7F) + 1
        inverse_count = 256 - segment[0]
        candidates.extend(
            [
                Candidate(
                    "first_byte_low7_zero_run",
                    f"count={low7_count}",
                    clamp((b"\x00" * low7_count) + segment[1:], limit),
                    1,
                ),
                Candidate(
                    "first_byte_inverse_zero_run",
                    f"count={inverse_count}",
                    clamp((b"\x00" * inverse_count) + segment[1:], limit),
                    1,
                ),
            ]
        )

    for decoder_name in (
        "pcx_rle",
        "packbits",
        "packbits_inverse",
        "hibit_repeat",
        "count_value",
        "count1_value",
    ):
        output, consumed, notes = decoder_candidate(decoder_name, segment, limit)
        candidates.append(Candidate(decoder_name, "offset=0", output, consumed, notes))
        output, consumed, notes = decoder_candidate(decoder_name, after_skip, limit)
        candidates.append(
            Candidate(
                f"{decoder_name}_after_best_skip",
                f"skip={best_skip}",
                output,
                consumed + best_skip if after_skip else 0,
                notes,
            )
        )

    return candidates


def candidate_row(
    fixture: dict[str, str],
    candidate: Candidate,
    expected: bytes,
    segment: bytes,
    *,
    context_bytes: int,
    source_issues: list[str],
) -> dict[str, str]:
    prefix = common_prefix(candidate.output, expected)
    exact = exact_byte_count(candidate.output, expected)
    pixel_gap = len(expected)
    full_match = bool(pixel_gap and prefix == pixel_gap and len(candidate.output) >= pixel_gap)
    notes = [candidate.notes] if candidate.notes else []
    if len(candidate.output) < pixel_gap:
        notes.append("output_short")
    issues = list(source_issues)
    return {
        "rank": fixture.get("rank", ""),
        "rule_type": fixture.get("rule_type", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "frontier_type": fixture.get("frontier_type", ""),
        "variant": candidate.variant,
        "parameter": candidate.parameter,
        "pixel_gap": str(pixel_gap),
        "segment_gap_bytes": str(len(segment)),
        "input_bytes": str(len(segment)),
        "consumed_bytes": str(candidate.consumed),
        "produced_bytes": str(len(candidate.output)),
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / pixel_gap) if pixel_gap else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / pixel_gap) if pixel_gap else 0.0:.6f}",
        "full_match": "1" if full_match else "0",
        "first_mismatch_at": first_mismatch(prefix, candidate.output, expected),
        "output_head_hex": candidate.output[:context_bytes].hex(),
        "expected_head_hex": expected[:context_bytes].hex(),
        "notes": ";".join(notes),
        "issues": ";".join(issues),
    }


def sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    return (
        int_value(row, "prefix_bytes"),
        int_value(row, "exact_bytes"),
        int(row.get("full_match", "0") or 0),
        row.get("variant", ""),
    )


def best_by_fixture(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        grouped.setdefault(key, []).append(row)

    best_rows: list[dict[str, str]] = []
    for candidates in grouped.values():
        best = max(candidates, key=sort_key)
        best_rows.append(
            {
                "rank": best.get("rank", ""),
                "rule_type": best.get("rule_type", ""),
                "archive": best.get("archive", ""),
                "archive_tag": best.get("archive_tag", ""),
                "pcx_name": best.get("pcx_name", ""),
                "frontier_id": best.get("frontier_id", ""),
                "frontier_type": best.get("frontier_type", ""),
                "pixel_gap": best.get("pixel_gap", ""),
                "segment_gap_bytes": best.get("segment_gap_bytes", ""),
                "best_variant": best.get("variant", ""),
                "best_parameter": best.get("parameter", ""),
                "best_prefix_bytes": best.get("prefix_bytes", ""),
                "best_prefix_ratio": best.get("prefix_ratio", ""),
                "best_exact_bytes": best.get("exact_bytes", ""),
                "best_exact_ratio": best.get("exact_ratio", ""),
                "full_match": best.get("full_match", ""),
                "first_mismatch_at": best.get("first_mismatch_at", ""),
                "notes": best.get("notes", ""),
                "issues": best.get("issues", ""),
            }
        )

    return sorted(best_rows, key=lambda row: int_value(row, "rank"))


def summary_row(
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> dict[str, str]:
    best_prefix = max(replay_rows, key=sort_key) if replay_rows else {}
    best_exact = (
        max(
            replay_rows,
            key=lambda row: (
                int_value(row, "exact_bytes"),
                int_value(row, "prefix_bytes"),
                int(row.get("full_match", "0") or 0),
                row.get("variant", ""),
            ),
        )
        if replay_rows
        else {}
    )
    exact_match_rows = sum(1 for row in replay_rows if row.get("full_match") == "1")
    exact_match_fixtures = sum(1 for row in best_rows if row.get("full_match") == "1")
    issue_rows = sum(1 for row in replay_rows if row.get("issues"))
    return {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "candidate_rows": str(len(replay_rows)),
        "tested_variants": str(len({row.get("variant", "") for row in replay_rows if row.get("variant")})),
        "exact_match_rows": str(exact_match_rows),
        "exact_match_fixtures": str(exact_match_fixtures),
        "best_prefix_bytes": str(int_value(best_prefix, "prefix_bytes")),
        "best_prefix_variant": best_prefix.get("variant", ""),
        "best_prefix_rank": best_prefix.get("rank", ""),
        "best_prefix_pcx": best_prefix.get("pcx_name", ""),
        "best_prefix_frontier_id": best_prefix.get("frontier_id", ""),
        "best_exact_bytes": str(int_value(best_exact, "exact_bytes")),
        "best_exact_variant": best_exact.get("variant", ""),
        "best_exact_rank": best_exact.get("rank", ""),
        "issue_rows": str(issue_rows),
    }


def build_replay_rows(
    fixtures: Path,
    *,
    limit: int,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = read_rows(fixtures)
    selected = sorted(fixture_rows, key=lambda row: int_value(row, "rank"))
    if limit > 0:
        selected = selected[:limit]

    replay_rows: list[dict[str, str]] = []
    for fixture in selected:
        issues: list[str] = []
        if fixture.get("issues"):
            issues.append("source_fixture_has_issues")
        segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
        fragment = load_bytes(fixture.get("fragment_path", ""), issues, "fragment")
        if len(segment) != int_value(fixture, "segment_gap_bytes"):
            issues.append("segment_size_mismatch")
        if len(expected) != int_value(fixture, "pixel_gap"):
            issues.append("expected_size_mismatch")
        if len(fragment) != int_value(fixture, "fragment_bytes"):
            issues.append("fragment_size_mismatch")

        candidates = build_candidates(
            segment,
            expected,
            fragment,
            best_skip=int_value(fixture, "best_raw_skip"),
        )
        for candidate in candidates:
            replay_rows.append(
                candidate_row(
                    fixture,
                    candidate,
                    expected,
                    segment,
                    context_bytes=context_bytes,
                    source_issues=issues,
                )
            )

    best_rows = best_by_fixture(replay_rows)
    return selected, replay_rows, best_rows


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('rule_type', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_variant', ''))}</td>"
        f"<td>{html.escape(row.get('best_parameter', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td>{html.escape(row.get('first_mismatch_at', ''))}</td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_replay_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('rank', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('variant', ''))}</td>"
        f"<td>{html.escape(row.get('parameter', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('exact_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td><code>{html.escape(row.get('output_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('notes', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    replay_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "best": best_rows, "replay": replay_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("replay.csv", output_dir / "replay.csv"),
            ("best_by_fixture.csv", output_dir / "best_by_fixture.csv"),
        )
    )
    best_markup = "\n".join(render_best_row(row) for row in best_rows)
    top_replay = sorted(replay_rows, key=sort_key, reverse=True)[:96]
    replay_markup = "\n".join(render_replay_row(row) for row in top_replay)
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
.sub {{ color: var(--muted); margin-top: 4px; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1200px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Replay verifie des fixtures de gaps .tex avec hypotheses candidates.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
    <div class="stat"><div class="label">Candidates</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['tested_variants'])}</div></div>
    <div class="stat"><div class="label">Exact matches</div><div class="value">{html.escape(summary['exact_match_rows'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value ok">{html.escape(summary['best_prefix_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by fixture</h2>
    <table>
      <thead><tr><th>Rank</th><th>Rule</th><th>PCX</th><th>Frontier</th><th>Pixels</th><th>Segment bytes</th><th>Variant</th><th>Param</th><th>Prefix</th><th>Exact bytes</th><th>Full</th><th>Mismatch</th><th>Notes</th><th>Issues</th></tr></thead>
      <tbody>{best_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Top replay rows</h2>
    <table>
      <thead><tr><th>Rank</th><th>PCX</th><th>Frontier</th><th>Variant</th><th>Param</th><th>Prefix</th><th>Exact bytes</th><th>Full</th><th>Output head</th><th>Expected head</th><th>Notes</th></tr></thead>
      <tbody>{replay_markup}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_FIXTURE_REPLAY = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    *,
    limit: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_rows, replay_rows, best_rows = build_replay_rows(
        fixtures,
        limit=limit,
        context_bytes=context_bytes,
    )
    summary = summary_row(fixture_rows, replay_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "replay.csv", REPLAY_FIELDNAMES, replay_rows)
    write_csv(output_dir / "best_by_fixture.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, replay_rows, best_rows, output_dir, title))
    return summary, replay_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay .tex gap fixtures with decoder-rule hypotheses.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Fixture Replay")
    args = parser.parse_args()

    summary, _replay_rows, _best_rows = write_report(
        args.output,
        args.fixtures,
        limit=args.limit,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Candidate rows: {summary['candidate_rows']}")
    print(f"Tested variants: {summary['tested_variants']}")
    print(f"Exact match rows: {summary['exact_match_rows']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
