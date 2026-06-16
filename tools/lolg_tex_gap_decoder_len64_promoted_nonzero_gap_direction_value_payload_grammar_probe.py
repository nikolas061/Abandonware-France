#!/usr/bin/env python3
"""Check direction/value rows for reusable payload grammar."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    read_bytes,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_micro_token_probe import (
    classify_micro,
    coarse_bucket,
    deltas,
    preview_text,
    shape_key,
    signed_bucket,
    token_shape,
    top_nibble_stats,
    transition_profile,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe"
)
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "fixture_keys",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "coarse_shape_groups",
    "repeated_coarse_shape_groups",
    "repeated_coarse_shape_rows",
    "repeated_coarse_shape_bytes",
    "signed_shape_groups",
    "repeated_signed_shape_groups",
    "repeated_signed_shape_rows",
    "repeated_signed_shape_bytes",
    "transition_profile_groups",
    "repeated_transition_profile_groups",
    "repeated_transition_profile_rows",
    "repeated_transition_profile_bytes",
    "top_token_groups",
    "repeated_top_token_groups",
    "repeated_top_token_rows",
    "repeated_top_token_bytes",
    "top_nibble_groups",
    "repeated_top_nibble_groups",
    "repeated_top_nibble_rows",
    "repeated_top_nibble_bytes",
    "top_token_nibble_groups",
    "repeated_top_token_nibble_groups",
    "repeated_top_token_nibble_rows",
    "repeated_top_token_nibble_bytes",
    "dominant_jump_rows",
    "dominant_jump_bytes",
    "dominant_top_nibble_rows",
    "dominant_top_nibble_bytes",
    "exact_profile_unique_bytes",
    "broad_signal_only_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "surface",
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
    "direction_value_key",
    "offset_delta",
    "top_token",
    "top_token_ratio",
    "top_nibble",
    "top_nibble_ratio",
    "zero_delta_ratio",
    "small_delta_ratio",
    "jump_delta_ratio",
    "coarse_shape_key",
    "coarse_shape_preview",
    "signed_shape_key",
    "signed_shape_preview",
    "transition_profile_key",
    "transition_profile_preview",
    "micro_class",
    "payload_signature",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "direction_value_keys",
    "surfaces",
    "micro_classes",
    "top_tokens",
    "top_nibbles",
    "profile_keys",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def fixture_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("pcx_name", ""), row.get("frontier_id", "")


def load_expected_by_frontier(
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str], bytes], dict[tuple[str, str], dict[str, str]], list[str]]:
    expected: dict[tuple[str, str], bytes] = {}
    metadata: dict[tuple[str, str], dict[str, str]] = {}
    issues: list[str] = []
    seen: Counter[tuple[str, str]] = Counter()
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        seen[key] += 1
        if key in expected:
            issues.append(f"duplicate_fixture_key:{key[0]}:{key[1]}")
            continue
        row_issues: list[str] = []
        expected[key] = read_bytes(fixture.get("expected_gap_path", ""), row_issues, "expected")
        metadata[key] = fixture
        issues.extend(row_issues)
    return expected, metadata, issues


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_frontier, fixture_metadata, fixture_issues = load_expected_by_frontier(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        if float_value(target, "best_value_ratio") < 0.75:
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        key = fixture_key(target)
        expected_all = expected_by_frontier.get(key, b"")
        if not expected_all:
            issues.append("missing_expected_fixture")
        start = int_value(target, "start")
        end = int_value(target, "end")
        payload = expected_all[start:end]
        if not payload:
            issues.append("missing_expected_chunk")
            continue

        delta_values = deltas(payload)
        coarse_values = [coarse_bucket(value) for value in delta_values]
        signed_values = [signed_bucket(value) for value in delta_values]
        coarse_shape = token_shape(coarse_values)
        signed_shape = token_shape(signed_values)
        profile = transition_profile(signed_values)
        top_token, top_token_count = Counter(coarse_values).most_common(1)[0] if coarse_values else ("", 0)
        top_nibble, top_nibble_ratio = top_nibble_stats(payload)
        zero_count = sum(1 for value in delta_values if value == 0)
        small_count = sum(1 for value in delta_values if abs(value) <= 4)
        jump_count = sum(1 for value in delta_values if abs(value) > 31)
        metadata = fixture_metadata.get(key, {})
        row = {
            "rank": metadata.get("rank", target.get("rank", "")),
            "surface": target.get("surface", ""),
            "archive": target.get("archive", metadata.get("archive", "")),
            "archive_tag": target.get("archive_tag", metadata.get("archive_tag", "")),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(payload)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "direction_value_key": target.get("direction_value_key", ""),
            "offset_delta": target.get("offset_delta", ""),
            "top_token": top_token,
            "top_token_ratio": ratio(top_token_count, len(coarse_values)),
            "top_nibble": top_nibble,
            "top_nibble_ratio": f"{top_nibble_ratio:.6f}",
            "zero_delta_ratio": ratio(zero_count, len(delta_values)),
            "small_delta_ratio": ratio(small_count, len(delta_values)),
            "jump_delta_ratio": ratio(jump_count, len(delta_values)),
            "coarse_shape_key": shape_key(coarse_shape),
            "coarse_shape_preview": preview_text(coarse_shape),
            "signed_shape_key": shape_key(signed_shape),
            "signed_shape_preview": preview_text(signed_shape),
            "transition_profile_key": shape_key(profile),
            "transition_profile_preview": preview_text(profile),
            "micro_class": "",
            "payload_signature": payload_signature(payload),
            "head_hex": payload[:16].hex(),
            "tail_hex": payload[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["micro_class"] = classify_micro(row)
        output.append(row)
    output.sort(
        key=lambda row: (
            row.get("top_token", ""),
            row.get("top_nibble", ""),
            row.get("surface", ""),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return output, fixture_issues


def group_rows(rows: list[dict[str, str]], kind: str, key_func) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[key_func(row)].append(row)
    output: list[dict[str, str]] = []
    for key, group in grouped.items():
        sample = group[0]
        payload_counts = Counter(row.get("payload_signature", "") for row in group)
        repeated_payload_rows = sum(count for count in payload_counts.values() if count > 1)
        repeated_payload_bytes = sum(
            int_value(row, "length")
            for row in group
            if payload_counts[row.get("payload_signature", "")] > 1
        )
        profile_keys = sorted({row.get("transition_profile_key", "") for row in group})
        if kind in {"coarse_shape", "signed_shape", "transition_profile"}:
            verdict = "repeated_exact_profile_review" if len(group) > 1 else "singleton_exact_profile"
        elif kind == "payload_signature":
            verdict = "repeated_payload_review" if len(group) > 1 else "singleton_payload"
        elif len(profile_keys) == 1 and len(group) > 1:
            verdict = "broad_signal_profile_repeat_review"
        elif len(group) > 1:
            verdict = "broad_signal_only"
        else:
            verdict = "singleton_broad_signal"
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "rows": str(len(group)),
                "bytes": str(sum(int_value(row, "length") for row in group)),
                "payload_signatures": str(len(payload_counts)),
                "repeated_payload_rows": str(repeated_payload_rows),
                "repeated_payload_bytes": str(repeated_payload_bytes),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group})),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group})),
                "micro_classes": "|".join(sorted({row.get("micro_class", "") for row in group})),
                "top_tokens": "|".join(sorted({row.get("top_token", "") for row in group})),
                "top_nibbles": "|".join(sorted({row.get("top_nibble", "") for row in group})),
                "profile_keys": "|".join(profile_keys),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("group_kind", ""),
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("group_key", ""),
        )
    )
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return (
        len(repeated),
        sum(int_value(row, "rows") for row in repeated),
        sum(int_value(row, "bytes") for row in repeated),
    )


def build_all_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    groups.extend(group_rows(rows, "payload_signature", lambda row: row.get("payload_signature", "")))
    groups.extend(group_rows(rows, "coarse_shape", lambda row: row.get("coarse_shape_key", "")))
    groups.extend(group_rows(rows, "signed_shape", lambda row: row.get("signed_shape_key", "")))
    groups.extend(group_rows(rows, "transition_profile", lambda row: row.get("transition_profile_key", "")))
    groups.extend(group_rows(rows, "top_token", lambda row: row.get("top_token", "")))
    groups.extend(group_rows(rows, "top_nibble", lambda row: row.get("top_nibble", "")))
    groups.extend(
        group_rows(
            rows,
            "top_token_nibble",
            lambda row: f"{row.get('top_token', '')}|{row.get('top_nibble', '')}",
        )
    )
    return groups


def groups_by_kind(groups: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
    return [row for row in groups if row.get("group_kind") == kind]


def build_summary(rows: list[dict[str, str]], groups: list[dict[str, str]]) -> dict[str, str]:
    payload_groups = groups_by_kind(groups, "payload_signature")
    coarse_groups = groups_by_kind(groups, "coarse_shape")
    signed_groups = groups_by_kind(groups, "signed_shape")
    profile_groups = groups_by_kind(groups, "transition_profile")
    top_token_groups = groups_by_kind(groups, "top_token")
    top_nibble_groups = groups_by_kind(groups, "top_nibble")
    top_token_nibble_groups = groups_by_kind(groups, "top_token_nibble")
    repeated_payload = repeated_stats(payload_groups)
    repeated_coarse = repeated_stats(coarse_groups)
    repeated_signed = repeated_stats(signed_groups)
    repeated_profile = repeated_stats(profile_groups)
    repeated_top_token = repeated_stats(top_token_groups)
    repeated_top_nibble = repeated_stats(top_nibble_groups)
    repeated_top_token_nibble = repeated_stats(top_token_nibble_groups)
    target_bytes = sum(int_value(row, "length") for row in rows)
    exact_profile_unique_bytes = target_bytes - repeated_profile[2]
    dominant_jump = [row for row in rows if row.get("top_token") == "JUMP"]
    dominant_top_nibble, dominant_top_nibble_count = Counter(
        row.get("top_nibble", "") for row in rows
    ).most_common(1)[0] if rows else ("", 0)
    dominant_top_nibble_rows = [row for row in rows if row.get("top_nibble") == dominant_top_nibble]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(target_bytes),
        "fixture_keys": str(len({fixture_key(row) for row in rows})),
        "payload_signature_groups": str(len(payload_groups)),
        "repeated_payload_groups": str(repeated_payload[0]),
        "repeated_payload_bytes": str(repeated_payload[2]),
        "coarse_shape_groups": str(len(coarse_groups)),
        "repeated_coarse_shape_groups": str(repeated_coarse[0]),
        "repeated_coarse_shape_rows": str(repeated_coarse[1]),
        "repeated_coarse_shape_bytes": str(repeated_coarse[2]),
        "signed_shape_groups": str(len(signed_groups)),
        "repeated_signed_shape_groups": str(repeated_signed[0]),
        "repeated_signed_shape_rows": str(repeated_signed[1]),
        "repeated_signed_shape_bytes": str(repeated_signed[2]),
        "transition_profile_groups": str(len(profile_groups)),
        "repeated_transition_profile_groups": str(repeated_profile[0]),
        "repeated_transition_profile_rows": str(repeated_profile[1]),
        "repeated_transition_profile_bytes": str(repeated_profile[2]),
        "top_token_groups": str(len(top_token_groups)),
        "repeated_top_token_groups": str(repeated_top_token[0]),
        "repeated_top_token_rows": str(repeated_top_token[1]),
        "repeated_top_token_bytes": str(repeated_top_token[2]),
        "top_nibble_groups": str(len(top_nibble_groups)),
        "repeated_top_nibble_groups": str(repeated_top_nibble[0]),
        "repeated_top_nibble_rows": str(repeated_top_nibble[1]),
        "repeated_top_nibble_bytes": str(repeated_top_nibble[2]),
        "top_token_nibble_groups": str(len(top_token_nibble_groups)),
        "repeated_top_token_nibble_groups": str(repeated_top_token_nibble[0]),
        "repeated_top_token_nibble_rows": str(repeated_top_token_nibble[1]),
        "repeated_top_token_nibble_bytes": str(repeated_top_token_nibble[2]),
        "dominant_jump_rows": str(len(dominant_jump)),
        "dominant_jump_bytes": str(sum(int_value(row, "length") for row in dominant_jump)),
        "dominant_top_nibble_rows": str(dominant_top_nibble_count),
        "dominant_top_nibble_bytes": str(sum(int_value(row, "length") for row in dominant_top_nibble_rows)),
        "exact_profile_unique_bytes": str(exact_profile_unique_bytes),
        "broad_signal_only_bytes": str(repeated_top_token_nibble[2]),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


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
    payload = {"summary": summary, "targets": rows, "sharedSignals": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("shared_signals.csv", output_dir / "shared_signals.csv"),
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
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.table-wrap {{ overflow: auto; max-height: 58vh; border: 1px solid var(--line); border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1160px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #26363b; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #1d292d; z-index: 1; }}
td {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Direction/value rows rechecked with expected payload micro-grammar.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target rows</div><div class="value">{html.escape(summary['target_rows'])}</div></div>
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated top token/nibble bytes</div><div class="value">{html.escape(summary['repeated_top_token_nibble_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated transition-profile bytes</div><div class="value">{html.escape(summary['repeated_transition_profile_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value">{html.escape(summary['repeated_payload_bytes'])}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </section>
  <section class="panel">
    <h2>Files</h2>
    <div class="links">{links}</div>
  </section>
  <section class="panel">
    <h2>Shared Signals</h2>
    <div class="table-wrap">{render_table(groups, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Targets</h2>
    <div class="table-wrap">{render_table(rows, TARGET_FIELDNAMES)}</div>
  </section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PAYLOAD_GRAMMAR_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Direction/Value Payload Grammar Probe",
    )
    args = parser.parse_args()

    rows, fixture_issues = build_target_rows(read_csv(args.targets), read_csv(args.fixtures))
    if fixture_issues:
        fixture_issue_text = ";".join(sorted(set(fixture_issues)))
        for row in rows:
            row["issues"] = ";".join(issue for issue in (row.get("issues", ""), fixture_issue_text) if issue)
    groups = build_all_groups(rows)
    summary = build_summary(rows, groups)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "shared_signals.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.output, args.title))

    print(f"Payload grammar rows: {summary['target_rows']}")
    print(f"Repeated top token/nibble bytes: {summary['repeated_top_token_nibble_bytes']}")
    print(f"Repeated transition-profile bytes: {summary['repeated_transition_profile_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
