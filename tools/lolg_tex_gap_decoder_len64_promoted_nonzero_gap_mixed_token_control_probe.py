#!/usr/bin/env python3
"""Correlate mixed-token rows with control/source value-band signals."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_dense_control_probe import (
    load_fixture_pools,
    operation_pools,
    score_pools,
    signed_delta,
    target_op_key,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    op_key,
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_micro_token_probe import signed_bucket
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe")
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "operation_rows",
    "missing_operation_rows",
    "candidate_windows",
    "top_nibble_exact_total",
    "top_nibble_best_single",
    "top_nibble_ge50_rows",
    "top_nibble_ge75_rows",
    "low_nibble_exact_total",
    "low_nibble_best_single",
    "low_nibble_ge50_rows",
    "low_nibble_ge75_rows",
    "signed_delta_exact_total",
    "signed_delta_best_single",
    "signed_delta_ge50_rows",
    "signed_delta_ge75_rows",
    "byte_exact_total",
    "byte_best_single",
    "byte_ge50_rows",
    "byte_ge75_rows",
    "best_overall_signal",
    "best_overall_exact",
    "best_overall_ratio",
    "dominant_top_nibble",
    "dominant_top_nibble_rows",
    "dominant_top_nibble_bytes",
    "top_nibble_only_rows",
    "top_nibble_only_bytes",
    "profile_like_rows",
    "profile_like_bytes",
    "profile_like_long_rows",
    "profile_like_long_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "start",
    "end",
    "top_nibble",
    "top_nibble_ratio",
    "control_ref_mod64",
    "operation_present",
    "candidate_windows",
    "best_top_nibble_pool",
    "best_top_nibble_transform",
    "best_top_nibble_offset",
    "best_top_nibble_exact",
    "best_top_nibble_ratio",
    "best_low_nibble_pool",
    "best_low_nibble_transform",
    "best_low_nibble_offset",
    "best_low_nibble_exact",
    "best_low_nibble_ratio",
    "best_signed_delta_pool",
    "best_signed_delta_transform",
    "best_signed_delta_offset",
    "best_signed_delta_exact",
    "best_signed_delta_ratio",
    "best_byte_pool",
    "best_byte_transform",
    "best_byte_offset",
    "best_byte_exact",
    "best_byte_ratio",
    "best_signal_kind",
    "best_signal_pool",
    "best_signal_transform",
    "best_signal_exact",
    "best_signal_ratio",
    "verdict",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "signal_kind",
    "pool",
    "transform",
    "rows",
    "bytes",
    "exact_total",
    "best_single",
    "ge50_rows",
    "ge75_rows",
    "top_nibble_only_rows",
    "top_nibble_only_bytes",
    "profile_like_rows",
    "profile_like_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def top_nibble_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if not data:
        return []
    return [
        ("high_nibble", [f"{value >> 4:x}" for value in data]),
        ("low_nibble_as_high", [f"{value & 0x0f:x}" for value in data]),
        ("high_nibble_rev", [f"{value >> 4:x}" for value in reversed(data)]),
    ]


def low_nibble_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if not data:
        return []
    return [
        ("low_nibble", [f"{value & 0x0f:x}" for value in data]),
        ("high_nibble_as_low", [f"{value >> 4:x}" for value in data]),
        ("low_nibble_rev", [f"{value & 0x0f:x}" for value in reversed(data)]),
    ]


def byte_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if not data:
        return []
    return [
        ("byte", [f"{value:02x}" for value in data]),
        ("byte_rev", [f"{value:02x}" for value in reversed(data)]),
    ]


def signed_delta_label_sets(data: bytes) -> list[tuple[str, list[str]]]:
    if len(data) < 2:
        return []
    labels = [signed_bucket(signed_delta(data[index - 1], data[index])) for index in range(1, len(data))]
    return [
        ("signed_delta", labels),
        ("signed_delta_rev", list(reversed(labels))),
    ]


def expected_span(target: dict[str, str], expected_by_fixture: dict[tuple[str, str, str], bytes]) -> bytes:
    expected_all = expected_by_fixture.get(fixture_key(target), b"")
    return expected_all[int_value(target, "start") : int_value(target, "end")]


def classify(row: dict[str, str]) -> str:
    top_ratio = float(row.get("best_top_nibble_ratio", "0") or 0)
    low_ratio = float(row.get("best_low_nibble_ratio", "0") or 0)
    signed_ratio = float(row.get("best_signed_delta_ratio", "0") or 0)
    byte_ratio = float(row.get("best_byte_ratio", "0") or 0)
    profile_like = max(low_ratio, signed_ratio, byte_ratio)
    if byte_ratio >= 0.75:
        return "byte_profile_review"
    if profile_like >= 0.75 and int_value(row, "length") >= 32:
        return "long_profile_review"
    if profile_like >= 0.75:
        return "short_profile_review"
    if top_ratio >= 0.75:
        return "top_nibble_only_reject"
    return "weak_control"


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    fixture_pools = load_fixture_pools(fixture_rows)
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        issues.extend(issue for issue in fixture_issues if str(fixture_key(target)) in issue)
        expected = expected_span(target, expected_by_fixture)
        if not expected:
            issues.append("missing_expected_chunk")
            continue

        top_values = [f"{value >> 4:x}" for value in expected]
        low_values = [f"{value & 0x0f:x}" for value in expected]
        byte_values = [f"{value:02x}" for value in expected]
        signed_values = [
            signed_bucket(signed_delta(expected[index - 1], expected[index]))
            for index in range(1, len(expected))
        ]

        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = {**fixture_pools.get(fixture_key(target), {}), **operation_pools(operation)}
        pools = {name: data for name, data in pools.items() if data}

        top_best, top_windows = score_pools(top_values, pools, top_nibble_label_sets)
        low_best, low_windows = score_pools(low_values, pools, low_nibble_label_sets)
        signed_best, signed_windows = score_pools(signed_values, pools, signed_delta_label_sets)
        byte_best, byte_windows = score_pools(byte_values, pools, byte_label_sets)
        scored = [
            ("top_nibble", top_best),
            ("low_nibble", low_best),
            ("signed_delta", signed_best),
            ("byte", byte_best),
        ]
        best_kind, best_signal = max(
            scored,
            key=lambda item: (
                float(item[1].get("ratio", "0") or 0),
                int_value(item[1], "exact"),
                item[0] == "byte",
            ),
        )
        row = {
            "rank": target.get("rank", ""),
            "archive": target.get("archive", ""),
            "archive_tag": target.get("archive_tag", ""),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(expected)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "top_nibble": target.get("top_nibble", ""),
            "top_nibble_ratio": target.get("top_nibble_ratio", "0"),
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "operation_present": "1" if operation else "0",
            "candidate_windows": str(top_windows + low_windows + signed_windows + byte_windows),
            "best_top_nibble_pool": top_best["pool"],
            "best_top_nibble_transform": top_best["transform"],
            "best_top_nibble_offset": top_best["offset"],
            "best_top_nibble_exact": top_best["exact"],
            "best_top_nibble_ratio": top_best["ratio"],
            "best_low_nibble_pool": low_best["pool"],
            "best_low_nibble_transform": low_best["transform"],
            "best_low_nibble_offset": low_best["offset"],
            "best_low_nibble_exact": low_best["exact"],
            "best_low_nibble_ratio": low_best["ratio"],
            "best_signed_delta_pool": signed_best["pool"],
            "best_signed_delta_transform": signed_best["transform"],
            "best_signed_delta_offset": signed_best["offset"],
            "best_signed_delta_exact": signed_best["exact"],
            "best_signed_delta_ratio": signed_best["ratio"],
            "best_byte_pool": byte_best["pool"],
            "best_byte_transform": byte_best["transform"],
            "best_byte_offset": byte_best["offset"],
            "best_byte_exact": byte_best["exact"],
            "best_byte_ratio": byte_best["ratio"],
            "best_signal_kind": best_kind,
            "best_signal_pool": best_signal["pool"],
            "best_signal_transform": best_signal["transform"],
            "best_signal_exact": best_signal["exact"],
            "best_signal_ratio": best_signal["ratio"],
            "verdict": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["verdict"] = classify(row)
        output.append(row)
    output.sort(
        key=lambda row: (
            row.get("verdict", ""),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return output


def dominant_top(rows: list[dict[str, str]]) -> tuple[str, int, int]:
    counter: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = row.get("top_nibble", "")
        counter[key]["rows"] += 1
        counter[key]["bytes"] += int_value(row, "length")
    if not counter:
        return "", 0, 0
    key, values = max(counter.items(), key=lambda item: (item[1]["bytes"], item[1]["rows"], item[0]))
    return key, values["rows"], values["bytes"]


def ge_rows(rows: list[dict[str, str]], field: str, threshold: float) -> list[dict[str, str]]:
    return [row for row in rows if float(row.get(field, "0") or 0) >= threshold]


def best_signal_summary(rows: list[dict[str, str]]) -> tuple[str, int, str]:
    if not rows:
        return "", 0, "0.000000"
    best = max(
        rows,
        key=lambda row: (
            float(row.get("best_signal_ratio", "0") or 0),
            int_value(row, "best_signal_exact"),
        ),
    )
    return (
        f"{best.get('best_signal_kind', '')}:{best.get('best_signal_pool', '')}:{best.get('best_signal_transform', '')}",
        int_value(best, "best_signal_exact"),
        best.get("best_signal_ratio", "0.000000"),
    )


def build_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    top_key, top_rows, top_bytes = dominant_top(rows)
    top_only = [row for row in rows if row.get("verdict") == "top_nibble_only_reject"]
    profile_like = [
        row
        for row in rows
        if row.get("verdict") in {"byte_profile_review", "long_profile_review", "short_profile_review"}
    ]
    long_profile = [row for row in profile_like if int_value(row, "length") >= 32]
    best_signal, best_exact, best_ratio = best_signal_summary(rows)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "operation_rows": str(sum(1 for row in rows if row.get("operation_present") == "1")),
        "missing_operation_rows": str(sum(1 for row in rows if row.get("operation_present") != "1")),
        "candidate_windows": str(sum(int_value(row, "candidate_windows") for row in rows)),
        "top_nibble_exact_total": str(sum(int_value(row, "best_top_nibble_exact") for row in rows)),
        "top_nibble_best_single": str(max((int_value(row, "best_top_nibble_exact") for row in rows), default=0)),
        "top_nibble_ge50_rows": str(len(ge_rows(rows, "best_top_nibble_ratio", 0.50))),
        "top_nibble_ge75_rows": str(len(ge_rows(rows, "best_top_nibble_ratio", 0.75))),
        "low_nibble_exact_total": str(sum(int_value(row, "best_low_nibble_exact") for row in rows)),
        "low_nibble_best_single": str(max((int_value(row, "best_low_nibble_exact") for row in rows), default=0)),
        "low_nibble_ge50_rows": str(len(ge_rows(rows, "best_low_nibble_ratio", 0.50))),
        "low_nibble_ge75_rows": str(len(ge_rows(rows, "best_low_nibble_ratio", 0.75))),
        "signed_delta_exact_total": str(sum(int_value(row, "best_signed_delta_exact") for row in rows)),
        "signed_delta_best_single": str(max((int_value(row, "best_signed_delta_exact") for row in rows), default=0)),
        "signed_delta_ge50_rows": str(len(ge_rows(rows, "best_signed_delta_ratio", 0.50))),
        "signed_delta_ge75_rows": str(len(ge_rows(rows, "best_signed_delta_ratio", 0.75))),
        "byte_exact_total": str(sum(int_value(row, "best_byte_exact") for row in rows)),
        "byte_best_single": str(max((int_value(row, "best_byte_exact") for row in rows), default=0)),
        "byte_ge50_rows": str(len(ge_rows(rows, "best_byte_ratio", 0.50))),
        "byte_ge75_rows": str(len(ge_rows(rows, "best_byte_ratio", 0.75))),
        "best_overall_signal": best_signal,
        "best_overall_exact": str(best_exact),
        "best_overall_ratio": best_ratio,
        "dominant_top_nibble": top_key,
        "dominant_top_nibble_rows": str(top_rows),
        "dominant_top_nibble_bytes": str(top_bytes),
        "top_nibble_only_rows": str(len(top_only)),
        "top_nibble_only_bytes": str(sum(int_value(row, "length") for row in top_only)),
        "profile_like_rows": str(len(profile_like)),
        "profile_like_bytes": str(sum(int_value(row, "length") for row in profile_like)),
        "profile_like_long_rows": str(len(long_profile)),
        "profile_like_long_bytes": str(sum(int_value(row, "length") for row in long_profile)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def build_group_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("best_signal_kind", ""), row.get("best_signal_pool", ""), row.get("best_signal_transform", ""))
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["exact_total"] += int_value(row, "best_signal_exact")
        counters[key]["best_single"] = max(counters[key]["best_single"], int_value(row, "best_signal_exact"))
        if float(row.get("best_signal_ratio", "0") or 0) >= 0.50:
            counters[key]["ge50_rows"] += 1
        if float(row.get("best_signal_ratio", "0") or 0) >= 0.75:
            counters[key]["ge75_rows"] += 1
        if row.get("verdict") == "top_nibble_only_reject":
            counters[key]["top_nibble_only_rows"] += 1
            counters[key]["top_nibble_only_bytes"] += int_value(row, "length")
        if row.get("verdict") in {"byte_profile_review", "long_profile_review", "short_profile_review"}:
            counters[key]["profile_like_rows"] += 1
            counters[key]["profile_like_bytes"] += int_value(row, "length")
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "signal_kind": key[0],
                "pool": key[1],
                "transform": key[2],
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "exact_total": str(counter["exact_total"]),
                "best_single": str(counter["best_single"]),
                "ge50_rows": str(counter["ge50_rows"]),
                "ge75_rows": str(counter["ge75_rows"]),
                "top_nibble_only_rows": str(counter["top_nibble_only_rows"]),
                "top_nibble_only_bytes": str(counter["top_nibble_only_bytes"]),
                "profile_like_rows": str(counter["profile_like_rows"]),
                "profile_like_bytes": str(counter["profile_like_bytes"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("pool", "")))
    return output


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_best_signal.csv", output_dir / "by_best_signal.csv"),
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
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
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
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1780px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores mixed-token high nibbles, low nibbles, signed deltas, and exact bytes against control/source pools.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mixed-token bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Candidate windows</div><div class="value">{summary['candidate_windows']}</div></div>
    <div class="stat"><div class="label">Top-only bytes</div><div class="value warn">{summary['top_nibble_only_bytes']}</div></div>
    <div class="stat"><div class="label">Profile-like bytes</div><div class="value warn">{summary['profile_like_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Best signal groups</h2>{render_table(groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 140)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_CONTROL_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe mixed-token rows against control/source value signals.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Mixed Token Control Probe",
    )
    args = parser.parse_args()

    rows = build_target_rows(read_csv(args.targets), read_csv(args.operations), read_csv(args.fixtures))
    groups = build_group_rows(rows)
    summary = build_summary(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_best_signal.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.output, args.title))

    print(f"Mixed-token-control rows: {summary['target_rows']}")
    print(f"Candidate windows: {summary['candidate_windows']}")
    print(f"Top-only bytes: {summary['top_nibble_only_bytes']}")
    print(f"Profile-like bytes: {summary['profile_like_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
