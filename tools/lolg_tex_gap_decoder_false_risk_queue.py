#!/usr/bin/env python3
"""Queue .tex decoder seed decisions into promoted, rejected, or review buckets."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_control_promotion_probe import (
    fixture_key,
    length,
    op_key,
    selector_signatures,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_false_risk_queue")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_DECISIONS = Path("output/tex_gap_decoder_seed_replay/decisions.csv")
DEFAULT_SIGNATURES = Path("output/tex_gap_decoder_control_promotion_probe/signatures.csv")

PROMOTION_SELECTORS = {"pre4_next2", "zero_len64_and_u8"}

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "decision_rows",
    "fixture_rows",
    "selected_ops",
    "selected_bytes",
    "promoted_ops",
    "promoted_bytes",
    "promoted_literal_bytes",
    "promoted_zero_bytes",
    "rejected_ops",
    "rejected_false_bytes",
    "review_ops",
    "review_bytes",
    "trusted_unpromoted_bytes",
    "false_remaining_bytes",
    "safe_rejector_groups",
    "mixed_rejector_groups",
    "issue_rows",
]

QUEUE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "op_kind",
    "expected_start",
    "expected_end",
    "length",
    "decision",
    "risk_class",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "verdict",
    "promotion_selector",
    "promotion_signature",
    "reject_reason",
    "pre4_hex",
    "next2_hex",
    "length_u8_hit_offsets",
    "token_value",
    "token_plus3_match",
    "source_offset",
    "source_end",
    "issues",
]

REJECTOR_FIELDNAMES = [
    "selector",
    "signature",
    "verdict",
    "selected_ops",
    "trusted_ops",
    "false_ops",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "sample_rank",
    "sample_pcx",
    "sample_frontier_id",
    "sample_op_index",
    "sample_pre4_hex",
    "sample_next2_hex",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "selected_ops",
    "selected_bytes",
    "promoted_ops",
    "promoted_bytes",
    "promoted_literal_bytes",
    "promoted_zero_bytes",
    "rejected_ops",
    "rejected_false_bytes",
    "review_ops",
    "review_bytes",
    "trusted_unpromoted_bytes",
    "false_remaining_bytes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def pure_promotion_signatures(signature_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {
        (row.get("selector", ""), row.get("signature", ""))
        for row in signature_rows
        if row.get("promotion_class") == "pure"
        and row.get("selector", "") in PROMOTION_SELECTORS
    }


def selected_signature_groups(
    joined_rows: list[tuple[dict[str, str], dict[str, str]]],
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for operation, decision in joined_rows:
        if not decision.get("decision"):
            continue
        for selector, signature in selector_signatures(operation).items():
            if signature:
                grouped[(selector, signature)].append((operation, decision))

    rows: list[dict[str, str]] = []
    for (selector, signature), group_rows in sorted(grouped.items()):
        false_bytes = sum(int_value(decision, "false_bytes") for _operation, decision in group_rows)
        if not false_bytes:
            continue
        trusted_bytes = sum(int_value(decision, "trusted_bytes") for _operation, decision in group_rows)
        sample = group_rows[0][0]
        rows.append(
            {
                "selector": selector,
                "signature": signature,
                "verdict": "safe_reject" if trusted_bytes == 0 else "mixed_review",
                "selected_ops": str(len(group_rows)),
                "trusted_ops": str(
                    sum(
                        1
                        for _operation, decision in group_rows
                        if decision.get("risk_class", "").startswith("true_")
                    )
                ),
                "false_ops": str(
                    sum(
                        1
                        for _operation, decision in group_rows
                        if decision.get("risk_class", "").startswith("false_")
                    )
                ),
                "selected_bytes": str(
                    sum(int_value(decision, "selected_bytes") for _operation, decision in group_rows)
                ),
                "trusted_bytes": str(trusted_bytes),
                "false_bytes": str(false_bytes),
                "sample_rank": sample.get("rank", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_op_index": sample.get("op_index", ""),
                "sample_pre4_hex": sample.get("pre4_hex", ""),
                "sample_next2_hex": sample.get("next2_hex", ""),
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("verdict") != "safe_reject",
            -int_value(row, "false_bytes"),
            int_value(row, "trusted_bytes"),
            row.get("selector", ""),
            row.get("signature", ""),
        )
    )
    return rows


def build_rows(
    operation_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    decisions = {op_key(row): row for row in decision_rows}
    joined: list[tuple[dict[str, str], dict[str, str]]] = [
        (operation, decisions.get(op_key(operation), {})) for operation in operation_rows
    ]
    pure_signatures = pure_promotion_signatures(signature_rows)

    queue_rows: list[dict[str, str]] = []
    fixture_totals: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "selected_ops": 0,
            "selected_bytes": 0,
            "promoted_ops": 0,
            "promoted_bytes": 0,
            "promoted_literal_bytes": 0,
            "promoted_zero_bytes": 0,
            "rejected_ops": 0,
            "rejected_false_bytes": 0,
            "review_ops": 0,
            "review_bytes": 0,
            "trusted_unpromoted_bytes": 0,
            "false_remaining_bytes": 0,
        }
    )
    fixture_meta: dict[tuple[str, str, str], dict[str, str]] = {}

    for operation, decision in joined:
        key = fixture_key(operation)
        fixture_meta[key] = operation
        totals = fixture_totals[key]
        if not decision.get("decision"):
            continue

        signatures = selector_signatures(operation)
        matched_promotions = [
            (selector, signatures.get(selector, ""))
            for selector in sorted(PROMOTION_SELECTORS)
            if signatures.get(selector, "") and (selector, signatures.get(selector, "")) in pure_signatures
        ]
        selected_bytes = int_value(decision, "selected_bytes")
        trusted_bytes = int_value(decision, "trusted_bytes")
        false_bytes = int_value(decision, "false_bytes")
        verdict = ""
        promotion_selector = ""
        promotion_signature = ""
        reject_reason = ""

        if matched_promotions:
            promotion_selector, promotion_signature = matched_promotions[0]
            verdict = "promoted"
        elif false_bytes:
            verdict = "reject_false_risk"
            reject_reason = "selected_without_false_free_control_signature"
        else:
            verdict = "review"
            reject_reason = "trusted_selected_without_promotion"

        totals["selected_ops"] += 1
        totals["selected_bytes"] += selected_bytes
        if verdict == "promoted":
            totals["promoted_ops"] += 1
            totals["promoted_bytes"] += selected_bytes
            if promotion_selector == "pre4_next2":
                totals["promoted_literal_bytes"] += selected_bytes
            elif promotion_selector == "zero_len64_and_u8":
                totals["promoted_zero_bytes"] += selected_bytes
        elif verdict == "reject_false_risk":
            totals["rejected_ops"] += 1
            totals["rejected_false_bytes"] += false_bytes
        else:
            totals["review_ops"] += 1
            totals["review_bytes"] += selected_bytes
            totals["trusted_unpromoted_bytes"] += trusted_bytes
            totals["false_remaining_bytes"] += false_bytes

        queue_rows.append(
            {
                "rank": operation.get("rank", ""),
                "archive": operation.get("archive", ""),
                "archive_tag": operation.get("archive_tag", ""),
                "pcx_name": operation.get("pcx_name", ""),
                "frontier_id": operation.get("frontier_id", ""),
                "op_index": operation.get("op_index", ""),
                "op_kind": operation.get("op_kind", ""),
                "expected_start": operation.get("expected_start", ""),
                "expected_end": operation.get("expected_end", ""),
                "length": str(length(operation)),
                "decision": decision.get("decision", ""),
                "risk_class": decision.get("risk_class", ""),
                "selected_bytes": str(selected_bytes),
                "trusted_bytes": str(trusted_bytes),
                "false_bytes": str(false_bytes),
                "verdict": verdict,
                "promotion_selector": promotion_selector,
                "promotion_signature": promotion_signature,
                "reject_reason": reject_reason,
                "pre4_hex": operation.get("pre4_hex", ""),
                "next2_hex": operation.get("next2_hex", ""),
                "length_u8_hit_offsets": operation.get("length_u8_hit_offsets", ""),
                "token_value": decision.get("token_value", ""),
                "token_plus3_match": decision.get("token_plus3_match", ""),
                "source_offset": operation.get("source_offset", ""),
                "source_end": operation.get("source_end", ""),
                "issues": ";".join(
                    issue
                    for issue in (operation.get("issues", ""), decision.get("issues", ""))
                    if issue
                ),
            }
        )

    rejector_rows = selected_signature_groups(joined)
    fixture_rows: list[dict[str, str]] = []
    for key in sorted(fixture_totals, key=lambda item: int(item[0]) if item[0].isdigit() else 999999):
        meta = fixture_meta[key]
        totals = fixture_totals[key]
        fixture_rows.append(
            {
                "rank": key[0],
                "archive": meta.get("archive", ""),
                "archive_tag": meta.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                **{field: str(totals[field]) for field in FIXTURE_FIELDNAMES[5:]},
            }
        )

    selected_ops = len(queue_rows)
    selected_bytes = sum(int_value(row, "selected_bytes") for row in queue_rows)
    promoted_ops = sum(1 for row in queue_rows if row.get("verdict") == "promoted")
    promoted_bytes = sum(
        int_value(row, "selected_bytes") for row in queue_rows if row.get("verdict") == "promoted"
    )
    rejected_ops = sum(1 for row in queue_rows if row.get("verdict") == "reject_false_risk")
    review_ops = sum(1 for row in queue_rows if row.get("verdict") == "review")
    summary = {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "decision_rows": str(len(decision_rows)),
        "fixture_rows": str(len({fixture_key(row) for row in operation_rows})),
        "selected_ops": str(selected_ops),
        "selected_bytes": str(selected_bytes),
        "promoted_ops": str(promoted_ops),
        "promoted_bytes": str(promoted_bytes),
        "promoted_literal_bytes": str(
            sum(
                int_value(row, "selected_bytes")
                for row in queue_rows
                if row.get("promotion_selector") == "pre4_next2"
            )
        ),
        "promoted_zero_bytes": str(
            sum(
                int_value(row, "selected_bytes")
                for row in queue_rows
                if row.get("promotion_selector") == "zero_len64_and_u8"
            )
        ),
        "rejected_ops": str(rejected_ops),
        "rejected_false_bytes": str(
            sum(
                int_value(row, "false_bytes")
                for row in queue_rows
                if row.get("verdict") == "reject_false_risk"
            )
        ),
        "review_ops": str(review_ops),
        "review_bytes": str(
            sum(int_value(row, "selected_bytes") for row in queue_rows if row.get("verdict") == "review")
        ),
        "trusted_unpromoted_bytes": str(
            sum(
                int_value(row, "trusted_bytes")
                for row in queue_rows
                if row.get("verdict") != "promoted"
            )
        ),
        "false_remaining_bytes": str(
            sum(
                int_value(row, "false_bytes")
                for row in queue_rows
                if row.get("verdict") != "reject_false_risk"
            )
        ),
        "safe_rejector_groups": str(
            sum(1 for row in rejector_rows if row.get("verdict") == "safe_reject")
        ),
        "mixed_rejector_groups": str(
            sum(1 for row in rejector_rows if row.get("verdict") == "mixed_review")
        ),
        "issue_rows": str(
            sum(1 for row in operation_rows if row.get("issues"))
            + sum(1 for row in decision_rows if row.get("issues"))
        ),
    }

    queue_rows.sort(
        key=lambda row: (
            row.get("verdict") != "reject_false_risk",
            row.get("verdict") != "review",
            int_value(row, "rank"),
            int_value(row, "op_index"),
        )
    )
    return summary, queue_rows, rejector_rows, fixture_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    queue_rows: list[dict[str, str]],
    rejector_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "queue": queue_rows,
        "rejectors": rejector_rows,
        "fixtures": fixture_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("queue.csv", output_dir / "queue.csv"),
            ("rejectors.csv", output_dir / "rejectors.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
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
  --risk: #f0a064;
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
.risk {{ color: var(--risk); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1280px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Partitions selected seed decisions into promoted bytes, deterministic false-risk rejects, and review rows.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Promoted</div><div class="value ok">{html.escape(summary['promoted_bytes'])}</div></div>
    <div class="stat"><div class="label">Rejected false-risk</div><div class="value risk">{html.escape(summary['rejected_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Review bytes</div><div class="value">{html.escape(summary['review_bytes'])}</div></div>
    <div class="stat"><div class="label">Trusted unpromoted</div><div class="value">{html.escape(summary['trusted_unpromoted_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Queue</h2>{render_table(queue_rows, QUEUE_FIELDNAMES)}</section>
  <section class="panel"><h2>Rejectors</h2>{render_table(rejector_rows, REJECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_FALSE_RISK_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    decisions_path: Path,
    signatures_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, queue_rows, rejector_rows, fixture_rows = build_rows(
        read_csv(operations_path),
        read_csv(decisions_path),
        read_csv(signatures_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "queue.csv", QUEUE_FIELDNAMES, queue_rows)
    write_csv(output_dir / "rejectors.csv", REJECTOR_FIELDNAMES, rejector_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, queue_rows, rejector_rows, fixture_rows, output_dir, title)
    )
    return summary, queue_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue .tex decoder seed false-risk decisions.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--signatures", type=Path, default=DEFAULT_SIGNATURES)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder False-Risk Queue")
    args = parser.parse_args()

    summary, _queue_rows = write_report(
        args.output,
        args.operations,
        args.decisions,
        args.signatures,
        title=args.title,
    )
    print(f"Promoted bytes: {summary['promoted_bytes']}")
    print(f"Rejected false-risk bytes: {summary['rejected_false_bytes']}")
    print(f"Review bytes: {summary['review_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
