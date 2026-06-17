#!/usr/bin/env python3
"""Review expanded pair+mod false rows for the frontier 80 five-byte guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_EXPANDED_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/summary.csv"
)
DEFAULT_EXPANDED_HITS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/hits.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "pair_any_rows",
    "pair_mod_rows",
    "pair_mod_non_target_rows",
    "feature_rows",
    "pair_mod_false_free_feature_rows",
    "base_guard_key",
    "best_refined_guard_family",
    "best_refined_guard_key",
    "best_pair_mod_rows",
    "best_pair_mod_non_target_rows",
    "best_pair_any_rows",
    "best_pair_any_non_target_rows",
    "best_pair_any_frontiers",
    "target_only_refined_rows",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

HIT_FIELDNAMES = [
    "rank",
    "hit_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "ref_offset",
    "matches_mod",
    "is_target_asset",
    "rule_type",
    "frontier_type",
    "pixel_gap",
    "pixel_gap_bucket",
    "segment_gap_bytes",
    "segment_gap_bytes_bucket",
    "segment_gap_ratio",
    "segment_gap_ratio_bucket",
    "opcode0_hex",
    "opcode1_hex",
    "opcode_pair",
    "best_raw_skip",
    "best_raw_skip_bucket",
    "best_raw_prefix_bytes",
    "control_prefix_bytes",
    "fragment_bytes",
    "segment_prev4_hex",
    "segment_ref_hex",
    "segment_next4_hex",
    "segment_rel_-8",
    "segment_rel_-7",
    "segment_rel_-6",
    "segment_rel_-5",
    "segment_rel_-4",
    "segment_rel_-3",
    "segment_rel_-2",
    "segment_rel_-1",
    "segment_rel_0",
    "segment_rel_1",
    "segment_rel_4",
    "segment_rel_5",
    "segment_rel_6",
]

FEATURE_FIELDNAMES = [
    "rank",
    "feature",
    "target_value",
    "pair_mod_rows",
    "pair_mod_target_rows",
    "pair_mod_non_target_rows",
    "pair_any_rows",
    "pair_any_non_target_rows",
    "pair_any_frontiers",
    "guard_key",
    "verdict",
]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    priority: int


FEATURE_SPECS = [
    FeatureSpec("rule_type", 0),
    FeatureSpec("segment_gap_ratio_bucket", 1),
    FeatureSpec("segment_gap_bytes_bucket", 2),
    FeatureSpec("pixel_gap_bucket", 3),
    FeatureSpec("frontier_type", 4),
    FeatureSpec("best_raw_prefix_bytes", 5),
    FeatureSpec("fragment_bytes", 6),
    FeatureSpec("control_prefix_bytes", 7),
    FeatureSpec("best_raw_skip_bucket", 8),
    FeatureSpec("opcode_pair", 20),
    FeatureSpec("opcode0_hex", 21),
    FeatureSpec("opcode1_hex", 22),
    FeatureSpec("segment_prev4_hex", 30),
    FeatureSpec("segment_next4_hex", 31),
    FeatureSpec("segment_rel_-8", 40),
    FeatureSpec("segment_rel_-7", 41),
    FeatureSpec("segment_rel_-6", 42),
    FeatureSpec("segment_rel_-5", 43),
    FeatureSpec("segment_rel_-4", 44),
    FeatureSpec("segment_rel_-3", 45),
    FeatureSpec("segment_rel_-2", 46),
    FeatureSpec("segment_rel_-1", 47),
    FeatureSpec("segment_rel_0", 48),
    FeatureSpec("segment_rel_1", 49),
    FeatureSpec("segment_rel_4", 50),
    FeatureSpec("segment_rel_5", 51),
    FeatureSpec("segment_rel_6", 52),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def float_value(row: dict[str, str], field: str, default: float = 0.0) -> float:
    try:
        return float(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def row_identity(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def bucket_pixel_gap(value: int) -> str:
    if value < 64:
        return "lt64"
    if value < 256:
        return "64_255"
    if value < 512:
        return "256_511"
    if value < 1024:
        return "512_1023"
    return "gte1024"


def bucket_segment_bytes(value: int) -> str:
    if value < 64:
        return "lt64"
    if value < 512:
        return "64_511"
    if value < 4096:
        return "512_4095"
    if value < 65536:
        return "4096_65535"
    return "gte65536"


def bucket_ratio(value: float) -> str:
    if value < 0.25:
        return "lt0.25"
    if value < 1.0:
        return "0.25_1"
    if value < 10.0:
        return "1_10"
    if value < 100.0:
        return "10_100"
    return "gte100"


def bucket_raw_skip(value: int) -> str:
    if value < 4:
        return "lt4"
    if value < 8:
        return "4_7"
    if value < 16:
        return "8_15"
    if value < 32:
        return "16_31"
    return "gte32"


def segment_byte(segment: bytes, ref: int, rel: int) -> str:
    index = ref + rel
    if index < 0 or index >= len(segment):
        return "."
    return f"{segment[index]:02x}"


def segment_slice(segment: bytes, start: int, end: int) -> str:
    return segment[max(0, start) : min(len(segment), end)].hex()


def build_hit_features(
    hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    manifest_by_key = {row_identity(row): row for row in manifest_rows}
    rows: list[dict[str, str]] = []
    issues: list[str] = []
    for hit in hit_rows:
        manifest = manifest_by_key.get(row_identity(hit))
        if manifest is None:
            issues.append(f"{'|'.join(row_identity(hit))}:missing_manifest")
            continue
        segment_path = manifest.get("segment_gap_path", "")
        try:
            segment = Path(segment_path).read_bytes()
        except OSError as exc:
            issues.append(f"{'|'.join(row_identity(hit))}:read_segment_failed:{exc}")
            segment = b""
        ref = int_value(hit, "ref_offset", -1)
        pixel_gap = int_value(manifest, "pixel_gap")
        segment_bytes = int_value(manifest, "segment_gap_bytes")
        segment_ratio = float_value(manifest, "segment_gap_ratio")
        raw_skip = int_value(manifest, "best_raw_skip")
        row = {
            "rank": "",
            "hit_rank": hit.get("rank", ""),
            "archive": hit.get("archive", ""),
            "archive_tag": hit.get("archive_tag", ""),
            "pcx_name": hit.get("pcx_name", ""),
            "frontier_id": hit.get("frontier_id", ""),
            "ref_offset": hit.get("ref_offset", ""),
            "matches_mod": hit.get("matches_mod", ""),
            "is_target_asset": hit.get("is_target_asset", ""),
            "rule_type": manifest.get("rule_type", ""),
            "frontier_type": manifest.get("frontier_type", ""),
            "pixel_gap": manifest.get("pixel_gap", ""),
            "pixel_gap_bucket": bucket_pixel_gap(pixel_gap),
            "segment_gap_bytes": manifest.get("segment_gap_bytes", ""),
            "segment_gap_bytes_bucket": bucket_segment_bytes(segment_bytes),
            "segment_gap_ratio": manifest.get("segment_gap_ratio", ""),
            "segment_gap_ratio_bucket": bucket_ratio(segment_ratio),
            "opcode0_hex": manifest.get("opcode0_hex", ""),
            "opcode1_hex": manifest.get("opcode1_hex", ""),
            "opcode_pair": f"{manifest.get('opcode0_hex', '')}/{manifest.get('opcode1_hex', '')}",
            "best_raw_skip": manifest.get("best_raw_skip", ""),
            "best_raw_skip_bucket": bucket_raw_skip(raw_skip),
            "best_raw_prefix_bytes": manifest.get("best_raw_prefix_bytes", ""),
            "control_prefix_bytes": manifest.get("control_prefix_bytes", ""),
            "fragment_bytes": manifest.get("fragment_bytes", ""),
            "segment_prev4_hex": segment_slice(segment, ref - 4, ref),
            "segment_ref_hex": segment_slice(segment, ref, ref + 4),
            "segment_next4_hex": segment_slice(segment, ref + 4, ref + 8),
        }
        for rel in (-8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 4, 5, 6):
            row[f"segment_rel_{rel}"] = segment_byte(segment, ref, rel)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("matches_mod") != "1",
            row.get("is_target_asset") != "1",
            int_value(row, "frontier_id"),
            int_value(row, "ref_offset"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows, issues


def frontier_list(rows: list[dict[str, str]], limit: int = 12) -> str:
    values = sorted({row.get("frontier_id", "") for row in rows}, key=lambda value: int(value or 0))
    suffix = "" if len(values) <= limit else ",..."
    return ",".join(values[:limit]) + suffix


def feature_verdict(pair_mod_rows: list[dict[str, str]]) -> str:
    if not pair_mod_rows:
        return "no_pair_mod_match"
    non_target = [row for row in pair_mod_rows if row.get("is_target_asset") != "1"]
    return "pair_mod_false_free" if not non_target else "pair_mod_conflict"


def build_feature_rows(
    hit_features: list[dict[str, str]],
    target: dict[str, str],
    base_guard_key: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for spec in FEATURE_SPECS:
        target_value = target.get(spec.name, "")
        pair_any = [row for row in hit_features if row.get(spec.name, "") == target_value]
        pair_mod = [row for row in pair_any if row.get("matches_mod") == "1"]
        pair_mod_target = [row for row in pair_mod if row.get("is_target_asset") == "1"]
        pair_mod_non_target = [row for row in pair_mod if row.get("is_target_asset") != "1"]
        pair_any_non_target = [row for row in pair_any if row.get("is_target_asset") != "1"]
        guard_key = f"{base_guard_key}|{spec.name}={target_value}"
        rows.append(
            {
                "rank": "",
                "feature": spec.name,
                "target_value": target_value,
                "pair_mod_rows": str(len(pair_mod)),
                "pair_mod_target_rows": str(len(pair_mod_target)),
                "pair_mod_non_target_rows": str(len(pair_mod_non_target)),
                "pair_any_rows": str(len(pair_any)),
                "pair_any_non_target_rows": str(len(pair_any_non_target)),
                "pair_any_frontiers": frontier_list(pair_any),
                "guard_key": guard_key,
                "verdict": feature_verdict(pair_mod),
            }
        )
    priority_by_feature = {spec.name: spec.priority for spec in FEATURE_SPECS}
    rows.sort(
        key=lambda row: (
            row.get("verdict") != "pair_mod_false_free",
            int_value(row, "pair_any_non_target_rows") == 0,
            priority_by_feature.get(row.get("feature", ""), 999),
            -int_value(row, "pair_any_rows"),
            row.get("feature", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def choose_best(feature_rows: list[dict[str, str]]) -> dict[str, str]:
    false_free = [row for row in feature_rows if row.get("verdict") == "pair_mod_false_free"]
    return false_free[0] if false_free else {}


def verdict_for(best: dict[str, str], pair_mod_non_target_rows: int) -> tuple[str, str]:
    if not best:
        return "pair_mod_refinement_unresolved", "derive alternate feature split for expanded pair-mod false rows"
    if int_value(best, "pair_any_non_target_rows") > 0:
        return (
            "pair_mod_false_free_broad_refinement",
            "seek independent support for compact-control five-byte guard refinement",
        )
    if pair_mod_non_target_rows > 0:
        return (
            "pair_mod_false_free_target_unique_refinement",
            "avoid target-unique five-byte guard; derive broader non-oracle refinement",
        )
    return "pair_mod_target_only_refinement", "expand five-byte guard support beyond expanded pair-mod review"


def build(
    expanded_summary_rows: list[dict[str, str]],
    hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    expanded_summary = expanded_summary_rows[0] if expanded_summary_rows else {}
    hit_features, issues = build_hit_features(hit_rows, manifest_rows)
    pair_mod_rows = [row for row in hit_features if row.get("matches_mod") == "1"]
    pair_mod_non_target = [row for row in pair_mod_rows if row.get("is_target_asset") != "1"]
    target_rows = [row for row in pair_mod_rows if row.get("is_target_asset") == "1"]
    if not target_rows:
        issues.append("missing_pair_mod_target_row")
        feature_rows: list[dict[str, str]] = []
        best = {}
    else:
        feature_rows = build_feature_rows(hit_features, target_rows[0], expanded_summary.get("best_guard_key", ""))
        best = choose_best(feature_rows)
    verdict, next_probe = verdict_for(best, len(pair_mod_non_target))
    false_free_rows = [row for row in feature_rows if row.get("verdict") == "pair_mod_false_free"]
    target_only_refined = (
        int_value(best, "pair_mod_rows")
        if best and int_value(best, "pair_mod_non_target_rows") == 0
        else 0
    )
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_pair_mod_review",
        "target_spans": expanded_summary.get("target_spans", "0"),
        "target_bytes": expanded_summary.get("target_bytes", "0"),
        "pair_any_rows": str(len(hit_features)),
        "pair_mod_rows": str(len(pair_mod_rows)),
        "pair_mod_non_target_rows": str(len(pair_mod_non_target)),
        "feature_rows": str(len(feature_rows)),
        "pair_mod_false_free_feature_rows": str(len(false_free_rows)),
        "base_guard_key": expanded_summary.get("best_guard_key", ""),
        "best_refined_guard_family": best.get("feature", ""),
        "best_refined_guard_key": best.get("guard_key", ""),
        "best_pair_mod_rows": best.get("pair_mod_rows", "0"),
        "best_pair_mod_non_target_rows": best.get("pair_mod_non_target_rows", "0"),
        "best_pair_any_rows": best.get("pair_any_rows", "0"),
        "best_pair_any_non_target_rows": best.get("pair_any_non_target_rows", "0"),
        "best_pair_any_frontiers": best.get("pair_any_frontiers", ""),
        "target_only_refined_rows": str(target_only_refined),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, hit_features, feature_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    hit_features: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "hit_features": hit_features, "features": feature_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("hit_features.csv", output_dir / "hit_features.csv"),
            ("features.csv", output_dir / "features.csv"),
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
  --panel: #182023;
  --line: #314247;
  --text: #edf4f2;
  --muted: #a4b2b5;
  --accent: #7bd5b4;
  --warn: #eebb70;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1420px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Reviews expanded pair+mod false rows and ranks non-oracle refinement features.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Pair any rows</div><div class="value">{summary['pair_any_rows']}</div></div>
    <div class="stat"><div class="muted">Pair+mod rows</div><div class="value">{summary['pair_mod_rows']}</div></div>
    <div class="stat"><div class="muted">Pair+mod non-target</div><div class="value warn">{summary['pair_mod_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">False-free features</div><div class="value">{summary['pair_mod_false_free_feature_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Best Refinement</h2>
    <p><code>{html.escape(summary['best_refined_guard_key'])}</code></p>
    <p class="muted">Verdict: <code>{html.escape(summary['review_verdict'])}</code>. Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Feature Rows</h2>{render_table(feature_rows, FEATURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Hit Features</h2>{render_table(hit_features, HIT_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-pair-mod-review-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review expanded pair+mod false rows for the five-byte guard.")
    parser.add_argument("--expanded-summary", type=Path, default=DEFAULT_EXPANDED_SUMMARY)
    parser.add_argument("--expanded-hits", type=Path, default=DEFAULT_EXPANDED_HITS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Pair+Mod Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, hit_features, feature_rows = build(
        read_rows(args.expanded_summary),
        read_rows(args.expanded_hits),
        read_rows(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "hit_features.csv", HIT_FIELDNAMES, hit_features)
    write_csv(args.output / "features.csv", FEATURE_FIELDNAMES, feature_rows)
    (args.output / "index.html").write_text(
        build_html(summary, hit_features, feature_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte pair+mod review: "
        f"pair_mod={summary['pair_mod_rows']} "
        f"non_target={summary['pair_mod_non_target_rows']} "
        f"false_free_features={summary['pair_mod_false_free_feature_rows']} "
        f"best={summary['best_refined_guard_family'] or 'none'} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
