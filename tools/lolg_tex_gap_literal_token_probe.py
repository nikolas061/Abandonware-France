#!/usr/bin/env python3
"""Probe .tex literal-copy length tokens from the zero/literal gap skeleton."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_control_grammar_probe import fixture_key
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_gap_zero_literal_segmentation_probe import load_bytes, read_rows, segment_fixture


DEFAULT_OUTPUT = Path("output/tex_gap_literal_token_probe")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_SEGMENTATION_BEST = Path("output/tex_gap_zero_literal_segmentation_probe/best_by_fixture.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "fixtures_with_literal_ops",
    "literal_ops",
    "literal_bytes",
    "token_plus3_match_ops",
    "token_plus3_match_bytes",
    "token_plus3_full_fixtures",
    "first_literal_token_plus3_matches",
    "with_prev_token_plus3_matches",
    "small_token_ops",
    "small_token_plus3_matches",
    "literal_ops_missing_pre1",
    "token_rule_rows",
    "issue_rows",
]

RULE_FIELDNAMES = [
    "rule",
    "tested_ops",
    "match_ops",
    "match_bytes",
    "match_ratio",
    "matched_fixture_count",
    "full_fixture_count",
]

LITERAL_FIELDNAMES = [
    "rank",
    "rule_type",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "strategy",
    "op_index",
    "expected_start",
    "expected_end",
    "length",
    "source_offset",
    "source_end",
    "token_offset",
    "token_hex",
    "token_value",
    "token_plus3_length",
    "token_low_plus3_length",
    "token_plus3_match",
    "token_low_plus3_match",
    "source_delta_from_prev_literal_end",
    "source_direction",
    "expected_hex",
    "source_hex",
    "issues",
]

TOKEN_FIELDNAMES = [
    "token_hex",
    "token_value",
    "literal_ops",
    "token_plus3_match_ops",
    "token_plus3_match_bytes",
    "lengths",
    "pcx_names",
    "sample_rank",
    "sample_frontier_id",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "strategy",
    "literal_ops",
    "literal_bytes",
    "token_plus3_match_ops",
    "token_plus3_match_bytes",
    "token_plus3_full",
    "issue_rows",
]


def read_best(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    return {fixture_key(row): row for row in read_rows(path)}


def signed_direction(delta: int | None) -> str:
    if delta is None:
        return ""
    if delta > 0:
        return "forward"
    if delta < 0:
        return "backward"
    return "reuse"


def literal_rows_for_fixture(
    fixture: dict[str, str],
    best: dict[str, str],
    *,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    max_hex: int,
) -> list[dict[str, str]]:
    issues: list[str] = []
    if fixture.get("issues"):
        issues.append("source_fixture_has_issues")
    segment = load_bytes(fixture.get("segment_gap_path", ""), issues, "segment")
    expected = load_bytes(fixture.get("expected_gap_path", ""), issues, "expected")
    if len(segment) != int_value(fixture, "segment_gap_bytes"):
        issues.append("segment_size_mismatch")
    if len(expected) != int_value(fixture, "pixel_gap"):
        issues.append("expected_size_mismatch")

    strategy = best.get("best_strategy", "zero_first") or "zero_first"
    ops = segment_fixture(
        expected,
        segment,
        strategy=strategy,
        min_zero=min_zero,
        min_literal=min_literal,
        max_literal=max_literal,
    )
    rows: list[dict[str, str]] = []
    prev_literal_end: int | None = None
    for index, op in enumerate(ops):
        if op.kind != "literal" or op.source_offset < 0:
            continue
        source_offset = op.source_offset
        source_end = source_offset + op.length
        token_offset = source_offset - 1
        if token_offset >= 0:
            token_value = segment[token_offset]
            token_hex = f"{token_value:02x}"
        else:
            token_value = -1
            token_hex = ""
        delta_end = source_offset - prev_literal_end if prev_literal_end is not None else None
        token_plus3 = token_value + 3 if token_value >= 0 else -1
        token_low_plus3 = (token_value & 0x0F) + 3 if token_value >= 0 else -1
        rows.append(
            {
                "rank": fixture.get("rank", ""),
                "rule_type": fixture.get("rule_type", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "strategy": strategy,
                "op_index": str(index),
                "expected_start": str(op.expected_start),
                "expected_end": str(op.expected_end),
                "length": str(op.length),
                "source_offset": str(source_offset),
                "source_end": str(source_end),
                "token_offset": "" if token_offset < 0 else str(token_offset),
                "token_hex": token_hex,
                "token_value": "" if token_value < 0 else str(token_value),
                "token_plus3_length": "" if token_plus3 < 0 else str(token_plus3),
                "token_low_plus3_length": "" if token_low_plus3 < 0 else str(token_low_plus3),
                "token_plus3_match": "1" if token_plus3 == op.length else "0",
                "token_low_plus3_match": "1" if token_low_plus3 == op.length else "0",
                "source_delta_from_prev_literal_end": "" if delta_end is None else str(delta_end),
                "source_direction": signed_direction(delta_end),
                "expected_hex": expected[op.expected_start : op.expected_end][:max_hex].hex(),
                "source_hex": segment[source_offset:source_end][:max_hex].hex(),
                "issues": ";".join(issues),
            }
        )
        prev_literal_end = source_end
    return rows


def build_literal_rows(
    fixtures_path: Path,
    best_path: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    max_hex: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixtures = sorted(read_rows(fixtures_path), key=lambda row: int_value(row, "rank"))
    if limit > 0:
        fixtures = fixtures[:limit]
    best_rows = read_best(best_path)
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        rows.extend(
            literal_rows_for_fixture(
                fixture,
                best_rows.get(fixture_key(fixture), {}),
                min_zero=min_zero,
                min_literal=min_literal,
                max_literal=max_literal,
                max_hex=max_hex,
            )
        )
    return fixtures, rows


def rule_length(rule: str, token_value: int) -> int:
    if token_value < 0:
        return -1
    if rule == "token":
        return token_value
    if rule.startswith("token_plus_"):
        return token_value + int(rule.rsplit("_", 1)[1])
    if rule == "low_nibble_plus_3":
        return (token_value & 0x0F) + 3
    if rule == "low_nibble_plus_4":
        return (token_value & 0x0F) + 4
    if rule == "high_nibble_plus_3":
        return (token_value >> 4) + 3
    return -1


def rule_rows(literal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rules = [
        "token",
        "token_plus_1",
        "token_plus_2",
        "token_plus_3",
        "token_plus_4",
        "low_nibble_plus_3",
        "low_nibble_plus_4",
        "high_nibble_plus_3",
    ]
    rows: list[dict[str, str]] = []
    fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in literal_rows
    }
    for rule in rules:
        matched = []
        for row in literal_rows:
            token_value = int_value(row, "token_value") if row.get("token_value") else -1
            if rule_length(rule, token_value) == int_value(row, "length"):
                matched.append(row)
        matched_fixtures = {
            (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
            for row in matched
        }
        full_fixture_count = 0
        for fixture_key_value in fixtures:
            fixture_rows = [
                row
                for row in literal_rows
                if (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) == fixture_key_value
            ]
            if fixture_rows and all(row in matched for row in fixture_rows):
                full_fixture_count += 1
        tested_ops = len(literal_rows)
        match_ratio = len(matched) / tested_ops if tested_ops else 0.0
        rows.append(
            {
                "rule": rule,
                "tested_ops": str(tested_ops),
                "match_ops": str(len(matched)),
                "match_bytes": str(sum(int_value(row, "length") for row in matched)),
                "match_ratio": f"{match_ratio:.6f}",
                "matched_fixture_count": str(len(matched_fixtures)),
                "full_fixture_count": str(full_fixture_count),
            }
        )
    return rows


def token_rows(literal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_token: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in literal_rows:
        by_token[row.get("token_hex", "")].append(row)
    rows: list[dict[str, str]] = []
    for token_hex, matches in by_token.items():
        if not token_hex:
            continue
        plus3 = [row for row in matches if row.get("token_plus3_match") == "1"]
        length_counter = Counter(row.get("length", "") for row in matches)
        sample = matches[0]
        rows.append(
            {
                "token_hex": token_hex,
                "token_value": sample.get("token_value", ""),
                "literal_ops": str(len(matches)),
                "token_plus3_match_ops": str(len(plus3)),
                "token_plus3_match_bytes": str(sum(int_value(row, "length") for row in plus3)),
                "lengths": ";".join(f"{length}:{count}" for length, count in length_counter.most_common()),
                "pcx_names": ";".join(sorted({row.get("pcx_name", "") for row in matches})),
                "sample_rank": sample.get("rank", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    return sorted(rows, key=lambda row: (-int_value(row, "literal_ops"), int_value(row, "token_value")))


def fixture_rows(fixtures: list[dict[str, str]], literal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_fixture: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in literal_rows:
        by_fixture[(row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))].append(row)
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        key = (fixture.get("archive", ""), fixture.get("pcx_name", ""), fixture.get("frontier_id", ""))
        matches = by_fixture.get(key, [])
        plus3 = [row for row in matches if row.get("token_plus3_match") == "1"]
        issue_rows = sum(1 for row in matches if row.get("issues"))
        rows.append(
            {
                "rank": fixture.get("rank", ""),
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": fixture.get("pcx_name", ""),
                "frontier_id": fixture.get("frontier_id", ""),
                "frontier_type": fixture.get("frontier_type", ""),
                "strategy": matches[0].get("strategy", "") if matches else "",
                "literal_ops": str(len(matches)),
                "literal_bytes": str(sum(int_value(row, "length") for row in matches)),
                "token_plus3_match_ops": str(len(plus3)),
                "token_plus3_match_bytes": str(sum(int_value(row, "length") for row in plus3)),
                "token_plus3_full": "1" if matches and len(plus3) == len(matches) else "0",
                "issue_rows": str(issue_rows),
            }
        )
    return rows


def summary_row(
    fixtures: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    rules: list[dict[str, str]],
    by_fixture: list[dict[str, str]],
) -> dict[str, str]:
    plus3 = [row for row in literal_rows if row.get("token_plus3_match") == "1"]
    with_prev = [row for row in literal_rows if row.get("source_delta_from_prev_literal_end")]
    first_literals = [row for row in literal_rows if not row.get("source_delta_from_prev_literal_end")]
    small_tokens = [
        row
        for row in literal_rows
        if row.get("token_value") and int_value(row, "token_value") <= 13
    ]
    return {
        "scope": "total",
        "fixture_rows": str(len(fixtures)),
        "fixtures_with_literal_ops": str(sum(1 for row in by_fixture if int_value(row, "literal_ops") > 0)),
        "literal_ops": str(len(literal_rows)),
        "literal_bytes": str(sum(int_value(row, "length") for row in literal_rows)),
        "token_plus3_match_ops": str(len(plus3)),
        "token_plus3_match_bytes": str(sum(int_value(row, "length") for row in plus3)),
        "token_plus3_full_fixtures": str(sum(1 for row in by_fixture if row.get("token_plus3_full") == "1")),
        "first_literal_token_plus3_matches": str(
            sum(1 for row in first_literals if row.get("token_plus3_match") == "1")
        ),
        "with_prev_token_plus3_matches": str(sum(1 for row in with_prev if row.get("token_plus3_match") == "1")),
        "small_token_ops": str(len(small_tokens)),
        "small_token_plus3_matches": str(sum(1 for row in small_tokens if row.get("token_plus3_match") == "1")),
        "literal_ops_missing_pre1": str(sum(1 for row in literal_rows if not row.get("token_hex"))),
        "token_rule_rows": str(len(rules)),
        "issue_rows": str(sum(1 for row in literal_rows if row.get("issues"))),
    }


def render_row(row: dict[str, str], fields: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"


def build_html(
    summary: dict[str, str],
    rules: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    by_token: list[dict[str, str]],
    by_fixture: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "rules": rules,
        "literals": literal_rows,
        "tokens": by_token,
        "fixtures": by_fixture,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("rules.csv", output_dir / "rules.csv"),
            ("literals.csv", output_dir / "literals.csv"),
            ("by_token.csv", output_dir / "by_token.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
        )
    )
    rule_markup = "\n".join(render_row(row, RULE_FIELDNAMES) for row in rules)
    literal_fields = [
        "rank",
        "pcx_name",
        "frontier_id",
        "op_index",
        "length",
        "source_offset",
        "token_hex",
        "token_plus3_length",
        "token_plus3_match",
        "source_delta_from_prev_literal_end",
        "source_direction",
    ]
    literal_markup = "\n".join(render_row(row, literal_fields) for row in literal_rows[:260])
    token_markup = "\n".join(render_row(row, TOKEN_FIELDNAMES) for row in by_token[:120])
    fixture_markup = "\n".join(render_row(row, FIXTURE_FIELDNAMES) for row in by_fixture[:80])
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #111417;
  --panel: #171e22;
  --line: #31404a;
  --text: #eef5f4;
  --muted: #9dafb5;
  --accent: #74d3ae;
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12181b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Tests whether the byte before each literal source encodes copy length as token + 3.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Literal ops</div><div class="value">{html.escape(summary['literal_ops'])}</div></div>
    <div class="stat"><div class="label">token+3 ops</div><div class="value ok">{html.escape(summary['token_plus3_match_ops'])}</div></div>
    <div class="stat"><div class="label">token+3 bytes</div><div class="value ok">{html.escape(summary['token_plus3_match_bytes'])}</div></div>
    <div class="stat"><div class="label">Full literal fixtures</div><div class="value">{html.escape(summary['token_plus3_full_fixtures'])}</div></div>
    <div class="stat"><div class="label">Issue rows</div><div class="value">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Length rules</h2>
    <table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in RULE_FIELDNAMES)}</tr></thead><tbody>{rule_markup}</tbody></table>
  </section>
  <section class="panel">
    <h2>Literal samples</h2>
    <table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in literal_fields)}</tr></thead><tbody>{literal_markup}</tbody></table>
  </section>
  <section class="panel">
    <h2>Tokens</h2>
    <table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in TOKEN_FIELDNAMES)}</tr></thead><tbody>{token_markup}</tbody></table>
  </section>
  <section class="panel">
    <h2>Fixtures</h2>
    <table><thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in FIXTURE_FIELDNAMES)}</tr></thead><tbody>{fixture_markup}</tbody></table>
  </section>
</main>
<script>
const TEX_GAP_LITERAL_TOKEN_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures: Path,
    best: Path,
    *,
    limit: int,
    min_zero: int,
    min_literal: int,
    max_literal: int,
    max_hex: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures_rows, literal_rows = build_literal_rows(
        fixtures,
        best,
        limit=limit,
        min_zero=min_zero,
        min_literal=min_literal,
        max_literal=max_literal,
        max_hex=max_hex,
    )
    rules = rule_rows(literal_rows)
    tokens = token_rows(literal_rows)
    fixtures_out = fixture_rows(fixtures_rows, literal_rows)
    summary = summary_row(fixtures_rows, literal_rows, rules, fixtures_out)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "rules.csv", RULE_FIELDNAMES, rules)
    write_csv(output_dir / "literals.csv", LITERAL_FIELDNAMES, literal_rows)
    write_csv(output_dir / "by_token.csv", TOKEN_FIELDNAMES, tokens)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures_out)
    (output_dir / "index.html").write_text(
        build_html(summary, rules, literal_rows, tokens, fixtures_out, output_dir, title)
    )
    return summary, rules, literal_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex literal length tokens from segmentation ops.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--best", type=Path, default=DEFAULT_SEGMENTATION_BEST)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-zero", type=int, default=2)
    parser.add_argument("--min-literal", type=int, default=4)
    parser.add_argument("--max-literal", type=int, default=256)
    parser.add_argument("--max-hex", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Literal Token Probe")
    args = parser.parse_args()

    summary, _rules, _literal_rows = write_report(
        args.output,
        args.fixtures,
        args.best,
        limit=args.limit,
        min_zero=args.min_zero,
        min_literal=args.min_literal,
        max_literal=args.max_literal,
        max_hex=args.max_hex,
        title=args.title,
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Literal ops: {summary['literal_ops']}")
    print(f"Token+3 matches: {summary['token_plus3_match_ops']}")
    print(f"Token+3 bytes: {summary['token_plus3_match_bytes']}")
    print(f"Token+3 full fixtures: {summary['token_plus3_full_fixtures']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
