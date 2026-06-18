#!/usr/bin/env python3
"""Review simple selectors for the largest post-frontier80 clean-gap runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_largest_run_selector_review")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe_frontier80_transfer_guard_promoted_replay/runs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

TRANSFORM_CONSTANTS = [*range(1, 17), 0x20, 0x40, 0x55, 0x80, 0xAA, 0xFF]

SUMMARY_FIELDNAMES = [
    "scope",
    "target_runs",
    "target_run_bytes",
    "largest_run_bytes",
    "exact_copy_total_nonself_matches",
    "exact_copy_known_matches",
    "best_known_relative_exact",
    "best_known_relative_ratio",
    "best_any_relative_exact",
    "best_any_relative_ratio",
    "best_pairwise_same",
    "best_pairwise_same_ratio",
    "candidate_rows",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

TARGET_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "distinct_bytes",
    "top_byte_hex",
    "top_byte_count",
    "head_hex",
    "tail_hex",
]

EXACT_FIELDNAMES = [
    "target_id",
    "match_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "known_source",
    "self_match",
    "head_hex",
    "tail_hex",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "target_start",
    "source_start",
    "relative_offset",
    "transform",
    "constant_hex",
    "exact_bytes",
    "exact_ratio",
    "source_known",
    "source_overlaps_target",
    "source_head_hex",
    "source_tail_hex",
]

PAIRWISE_FIELDNAMES = [
    "left_target_id",
    "right_target_id",
    "same_bytes",
    "same_ratio",
    "top_delta_hex",
    "top_delta_count",
    "top_xor_hex",
    "top_xor_count",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def target_id(row: dict[str, str]) -> str:
    return (
        f"r{int_value(row, 'rank'):03d}_f{row.get('frontier_id', '')}_"
        f"s{row.get('span_index', '')}_run{row.get('run_index', '')}"
    )


def load_bytes(path_text: str, issues: list[str], label: str, key: tuple[str, str, str]) -> bytes:
    if not path_text:
        issues.append(f"{key}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{key}:read_{label}_failed:{exc}")
        return b""


def load_fixture_data(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[tuple[str, str, str], dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    fixtures: dict[tuple[str, str, str], dict[str, object]] = {}
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key, {})
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", key)
        known_mask = load_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key) if clean else b""
        fixtures[key] = {
            "manifest": manifest,
            "clean": clean,
            "expected": expected,
            "known_mask": known_mask,
        }
    return fixtures


def select_targets(run_rows: list[dict[str, str]], issues: list[str]) -> list[dict[str, str]]:
    nonzero = [row for row in run_rows if row.get("run_class") == "nonzero"]
    if not nonzero:
        issues.append("missing_nonzero_run_rows")
        return []
    max_len = max(int_value(row, "length") for row in nonzero)
    return [
        {**row, "target_id": target_id(row)}
        for row in nonzero
        if int_value(row, "length") == max_len
    ]


def known_window(mask: bytes, start: int, length: int) -> bool:
    if start < 0 or length <= 0 or start + length > len(mask):
        return False
    return all(value != 0 for value in mask[start : start + length])


def transform_byte(value: int, transform: str, constant: int) -> int:
    if transform == "identity":
        return value
    if transform == "add":
        return (value + constant) & 0xFF
    if transform == "sub":
        return (value - constant) & 0xFF
    if transform == "xor":
        return value ^ constant
    raise ValueError(f"unknown transform: {transform}")


def score_transform(source: bytes, target: bytes, transform: str, constant: int) -> int:
    return sum(
        1
        for source_value, target_value in zip(source, target)
        if transform_byte(source_value, transform, constant) == target_value
    )


def hex_byte(value: int | None) -> str:
    return f"0x{value:02x}" if value is not None else ""


def build_target_rows(
    targets: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    issues: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        key = fixture_key(target)
        fixture = fixtures.get(key)
        expected = fixture.get("expected", b"") if fixture else b""
        if not isinstance(expected, bytes):
            expected = b""
        start = int_value(target, "start")
        end = int_value(target, "end")
        data = expected[start:end]
        if len(data) != int_value(target, "length"):
            issues.append(f"{target.get('target_id', '')}:target_window_out_of_bounds")
        top_byte, top_count = Counter(data).most_common(1)[0] if data else (None, 0)
        rows.append(
            {
                "target_id": target.get("target_id", ""),
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "length": target.get("length", ""),
                "distinct_bytes": str(len(set(data))),
                "top_byte_hex": hex_byte(top_byte),
                "top_byte_count": str(top_count),
                "head_hex": data[:16].hex(),
                "tail_hex": data[-16:].hex(),
            }
        )
    return rows


def find_exact_matches(
    targets: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in targets:
        target_key = fixture_key(target)
        target_fixture = fixtures.get(target_key, {})
        target_expected = target_fixture.get("expected", b"")
        if not isinstance(target_expected, bytes):
            target_expected = b""
        start = int_value(target, "start")
        end = int_value(target, "end")
        target_bytes = target_expected[start:end]
        if not target_bytes:
            continue

        match_index = 0
        for key, fixture in fixtures.items():
            expected = fixture.get("expected", b"")
            known_mask = fixture.get("known_mask", b"")
            manifest = fixture.get("manifest", {})
            if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
                continue
            if not isinstance(manifest, dict):
                manifest = {}
            pos = expected.find(target_bytes)
            while pos >= 0:
                match_end = pos + len(target_bytes)
                self_match = key == target_key and pos == start and match_end == end
                rows.append(
                    {
                        "target_id": target.get("target_id", ""),
                        "match_id": str(match_index),
                        "rank": manifest.get("rank", key[0]),
                        "archive": manifest.get("archive", ""),
                        "archive_tag": manifest.get("archive_tag", ""),
                        "pcx_name": manifest.get("pcx_name", key[1]),
                        "frontier_id": manifest.get("frontier_id", key[2]),
                        "start": str(pos),
                        "end": str(match_end),
                        "known_source": "1" if known_window(known_mask, pos, len(target_bytes)) else "0",
                        "self_match": "1" if self_match else "0",
                        "head_hex": expected[pos : pos + 16].hex(),
                        "tail_hex": expected[match_end - 16 : match_end].hex(),
                    }
                )
                match_index += 1
                pos = expected.find(target_bytes, pos + 1)
    return rows


def build_relative_candidates(
    targets: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    *,
    max_relative: int,
    output_limit: int,
) -> tuple[list[dict[str, str]], int, int]:
    all_rows: list[dict[str, str]] = []
    best_known = 0
    best_any = 0
    transform_specs = [("identity", 0)] + [
        (transform, constant)
        for transform in ("add", "sub", "xor")
        for constant in TRANSFORM_CONSTANTS
    ]

    for target in targets:
        key = fixture_key(target)
        fixture = fixtures.get(key, {})
        expected = fixture.get("expected", b"")
        known_mask = fixture.get("known_mask", b"")
        if not isinstance(expected, bytes) or not isinstance(known_mask, bytes):
            continue
        target_start = int_value(target, "start")
        target_end = int_value(target, "end")
        target_bytes = expected[target_start:target_end]
        length = len(target_bytes)
        if not target_bytes:
            continue

        for rel in range(-max_relative, max_relative + 1):
            source_start = target_start + rel
            source_end = source_start + length
            if source_start < 0 or source_end > len(expected):
                continue
            source = expected[source_start:source_end]
            source_known = known_window(known_mask, source_start, length)
            source_overlaps = max(source_start, target_start) < min(source_end, target_end)
            if source_overlaps:
                continue
            for transform, constant in transform_specs:
                exact = score_transform(source, target_bytes, transform, constant)
                best_any = max(best_any, exact)
                if source_known:
                    best_known = max(best_known, exact)
                all_rows.append(
                    {
                        "target_id": target.get("target_id", ""),
                        "rank": target.get("rank", ""),
                        "pcx_name": target.get("pcx_name", ""),
                        "frontier_id": target.get("frontier_id", ""),
                        "target_start": str(target_start),
                        "source_start": str(source_start),
                        "relative_offset": str(rel),
                        "transform": transform,
                        "constant_hex": "" if transform == "identity" else f"0x{constant:02x}",
                        "exact_bytes": str(exact),
                        "exact_ratio": f"{exact / length:.6f}",
                        "source_known": "1" if source_known else "0",
                        "source_overlaps_target": "1" if source_overlaps else "0",
                        "source_head_hex": source[:16].hex(),
                        "source_tail_hex": source[-16:].hex(),
                    }
                )

    all_rows.sort(
        key=lambda row: (
            -int_value(row, "exact_bytes"),
            int_value(row, "source_overlaps_target"),
            -int_value(row, "source_known"),
            abs(int_value(row, "relative_offset")),
            row.get("target_id", ""),
            row.get("transform", ""),
            row.get("constant_hex", ""),
        )
    )
    return all_rows[:output_limit], best_known, best_any


def build_pairwise_rows(
    targets: list[dict[str, str]],
    fixtures: dict[tuple[str, str, str], dict[str, object]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    target_data: list[tuple[dict[str, str], bytes]] = []
    for target in targets:
        fixture = fixtures.get(fixture_key(target), {})
        expected = fixture.get("expected", b"")
        if not isinstance(expected, bytes):
            expected = b""
        target_data.append((target, expected[int_value(target, "start") : int_value(target, "end")]))

    for left_index, (left, left_bytes) in enumerate(target_data):
        for right, right_bytes in target_data[left_index + 1 :]:
            same = sum(1 for a, b in zip(left_bytes, right_bytes) if a == b)
            delta_counts = Counter((a - b) & 0xFF for a, b in zip(left_bytes, right_bytes))
            xor_counts = Counter(a ^ b for a, b in zip(left_bytes, right_bytes))
            top_delta, top_delta_count = delta_counts.most_common(1)[0] if delta_counts else (None, 0)
            top_xor, top_xor_count = xor_counts.most_common(1)[0] if xor_counts else (None, 0)
            length = min(len(left_bytes), len(right_bytes))
            rows.append(
                {
                    "left_target_id": left.get("target_id", ""),
                    "right_target_id": right.get("target_id", ""),
                    "same_bytes": str(same),
                    "same_ratio": f"{same / length:.6f}" if length else "0.000000",
                    "top_delta_hex": hex_byte(top_delta),
                    "top_delta_count": str(top_delta_count),
                    "top_xor_hex": hex_byte(top_xor),
                    "top_xor_count": str(top_xor_count),
                }
            )
    rows.sort(key=lambda row: (-int_value(row, "same_bytes"), row.get("left_target_id", "")))
    return rows


def build_summary(
    target_rows: list[dict[str, str]],
    exact_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    *,
    best_known: int,
    best_any: int,
    issue_count: int,
) -> dict[str, str]:
    largest = max([int_value(row, "length") for row in target_rows] or [0])
    target_bytes = sum(int_value(row, "length") for row in target_rows)
    nonself_exact = [row for row in exact_rows if row.get("self_match") != "1"]
    known_exact = [row for row in nonself_exact if row.get("known_source") == "1"]
    best_pairwise = max([int_value(row, "same_bytes") for row in pairwise_rows] or [0])
    simple_support = bool(known_exact) or best_known >= largest
    verdict = (
        "frontier80_clean_largest_run_simple_selector_support"
        if simple_support
        else "frontier80_clean_largest_run_no_simple_selector"
    )
    next_probe = (
        "validate simple selector support for frontier80 clean-gap nonzero runs"
        if simple_support
        else "derive structural nonzero-run grammar beyond local copy/delta/xor selectors"
    )
    return {
        "scope": "total",
        "target_runs": str(len(target_rows)),
        "target_run_bytes": str(target_bytes),
        "largest_run_bytes": str(largest),
        "exact_copy_total_nonself_matches": str(len(nonself_exact)),
        "exact_copy_known_matches": str(len(known_exact)),
        "best_known_relative_exact": str(best_known),
        "best_known_relative_ratio": f"{best_known / largest:.6f}" if largest else "0.000000",
        "best_any_relative_exact": str(best_any),
        "best_any_relative_ratio": f"{best_any / largest:.6f}" if largest else "0.000000",
        "best_pairwise_same": str(best_pairwise),
        "best_pairwise_same_ratio": f"{best_pairwise / largest:.6f}" if largest else "0.000000",
        "candidate_rows": str(len(candidate_rows)),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    exact_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "exact": exact_rows,
        "candidates": candidate_rows,
        "pairwise": pairwise_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("exact_matches.csv", output_dir / "exact_matches.csv"),
            ("relative_candidates.csv", output_dir / "relative_candidates.csv"),
            ("pairwise.csv", output_dir / "pairwise.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
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
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Reviews exact copies and local identity/add/sub/xor selectors for the largest post-frontier80 nonzero runs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target runs</div><div class="value">{html.escape(summary['target_runs'])}</div></div>
    <div class="stat"><div class="label">Largest run</div><div class="value">{html.escape(summary['largest_run_bytes'])}</div></div>
    <div class="stat"><div class="label">Known exact copies</div><div class="value warn">{html.escape(summary['exact_copy_known_matches'])}</div></div>
    <div class="stat"><div class="label">Best known relative</div><div class="value">{html.escape(summary['best_known_relative_exact'])}</div></div>
    <div class="stat"><div class="label">Best pairwise same</div><div class="value">{html.escape(summary['best_pairwise_same'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Relative candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Exact matches</h2>{render_table(exact_rows, EXACT_FIELDNAMES)}</section>
  <section class="panel"><h2>Pairwise targets</h2>{render_table(pairwise_rows, PAIRWISE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="selector-review-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    runs_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    *,
    max_relative: int,
    candidate_limit: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    runs = read_csv(runs_path)
    targets = select_targets(runs, issues)
    fixtures = load_fixture_data(read_csv(manifest_path), read_csv(clean_fixtures_path), issues)

    target_rows = build_target_rows(targets, fixtures, issues)
    exact_rows = find_exact_matches(targets, fixtures)
    candidate_rows, best_known, best_any = build_relative_candidates(
        targets,
        fixtures,
        max_relative=max_relative,
        output_limit=candidate_limit,
    )
    pairwise_rows = build_pairwise_rows(targets, fixtures)
    summary = build_summary(
        target_rows,
        exact_rows,
        candidate_rows,
        pairwise_rows,
        best_known=best_known,
        best_any=best_any,
        issue_count=len(issues),
    )

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(output_dir / "exact_matches.csv", EXACT_FIELDNAMES, exact_rows)
    write_csv(output_dir / "relative_candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "pairwise.csv", PAIRWISE_FIELDNAMES, pairwise_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, target_rows, exact_rows, candidate_rows, pairwise_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Review simple selectors for largest post-frontier80 .tex runs.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--max-relative", type=int, default=640)
    parser.add_argument("--candidate-limit", type=int, default=240)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Largest Run Selector Review",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.runs,
        args.manifest,
        args.clean_fixtures,
        max_relative=args.max_relative,
        candidate_limit=args.candidate_limit,
        title=args.title,
    )
    print(f"Target runs: {summary['target_runs']}")
    print(f"Largest run bytes: {summary['largest_run_bytes']}")
    print(f"Known exact copies: {summary['exact_copy_known_matches']}")
    print(f"Best known relative exact: {summary['best_known_relative_exact']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
