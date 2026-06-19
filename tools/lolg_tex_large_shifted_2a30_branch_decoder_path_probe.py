#!/usr/bin/env python3
"""Join shifted 0x2a30 branch evidence to existing preview choices and review risk."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_decoder_path_probe")
DEFAULT_BRANCHES = Path("output/tex_large_shifted_2a30_branch_probe/branches.csv")
DEFAULT_PROLOGUE_FAMILIES = Path("reports/te_prologue_families.tsv")
DEFAULT_CHOICES = Path("reports/te_guarded_cmd20_v10_riskaware_markerknownsymadv_plus_puddle.tsv")
DEFAULT_REVIEW_QUEUE = Path("reports/lvl_pcx_te_review_queue_decisions_smoke.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "branch_rows",
    "prologue_rows",
    "choice_rows",
    "review_rows",
    "preview_rows",
    "visual_blocked_rows",
    "alignment_rows",
    "candidate_alignment_rows",
    "best_alignment_shift",
    "best_alignment_field16_hex",
    "best_alignment_field16_low_dec",
    "oracle_extra",
    "choice_mode",
    "choice_score",
    "issue_rows",
    "next_action",
]

PATH_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "branch_key",
    "prologue_family",
    "family_branch_value_dec",
    "oracle_extra",
    "choice_mode",
    "choice_extra",
    "choice_score",
    "choice_width",
    "choice_height",
    "choice_preview_path",
    "choice_preview_exists",
    "choice_preview_width",
    "choice_preview_height",
    "review_status",
    "review_hint",
    "visual_status",
    "next_probe",
    "issues",
]

ALIGNMENT_FIELDNAMES = [
    "branch_id",
    "archive_tag",
    "pcx_name",
    "branch_key",
    "field_start_delta",
    "field16_hex",
    "field16_low_dec",
    "field16_high_dec",
    "field16_low_mod4",
    "next_word16_hex",
    "next_word_low_dec",
    "next_word_high_dec",
    "family_branch_value_dec",
    "oracle_extra",
    "matches_family_branch_value",
    "known_high_context",
    "alignment_score",
    "verdict",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_text(value: str) -> int:
    try:
        return int(value, 0) if value else 0
    except ValueError:
        return 0


def row_key(row: dict[str, str], archive_field: str = "archive_tag", name_field: str = "pcx_name") -> tuple[str, str]:
    return row.get(archive_field, "") or row.get("level", ""), row.get(name_field, "").lower() or row.get("name", "").lower()


def bytes_from_hex(text: str) -> bytes:
    try:
        return bytes.fromhex(text)
    except ValueError:
        return b""


def word_at(data: bytes, index: int) -> int | None:
    if 0 <= index <= len(data) - 2:
        return int.from_bytes(data[index : index + 2], "little")
    return None


def hex_word(value: int | None) -> str:
    return f"0x{value:04x}" if value is not None else ""


def parse_family(text: str) -> tuple[int, int]:
    match = re.search(r"_b3_(\d+)_rel_(\d+)", text or "")
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def prologue_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {row_key(row, "level", "name"): row for row in rows}


def choice_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {row_key(row, "level", "name"): row for row in rows if row.get("source") == "marker"}


def review_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row.get("archive", ""), row.get("name", "").lower()): row for row in rows}


def preview_size(path_text: str) -> tuple[str, str, bool]:
    if not path_text:
        return "", "", False
    path = Path(path_text)
    if not path.exists():
        return "", "", False
    with Image.open(path) as image:
        return str(image.width), str(image.height), True


def visual_status(review: dict[str, str], preview_exists: bool) -> str:
    if not preview_exists:
        return "missing_preview"
    if review.get("review_status") == "accepted":
        return "accepted"
    if "high_risk" in review.get("review_hint", ""):
        return "blocked_high_risk_review"
    if review.get("review_status"):
        return f"blocked_review_{review.get('review_status')}"
    return "blocked_missing_review"


def build_alignment_rows(branch_rows: list[dict[str, str]], prologues: dict[tuple[str, str], dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    known_high_values = {0, 1, 2, 4, 6, 64}
    for branch in branch_rows:
        key = row_key(branch)
        prologue = prologues.get(key, {})
        family_value, oracle_extra = parse_family(prologue.get("family", ""))
        data = bytes_from_hex(branch.get("head64_hex", ""))
        pair_offset = int_text(branch.get("pair_2a30_offset", ""))
        for delta in range(2, 7):
            field16 = word_at(data, pair_offset + delta)
            next_word = word_at(data, pair_offset + delta + 2)
            if field16 is None:
                continue
            low = field16 & 0xFF
            high = (field16 >> 8) & 0xFF
            next_low = (next_word or 0) & 0xFF
            next_high = ((next_word or 0) >> 8) & 0xFF
            matches_family = low == family_value
            known_high = high in known_high_values
            score = 0
            if low % 4 == 0:
                score += 1
            if matches_family:
                score += 3
            if known_high:
                score += 1
            if oracle_extra:
                score += 1
            if matches_family and oracle_extra:
                verdict = "branch_field_alignment_candidate"
            elif low % 4 == 0 and known_high:
                verdict = "plausible_field_alignment"
            else:
                verdict = "weak_alignment"
            output.append(
                {
                    "branch_id": branch.get("branch_id", ""),
                    "archive_tag": branch.get("archive_tag", ""),
                    "pcx_name": branch.get("pcx_name", ""),
                    "branch_key": branch.get("branch_key", ""),
                    "field_start_delta": str(delta),
                    "field16_hex": hex_word(field16),
                    "field16_low_dec": str(low),
                    "field16_high_dec": str(high),
                    "field16_low_mod4": str(low % 4),
                    "next_word16_hex": hex_word(next_word),
                    "next_word_low_dec": str(next_low),
                    "next_word_high_dec": str(next_high),
                    "family_branch_value_dec": str(family_value) if family_value else "",
                    "oracle_extra": str(oracle_extra) if oracle_extra else "",
                    "matches_family_branch_value": "yes" if matches_family else "no",
                    "known_high_context": "yes" if known_high else "no",
                    "alignment_score": str(score),
                    "verdict": verdict,
                }
            )
    return output


def build_path_rows(
    branch_rows: list[dict[str, str]],
    prologues: dict[tuple[str, str], dict[str, str]],
    choices: dict[tuple[str, str], dict[str, str]],
    reviews: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for branch in branch_rows:
        key = row_key(branch)
        prologue = prologues.get(key, {})
        choice = choices.get(key, {})
        review = reviews.get(key, {})
        family_value, oracle_extra = parse_family(prologue.get("family", ""))
        width, height, preview_exists = preview_size(choice.get("out", ""))
        issues: list[str] = []
        if not prologue:
            issues.append("missing_prologue_family")
        if not choice:
            issues.append("missing_choice_row")
        if choice and choice.get("extra") != str(oracle_extra):
            issues.append("choice_extra_mismatch")
        if not review:
            issues.append("missing_review_row")
        if choice and not preview_exists:
            issues.append("missing_choice_preview")
        status = visual_status(review, preview_exists)
        if status.startswith("blocked"):
            next_probe = "derive non-noisy renderer before branch preview promotion"
        elif status == "accepted":
            next_probe = "materialize accepted branch preview for Full HD review"
        else:
            next_probe = "fix branch decoder path inputs"
        rows.append(
            {
                "archive_tag": branch.get("archive_tag", ""),
                "pcx_name": branch.get("pcx_name", ""),
                "branch_key": branch.get("branch_key", ""),
                "prologue_family": prologue.get("family", ""),
                "family_branch_value_dec": str(family_value) if family_value else "",
                "oracle_extra": str(oracle_extra) if oracle_extra else "",
                "choice_mode": choice.get("mode", ""),
                "choice_extra": choice.get("extra", ""),
                "choice_score": choice.get("score", ""),
                "choice_width": choice.get("width", ""),
                "choice_height": choice.get("height", ""),
                "choice_preview_path": choice.get("out", ""),
                "choice_preview_exists": "yes" if preview_exists else "no",
                "choice_preview_width": width,
                "choice_preview_height": height,
                "review_status": review.get("review_status", ""),
                "review_hint": review.get("review_hint", ""),
                "visual_status": status,
                "next_probe": next_probe,
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def build_summary(path_rows: list[dict[str, str]], alignment_rows: list[dict[str, str]]) -> dict[str, str]:
    issue_rows = sum(1 for row in path_rows if row.get("issues"))
    visual_blocked = [row for row in path_rows if row.get("visual_status", "").startswith("blocked")]
    candidate_alignments = [row for row in alignment_rows if row.get("verdict") == "branch_field_alignment_candidate"]
    best_alignment = sorted(
        alignment_rows,
        key=lambda row: int_text(row.get("alignment_score", "")),
        reverse=True,
    )
    first_path = path_rows[0] if path_rows else {}
    first_alignment = best_alignment[0] if best_alignment else {}
    if issue_rows:
        next_action = "fix shifted 0x2a30 branch decoder path probe issues"
    elif visual_blocked:
        next_action = (
            "derive non-noisy renderer for shifted 0x2a30 branch "
            f"{first_path.get('branch_key', '')} beyond existing extra{first_path.get('oracle_extra', '')} preview"
        )
    elif path_rows:
        next_action = (
            f"materialize shifted 0x2a30 branch {first_path.get('branch_key', '')} "
            f"extra{first_path.get('oracle_extra', '')} preview for Full HD review"
        )
    else:
        next_action = "no shifted 0x2a30 branch decoder path rows"
    return {
        "scope": "total",
        "branch_rows": str(len(path_rows)),
        "prologue_rows": str(sum(1 for row in path_rows if row.get("prologue_family"))),
        "choice_rows": str(sum(1 for row in path_rows if row.get("choice_mode"))),
        "review_rows": str(sum(1 for row in path_rows if row.get("review_status"))),
        "preview_rows": str(sum(1 for row in path_rows if row.get("choice_preview_exists") == "yes")),
        "visual_blocked_rows": str(len(visual_blocked)),
        "alignment_rows": str(len(alignment_rows)),
        "candidate_alignment_rows": str(len(candidate_alignments)),
        "best_alignment_shift": first_alignment.get("field_start_delta", ""),
        "best_alignment_field16_hex": first_alignment.get("field16_hex", ""),
        "best_alignment_field16_low_dec": first_alignment.get("field16_low_dec", ""),
        "oracle_extra": first_path.get("oracle_extra", ""),
        "choice_mode": first_path.get("choice_mode", ""),
        "choice_score": first_path.get("choice_score", ""),
        "issue_rows": str(issue_rows),
        "next_action": next_action,
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    paths: list[dict[str, str]],
    alignments: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "paths": paths, "alignments": alignments}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("paths.csv", output_dir / "paths.csv"),
            ("alignments.csv", output_dir / "alignments.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">This joins branch bytes, prologue family, existing preview choice, and review risk.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Decoder Path</h2>
{render_table(paths, PATH_FIELDNAMES)}
<h2>Field Alignments</h2>
{render_table(alignments, ALIGNMENT_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_DECODER_PATH_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    branches_path: Path,
    prologue_path: Path,
    choices_path: Path,
    review_queue_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    branches = read_csv(branches_path)
    prologues = prologue_lookup(read_csv(prologue_path, delimiter="\t"))
    choices = choice_lookup(read_csv(choices_path, delimiter="\t"))
    reviews = review_lookup(read_csv(review_queue_path, delimiter="\t"))
    paths = build_path_rows(branches, prologues, choices, reviews)
    alignments = build_alignment_rows(branches, prologues)
    summary = build_summary(paths, alignments)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "paths.csv", PATH_FIELDNAMES, paths)
    write_csv(output_dir / "alignments.csv", ALIGNMENT_FIELDNAMES, alignments)
    (output_dir / "index.html").write_text(build_html(summary, paths, alignments, output_dir, title))
    return summary, paths, alignments


def main() -> None:
    parser = argparse.ArgumentParser(description="Join shifted 0x2a30 branch decoder path evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--branches", type=Path, default=DEFAULT_BRANCHES)
    parser.add_argument("--prologue-families", type=Path, default=DEFAULT_PROLOGUE_FAMILIES)
    parser.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Decoder Path")
    args = parser.parse_args()

    summary, paths, alignments = write_report(
        args.output,
        args.branches,
        args.prologue_families,
        args.choices,
        args.review_queue,
        args.title,
    )
    print(f"Branch rows: {summary['branch_rows']}")
    print(f"Choice rows: {summary['choice_rows']}")
    print(f"Candidate alignments: {summary['candidate_alignment_rows']}")
    print(f"Visual blocked rows: {summary['visual_blocked_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
