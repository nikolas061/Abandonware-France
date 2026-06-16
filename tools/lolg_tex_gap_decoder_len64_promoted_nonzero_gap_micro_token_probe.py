#!/usr/bin/env python3
"""Tokenize noisy nonzero gap rows into small-delta micro grammar shapes."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "delta_count",
    "zero_delta_count",
    "step_delta_count",
    "small_delta_count",
    "jump_delta_count",
    "small_delta_ratio",
    "jump_delta_ratio",
    "token_runs",
    "avg_token_run_length",
    "coarse_shape_groups",
    "coarse_repeated_groups",
    "coarse_repeated_rows",
    "coarse_repeated_bytes",
    "signed_shape_groups",
    "signed_repeated_groups",
    "signed_repeated_rows",
    "signed_repeated_bytes",
    "transition_profile_groups",
    "transition_profile_repeated_groups",
    "transition_profile_repeated_rows",
    "transition_profile_repeated_bytes",
    "plateau_walk_rows",
    "plateau_walk_bytes",
    "small_signed_walk_rows",
    "small_signed_walk_bytes",
    "banded_walk_rows",
    "banded_walk_bytes",
    "jump_mixed_rows",
    "jump_mixed_bytes",
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
    "start_mod64",
    "control_ref_offset",
    "control_ref_mod64",
    "control_window_signature",
    "source_classification",
    "unique_bytes",
    "dominant_byte_hex",
    "dominant_ratio",
    "delta_count",
    "zero_delta_count",
    "zero_delta_ratio",
    "step_delta_count",
    "step_delta_ratio",
    "small_delta_count",
    "small_delta_ratio",
    "jump_delta_count",
    "jump_delta_ratio",
    "token_run_count",
    "max_token_run",
    "top_token",
    "top_token_count",
    "top_token_ratio",
    "top_nibble",
    "top_nibble_ratio",
    "coarse_shape_key",
    "coarse_shape_preview",
    "signed_shape_key",
    "signed_shape_preview",
    "transition_profile_key",
    "transition_profile_preview",
    "micro_class",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "group_preview",
    "rows",
    "bytes",
    "delta_count",
    "small_delta_count",
    "jump_delta_count",
    "micro_classes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def deltas(data: bytes) -> list[int]:
    return [signed_delta(data[index - 1], data[index]) for index in range(1, len(data))]


def coarse_bucket(delta: int) -> str:
    magnitude = abs(delta)
    if delta == 0:
        return "Z"
    if magnitude == 1:
        return "STEP"
    if magnitude <= 4:
        return "SMALL"
    if magnitude <= 31:
        return "MED"
    return "JUMP"


def signed_bucket(delta: int) -> str:
    if delta == 0:
        return "0"
    prefix = "+" if delta > 0 else "-"
    magnitude = abs(delta)
    if magnitude <= 2:
        return f"{prefix}{magnitude}"
    if magnitude <= 4:
        return f"{prefix}s4"
    if magnitude <= 15:
        return f"{prefix}s15"
    if magnitude <= 31:
        return f"{prefix}m"
    return f"{prefix}j"


def run_lengths(values: list[str]) -> list[tuple[str, int]]:
    if not values:
        return []
    runs: list[tuple[str, int]] = []
    current = values[0]
    count = 1
    for value in values[1:]:
        if value == current:
            count += 1
            continue
        runs.append((current, count))
        current = value
        count = 1
    runs.append((current, count))
    return runs


def token_shape(values: list[str]) -> str:
    return ".".join(f"{value}x{count}" for value, count in run_lengths(values))


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 120) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def top_nibble_stats(data: bytes) -> tuple[str, float]:
    if not data:
        return "", 0.0
    nibble, count = Counter(value >> 4 for value in data).most_common(1)[0]
    return f"0x{nibble:x}", count / len(data)


def transition_profile(values: list[str]) -> str:
    counts = Counter(values)
    order = ["0", "+1", "-1", "+2", "-2", "+s4", "-s4", "+s15", "-s15", "+m", "-m", "+j", "-j"]
    return ";".join(f"{label}:{counts[label]}" for label in order if counts[label])


def classify_micro(row: dict[str, str]) -> str:
    zero_ratio = float(row.get("zero_delta_ratio", "0") or 0)
    small_ratio = float(row.get("small_delta_ratio", "0") or 0)
    jump_ratio = float(row.get("jump_delta_ratio", "0") or 0)
    top_nibble_ratio = float(row.get("top_nibble_ratio", "0") or 0)
    if zero_ratio >= 0.45 and small_ratio >= 0.75:
        return "plateau_walk"
    if small_ratio >= 0.90 and top_nibble_ratio >= 0.75:
        return "banded_small_signed_walk"
    if small_ratio >= 0.90:
        return "small_signed_walk"
    if jump_ratio >= 0.25:
        return "jump_mixed_walk"
    if top_nibble_ratio >= 0.75 and small_ratio >= 0.75:
        return "banded_mixed_walk"
    return "mixed_token_walk"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue

        delta_values = deltas(expected)
        coarse_values = [coarse_bucket(value) for value in delta_values]
        signed_values = [signed_bucket(value) for value in delta_values]
        coarse_shape = token_shape(coarse_values)
        signed_shape = token_shape(signed_values)
        profile = transition_profile(signed_values)
        top_token, top_token_count = Counter(coarse_values).most_common(1)[0] if coarse_values else ("", 0)
        token_runs = run_lengths(coarse_values)
        zero_count = sum(1 for value in delta_values if value == 0)
        step_count = sum(1 for value in delta_values if abs(value) == 1)
        small_count = sum(1 for value in delta_values if abs(value) <= 4)
        jump_count = sum(1 for value in delta_values if abs(value) > 31)
        top_nibble, top_nibble_ratio = top_nibble_stats(expected)
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
            "start_mod64": target.get("start_mod64", ""),
            "control_ref_offset": target.get("control_ref_offset", ""),
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "control_window_signature": target.get("control_window_signature", ""),
            "source_classification": target.get("classification", ""),
            "unique_bytes": target.get("unique_bytes", ""),
            "dominant_byte_hex": target.get("dominant_byte_hex", ""),
            "dominant_ratio": target.get("dominant_ratio", ""),
            "delta_count": str(len(delta_values)),
            "zero_delta_count": str(zero_count),
            "zero_delta_ratio": ratio(zero_count, len(delta_values)),
            "step_delta_count": str(step_count),
            "step_delta_ratio": ratio(step_count, len(delta_values)),
            "small_delta_count": str(small_count),
            "small_delta_ratio": ratio(small_count, len(delta_values)),
            "jump_delta_count": str(jump_count),
            "jump_delta_ratio": ratio(jump_count, len(delta_values)),
            "token_run_count": str(len(token_runs)),
            "max_token_run": str(max((count for _value, count in token_runs), default=0)),
            "top_token": top_token,
            "top_token_count": str(top_token_count),
            "top_token_ratio": ratio(top_token_count, len(coarse_values)),
            "top_nibble": top_nibble,
            "top_nibble_ratio": f"{top_nibble_ratio:.6f}",
            "coarse_shape_key": shape_key(coarse_shape),
            "coarse_shape_preview": preview_text(coarse_shape),
            "signed_shape_key": shape_key(signed_shape),
            "signed_shape_preview": preview_text(signed_shape),
            "transition_profile_key": shape_key(profile),
            "transition_profile_preview": preview_text(profile),
            "micro_class": "",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        row["micro_class"] = classify_micro(row)
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], key_field: str, preview_field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    classes: dict[str, set[str]] = defaultdict(set)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    previews: dict[str, str] = {}
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["delta_count"] += int_value(row, "delta_count")
        counters[key]["small_delta_count"] += int_value(row, "small_delta_count")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        classes[key].add(row.get("micro_class", ""))
        fixtures[key].add(fixture_key(row))
        previews.setdefault(key, row.get(preview_field, ""))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "group_kind": kind,
                "group_key": key,
                "group_preview": previews.get(key, ""),
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "delta_count": str(counter["delta_count"]),
                "small_delta_count": str(counter["small_delta_count"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "micro_classes": ";".join(sorted(classes[key])),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("group_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    coarse_groups: list[dict[str, str]],
    signed_groups: list[dict[str, str]],
    profile_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    delta_count = sum(int_value(row, "delta_count") for row in rows)
    zero_count = sum(int_value(row, "zero_delta_count") for row in rows)
    step_count = sum(int_value(row, "step_delta_count") for row in rows)
    small_count = sum(int_value(row, "small_delta_count") for row in rows)
    jump_count = sum(int_value(row, "jump_delta_count") for row in rows)
    token_runs = sum(int_value(row, "token_run_count") for row in rows)
    coarse_repeated = repeated_stats(coarse_groups)
    signed_repeated = repeated_stats(signed_groups)
    profile_repeated = repeated_stats(profile_groups)
    plateau_rows = [row for row in rows if row.get("micro_class") == "plateau_walk"]
    small_rows = [row for row in rows if row.get("micro_class") == "small_signed_walk"]
    banded_rows = [row for row in rows if row.get("micro_class") == "banded_small_signed_walk"]
    jump_rows = [row for row in rows if row.get("micro_class") == "jump_mixed_walk"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum_bytes(rows)),
        "delta_count": str(delta_count),
        "zero_delta_count": str(zero_count),
        "step_delta_count": str(step_count),
        "small_delta_count": str(small_count),
        "jump_delta_count": str(jump_count),
        "small_delta_ratio": ratio(small_count, delta_count),
        "jump_delta_ratio": ratio(jump_count, delta_count),
        "token_runs": str(token_runs),
        "avg_token_run_length": ratio(delta_count, token_runs),
        "coarse_shape_groups": str(len(coarse_groups)),
        "coarse_repeated_groups": str(coarse_repeated[0]),
        "coarse_repeated_rows": str(coarse_repeated[1]),
        "coarse_repeated_bytes": str(coarse_repeated[2]),
        "signed_shape_groups": str(len(signed_groups)),
        "signed_repeated_groups": str(signed_repeated[0]),
        "signed_repeated_rows": str(signed_repeated[1]),
        "signed_repeated_bytes": str(signed_repeated[2]),
        "transition_profile_groups": str(len(profile_groups)),
        "transition_profile_repeated_groups": str(profile_repeated[0]),
        "transition_profile_repeated_rows": str(profile_repeated[1]),
        "transition_profile_repeated_bytes": str(profile_repeated[2]),
        "plateau_walk_rows": str(len(plateau_rows)),
        "plateau_walk_bytes": str(sum_bytes(plateau_rows)),
        "small_signed_walk_rows": str(len(small_rows)),
        "small_signed_walk_bytes": str(sum_bytes(small_rows)),
        "banded_walk_rows": str(len(banded_rows)),
        "banded_walk_bytes": str(sum_bytes(banded_rows)),
        "jump_mixed_rows": str(len(jump_rows)),
        "jump_mixed_bytes": str(sum_bytes(jump_rows)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    class_groups = build_group_rows(rows, "micro_class", "micro_class", "micro_class")
    coarse_groups = build_group_rows(rows, "coarse_shape_key", "coarse_shape_preview", "coarse_shape")
    signed_groups = build_group_rows(rows, "signed_shape_key", "signed_shape_preview", "signed_shape")
    profile_groups = build_group_rows(rows, "transition_profile_key", "transition_profile_preview", "transition_profile")
    summary = build_summary(rows, coarse_groups, signed_groups, profile_groups, len(fixture_issues))
    return summary, rows, class_groups, coarse_groups, signed_groups, profile_groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    class_groups: list[dict[str, str]],
    coarse_groups: list[dict[str, str]],
    signed_groups: list[dict[str, str]],
    profile_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "classGroups": class_groups,
        "coarseGroups": coarse_groups,
        "signedGroups": signed_groups,
        "profileGroups": profile_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_micro_class.csv", output_dir / "by_micro_class.csv"),
            ("by_coarse_shape.csv", output_dir / "by_coarse_shape.csv"),
            ("by_signed_shape.csv", output_dir / "by_signed_shape.csv"),
            ("by_transition_profile.csv", output_dir / "by_transition_profile.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Segments unresolved noisy rows into coarse and signed small-delta token shapes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Noisy bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Small-delta ratio</div><div class="value ok">{summary['small_delta_ratio']}</div></div>
    <div class="stat"><div class="label">Coarse repeated bytes</div><div class="value">{summary['coarse_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Signed repeated bytes</div><div class="value warn">{summary['signed_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Micro classes</h2>{render_table(class_groups, GROUP_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Coarse shapes</h2>{render_table(coarse_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Signed shapes</h2>{render_table(signed_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Transition profiles</h2>{render_table(profile_groups, GROUP_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 150)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MICRO_TOKEN_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe noisy .tex nonzero gaps as small-delta micro tokens.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Micro Token Probe",
    )
    args = parser.parse_args()

    summary, rows, class_groups, coarse_groups, signed_groups, profile_groups = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_micro_class.csv", GROUP_FIELDNAMES, class_groups)
    write_csv(args.output / "by_coarse_shape.csv", GROUP_FIELDNAMES, coarse_groups)
    write_csv(args.output / "by_signed_shape.csv", GROUP_FIELDNAMES, signed_groups)
    write_csv(args.output / "by_transition_profile.csv", GROUP_FIELDNAMES, profile_groups)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, rows, class_groups, coarse_groups, signed_groups, profile_groups, args.output, args.title)
    )

    print(f"Micro-token targets: {summary['target_rows']}")
    print(f"Micro-token bytes: {summary['target_bytes']}")
    print(f"Small-delta ratio: {summary['small_delta_ratio']}")
    print(f"Signed repeated bytes: {summary['signed_repeated_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
