#!/usr/bin/env python3
"""Run iterative non-high-safe source dependency reviews after the old-clean union."""

from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
import sys
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_BASE_FIXTURES = Path("output/tex_old_clean_byte_union_outside_source_dependency_promoted_replay/fixtures.csv")
DEFAULT_BASE_SLOTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_outside_source_dependency_promoted_replay/slots.csv"
)
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_outside_source_dependency_cascade")

PASS_FIELDNAMES = [
    "pass_index",
    "pass_label",
    "review_dir",
    "review_verdict",
    "unknown_source_rows",
    "unknown_source_groups",
    "supported_guard_rows",
    "target_only_guard_rows",
    "promotion_ready_bytes",
    "promoted_dir",
    "source_added_bytes",
    "source_false_bytes",
    "total_clean_bytes",
    "remaining_unresolved_bytes",
    "dependency_dir",
    "source_available_slots",
    "source_unknown_outside_highsafe_slots",
    "source_unknown_in_highsafe_slots",
    "residual_dir",
    "dominant_blocker",
    "next_probe",
    "issues",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "review_passes",
    "promoted_passes",
    "stop_pass_label",
    "stop_review_verdict",
    "base_clean_bytes",
    "final_clean_bytes",
    "source_added_bytes",
    "source_false_bytes",
    "remaining_unresolved_bytes",
    "base_unknown_outside_slots",
    "final_unknown_outside_slots",
    "final_unknown_highsafe_slots",
    "final_source_available_slots",
    "final_unknown_source_groups",
    "final_target_only_guard_rows",
    "final_top_unknown_group_key",
    "promotion_ready_bytes",
    "issue_rows",
    "next_probe",
]


