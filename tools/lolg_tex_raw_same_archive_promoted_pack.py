#!/usr/bin/env python3
"""Pack reviewed raw same-archive .tex preview candidates as Full HD assets."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)

DEFAULT_OUTPUT = Path("output/tex_raw_same_archive_promoted_pack")
DEFAULT_PROFILE = Path("output/tex_remaining_reference_profile/profile.csv")
DEFAULT_REVIEW_DECISIONS = Path("reports/lvl_pcx_te_review_queue_decisions_smoke.tsv")
DEFAULT_PENDING_REVIEWS = Path("reports/lvl_pcx_te_pending_review_batches.tsv")
DEFAULT_PREVIEW_ROOTS = [
    Path("previews_lvl_pcx_payloads_v10_riskaware"),
    Path("previews_te_guarded_cmd20_v10_markerknown"),
    Path("previews_te_guided_op4_state_probe_v5"),
]

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "unique_pcx",
    "accepted_rows",
    "pending_rows",
    "coverage_eligible_rows",
    "coverage_eligible_unique_pcx",
    "native_assets",
    "fullhd_assets",
    "accepted_fullhd_assets",
    "missing_source_paths",
    "missing_fullhd_paths",
    "issue_rows",
    "next_action",
]

MANIFEST_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "texture_path",
    "profile_priority",
    "review_status",
    "coverage_eligible",
    "decision",
    "risk",
    "focus",
    "base_mode",
    "candidate_mode",
    "changed_ratio",
    "changed_pixels",
    "source_native_path",
    "source_native_exists",
    "source_width",
    "source_height",
    "promoted_native_path",
    "promoted_native_exists",
    "promoted_fullhd_path",
    "promoted_fullhd_exists",
    "promoted_fullhd_width",
    "promoted_fullhd_height",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def relative_symlink(source: Path, target: Path) -> str:
    return os.path.relpath(source, target.parent)


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else 0
    except ValueError:
        return 0


def review_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("archive", ""), normalize_pcx(row.get("name", "") or row.get("pcx_name", "")))


def build_review_lookup(
    decisions: list[dict[str, str]],
    pending_reviews: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in pending_reviews:
        key = review_key(row)
        if key[0] and key[1]:
            lookup[key] = row
    for row in decisions:
        key = review_key(row)
        if key[0] and key[1]:
            lookup[key] = row
    return lookup


def candidate_profile_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("priority") == "promote_raw_same_archive"
        and int_value(row, "raw_cache_same_archive_refs") > 0
    ]


def candidate_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))


def carry_forward_accepted_rows(
    profile_rows: list[dict[str, str]],
    existing_manifest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows = list(profile_rows)
    seen = {candidate_key(row) for row in rows}
    for existing in existing_manifest_rows:
        key = candidate_key(existing)
        if not key[0] or not key[1] or key in seen:
            continue
        if existing.get("coverage_eligible") != "yes" or existing.get("review_status") != "accepted":
            continue
        rows.append(
            {
                "archive": existing.get("archive", ""),
                "archive_tag": existing.get("archive_tag", ""),
                "texture_path": existing.get("texture_path", ""),
                "pcx_name": existing.get("pcx_name", ""),
                "normalized_pcx_name": existing.get("normalized_pcx_name", ""),
                "raw_cache_same_archive_refs": "1",
                "priority": "promote_raw_same_archive",
            }
        )
        seen.add(key)
    return rows


def review_status(row: dict[str, str]) -> str:
    return row.get("review_status") or row.get("status") or "unreviewed"


def candidate_preview_path(review: dict[str, str], archive: str, normalized_pcx: str, roots: list[Path]) -> str:
    explicit = review.get("candidate_preview", "")
    if explicit and Path(explicit).exists():
        return explicit

    stem = Path(normalized_pcx).stem.lower()
    for root in roots:
        level_dir = root / archive
        if not level_dir.exists():
            continue
        matches = sorted(level_dir.glob(f"*{stem}*.png"))
        if matches:
            return str(matches[0])
    return explicit


def make_fullhd(image: Image.Image) -> Image.Image:
    has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
    source = image.convert("RGBA" if has_alpha else "RGB")
    scale = min(TARGET_SIZE[0] / source.width, TARGET_SIZE[1] / source.height)
    scaled_size = (
        max(1, round(source.width * scale)),
        max(1, round(source.height * scale)),
    )
    scaled = source.resize(scaled_size, Image.Resampling.NEAREST)
    origin = ((TARGET_SIZE[0] - scaled.width) // 2, (TARGET_SIZE[1] - scaled.height) // 2)
    if has_alpha:
        canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(scaled, origin)
    else:
        canvas = Image.new("RGB", TARGET_SIZE, (0, 0, 0))
        canvas.paste(scaled, origin)
    return canvas


def link_native(source: Path, target: Path, issues: list[str]) -> bool:
    if not source.exists():
        issues.append("missing_source_path")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(relative_symlink(source, target))
    if not target.exists():
        issues.append("missing_promoted_native_path")
        return False
    if os.path.realpath(source) != os.path.realpath(target):
        issues.append("native_target_mismatch")
        return False
    return True


def write_fullhd(source: Path, target: Path, issues: list[str]) -> tuple[str, str, str, str]:
    if not source.exists():
        issues.append("missing_source_path")
        return "", "", "0", "0"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source) as image:
            image.load()
            source_width, source_height = image.size
            fullhd = make_fullhd(image)
            fullhd.save(target, "PNG", optimize=True)
    except Exception as exc:
        issues.append(f"render_failed:{exc}")
        return "", "", "0", "0"

    if not target.exists():
        issues.append("missing_promoted_fullhd_path")
        return str(source_width), str(source_height), "0", "0"

    try:
        with Image.open(target) as rendered:
            fullhd_width, fullhd_height = rendered.size
    except Exception as exc:
        issues.append(f"promoted_fullhd_open_failed:{exc}")
        return str(source_width), str(source_height), "0", "0"

    if (fullhd_width, fullhd_height) != TARGET_SIZE:
        issues.append("promoted_fullhd_not_fullhd")
    return str(source_width), str(source_height), str(fullhd_width), str(fullhd_height)


def asset_id_for(row: dict[str, str]) -> str:
    tag = row.get("archive_tag", "") or archive_tag(row.get("archive", ""))
    normalized = normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", ""))
    return f"{safe_name(tag)}__{safe_name(normalized)}__raw_same_archive"


def build_manifest(
    output_dir: Path,
    profile_rows: list[dict[str, str]],
    review_lookup: dict[tuple[str, str], dict[str, str]],
    preview_roots: list[Path],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for profile in sorted(profile_rows, key=lambda row: (row.get("archive_tag", ""), row.get("normalized_pcx_name", ""))):
        tag = profile.get("archive_tag", "") or archive_tag(profile.get("archive", ""))
        normalized = normalize_pcx(profile.get("normalized_pcx_name", "") or profile.get("pcx_name", ""))
        review = review_lookup.get((tag, normalized), {})
        status = review_status(review)
        coverage_eligible = status == "accepted"
        source_path_text = candidate_preview_path(review, tag, normalized, preview_roots)
        source_path = Path(source_path_text) if source_path_text else Path()
        asset_id = asset_id_for(profile)
        target_dir = output_dir / "descriptors" / safe_name(tag)
        native_dir = output_dir / "native" / safe_name(tag)
        promoted_fullhd = target_dir / f"{asset_id}.png"
        promoted_native = native_dir / f"{asset_id}_native.png"
        issues: list[str] = []
        if status != "accepted":
            issues.append(f"review_status:{status}")

        native_ok = link_native(source_path, promoted_native, issues) if source_path_text else False
        if not source_path_text:
            issues.append("missing_source_path")
        source_width, source_height, fullhd_width, fullhd_height = write_fullhd(
            source_path,
            promoted_fullhd,
            issues,
        )

        rows.append(
            {
                "asset_id": asset_id,
                "archive": profile.get("archive", ""),
                "archive_tag": tag,
                "pcx_name": profile.get("pcx_name", ""),
                "normalized_pcx_name": normalized,
                "texture_path": profile.get("texture_path", ""),
                "profile_priority": profile.get("priority", ""),
                "review_status": status,
                "coverage_eligible": "yes" if coverage_eligible else "no",
                "decision": review.get("decision", ""),
                "risk": review.get("risk", ""),
                "focus": review.get("focus", "") or review.get("review_hint", ""),
                "base_mode": review.get("base_mode", ""),
                "candidate_mode": review.get("candidate_mode", ""),
                "changed_ratio": review.get("changed_ratio", ""),
                "changed_pixels": review.get("changed_pixels", ""),
                "source_native_path": source_path_text,
                "source_native_exists": "yes" if source_path_text and source_path.exists() else "no",
                "source_width": source_width,
                "source_height": source_height,
                "promoted_native_path": str(promoted_native),
                "promoted_native_exists": "yes" if native_ok else "no",
                "promoted_fullhd_path": str(promoted_fullhd),
                "promoted_fullhd_exists": "yes" if promoted_fullhd.exists() else "no",
                "promoted_fullhd_width": fullhd_width,
                "promoted_fullhd_height": fullhd_height,
                "issues": ";".join(dict.fromkeys(issues)),
            }
        )
    return rows


def summary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    pending = [row for row in rows if row["review_status"] != "accepted"]
    eligible = [row for row in rows if row["coverage_eligible"] == "yes"]
    if pending:
        next_action = f"review {len(pending)} pending raw same-archive .tex promotions"
    elif accepted:
        next_action = f"integrate {len(accepted)} accepted raw same-archive .tex promotions"
    else:
        next_action = "find review evidence for raw same-archive .tex promotions"
    return {
        "scope": "total",
        "candidate_rows": str(len(rows)),
        "unique_pcx": str(len({row["normalized_pcx_name"] for row in rows})),
        "accepted_rows": str(len(accepted)),
        "pending_rows": str(len(pending)),
        "coverage_eligible_rows": str(len(eligible)),
        "coverage_eligible_unique_pcx": str(len({row["normalized_pcx_name"] for row in eligible})),
        "native_assets": str(sum(1 for row in rows if row["promoted_native_exists"] == "yes")),
        "fullhd_assets": str(sum(1 for row in rows if row["promoted_fullhd_exists"] == "yes")),
        "accepted_fullhd_assets": str(
            sum(1 for row in accepted if row["promoted_fullhd_exists"] == "yes")
        ),
        "missing_source_paths": str(sum(1 for row in rows if row["source_native_exists"] != "yes")),
        "missing_fullhd_paths": str(sum(1 for row in rows if row["promoted_fullhd_exists"] != "yes")),
        "issue_rows": str(sum(1 for row in rows if row["issues"] and row["review_status"] == "accepted")),
        "next_action": next_action,
    }


def render_card(row: dict[str, str], base_dir: Path) -> str:
    image = html.escape(relative_href(row.get("promoted_fullhd_path", ""), base_dir))
    title = f"{row.get('archive_tag', '')} / {row.get('pcx_name', '')}"
    status_class = "ok" if row.get("coverage_eligible") == "yes" else "warn"
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="body">
    <div class="title">{html.escape(title)}</div>
    <div class="{status_class}">{html.escape(row.get('review_status', ''))}</div>
    <div class="muted">{html.escape(row.get('candidate_mode', ''))}</div>
    <div class="muted">{html.escape(row.get('source_width', ''))}x{html.escape(row.get('source_height', ''))}</div>
  </div>
</article>"""


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "assets": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    cards = "\n".join(render_card(row, output_dir) for row in rows)
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("manifest.csv", output_dir / "manifest.csv"),
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
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
  --warn: #f0b06a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #11171b; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #050607; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
