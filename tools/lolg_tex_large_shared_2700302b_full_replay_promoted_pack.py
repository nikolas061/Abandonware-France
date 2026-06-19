#!/usr/bin/env python3
"""Pack the completed shared 0x2700302b full replay as a promoted coverage asset."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DECODER_RULE = "shared_2700302b_reference_fixed_dy1_full_replay"
DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_full_replay_promoted_pack")
DEFAULT_FINAL_CLEAR_SUMMARY = Path(
    "output/tex_large_shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_probe/summary.csv"
)
DEFAULT_REFERENCES = Path("output/tex_reference_coverage/references.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "proof_rows",
    "ready_rows",
    "coverage_eligible_rows",
    "coverage_eligible_unique_pcx",
    "native_assets",
    "fullhd_assets",
    "selected_pixels",
    "covered_pixels",
    "target_pixels",
    "remaining_nonzero_pixels",
    "missing_native_paths",
    "missing_fullhd_paths",
    "issue_rows",
    "review_verdict",
    "next_action",
]

MANIFEST_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "texture_path",
    "pcx_name",
    "normalized_pcx_name",
    "decoder_rule",
    "decoder_extra",
    "frontier_id",
    "dy",
    "shift",
    "selected_pixels",
    "target_pixels",
    "combined_covered_pixels",
    "remaining_nonzero_pixels",
    "full_coverage",
    "coverage_eligible",
    "source_native_path",
    "source_native_exists",
    "source_fullhd_path",
    "source_fullhd_exists",
    "promoted_native_path",
    "promoted_native_exists",
    "promoted_fullhd_path",
    "promoted_fullhd_exists",
    "promoted_fullhd_width",
    "promoted_fullhd_height",
    "proof_summary_path",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw, 0) if raw else 0


def split_paths(value: str) -> list[str]:
    return [item for item in value.split(";") if item]


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def native_candidate(reference: dict[str, str]) -> Path:
    fullhd_sources = split_paths(reference.get("descriptor_fullhd_paths", ""))
    if not fullhd_sources:
        return Path("")
    text = fullhd_sources[0]
    text = text.replace("/crop_fullhd/", "/crop_native/")
    text = text.replace("_crop_fullhd.png", "_crop.png")
    return Path(text)


def asset_id_for(row: dict[str, str]) -> str:
    return "__".join([safe_name(row.get("archive_tag", "")), safe_name(normalize_pcx(row.get("pcx_name", ""))), "shared_2700302b_full_replay"])


def copy_asset(source: Path, target: Path, issues: list[str], issue_name: str) -> bool:
    if not source.exists():
        issues.append(issue_name)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    shutil.copy2(source, target)
    if not target.exists():
        issues.append(f"missing_target:{issue_name}")
        return False
    return True


def image_size(path: Path, issues: list[str]) -> tuple[str, str]:
    if not path.exists():
        issues.append("missing_promoted_fullhd_path")
        return "", ""
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
    except Exception as exc:
        issues.append(f"open_failed:{type(exc).__name__}")
        return "", ""
    return str(width), str(height)


def matching_reference(references: list[dict[str, str]], proof: dict[str, str]) -> dict[str, str]:
    archive = proof.get("archive", "")
    pcx = normalize_pcx(proof.get("pcx_name", ""))
    for row in references:
        if row.get("archive", "") == archive and normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")) == pcx:
            return row
    return {}


def build_manifest(
    output_dir: Path,
    proof: dict[str, str],
    reference: dict[str, str],
    proof_summary_path: Path,
) -> list[dict[str, str]]:
    issues: list[str] = []
    if not proof:
        issues.append("missing_final_clear_summary")
    if not reference:
        issues.append("missing_reference_row")
    if proof.get("final_clear_verdict") != "shared_2700302b_reference_fixed_dy1_final_clear_residual_profile_complete":
        issues.append("final_clear_verdict_mismatch")
    if int_value(proof, "full_coverage") != 1:
        issues.append("full_coverage_not_confirmed")
    if int_value(proof, "remaining_nonzero_pixels") != 0:
        issues.append("remaining_nonzero_pixels_not_zero")
    if int_value(proof, "combined_covered_pixels") != int_value(proof, "target_pixels"):
        issues.append("coverage_not_complete")

    asset_id = asset_id_for(proof)
    tag = safe_name(proof.get("archive_tag", ""))
    source_native = native_candidate(reference)
    source_fullhd_values = split_paths(reference.get("descriptor_pack_paths", ""))
    source_fullhd = Path(source_fullhd_values[0]) if source_fullhd_values else Path("")
    promoted_native = output_dir / "native" / tag / f"{asset_id}_native.png"
    promoted_fullhd = output_dir / "descriptors" / tag / f"{asset_id}.png"
    native_ok = copy_asset(source_native, promoted_native, issues, "missing_source_native_path")
    fullhd_ok = copy_asset(source_fullhd, promoted_fullhd, issues, "missing_source_fullhd_path")
    fullhd_width, fullhd_height = image_size(promoted_fullhd, issues)
    if fullhd_ok and (fullhd_width, fullhd_height) != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1])):
        issues.append("promoted_fullhd_not_fullhd")

    coverage_eligible = not issues
    return [
        {
            "asset_id": asset_id,
            "archive": proof.get("archive", ""),
            "archive_tag": proof.get("archive_tag", ""),
            "texture_path": reference.get("texture_path", ""),
            "pcx_name": proof.get("pcx_name", ""),
            "normalized_pcx_name": normalize_pcx(proof.get("pcx_name", "")),
            "decoder_rule": DECODER_RULE,
            "decoder_extra": f"frontier{proof.get('frontier_id', '')}_dy{proof.get('dy', '')}_shift{proof.get('shift', '')}",
            "frontier_id": proof.get("frontier_id", ""),
            "dy": proof.get("dy", ""),
            "shift": proof.get("shift", ""),
            "selected_pixels": proof.get("selected_pixels", ""),
            "target_pixels": proof.get("target_pixels", ""),
            "combined_covered_pixels": proof.get("combined_covered_pixels", ""),
            "remaining_nonzero_pixels": proof.get("remaining_nonzero_pixels", ""),
            "full_coverage": proof.get("full_coverage", ""),
            "coverage_eligible": "yes" if coverage_eligible else "no",
            "source_native_path": source_native.as_posix() if source_native else "",
            "source_native_exists": "yes" if source_native.exists() else "no",
            "source_fullhd_path": source_fullhd.as_posix() if source_fullhd else "",
            "source_fullhd_exists": "yes" if source_fullhd.exists() else "no",
            "promoted_native_path": promoted_native.as_posix(),
            "promoted_native_exists": "yes" if native_ok else "no",
            "promoted_fullhd_path": promoted_fullhd.as_posix(),
            "promoted_fullhd_exists": "yes" if promoted_fullhd.exists() else "no",
            "promoted_fullhd_width": fullhd_width,
            "promoted_fullhd_height": fullhd_height,
            "proof_summary_path": proof_summary_path.as_posix(),
            "issues": ";".join(dict.fromkeys(issues)),
        }
    ]


def build_summary(proof_rows: list[dict[str, str]], manifest_rows: list[dict[str, str]]) -> dict[str, str]:
    ready_rows = [row for row in proof_rows if row.get("final_clear_verdict", "").endswith("_complete")]
    eligible_rows = [row for row in manifest_rows if row.get("coverage_eligible") == "yes"]
    issue_rows = [row for row in manifest_rows if row.get("issues")]
    clean = len(proof_rows) == 1 and len(ready_rows) == 1 and len(eligible_rows) == 1 and not issue_rows
    if clean:
        verdict = "shared_2700302b_full_replay_promoted_pack_ready"
        next_action = "continue remaining large .tex decoder work after shared 0x2700302b full replay promotion"
    elif issue_rows:
        verdict = "shared_2700302b_full_replay_promoted_pack_blocked"
        next_action = "fix shared 0x2700302b full replay promoted pack issues"
    else:
        verdict = "shared_2700302b_full_replay_promoted_pack_incomplete"
        next_action = "complete shared 0x2700302b full replay promoted pack"
    proof = proof_rows[0] if proof_rows else {}
    return {
        "scope": "total",
        "proof_rows": str(len(proof_rows)),
        "ready_rows": str(len(ready_rows)),
        "coverage_eligible_rows": str(len(eligible_rows)),
        "coverage_eligible_unique_pcx": str(len({row["normalized_pcx_name"] for row in eligible_rows})),
        "native_assets": str(sum(1 for row in manifest_rows if row.get("promoted_native_exists") == "yes")),
        "fullhd_assets": str(sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") == "yes")),
        "selected_pixels": proof.get("selected_pixels", "0"),
        "covered_pixels": proof.get("combined_covered_pixels", "0"),
        "target_pixels": proof.get("target_pixels", "0"),
        "remaining_nonzero_pixels": proof.get("remaining_nonzero_pixels", "0"),
        "missing_native_paths": str(sum(1 for row in manifest_rows if row.get("promoted_native_exists") != "yes")),
        "missing_fullhd_paths": str(sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") != "yes")),
        "issue_rows": str(len(issue_rows)),
        "review_verdict": verdict,
        "next_action": next_action,
    }


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    manifest_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "manifest": manifest_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    row = manifest_rows[0] if manifest_rows else {}
    image = html.escape(relative_href(row.get("promoted_fullhd_path", ""), output_dir))
    native = html.escape(relative_href(row.get("promoted_native_path", ""), output_dir))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
            ("fullhd", row.get("promoted_fullhd_path", "")),
            ("native", row.get("promoted_native_path", "")),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; --accent: #74d3ae; --ok: #78d98f; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1500px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }}
.stat {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ padding: 12px; overflow-x: auto; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #050607; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>{html.escape(title)}</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Coverage eligible</div><div class="value ok">{html.escape(summary['coverage_eligible_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD assets</div><div class="value ok">{html.escape(summary['fullhd_assets'])}</div></div>
    <div class="stat"><div class="label">Covered</div><div class="value ok">{html.escape(summary['covered_pixels'])}/{html.escape(summary['target_pixels'])}</div></div>
    <div class="stat"><div class="label">Remaining</div><div class="value ok">{html.escape(summary['remaining_nonzero_pixels'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="muted">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_action'])}</div></section>
  <a class="preview" href="{image}"><img src="{native or image}" loading="lazy" decoding="async" alt=""></a>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Manifest</h2>{render_table(manifest_rows, MANIFEST_FIELDNAMES)}</section>
</main>
<script>const TEX_LARGE_SHARED_2700302B_FULL_REPLAY_PROMOTED_PACK = {data_json};</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    final_clear_summary: Path,
    references_path: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_rows = read_csv(final_clear_summary) if final_clear_summary.exists() else []
    proof = proof_rows[0] if proof_rows else {}
    references = read_csv(references_path)
    reference = matching_reference(references, proof)
    manifest_rows = build_manifest(output_dir, proof, reference, final_clear_summary)
    summary = build_summary(proof_rows, manifest_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, manifest_rows)
    (output_dir / "index.html").write_text(build_html(summary, manifest_rows, output_dir, title), encoding="utf-8")
    return summary, manifest_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack shared 0x2700302b full replay promotion.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--final-clear-summary", type=Path, default=DEFAULT_FINAL_CLEAR_SUMMARY)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Shared 0x2700302b Full Replay Promoted Pack",
    )
    args = parser.parse_args()
    summary, _manifest = write_report(args.output, args.final_clear_summary, args.references, args.title)
    print(f"Proof rows: {summary['proof_rows']}")
    print(f"Coverage eligible rows: {summary['coverage_eligible_rows']}")
    print(f"Full HD assets: {summary['fullhd_assets']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