ORDINALS = {
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
    11: "eleventh",
    12: "twelfth",
    13: "thirteenth",
    14: "fourteenth",
    15: "fifteenth",
    16: "sixteenth",
    17: "seventeenth",
    18: "eighteenth",
    19: "nineteenth",
    20: "twentieth",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def run_step(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def pass_label(index: int) -> str:
    return ORDINALS.get(index, f"pass{index}")


def review_output(label: str) -> Path:
    return Path(f"output/tex_old_clean_byte_union_{label}_outside_source_dependency_review")


def promoted_output(label: str) -> Path:
    return Path(f"output/tex_old_clean_byte_union_{label}_outside_source_dependency_promoted_replay")


def dependency_output(label: str) -> Path:
    return Path(
        "output/"
        f"tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_{label}_outside_source_dependency_promoted_replay"
    )


def residual_output(label: str) -> Path:
    return Path(f"{dependency_output(label).as_posix()}_residual_core")


def fixture_clean_bytes(path: Path) -> int:
    return sum(int_value(row, "total_clean_bytes") for row in read_csv(path))


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, str], passes: list[dict[str, str]], output_dir: Path) -> str:
    payload = {"summary": summary, "passes": passes}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (("summary.csv", output_dir / "summary.csv"), ("passes.csv", output_dir / "passes.csv"))
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Lands of Lore II .tex Outside Source Dependency Cascade</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #202529; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: white; border: 1px solid #d5dbe0; padding: 10px; }}
    .label {{ color: #68737d; font-size: 12px; }}
    .value {{ font-size: 21px; font-weight: 750; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #d5dbe0; padding: 6px 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    th {{ background: #e9edf0; }}
  </style>
</head>
<body>
  <h1>Lands of Lore II .tex Outside Source Dependency Cascade</h1>
  <p>{links}</p>
  <div class="stats">
    <div class="stat"><div class="label">Promoted passes</div><div class="value">{html.escape(summary['promoted_passes'])}</div></div>
    <div class="stat"><div class="label">Added bytes</div><div class="value">{html.escape(summary['source_added_bytes'])}</div></div>
    <div class="stat"><div class="label">Final outside unknown</div><div class="value">{html.escape(summary['final_unknown_outside_slots'])}</div></div>
    <div class="stat"><div class="label">Stop verdict</div><div class="value">{html.escape(summary['stop_review_verdict'])}</div></div>
    <div class="stat"><div class="label">False bytes</div><div class="value">{html.escape(summary['source_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value">{html.escape(summary['issue_rows'])}</div></div>
  </div>
  <h2>Passes</h2>
  {render_table(passes, PASS_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def build_summary(
    *,
    base_clean: int,
    base_unknown_outside: int,
    pass_rows: list[dict[str, str]],
    final_dependency: dict[str, str],
    stop_review: dict[str, str],
) -> dict[str, str]:
    promoted_rows = [row for row in pass_rows if int_value(row, "source_added_bytes") > 0]
    final_promoted = promoted_rows[-1] if promoted_rows else {}
    final_clean = int_value(final_promoted, "total_clean_bytes", base_clean)
    source_added = max(0, final_clean - base_clean)
    top_key = stop_review.get("top_unknown_group_key", "")
    next_probe = stop_review.get("next_probe", "")
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_outside_source_dependency_cascade",
        "review_passes": str(len(pass_rows)),
        "promoted_passes": str(len(promoted_rows)),
        "stop_pass_label": pass_rows[-1].get("pass_label", "") if pass_rows else "",
        "stop_review_verdict": stop_review.get("review_verdict", ""),
        "base_clean_bytes": str(base_clean),
        "final_clean_bytes": str(final_clean),
        "source_added_bytes": str(source_added),
        "source_false_bytes": str(sum(int_value(row, "source_false_bytes") for row in pass_rows)),
        "remaining_unresolved_bytes": final_promoted.get("remaining_unresolved_bytes", ""),
        "base_unknown_outside_slots": str(base_unknown_outside),
        "final_unknown_outside_slots": final_dependency.get("source_unknown_outside_highsafe_slots", ""),
        "final_unknown_highsafe_slots": final_dependency.get("source_unknown_in_highsafe_slots", ""),
        "final_source_available_slots": final_dependency.get("source_available_slots", ""),
        "final_unknown_source_groups": stop_review.get("unknown_source_groups", ""),
        "final_target_only_guard_rows": stop_review.get("target_only_guard_rows", ""),
        "final_top_unknown_group_key": top_key,
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(int_value(row, "issues") for row in pass_rows)),
        "next_probe": next_probe,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--base-slots", type=Path, default=DEFAULT_BASE_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-index", type=int, default=2)
    parser.add_argument("--max-passes", type=int, default=20)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    current_fixtures = args.base_fixtures
    current_slots = args.base_slots
    base_clean = fixture_clean_bytes(current_fixtures)
    base_unknown_outside = 0
    pass_rows: list[dict[str, str]] = []
    final_dependency: dict[str, str] = {}
    stop_review: dict[str, str] = {}

    for pass_index in range(args.start_index, args.start_index + args.max_passes):
        label = pass_label(pass_index)
        review_dir = review_output(label)
        run_step(
            [
                sys.executable,
                "tools/lolg_tex_old_clean_byte_union_outside_source_dependency_review.py",
                "--slots",
                current_slots.as_posix(),
                "-o",
                review_dir.as_posix(),
                "--title",
                f"Lands of Lore II .tex Old Clean Union {label.title()} Outside Source Dependency Review",
            ]
        )
        review = read_summary(review_dir / "summary.csv")
        if not pass_rows:
            base_unknown_outside = int_value(review, "unknown_source_rows")

        pass_row = {
            "pass_index": str(pass_index),
            "pass_label": label,
            "review_dir": review_dir.as_posix(),
            "review_verdict": review.get("review_verdict", ""),
            "unknown_source_rows": review.get("unknown_source_rows", ""),
            "unknown_source_groups": review.get("unknown_source_groups", ""),
            "supported_guard_rows": review.get("supported_guard_rows", ""),
            "target_only_guard_rows": review.get("target_only_guard_rows", ""),
            "promotion_ready_bytes": review.get("promotion_ready_bytes", ""),
            "promoted_dir": "",
            "source_added_bytes": "0",
            "source_false_bytes": "0",
            "total_clean_bytes": "",
            "remaining_unresolved_bytes": "",
            "dependency_dir": "",
            "source_available_slots": "",
            "source_unknown_outside_highsafe_slots": "",
            "source_unknown_in_highsafe_slots": "",
            "residual_dir": "",
            "dominant_blocker": "",
            "next_probe": review.get("next_probe", ""),
            "issues": review.get("issue_rows", "0"),
        }

        if int_value(review, "promotion_ready_bytes") <= 0:
            stop_review = review
            pass_rows.append(pass_row)
            break

        promoted_dir = promoted_output(label)
        run_step(
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                current_fixtures.as_posix(),
                "--targets",
                (review_dir / "targets.csv").as_posix(),
                "-o",
                promoted_dir.as_posix(),
                "--title",
                f"Lands of Lore II .tex Old Clean Union {label.title()} Outside Source Dependency Promoted Replay",
            ]
        )
        promoted = read_summary(promoted_dir / "summary.csv")

        dependency_dir = dependency_output(label)
        run_step(
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                (promoted_dir / "fixtures.csv").as_posix(),
                "-o",
                dependency_dir.as_posix(),
                "--title",
                f"Lands of Lore II .tex Source-Dependency After Old Clean Union {label.title()} Outside Source Dependency Promoted",
            ]
        )
        dependency = read_summary(dependency_dir / "summary.csv")

        residual_dir = residual_output(label)
        run_step(
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                (dependency_dir / "slots.csv").as_posix(),
                "--edges",
                (dependency_dir / "edges.csv").as_posix(),
                "-o",
                residual_dir.as_posix(),
            ]
        )
        residual = read_summary(residual_dir / "summary.csv")

        pass_row.update(
            {
                "promoted_dir": promoted_dir.as_posix(),
                "source_added_bytes": promoted.get("source_added_bytes", "0"),
                "source_false_bytes": promoted.get("source_false_bytes", "0"),
                "total_clean_bytes": promoted.get("total_clean_bytes", ""),
                "remaining_unresolved_bytes": promoted.get("remaining_unresolved_bytes", ""),
                "dependency_dir": dependency_dir.as_posix(),
                "source_available_slots": dependency.get("source_available_slots", ""),
                "source_unknown_outside_highsafe_slots": dependency.get("source_unknown_outside_highsafe_slots", ""),
                "source_unknown_in_highsafe_slots": dependency.get("source_unknown_in_highsafe_slots", ""),
                "residual_dir": residual_dir.as_posix(),
                "dominant_blocker": residual.get("dominant_blocker", ""),
                "issues": str(
                    int_value(review, "issue_rows")
                    + int_value(promoted, "issue_rows")
                    + int_value(dependency, "issue_rows")
                    + int_value(residual, "issue_rows")
                ),
            }
        )
        pass_rows.append(pass_row)

        final_dependency = dependency
        current_fixtures = promoted_dir / "fixtures.csv"
        current_slots = dependency_dir / "slots.csv"
        if int_value(promoted, "source_added_bytes") <= 0:
            stop_review = review
            break

    summary = build_summary(
        base_clean=base_clean,
        base_unknown_outside=base_unknown_outside,
        pass_rows=pass_rows,
        final_dependency=final_dependency,
        stop_review=stop_review,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "passes.csv", PASS_FIELDNAMES, pass_rows)
    (args.output / "index.html").write_text(build_html(summary, pass_rows, args.output), encoding="utf-8")

    print(
        "Outside source dependency cascade: "
        f"promoted_passes={summary['promoted_passes']} "
        f"added={summary['source_added_bytes']} "
        f"outside_unknown={summary['base_unknown_outside_slots']}->{summary['final_unknown_outside_slots']} "
        f"stop={summary['stop_review_verdict']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