.body {{ padding: 10px; display: grid; gap: 3px; }}
.title {{ font-weight: 700; }}
.muted {{ color: var(--muted); }}
.ok {{ color: var(--ok); font-weight: 700; }}
.warn {{ color: var(--warn); font-weight: 700; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap"><h1>{html.escape(title)}</h1></div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Candidats</div><div class="value">{html.escape(summary['candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Acceptes</div><div class="value ok">{html.escape(summary['accepted_rows'])}</div></div>
    <div class="stat"><div class="label">En revue</div><div class="value warn">{html.escape(summary['pending_rows'])}</div></div>
    <div class="stat"><div class="label">Full HD</div><div class="value">{html.escape(summary['fullhd_assets'])}</div></div>
    <div class="stat"><div class="label">Issues acceptes</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="grid">{cards}</section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Manifest</h2>
    {render_table(rows, MANIFEST_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    profile: Path,
    review_decisions: Path,
    pending_reviews: Path,
    preview_roots: list[Path],
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reviews = build_review_lookup(read_tsv(review_decisions), read_tsv(pending_reviews))
    existing_manifest = output_dir / "manifest.csv"
    existing_rows = read_csv(existing_manifest) if existing_manifest.exists() else []
    profile_candidates = carry_forward_accepted_rows(
        candidate_profile_rows(read_csv(profile)),
        existing_rows,
    )
    rows = build_manifest(
        output_dir,
        profile_candidates,
        reviews,
        preview_roots,
    )
    summary = summary_row(rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "manifest.csv", MANIFEST_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack raw same-archive .tex preview candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--review-decisions", type=Path, default=DEFAULT_REVIEW_DECISIONS)
    parser.add_argument("--pending-reviews", type=Path, default=DEFAULT_PENDING_REVIEWS)
    parser.add_argument(
        "--preview-root",
        type=Path,
        action="append",
        default=None,
        help="Preview root to search, repeatable. Defaults to known old-work roots.",
    )
    parser.add_argument("--title", default="Lands of Lore II .tex Raw Same-Archive Promoted Pack")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.profile,
        args.review_decisions,
        args.pending_reviews,
        args.preview_root or DEFAULT_PREVIEW_ROOTS,
        args.title,
    )
    print(f"Raw same-archive candidates: {summary['candidate_rows']}")
    print(f"Accepted rows: {summary['accepted_rows']}")
    print(f"Pending rows: {summary['pending_rows']}")
    print(f"Full HD assets: {summary['fullhd_assets']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
