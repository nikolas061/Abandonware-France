#!/usr/bin/env python3
"""Find .tex decoder seed decisions that can be promoted from control-byte signatures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_control_promotion_probe")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")
DEFAULT_DECISIONS = Path("output/tex_gap_decoder_seed_replay/decisions.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "decision_rows",
    "fixture_rows",
    "seed_selected_bytes",
    "seed_trusted_bytes",
    "seed_false_bytes",
    "best_selector",
    "best_selector_pure_bytes",
    "best_selector_pure_groups",
    "literal_pre4_next2_pure_bytes",
    "zero_len64_and_u8_pure_bytes",
    "combined_promoted_bytes",
    "ambiguous_signature_groups",
    "issue_rows",
]

SELECTOR_FIELDNAMES = [
    "selector",
    "signature_groups",
    "selected_groups",
    "pure_groups",
    "trusted_partial_groups",
    "ambiguous_groups",
    "pure_bytes",
    "trusted_no_false_bytes",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "total_bytes",
]

SIGNATURE_FIELDNAMES = [
    "selector",
    "signature",
    "promotion_class",
    "operation_rows",
    "fixture_rows",
    "total_bytes",
    "selected_ops",
    "trusted_ops",
    "false_ops",
    "unselected_ops",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "unselected_bytes",
    "decision_counts",
    "risk_counts",
    "op_kind_counts",
    "sample_rank",
    "sample_pcx",
    "sample_frontier_id",
    "sample_op_index",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "seed_selected_bytes",
    "seed_trusted_bytes",
    "seed_false_bytes",
    "pre4_next2_pure_bytes",
    "zero_len64_and_u8_pure_bytes",
    "combined_promoted_bytes",
    "remaining_seed_trusted_bytes",
    "remaining_seed_false_bytes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def op_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (*fixture_key(row), row.get("op_index", ""))


def length(row: dict[str, str]) -> int:
    return int_value(row, "length")


def count_text(values: list[str]) -> str:
    counts = Counter(value or "blank" for value in values)
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


def selector_signatures(row: dict[str, str]) -> dict[str, str]:
    pre2 = row.get("pre2_hex", "")
    pre4 = row.get("pre4_hex", "")
    next2 = row.get("next2_hex", "")
    control_head = row.get("control_window_hex", "")[:16]
    length_u8 = row.get("length_u8_hit_offsets", "")
    row_length = length(row)
    signatures = {
        "pre2": pre2,
        "pre4": pre4,
        "next2": next2,
        "pre4_next2": f"{pre4}|{next2}" if pre4 or next2 else "",
        "control_head8": control_head,
        "length_u8_offsets": length_u8,
    }
    if row_length == 64 and length_u8:
        signatures["zero_len64_and_u8"] = f"len=64|u8={length_u8}"
    else:
        signatures["zero_len64_and_u8"] = ""
    if pre4 or next2:
        signatures["pre4_next2_len"] = f"{pre4}|{next2}|len={row_length}"
    else:
        signatures["pre4_next2_len"] = ""
    return signatures


def promotion_class(total_bytes: int, selected_bytes: int, trusted_bytes: int, false_bytes: int) -> str:
    if not selected_bytes:
        return "unselected"
    if false_bytes:
        return "ambiguous"
    if trusted_bytes == total_bytes:
        return "pure"
    return "trusted_partial"


def build_rows(
    operation_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    decisions = {op_key(row): row for row in decision_rows}
    joined: list[tuple[dict[str, str], dict[str, str]]] = []
    for operation in operation_rows:
        joined.append((operation, decisions.get(op_key(operation), {})))

    signature_groups: dict[tuple[str, str], list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for operation, decision in joined:
        for selector, signature in selector_signatures(operation).items():
            if signature:
                signature_groups[(selector, signature)].append((operation, decision))

    signature_rows: list[dict[str, str]] = []
    for (selector, signature), rows in sorted(signature_groups.items()):
        operations = [row[0] for row in rows]
        decisions_for_group = [row[1] for row in rows]
        total_bytes = sum(length(row) for row in operations)
        selected_bytes = sum(int_value(row, "selected_bytes") for row in decisions_for_group)
        trusted_bytes = sum(int_value(row, "trusted_bytes") for row in decisions_for_group)
        false_bytes = sum(int_value(row, "false_bytes") for row in decisions_for_group)
        selected_ops = sum(1 for row in decisions_for_group if row.get("decision"))
        trusted_ops = sum(1 for row in decisions_for_group if row.get("risk_class", "").startswith("true_"))
        false_ops = sum(1 for row in decisions_for_group if row.get("risk_class", "").startswith("false_"))
        unselected_ops = len(rows) - selected_ops
        sample = operations[0]
        signature_rows.append(
            {
                "selector": selector,
                "signature": signature,
                "promotion_class": promotion_class(
                    total_bytes, selected_bytes, trusted_bytes, false_bytes
                ),
                "operation_rows": str(len(rows)),
                "fixture_rows": str(len({fixture_key(row) for row in operations})),
                "total_bytes": str(total_bytes),
                "selected_ops": str(selected_ops),
                "trusted_ops": str(trusted_ops),
                "false_ops": str(false_ops),
                "unselected_ops": str(unselected_ops),
                "selected_bytes": str(selected_bytes),
                "trusted_bytes": str(trusted_bytes),
                "false_bytes": str(false_bytes),
                "unselected_bytes": str(max(0, total_bytes - selected_bytes)),
                "decision_counts": count_text([row.get("decision", "") for row in decisions_for_group]),
                "risk_counts": count_text([row.get("risk_class", "") for row in decisions_for_group]),
                "op_kind_counts": count_text([row.get("op_kind", "") for row in operations]),
                "sample_rank": sample.get("rank", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_op_index": sample.get("op_index", ""),
            }
        )

    selector_rows: list[dict[str, str]] = []
    by_selector: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in signature_rows:
        by_selector[row.get("selector", "")].append(row)
    for selector, rows in sorted(by_selector.items()):
        selector_rows.append(
            {
                "selector": selector,
                "signature_groups": str(len(rows)),
                "selected_groups": str(sum(1 for row in rows if int_value(row, "selected_bytes"))),
                "pure_groups": str(sum(1 for row in rows if row.get("promotion_class") == "pure")),
                "trusted_partial_groups": str(
                    sum(1 for row in rows if row.get("promotion_class") == "trusted_partial")
                ),
                "ambiguous_groups": str(
                    sum(1 for row in rows if row.get("promotion_class") == "ambiguous")
                ),
                "pure_bytes": str(
                    sum(int_value(row, "trusted_bytes") for row in rows if row.get("promotion_class") == "pure")
                ),
                "trusted_no_false_bytes": str(
                    sum(
                        int_value(row, "trusted_bytes")
                        for row in rows
                        if row.get("promotion_class") in {"pure", "trusted_partial"}
                    )
                ),
                "selected_bytes": str(sum(int_value(row, "selected_bytes") for row in rows)),
                "trusted_bytes": str(sum(int_value(row, "trusted_bytes") for row in rows)),
                "false_bytes": str(sum(int_value(row, "false_bytes") for row in rows)),
                "total_bytes": str(sum(int_value(row, "total_bytes") for row in rows)),
            }
        )

    selector_by_name = {row.get("selector", ""): row for row in selector_rows}
    selector_preference = {
        "pre4_next2": 0,
        "zero_len64_and_u8": 1,
        "pre4": 2,
        "next2": 3,
        "pre2": 4,
        "pre4_next2_len": 5,
        "length_u8_offsets": 6,
        "control_head8": 7,
    }
    best_selector = max(
        selector_rows,
        key=lambda row: (
            int_value(row, "pure_bytes"),
            int_value(row, "pure_groups"),
            -selector_preference.get(row.get("selector", ""), 99),
        ),
    )

    pure_signature_keys = {
        (row.get("selector", ""), row.get("signature", ""))
        for row in signature_rows
        if row.get("promotion_class") == "pure"
        and row.get("selector") in {"pre4_next2", "zero_len64_and_u8"}
    }

    fixture_totals: dict[tuple[str, str, str], dict[str, int | str]] = defaultdict(
        lambda: {
            "fixture_bytes": 0,
            "seed_selected_bytes": 0,
            "seed_trusted_bytes": 0,
            "seed_false_bytes": 0,
            "pre4_next2_pure_bytes": 0,
            "zero_len64_and_u8_pure_bytes": 0,
        }
    )
    fixture_meta: dict[tuple[str, str, str], dict[str, str]] = {}
    for operation, decision in joined:
        key = fixture_key(operation)
        fixture_meta[key] = operation
        values = fixture_totals[key]
        values["fixture_bytes"] = int(values["fixture_bytes"]) + length(operation)
        values["seed_selected_bytes"] = int(values["seed_selected_bytes"]) + int_value(decision, "selected_bytes")
        values["seed_trusted_bytes"] = int(values["seed_trusted_bytes"]) + int_value(decision, "trusted_bytes")
        values["seed_false_bytes"] = int(values["seed_false_bytes"]) + int_value(decision, "false_bytes")
        signatures = selector_signatures(operation)
        for selector in ("pre4_next2", "zero_len64_and_u8"):
            if (selector, signatures.get(selector, "")) in pure_signature_keys:
                field = f"{selector}_pure_bytes"
                values[field] = int(values[field]) + int_value(decision, "trusted_bytes")

    fixture_rows: list[dict[str, str]] = []
    for key in sorted(fixture_totals, key=lambda item: int(item[0]) if item[0].isdigit() else 999999):
        values = fixture_totals[key]
        meta = fixture_meta[key]
        combined = (
            int(values["pre4_next2_pure_bytes"])
            + int(values["zero_len64_and_u8_pure_bytes"])
        )
        fixture_rows.append(
            {
                "rank": key[0],
                "archive": meta.get("archive", ""),
                "archive_tag": meta.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(values["fixture_bytes"]),
                "seed_selected_bytes": str(values["seed_selected_bytes"]),
                "seed_trusted_bytes": str(values["seed_trusted_bytes"]),
                "seed_false_bytes": str(values["seed_false_bytes"]),
                "pre4_next2_pure_bytes": str(values["pre4_next2_pure_bytes"]),
                "zero_len64_and_u8_pure_bytes": str(values["zero_len64_and_u8_pure_bytes"]),
                "combined_promoted_bytes": str(combined),
                "remaining_seed_trusted_bytes": str(
                    max(0, int(values["seed_trusted_bytes"]) - combined)
                ),
                "remaining_seed_false_bytes": str(values["seed_false_bytes"]),
            }
        )

    seed_selected_bytes = sum(int_value(row, "selected_bytes") for row in decision_rows)
    seed_trusted_bytes = sum(int_value(row, "trusted_bytes") for row in decision_rows)
    seed_false_bytes = sum(int_value(row, "false_bytes") for row in decision_rows)
    literal_pure = int_value(selector_by_name.get("pre4_next2", {}), "pure_bytes")
    zero_pure = int_value(selector_by_name.get("zero_len64_and_u8", {}), "pure_bytes")
    summary = {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "decision_rows": str(len(decision_rows)),
        "fixture_rows": str(len({fixture_key(row) for row in operation_rows})),
        "seed_selected_bytes": str(seed_selected_bytes),
        "seed_trusted_bytes": str(seed_trusted_bytes),
        "seed_false_bytes": str(seed_false_bytes),
        "best_selector": best_selector.get("selector", ""),
        "best_selector_pure_bytes": best_selector.get("pure_bytes", "0"),
        "best_selector_pure_groups": best_selector.get("pure_groups", "0"),
        "literal_pre4_next2_pure_bytes": str(literal_pure),
        "zero_len64_and_u8_pure_bytes": str(zero_pure),
        "combined_promoted_bytes": str(literal_pure + zero_pure),
        "ambiguous_signature_groups": str(
            sum(1 for row in signature_rows if row.get("promotion_class") == "ambiguous")
        ),
        "issue_rows": str(
            sum(1 for row in operation_rows if row.get("issues"))
            + sum(1 for row in decision_rows if row.get("issues"))
        ),
    }

    signature_rows.sort(
        key=lambda row: (
            row.get("promotion_class") != "pure",
            row.get("promotion_class") != "trusted_partial",
            row.get("selector", ""),
            -int_value(row, "trusted_bytes"),
            int_value(row, "false_bytes"),
            row.get("signature", ""),
        )
    )
    selector_rows.sort(
        key=lambda row: (-int_value(row, "pure_bytes"), int_value(row, "false_bytes"), row.get("selector", ""))
    )
    return summary, selector_rows, signature_rows, fixture_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    selector_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "selectors": selector_rows,
        "signatures": signature_rows,
        "fixtures": fixture_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("selectors.csv", output_dir / "selectors.csv"),
            ("signatures.csv", output_dir / "signatures.csv"),
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
    <div class="sub">Promotes seed decoder decisions only when observed control signatures stay false-free.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Combined promoted</div><div class="value ok">{html.escape(summary['combined_promoted_bytes'])}</div></div>
    <div class="stat"><div class="label">Literal pure</div><div class="value">{html.escape(summary['literal_pre4_next2_pure_bytes'])}</div></div>
    <div class="stat"><div class="label">Zero pure</div><div class="value">{html.escape(summary['zero_len64_and_u8_pure_bytes'])}</div></div>
    <div class="stat"><div class="label">Ambiguous groups</div><div class="value">{html.escape(summary['ambiguous_signature_groups'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Selectors</h2>{render_table(selector_rows, SELECTOR_FIELDNAMES)}</section>
  <section class="panel"><h2>Signatures</h2>{render_table(signature_rows, SIGNATURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_CONTROL_PROMOTION_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    decisions_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, selector_rows, signature_rows, fixture_rows = build_rows(
        read_csv(operations_path),
        read_csv(decisions_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "selectors.csv", SELECTOR_FIELDNAMES, selector_rows)
    write_csv(output_dir / "signatures.csv", SIGNATURE_FIELDNAMES, signature_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, selector_rows, signature_rows, fixture_rows, output_dir, title)
    )
    return summary, selector_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Find promotable .tex decoder control signatures.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Control Promotion Probe")
    args = parser.parse_args()

    summary, _selectors = write_report(
        args.output,
        args.operations,
        args.decisions,
        title=args.title,
    )
    print(f"Best selector: {summary['best_selector']}")
    print(f"Combined promoted bytes: {summary['combined_promoted_bytes']}")
    print(f"Literal pre4/next2 pure bytes: {summary['literal_pre4_next2_pure_bytes']}")
    print(f"Zero len64+u8 pure bytes: {summary['zero_len64_and_u8_pure_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
