#!/usr/bin/env python3
"""Split exact residual consensus changes by wider high-row support context."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_context_split_probe")
DEFAULT_VALIDATION_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_consensus_validation_probe/"
    "validation_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "changed_bytes",
    "changed_exact_bytes",
    "changed_false_bytes",
    "best_guard",
    "best_guard_scope",
    "best_guard_keys",
    "best_guard_safe_keys",
    "best_guard_accepted_bytes",
    "best_guard_accepted_exact_bytes",
    "best_guard_accepted_false_bytes",
    "best_guard_rejected_exact_bytes",
    "best_guard_rejected_false_bytes",
    "best_guard_safe_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "guard_name",
    "guard_scope",
    "key_count",
    "safe_key_count",
    "false_key_count",
    "mixed_key_count",
    "accepted_bytes",
    "accepted_exact_bytes",
    "accepted_false_bytes",
    "rejected_exact_bytes",
    "rejected_false_bytes",
    "changed_exact_bytes",
    "changed_false_bytes",
    "safe_ratio",
    "table_preview",
]

TABLE_FIELDNAMES = [
    "guard_name",
    "guard_scope",
    "guard_key",
    "decision",
    "group_size",
    "exact_bytes",
    "false_bytes",
    "predicted_delta_domain",
    "source_ids",
    "byte_indices",
    "support_values",
    "support_starts",
]

SPLIT_FIELDNAMES = [
    "source_id",
    "support_id",
    "rank",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "support_start",
    "byte_index",
    "selector_key",
    "support_value_hex",
    "source_value_hex",
    "observed_delta",
    "predicted_delta",
    "exact",
    "guard_name",
    "guard_key",
    "group_size",
    "group_exact_bytes",
    "group_false_bytes",
    "split_decision",
]

Feature = tuple[str, str, Callable[[dict[str, str]], str]]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def byte_index(row: dict[str, str]) -> int:
    return int_value(row, "byte_index")


def support_start(row: dict[str, str]) -> int:
    return int_value(row, "support_start")


def feature_defs() -> list[Feature]:
    return [
        (
            "source_byte_support_value_delta",
            "context_split",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_byte_support_value",
            "context_split",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|"
                f"v{row.get('support_value_hex', '')}"
            ),
        ),
        (
            "source_mod_support_value_delta",
            "compact_context",
            lambda row: (
                f"{row.get('source_id', '')}|m{byte_index(row) % 16}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_mod_support_value",
            "compact_context",
            lambda row: (
                f"{row.get('source_id', '')}|m{byte_index(row) % 16}|"
                f"v{row.get('support_value_hex', '')}"
            ),
        ),
        (
            "source_byte_start_mod4_value_delta",
            "context_split",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|s{support_start(row) % 4}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_byte_start_mod8_value_delta",
            "context_split",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|s{support_start(row) % 8}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_byte_rank_frontier_value_delta",
            "support_context",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|"
                f"r{row.get('rank', '')}f{row.get('frontier_id', '')}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_byte_support_id_value_delta",
            "support_rank_context",
            lambda row: (
                f"{row.get('source_id', '')}|p{byte_index(row):02d}|sid{row.get('support_id', '')}|"
                f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "source_support_value_delta",
            "source_context",
            lambda row: (
                f"{row.get('source_id', '')}|v{row.get('support_value_hex', '')}|"
                f"d{row.get('predicted_delta', '')}"
            ),
        ),
        (
            "support_value_delta",
            "compact_context",
            lambda row: f"v{row.get('support_value_hex', '')}|d{row.get('predicted_delta', '')}",
        ),
    ]


def changed_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("changed") == "1"]


def group_rows(rows: list[dict[str, str]], feature: Callable[[dict[str, str]], str]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[feature(row)].append(row)
    return groups


def key_decision(rows: list[dict[str, str]], *, min_group_size: int) -> str:
    exact = sum(1 for row in rows if row.get("exact") == "1")
    false = len(rows) - exact
    if len(rows) >= min_group_size and false == 0:
        return "accept"
    if exact == 0:
        return "reject"
    return "mixed"


def build_guard_table(
    rows: list[dict[str, str]],
    guard_name: str,
    guard_scope: str,
    feature: Callable[[dict[str, str]], str],
    *,
    min_group_size: int,
) -> list[dict[str, str]]:
    table_rows: list[dict[str, str]] = []
    for key, group in sorted(group_rows(rows, feature).items()):
        exact = sum(1 for row in group if row.get("exact") == "1")
        false = len(group) - exact
        table_rows.append(
            {
                "guard_name": guard_name,
                "guard_scope": guard_scope,
                "guard_key": key,
                "decision": key_decision(group, min_group_size=min_group_size),
                "group_size": str(len(group)),
                "exact_bytes": str(exact),
                "false_bytes": str(false),
                "predicted_delta_domain": ";".join(
                    str(delta) for delta in sorted({int_value(row, "predicted_delta") for row in group})
                ),
                "source_ids": ";".join(sorted({row.get("source_id", "") for row in group})),
                "byte_indices": ";".join(str(index) for index in sorted({byte_index(row) for row in group})),
                "support_values": ";".join(sorted({row.get("support_value_hex", "") for row in group})),
                "support_starts": ";".join(str(start) for start in sorted({support_start(row) for row in group})[:16]),
            }
        )
    return table_rows


def candidate_stats(
    rows: list[dict[str, str]],
    guard_name: str,
    guard_scope: str,
    feature: Callable[[dict[str, str]], str],
    *,
    min_group_size: int,
) -> dict[str, str]:
    table = build_guard_table(rows, guard_name, guard_scope, feature, min_group_size=min_group_size)
    decision_by_key = {row["guard_key"]: row for row in table}
    accepted = [row for row in rows if decision_by_key[feature(row)]["decision"] == "accept"]
    accepted_exact = sum(1 for row in accepted if row.get("exact") == "1")
    accepted_false = len(accepted) - accepted_exact
    changed_exact = sum(1 for row in rows if row.get("exact") == "1")
    changed_false = len(rows) - changed_exact
    rejected_exact = changed_exact - accepted_exact
    rejected_false = changed_false - accepted_false
    previews = [
        f"{row['guard_key']}:{row['decision']}:{row['exact_bytes']}/{row['group_size']}"
        for row in table[:24]
    ]
    return {
        "guard_name": guard_name,
        "guard_scope": guard_scope,
        "key_count": str(len(table)),
        "safe_key_count": str(sum(1 for row in table if row.get("decision") == "accept")),
        "false_key_count": str(sum(1 for row in table if row.get("decision") == "reject")),
        "mixed_key_count": str(sum(1 for row in table if row.get("decision") == "mixed")),
        "accepted_bytes": str(len(accepted)),
        "accepted_exact_bytes": str(accepted_exact),
        "accepted_false_bytes": str(accepted_false),
        "rejected_exact_bytes": str(rejected_exact),
        "rejected_false_bytes": str(rejected_false),
        "changed_exact_bytes": str(changed_exact),
        "changed_false_bytes": str(changed_false),
        "safe_ratio": ratio(accepted_exact, changed_exact),
        "table_preview": " | ".join(previews),
    }


def build_candidates(rows: list[dict[str, str]], *, min_group_size: int) -> list[dict[str, str]]:
    candidates = [
        candidate_stats(rows, name, scope, feature, min_group_size=min_group_size)
        for name, scope, feature in feature_defs()
    ]
    order = {name: index for index, (name, _scope, _feature) in enumerate(feature_defs())}
    candidates.sort(
        key=lambda row: (
            int_value(row, "accepted_false_bytes") != 0,
            -int_value(row, "accepted_exact_bytes"),
            int_value(row, "rejected_exact_bytes"),
            int_value(row, "key_count"),
            order.get(row.get("guard_name", ""), 999),
        )
    )
    return candidates


def feature_by_name(name: str) -> tuple[str, Callable[[dict[str, str]], str]]:
    for guard_name, scope, feature in feature_defs():
        if guard_name == name:
            return scope, feature
    return "", lambda row: ""


def build_split_rows(
    rows: list[dict[str, str]],
    guard_name: str,
    feature: Callable[[dict[str, str]], str],
    table_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    table_by_key = {row.get("guard_key", ""): row for row in table_rows}
    split_rows: list[dict[str, str]] = []
    for row in rows:
        key = feature(row)
        table = table_by_key.get(key, {})
        split_rows.append(
            {
                "source_id": row.get("source_id", ""),
                "support_id": row.get("support_id", ""),
                "rank": row.get("rank", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "support_start": row.get("support_start", ""),
                "byte_index": row.get("byte_index", ""),
                "selector_key": row.get("selector_key", ""),
                "support_value_hex": row.get("support_value_hex", ""),
                "source_value_hex": row.get("source_value_hex", ""),
                "observed_delta": row.get("observed_delta", ""),
                "predicted_delta": row.get("predicted_delta", ""),
                "exact": row.get("exact", ""),
                "guard_name": guard_name,
                "guard_key": key,
                "group_size": table.get("group_size", "0"),
                "group_exact_bytes": table.get("exact_bytes", "0"),
                "group_false_bytes": table.get("false_bytes", "0"),
                "split_decision": table.get("decision", "reject"),
            }
        )
    return split_rows


def build_summary(rows: list[dict[str, str]], best: dict[str, str], *, issue_count: int) -> dict[str, str]:
    changed_exact = sum(1 for row in rows if row.get("exact") == "1")
    changed_false = len(rows) - changed_exact
    accepted_exact = int_value(best, "accepted_exact_bytes")
    accepted_false = int_value(best, "accepted_false_bytes")
    if issue_count:
        verdict = "frontier80_prior_high_row_exact_residual_context_split_issues"
        next_probe = "fix context-split residual guard input issues"
    elif accepted_false == 0 and accepted_exact == changed_exact and changed_exact > 0:
        verdict = "frontier80_prior_high_row_exact_residual_context_split_ready"
        next_probe = "promote context-split residual correction for threshold-guarded high-row selector"
    elif accepted_false == 0 and accepted_exact > 0:
        verdict = "frontier80_prior_high_row_exact_residual_context_split_partial_ready"
        next_probe = "expand context-split residual guard to recover rejected true changes"
    elif accepted_false > 0:
        verdict = "frontier80_prior_high_row_exact_residual_context_split_rejected"
        next_probe = "derive stricter support context for residual correction false positives"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_context_split_weak"
        next_probe = "expand residual context features beyond source byte and support value"

    return {
        "scope": "changed",
        "changed_bytes": str(len(rows)),
        "changed_exact_bytes": str(changed_exact),
        "changed_false_bytes": str(changed_false),
        "best_guard": best.get("guard_name", ""),
        "best_guard_scope": best.get("guard_scope", ""),
        "best_guard_keys": best.get("key_count", "0"),
        "best_guard_safe_keys": best.get("safe_key_count", "0"),
        "best_guard_accepted_bytes": best.get("accepted_bytes", "0"),
        "best_guard_accepted_exact_bytes": best.get("accepted_exact_bytes", "0"),
        "best_guard_accepted_false_bytes": best.get("accepted_false_bytes", "0"),
        "best_guard_rejected_exact_bytes": best.get("rejected_exact_bytes", "0"),
        "best_guard_rejected_false_bytes": best.get("rejected_false_bytes", "0"),
        "best_guard_safe_ratio": best.get("safe_ratio", "0.000000"),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    table_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidates,
        "guard_table": table_rows,
        "split_rows": split_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("guard_candidates.csv", output_dir / "guard_candidates.csv"),
            ("guard_table.csv", output_dir / "guard_table.csv"),
            ("split_rows.csv", output_dir / "split_rows.csv"),
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
  --ok: #80df94;
  --warn: #f2c36b;
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
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1420px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Splits rejected residual consensus changes with support-byte context guards.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Changed exact</div><div class="value">{summary['changed_exact_bytes']}/{summary['changed_bytes']}</div></div>
    <div class="stat"><div class="label">Accepted exact</div><div class="value ok">{summary['best_guard_accepted_exact_bytes']}</div></div>
    <div class="stat"><div class="label">Accepted false</div><div class="value warn">{summary['best_guard_accepted_false_bytes']}</div></div>
    <div class="stat"><div class="label">Best guard</div><div class="value">{html.escape(summary['best_guard'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Guard candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Selected guard table</h2>{render_table(table_rows, TABLE_FIELDNAMES)}</section>
  <section class="panel"><h2>Split rows</h2>{render_table(split_rows, SPLIT_FIELDNAMES)}</section>
</main>
<script type="application/json" id="high-row-exact-residual-context-split-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    validation_rows_path: Path,
    output_dir: Path,
    *,
    min_group_size: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    rows = changed_rows(read_csv(validation_rows_path))
    if not rows:
        issues.append("missing_changed_validation_rows")

    candidates = build_candidates(rows, min_group_size=min_group_size) if rows else []
    best = candidates[0] if candidates else {}
    best_scope, best_feature = feature_by_name(best.get("guard_name", ""))
    table_rows = (
        build_guard_table(rows, best.get("guard_name", ""), best_scope, best_feature, min_group_size=min_group_size)
        if rows and best
        else []
    )
    split_rows = build_split_rows(rows, best.get("guard_name", ""), best_feature, table_rows) if rows and best else []
    summary = build_summary(rows, best, issue_count=len(issues))

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "guard_candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(output_dir / "guard_table.csv", TABLE_FIELDNAMES, table_rows)
    write_csv(output_dir / "split_rows.csv", SPLIT_FIELDNAMES, split_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, candidates, table_rows, split_rows, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-rows", type=Path, default=DEFAULT_VALIDATION_ROWS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-group-size", type=int, default=2)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Context Split Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.validation_rows,
        args.output,
        min_group_size=args.min_group_size,
        title=args.title,
    )
    print(f"Best guard: {summary['best_guard']}")
    print(
        "Accepted exact: "
        f"{summary['best_guard_accepted_exact_bytes']}/{summary['changed_exact_bytes']}"
    )
    print(f"Accepted false: {summary['best_guard_accepted_false_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
