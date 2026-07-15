#!/usr/bin/env python3
"""Probe 04a900 header semantics for the shifted 0x2a30 branch target."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import defaultdict
from pathlib import Path

try:
    from analyze_te_pcx_payloads import MARKERS, bounded_payload, load_rows
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    MARKERS = []
    bounded_payload = None
    load_rows = None
else:
    OPTIONAL_IMPORT_ERROR = None


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_singleton_header_probe")
DEFAULT_SELECTOR_SUMMARY = Path("output/tex_large_shifted_2a30_branch_selector_probe/summary.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_FEATURES = Path("reports/te_decoder_features.tsv")
DEFAULT_PROLOGUES = Path("reports/te_prologue_families.tsv")
DEFAULT_TARGET_ARCHIVE_TAG = "L17_HC"
DEFAULT_TARGET_PCX_NAME = "MTMMgutz4.pcx"
DEFAULT_SIGNATURE = bytes.fromhex("04 a9 00")

SUMMARY_FIELDNAMES = [
    "scope",
    "scan_head",
    "signature_hex",
    "signature_rows",
    "selector_renderer_candidate_rows",
    "selector_target_best_fingerprint",
    "selector_best_supported_command_fingerprint",
    "selector_best_supported_command_delta",
    "target_archive_tag",
    "target_pcx_name",
    "target_marker_pos",
    "target_marker",
    "target_sig_rel",
    "target_rect_x",
    "target_rect_y",
    "target_tail4_hex",
    "target_exact_after8_hex",
    "target_tail4_rows",
    "target_tail4_cross_rows",
    "target_tail4_cross_pcx_support",
    "target_tail4_cross_examples",
    "target_xy_rows",
    "target_xy_cross_rows",
    "target_xy_cross_pcx_support",
    "target_exact_after8_rows",
    "target_exact_after8_cross_rows",
    "target_exact_after8_cross_pcx_support",
    "zero_separated_rows",
    "zero_separated_target_tail4_rows",
    "same_marker_tail4_cross_rows",
    "issue_rows",
    "visual_status",
    "next_action",
]

RECORD_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "payload_len",
    "marker_pos",
    "marker",
    "sig_rel",
    "signature_hex",
    "is_target",
    "known_mode",
    "known_width",
    "known_score",
    "prologue_family",
    "prologue_source",
    "prologue_mode",
    "prologue_width",
    "prologue_start",
    "prologue_start_minus_marker",
    "before8_hex",
    "head32_hex",
    "sig_after16_hex",
    "after8_hex",
    "after_u16_0",
    "after_u16_2",
    "after_u16_4",
    "after_u16_6",
    "rect_x",
    "rect_y",
    "rect_pair_zero_separated",
    "tail4_hex",
    "tail_u16_0",
    "tail_u16_2",
    "target_tail4_match",
    "target_xy_match",
    "exact_after8_match",
]

GROUP_FIELDNAMES = [
    "group_by",
    "key",
    "rows",
    "target_rows",
    "cross_rows",
    "cross_pcx_support",
    "examples",
]


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_text(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value), 0) if value not in (None, "") else default
    except ValueError:
        return default


def key_for(level: str, name: str) -> tuple[str, str]:
    return level, name.lower()


def u16_text(data: bytes, offset: int) -> str:
    if 0 <= offset <= len(data) - 2:
        return str(int.from_bytes(data[offset : offset + 2], "little"))
    return ""


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def catalog_payloads(catalog: Path) -> dict[tuple[str, str], tuple[str, bytes]]:
    payloads: dict[tuple[str, str], tuple[str, bytes]] = {}
    for row in load_rows(catalog):
        if row.get("ext") != ".pcx" or row.get("name", "").lower() == "palette.pcx":
            continue
        level = row["source_path"].parent.name
        name = row.get("name", "")
        payloads[key_for(level, name)] = (name, bounded_payload(row))
    return payloads


def lookup_by_resource(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path, delimiter="\t"):
        rows[key_for(row.get("level", ""), row.get("name", ""))] = row
    return rows


def scan_signature_records(
    payloads: dict[tuple[str, str], tuple[str, bytes]],
    features: dict[tuple[str, str], dict[str, str]],
    prologues: dict[tuple[str, str], dict[str, str]],
    target_key: tuple[str, str],
    signature: bytes,
    scan_head: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, (original_name, payload) in sorted(payloads.items()):
        for marker in MARKERS:
            marker_start = 0
            while True:
                marker_pos = payload.find(marker, marker_start)
                if marker_pos < 0:
                    break
                marker_start = marker_pos + 1
                search_start = marker_pos + len(marker)
                search_end = min(len(payload), search_start + scan_head)
                sig_start = 0
                search = payload[search_start:search_end]
                while True:
                    sig_index = search.find(signature, sig_start)
                    if sig_index < 0:
                        break
                    sig_start = sig_index + 1
                    sig_abs = search_start + sig_index
                    after = payload[sig_abs + len(signature) : sig_abs + len(signature) + 8]
                    if len(after) < 8:
                        continue
                    feature = features.get(key, {})
                    prologue = prologues.get(key, {})
                    before = payload[max(0, marker_pos - 8) : marker_pos]
                    head = payload[marker_pos : marker_pos + 32]
                    sig_after = payload[sig_abs : sig_abs + 16]
                    tail = after[4:8]
                    rect_x = after[0]
                    rect_y = after[2]
                    rows.append(
                        {
                            "archive_tag": key[0],
                            "pcx_name": original_name,
                            "payload_len": str(len(payload)),
                            "marker_pos": str(marker_pos),
                            "marker": marker.hex(),
                            "sig_rel": str(sig_abs - marker_pos),
                            "signature_hex": signature.hex(" "),
                            "is_target": "yes" if key == target_key else "no",
                            "known_mode": feature.get("mode", ""),
                            "known_width": feature.get("width", ""),
                            "known_score": feature.get("score", ""),
                            "prologue_family": prologue.get("family", ""),
                            "prologue_source": prologue.get("source", ""),
                            "prologue_mode": prologue.get("mode", ""),
                            "prologue_width": prologue.get("width", ""),
                            "prologue_start": prologue.get("start", ""),
                            "prologue_start_minus_marker": prologue.get("start_minus_marker", ""),
                            "before8_hex": before.hex(" "),
                            "head32_hex": head.hex(" "),
                            "sig_after16_hex": sig_after.hex(" "),
                            "after8_hex": after.hex(" "),
                            "after_u16_0": u16_text(after, 0),
                            "after_u16_2": u16_text(after, 2),
                            "after_u16_4": u16_text(after, 4),
                            "after_u16_6": u16_text(after, 6),
                            "rect_x": str(rect_x),
                            "rect_y": str(rect_y),
                            "rect_pair_zero_separated": "yes" if after[1] == 0 and after[3] == 0 else "no",
                            "tail4_hex": tail.hex(" "),
                            "tail_u16_0": u16_text(tail, 0),
                            "tail_u16_2": u16_text(tail, 2),
                            "target_tail4_match": "",
                            "target_xy_match": "",
                            "exact_after8_match": "",
                        }
                    )
    return rows


def example_text(rows: list[dict[str, str]], limit: int = 6) -> str:
    examples = []
    seen = set()
    for row in rows:
        item = f"{row.get('archive_tag', '')}/{row.get('pcx_name', '')}@{row.get('marker_pos', '')}"
        if item in seen:
            continue
        seen.add(item)
        examples.append(item)
        if len(examples) >= limit:
            break
    return "|".join(examples)


def cross_pcx_support(rows: list[dict[str, str]]) -> int:
    return len({(row.get("archive_tag", ""), row.get("pcx_name", "").lower()) for row in rows})


def target_record(rows: list[dict[str, str]], target_marker: str) -> dict[str, str]:
    targets = [row for row in rows if row.get("is_target") == "yes" and row.get("marker") == target_marker]
    if not targets:
        targets = [row for row in rows if row.get("is_target") == "yes"]
    return min(targets, key=lambda row: int_text(row.get("marker_pos")), default={})


def annotate_matches(rows: list[dict[str, str]], target: dict[str, str]) -> None:
    target_tail = target.get("tail4_hex", "")
    target_xy = (target.get("rect_x", ""), target.get("rect_y", ""))
    target_after = target.get("after8_hex", "")
    for row in rows:
        row["target_tail4_match"] = "yes" if row.get("tail4_hex") == target_tail else "no"
        row["target_xy_match"] = "yes" if (row.get("rect_x", ""), row.get("rect_y", "")) == target_xy else "no"
        row["exact_after8_match"] = "yes" if row.get("after8_hex") == target_after else "no"


def matching_rows(rows: list[dict[str, str]], field: str, value: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get(field) == value]


def cross_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("is_target") != "yes"]


def build_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[("tail4_hex", row.get("tail4_hex", ""))].append(row)
        grouped[("marker", row.get("marker", ""))].append(row)
        grouped[("sig_rel", row.get("sig_rel", ""))].append(row)
        grouped[("rect_xy", f"{row.get('rect_x', '')},{row.get('rect_y', '')}")].append(row)
        grouped[
            (
                "marker_sigrel_tail4",
                f"{row.get('marker', '')}|{row.get('sig_rel', '')}|{row.get('tail4_hex', '')}",
            )
        ].append(row)
    output = []
    for (group_by, key), group_rows in sorted(grouped.items()):
        outside = cross_rows(group_rows)
        output.append(
            {
                "group_by": group_by,
                "key": key,
                "rows": str(len(group_rows)),
                "target_rows": str(sum(1 for row in group_rows if row.get("is_target") == "yes")),
                "cross_rows": str(len(outside)),
                "cross_pcx_support": str(cross_pcx_support(outside)),
                "examples": example_text(group_rows),
            }
        )
    return output


def build_summary(
    rows: list[dict[str, str]],
    selector_summary: dict[str, str],
    target: dict[str, str],
    signature: bytes,
    scan_head: int,
    issues: list[str],
) -> dict[str, str]:
    target_tail = target.get("tail4_hex", "")
    target_after = target.get("after8_hex", "")
    target_x = target.get("rect_x", "")
    target_y = target.get("rect_y", "")
    tail_rows = matching_rows(rows, "tail4_hex", target_tail) if target_tail else []
    exact_rows = matching_rows(rows, "after8_hex", target_after) if target_after else []
    xy_rows = [row for row in rows if row.get("rect_x") == target_x and row.get("rect_y") == target_y] if target else []
    zero_rows = [row for row in rows if row.get("rect_pair_zero_separated") == "yes"]
    zero_tail_rows = [row for row in zero_rows if row.get("tail4_hex") == target_tail] if target_tail else []
    tail_cross = cross_rows(tail_rows)
    xy_cross = cross_rows(xy_rows)
    exact_cross = cross_rows(exact_rows)
    same_marker_tail_cross = [
        row
        for row in tail_cross
        if row.get("marker") == target.get("marker", "") and row.get("tail4_hex") == target_tail
    ]
    if issues:
        visual_status = "blocked_singleton_header_probe_issues"
        next_action = "fix shifted 0x2a30 singleton header probe inputs"
    elif exact_cross:
        visual_status = "candidate_04a900_exact_header_has_cross_support"
        next_action = (
            "review exact 04a900 header support for shifted 0x2a30 branch target "
            f"{target_after}"
        )
    elif tail_cross:
        visual_status = "blocked_04a900_header_tail_supported_xy_singleton"
        next_action = (
            "derive 04a900 rectangle-anchor semantics for shifted 0x2a30 branch target; "
            f"tail {target_tail} has cross-PCX support {cross_pcx_support(tail_cross)} "
            f"but xy {target_x}/{target_y} exact support is {cross_pcx_support(xy_cross)}"
        )
    else:
        visual_status = "blocked_04a900_header_singleton"
        next_action = (
            "derive singleton 04a900 header semantics for shifted 0x2a30 branch target "
            f"{target_after}"
        )
    return {
        "scope": "total",
        "scan_head": str(scan_head),
        "signature_hex": signature.hex(" "),
        "signature_rows": str(len(rows)),
        "selector_renderer_candidate_rows": selector_summary.get("renderer_candidate_rows", ""),
        "selector_target_best_fingerprint": selector_summary.get("target_best_fingerprint", ""),
        "selector_best_supported_command_fingerprint": selector_summary.get(
            "best_supported_command_fingerprint", ""
        ),
        "selector_best_supported_command_delta": selector_summary.get("best_supported_command_delta", ""),
        "target_archive_tag": target.get("archive_tag", ""),
        "target_pcx_name": target.get("pcx_name", ""),
        "target_marker_pos": target.get("marker_pos", ""),
        "target_marker": target.get("marker", ""),
        "target_sig_rel": target.get("sig_rel", ""),
        "target_rect_x": target_x,
        "target_rect_y": target_y,
        "target_tail4_hex": target_tail,
        "target_exact_after8_hex": target_after,
        "target_tail4_rows": str(len(tail_rows)),
        "target_tail4_cross_rows": str(len(tail_cross)),
        "target_tail4_cross_pcx_support": str(cross_pcx_support(tail_cross)),
        "target_tail4_cross_examples": example_text(tail_cross),
        "target_xy_rows": str(len(xy_rows)),
        "target_xy_cross_rows": str(len(xy_cross)),
        "target_xy_cross_pcx_support": str(cross_pcx_support(xy_cross)),
        "target_exact_after8_rows": str(len(exact_rows)),
        "target_exact_after8_cross_rows": str(len(exact_cross)),
        "target_exact_after8_cross_pcx_support": str(cross_pcx_support(exact_cross)),
        "zero_separated_rows": str(len(zero_rows)),
        "zero_separated_target_tail4_rows": str(len(zero_tail_rows)),
        "same_marker_tail4_cross_rows": str(len(same_marker_tail_cross)),
        "issue_rows": str(len(issues)),
        "visual_status": visual_status,
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
    groups: list[dict[str, str]],
    records: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "groups": groups, "records": records}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("records.csv", output_dir / "records.csv"),
            ("groups.csv", output_dir / "groups.csv"),
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
<p class="muted">Corpus scan for marker-local 04a900 records near the shifted 0x2a30 branch target.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Groups</h2>
{render_table(groups, GROUP_FIELDNAMES)}
<h2>Records</h2>
{render_table(records, RECORD_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_SINGLETON_HEADER_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    selector_summary = (read_csv(args.selector_summary) or [{}])[0]
    if not selector_summary:
        issues.append("missing_selector_summary")
    if selector_summary.get("renderer_candidate_rows") in ("", "0"):
        records: list[dict[str, str]] = []
        groups: list[dict[str, str]] = []
        target: dict[str, str] = {}
        summary = build_summary(records, selector_summary, target, args.signature, args.scan_head, issues)
        write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(args.output / "records.csv", RECORD_FIELDNAMES, records)
        write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
        (args.output / "index.html").write_text(
            build_html(summary, groups, records, args.output, args.title),
            encoding="utf-8",
        )
        return summary, issues
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    payloads = catalog_payloads(args.catalog)
    features = lookup_by_resource(args.features)
    prologues = lookup_by_resource(args.prologues)
    target_key = key_for(args.target_archive_tag, args.target_pcx_name)
    if target_key not in payloads:
        issues.append(f"missing_target_payload:{args.target_archive_tag}/{args.target_pcx_name}")
    records = scan_signature_records(
        payloads,
        features,
        prologues,
        target_key,
        args.signature,
        args.scan_head,
    )
    target = target_record(records, args.target_marker.lower())
    if not target:
        issues.append("missing_target_signature_record")
    annotate_matches(records, target)
    groups = build_groups(records)
    summary = build_summary(records, selector_summary, target, args.signature, args.scan_head, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "records.csv", RECORD_FIELDNAMES, records)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    (args.output / "index.html").write_text(
        build_html(summary, groups, records, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe marker-local 04a900 header semantics for shifted 0x2a30 branch target."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selector-summary", type=Path, default=DEFAULT_SELECTOR_SUMMARY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--prologues", type=Path, default=DEFAULT_PROLOGUES)
    parser.add_argument("--target-archive-tag", default=DEFAULT_TARGET_ARCHIVE_TAG)
    parser.add_argument("--target-pcx-name", default=DEFAULT_TARGET_PCX_NAME)
    parser.add_argument("--target-marker", default="2a30")
    parser.add_argument("--signature", type=bytes.fromhex, default=DEFAULT_SIGNATURE)
    parser.add_argument("--scan-head", type=int, default=12)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Singleton Header Probe",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Signature rows: {summary['signature_rows']}")
    print(f"Target marker: {summary['target_marker']}@{summary['target_marker_pos']}")
    print(f"Target rect xy: {summary['target_rect_x']}/{summary['target_rect_y']}")
    print(f"Target tail4 cross support: {summary['target_tail4_cross_pcx_support']}")
    print(f"Target exact after8 cross support: {summary['target_exact_after8_cross_pcx_support']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
