#!/usr/bin/env python3
"""Combine exact .tex coverage with CDCACHE alias candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import defaultdict
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_augmented_coverage")
DEFAULT_REFERENCES = Path("output/tex_reference_coverage/references.csv")
DEFAULT_ALIAS_PACK = Path("output/cdcache_tex_alias_pack/manifest.csv")
DEFAULT_MATERIAL_DECODE_PACK = Path("output/tex_material_decode_pack/manifest.csv")
DEFAULT_RAW_SAME_ARCHIVE_PROMOTED_PACK = Path("output/tex_raw_same_archive_promoted_pack/manifest.csv")
DEFAULT_FIELD16_DECODER_PROMOTED_PACK = Path(
    "output/tex_large_shifted_2a30_field16_decoder_promoted_pack/manifest.csv"
)
DEFAULT_BRANCH_HIGH_ARG2_PROMOTED_PACK = Path(
    "output/tex_large_shifted_2a30_branch_high_arg2_promoted_pack/manifest.csv"
)
DEFAULT_SHARED_2700302B_OP4_SEGMENT_RULE_PROMOTED_PACK = Path(
    "output/tex_large_shared_2700302b_op4_segment_rule_promoted_pack/manifest.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "reference_rows",
    "unique_likely_pcx",
    "exact_covered_reference_rows",
    "exact_covered_unique_pcx",
    "alias_reference_rows",
    "alias_unique_pcx",
    "alias_assets",
    "decoded_material_reference_rows",
    "decoded_material_unique_pcx",
    "decoded_material_assets",
    "raw_same_archive_reference_rows",
    "raw_same_archive_unique_pcx",
    "raw_same_archive_assets",
    "field16_decoder_reference_rows",
    "field16_decoder_unique_pcx",
    "field16_decoder_assets",
    "branch_high_arg2_reference_rows",
    "branch_high_arg2_unique_pcx",
    "branch_high_arg2_assets",
    "shared_2700302b_op4_segment_rule_reference_rows",
    "shared_2700302b_op4_segment_rule_unique_pcx",
    "shared_2700302b_op4_segment_rule_assets",
    "exact_or_alias_unique_pcx",
    "exact_alias_or_decoded_unique_pcx",
    "exact_alias_decoded_or_raw_unique_pcx",
    "exact_alias_decoded_raw_or_field16_unique_pcx",
    "exact_alias_decoded_raw_field16_or_branch_unique_pcx",
    "exact_alias_decoded_raw_field16_branch_or_shared2700302b_unique_pcx",
    "unresolved_reference_rows",
    "unresolved_unique_pcx",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "texture_path",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "coverage_status",
    "exact_covered",
    "exact_descriptor_count",
    "alias_assets",
    "alias_kinds",
    "alias_candidate_base_names",
    "alias_pack_paths",
    "decoded_material_assets",
    "decoded_material_pack_paths",
    "raw_same_archive_assets",
    "raw_same_archive_pack_paths",
    "field16_decoder_assets",
    "field16_decoder_pack_paths",
    "branch_high_arg2_assets",
    "branch_high_arg2_pack_paths",
    "shared_2700302b_op4_segment_rule_assets",
    "shared_2700302b_op4_segment_rule_pack_paths",
    "issues",
]

ALIAS_FIELDNAMES = [
    "archive",
    "archive_tag",
    "missing_pcx_name",
    "alias_kind",
    "candidate_pcx_name",
    "candidate_base_name",
    "cache_index",
    "width",
    "height",
    "alias_pack_path",
    "issues",
]

RAW_SAME_ARCHIVE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "review_status",
    "coverage_eligible",
    "promoted_fullhd_path",
    "issues",
]

FIELD16_DECODER_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "texture_path",
    "decoder_rule",
    "decoder_extra",
    "review_status",
    "coverage_eligible",
    "promoted_fullhd_path",
    "issues",
]

BRANCH_HIGH_ARG2_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "texture_path",
    "decoder_rule",
    "decoder_extra",
    "renderer_mode",
    "high_arg2_skips",
    "review_status",
    "coverage_eligible",
    "promoted_fullhd_path",
    "issues",
]

SHARED_2700302B_OP4_SEGMENT_RULE_FIELDNAMES = [
    "asset_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "texture_path",
    "decoder_rule",
    "decoder_extra",
    "selected_condition_id",
    "selected_action",
    "review_status",
    "coverage_eligible",
    "promoted_fullhd_path",
    "issues",
]

DECODED_MATERIAL_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "normalized_pcx_name",
    "material_clean_text",
    "segment_index",
    "body_offset_hex",
    "width",
    "height",
    "skip",
    "structure_score",
    "decoded_fullhd_path",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def aliases_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("archive", ""), normalize_pcx(row.get("missing_pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def decoded_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def raw_promotions_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("coverage_eligible") != "yes":
            continue
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def field16_promotions_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("coverage_eligible") != "yes":
            continue
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def branch_promotions_by_archive_name(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("coverage_eligible") != "yes":
            continue
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def shared_2700302b_promotions_by_archive_name(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("coverage_eligible") != "yes":
            continue
        key = (row.get("archive", ""), normalize_pcx(row.get("normalized_pcx_name", "") or row.get("pcx_name", "")))
        if key[0] and key[1]:
            output[key].append(row)
    return output


def read_optional_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_rows(path)


def build_rows(
    references: list[dict[str, str]],
    aliases: list[dict[str, str]],
    decoded_materials: list[dict[str, str]],
    raw_promotions: list[dict[str, str]],
    field16_promotions: list[dict[str, str]],
    branch_promotions: list[dict[str, str]],
    shared_2700302b_promotions: list[dict[str, str]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    alias_lookup = aliases_by_archive_name(aliases)
    decoded_lookup = decoded_by_archive_name(decoded_materials)
    raw_lookup = raw_promotions_by_archive_name(raw_promotions)
    field16_lookup = field16_promotions_by_archive_name(field16_promotions)
    branch_lookup = branch_promotions_by_archive_name(branch_promotions)
    shared_2700302b_lookup = shared_2700302b_promotions_by_archive_name(shared_2700302b_promotions)
    rows: list[dict[str, str]] = []
    alias_rows: list[dict[str, str]] = []
    decoded_rows: list[dict[str, str]] = []
    raw_rows: list[dict[str, str]] = []
    field16_rows: list[dict[str, str]] = []
    branch_rows: list[dict[str, str]] = []
    shared_2700302b_rows: list[dict[str, str]] = []
    for reference in references:
        archive = reference.get("archive", "")
        name = normalize_pcx(reference.get("normalized_pcx_name", "") or reference.get("pcx_name", ""))
        exact_covered = reference.get("covered") == "yes"
        matching_aliases = alias_lookup.get((archive, name), [])
        matching_decoded = decoded_lookup.get((archive, name), [])
        matching_raw = raw_lookup.get((archive, name), [])
        matching_field16 = field16_lookup.get((archive, name), [])
        matching_branch = branch_lookup.get((archive, name), [])
        matching_shared_2700302b = shared_2700302b_lookup.get((archive, name), [])
        issues = []
        for alias in matching_aliases:
            if alias.get("issues"):
                issues.append("alias_has_issues")
            if alias.get("alias_exists") != "yes" or not Path(alias.get("alias_pack_path", "")).exists():
                issues.append("missing_alias_pack_path")
        for decoded in matching_decoded:
            if decoded.get("issues"):
                issues.append("decoded_material_has_issues")
            if decoded.get("decoded_fullhd_exists") != "yes" or not Path(decoded.get("decoded_fullhd_path", "")).exists():
                issues.append("missing_decoded_material_path")
        for raw in matching_raw:
            if raw.get("issues"):
                issues.append("raw_same_archive_has_issues")
            if raw.get("promoted_fullhd_exists") != "yes" or not Path(raw.get("promoted_fullhd_path", "")).exists():
                issues.append("missing_raw_same_archive_path")
        for field16 in matching_field16:
            if field16.get("issues"):
                issues.append("field16_decoder_has_issues")
            if field16.get("promoted_fullhd_exists") != "yes" or not Path(field16.get("promoted_fullhd_path", "")).exists():
                issues.append("missing_field16_decoder_path")
        for branch in matching_branch:
            if branch.get("issues"):
                issues.append("branch_high_arg2_has_issues")
            if branch.get("promoted_fullhd_exists") != "yes" or not Path(branch.get("promoted_fullhd_path", "")).exists():
                issues.append("missing_branch_high_arg2_path")
        for shared in matching_shared_2700302b:
            if shared.get("issues"):
                issues.append("shared_2700302b_op4_segment_rule_has_issues")
            if shared.get("promoted_fullhd_exists") != "yes" or not Path(shared.get("promoted_fullhd_path", "")).exists():
                issues.append("missing_shared_2700302b_op4_segment_rule_path")
        if exact_covered:
            status = "exact"
        elif matching_aliases:
            status = "alias"
        elif matching_decoded:
            status = "decoded_material"
        elif matching_field16:
            status = "field16_decoder"
        elif matching_branch:
            status = "branch_high_arg2"
        elif matching_shared_2700302b:
            status = "shared_2700302b_op4_segment_rule"
        elif matching_raw:
            status = "raw_same_archive"
        else:
            status = "unresolved"
        rows.append(
            {
                "texture_path": reference.get("texture_path", ""),
                "archive": archive,
                "archive_tag": reference.get("archive_tag", ""),
                "pcx_name": reference.get("pcx_name", ""),
                "normalized_pcx_name": name,
                "coverage_status": status,
                "exact_covered": "yes" if exact_covered else "no",
                "exact_descriptor_count": reference.get("descriptor_count", ""),
                "alias_assets": str(len(matching_aliases)),
                "alias_kinds": ";".join(sorted({row.get("alias_kind", "") for row in matching_aliases if row.get("alias_kind")})),
                "alias_candidate_base_names": ";".join(
                    sorted({row.get("candidate_base_name", "") for row in matching_aliases if row.get("candidate_base_name")})
                ),
                "alias_pack_paths": ";".join(row.get("alias_pack_path", "") for row in matching_aliases),
                "decoded_material_assets": str(len(matching_decoded)),
                "decoded_material_pack_paths": ";".join(
                    row.get("decoded_fullhd_path", "") for row in matching_decoded
                ),
                "raw_same_archive_assets": str(len(matching_raw)),
                "raw_same_archive_pack_paths": ";".join(
                    row.get("promoted_fullhd_path", "") for row in matching_raw
                ),
                "field16_decoder_assets": str(len(matching_field16)),
                "field16_decoder_pack_paths": ";".join(
                    row.get("promoted_fullhd_path", "") for row in matching_field16
                ),
                "branch_high_arg2_assets": str(len(matching_branch)),
                "branch_high_arg2_pack_paths": ";".join(
                    row.get("promoted_fullhd_path", "") for row in matching_branch
                ),
                "shared_2700302b_op4_segment_rule_assets": str(len(matching_shared_2700302b)),
                "shared_2700302b_op4_segment_rule_pack_paths": ";".join(
                    row.get("promoted_fullhd_path", "") for row in matching_shared_2700302b
                ),
                "issues": ";".join(sorted(set(issues))),
            }
        )

    for alias in aliases:
        alias_rows.append(
            {
                "archive": alias.get("archive", ""),
                "archive_tag": alias.get("archive_tag", ""),
                "missing_pcx_name": alias.get("missing_pcx_name", ""),
                "alias_kind": alias.get("alias_kind", ""),
                "candidate_pcx_name": alias.get("candidate_pcx_name", ""),
                "candidate_base_name": alias.get("candidate_base_name", ""),
                "cache_index": alias.get("cache_index", ""),
                "width": alias.get("width", ""),
                "height": alias.get("height", ""),
                "alias_pack_path": alias.get("alias_pack_path", ""),
                "issues": alias.get("issues", ""),
            }
        )

    for decoded in decoded_materials:
        decoded_rows.append(
            {
                "archive": decoded.get("archive", ""),
                "archive_tag": decoded.get("archive_tag", ""),
                "pcx_name": decoded.get("pcx_name", ""),
                "normalized_pcx_name": decoded.get("normalized_pcx_name", ""),
                "material_clean_text": decoded.get("material_clean_text", ""),
                "segment_index": decoded.get("segment_index", ""),
                "body_offset_hex": decoded.get("body_offset_hex", ""),
                "width": decoded.get("width", ""),
                "height": decoded.get("height", ""),
                "skip": decoded.get("skip", ""),
                "structure_score": decoded.get("structure_score", ""),
                "decoded_fullhd_path": decoded.get("decoded_fullhd_path", ""),
                "issues": decoded.get("issues", ""),
            }
        )

    for raw in raw_promotions:
        raw_rows.append(
            {
                "archive": raw.get("archive", ""),
                "archive_tag": raw.get("archive_tag", ""),
                "pcx_name": raw.get("pcx_name", ""),
                "normalized_pcx_name": raw.get("normalized_pcx_name", ""),
                "review_status": raw.get("review_status", ""),
                "coverage_eligible": raw.get("coverage_eligible", ""),
                "promoted_fullhd_path": raw.get("promoted_fullhd_path", ""),
                "issues": raw.get("issues", ""),
            }
        )

    for field16 in field16_promotions:
        field16_rows.append(
            {
                "asset_id": field16.get("asset_id", ""),
                "archive": field16.get("archive", ""),
                "archive_tag": field16.get("archive_tag", ""),
                "pcx_name": field16.get("pcx_name", ""),
                "normalized_pcx_name": field16.get("normalized_pcx_name", ""),
                "texture_path": field16.get("texture_path", ""),
                "decoder_rule": field16.get("decoder_rule", ""),
                "decoder_extra": field16.get("decoder_extra", ""),
                "review_status": field16.get("review_status", ""),
                "coverage_eligible": field16.get("coverage_eligible", ""),
                "promoted_fullhd_path": field16.get("promoted_fullhd_path", ""),
                "issues": field16.get("issues", ""),
            }
        )

    for branch in branch_promotions:
        branch_rows.append(
            {
                "asset_id": branch.get("asset_id", ""),
                "archive": branch.get("archive", ""),
                "archive_tag": branch.get("archive_tag", ""),
                "pcx_name": branch.get("pcx_name", ""),
                "normalized_pcx_name": branch.get("normalized_pcx_name", ""),
                "texture_path": branch.get("texture_path", ""),
                "decoder_rule": branch.get("decoder_rule", ""),
                "decoder_extra": branch.get("decoder_extra", ""),
                "renderer_mode": branch.get("renderer_mode", ""),
                "high_arg2_skips": branch.get("high_arg2_skips", ""),
                "review_status": branch.get("review_status", ""),
                "coverage_eligible": branch.get("coverage_eligible", ""),
                "promoted_fullhd_path": branch.get("promoted_fullhd_path", ""),
                "issues": branch.get("issues", ""),
            }
        )

    for shared in shared_2700302b_promotions:
        shared_2700302b_rows.append(
            {
                "asset_id": shared.get("asset_id", ""),
                "archive": shared.get("archive", ""),
                "archive_tag": shared.get("archive_tag", ""),
                "pcx_name": shared.get("pcx_name", ""),
                "normalized_pcx_name": shared.get("normalized_pcx_name", ""),
                "texture_path": shared.get("texture_path", ""),
                "decoder_rule": shared.get("decoder_rule", ""),
                "decoder_extra": shared.get("decoder_extra", ""),
                "selected_condition_id": shared.get("selected_condition_id", ""),
                "selected_action": shared.get("selected_action", ""),
                "review_status": shared.get("review_status", ""),
                "coverage_eligible": shared.get("coverage_eligible", ""),
                "promoted_fullhd_path": shared.get("promoted_fullhd_path", ""),
                "issues": shared.get("issues", ""),
            }
        )
    return rows, alias_rows, decoded_rows, raw_rows, field16_rows, branch_rows, shared_2700302b_rows


def summary_row(
    rows: list[dict[str, str]],
    aliases: list[dict[str, str]],
    decoded_materials: list[dict[str, str]],
    raw_promotions: list[dict[str, str]],
    field16_promotions: list[dict[str, str]],
    branch_promotions: list[dict[str, str]],
    shared_2700302b_promotions: list[dict[str, str]],
) -> dict[str, str]:
    unique_names = {row["normalized_pcx_name"] for row in rows}
    exact_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "exact"}
    alias_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "alias"}
    decoded_names = {
        row["normalized_pcx_name"]
        for row in rows
        if row["coverage_status"] == "decoded_material"
    }
    raw_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "raw_same_archive"}
    field16_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "field16_decoder"}
    branch_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "branch_high_arg2"}
    shared_2700302b_names = {
        row["normalized_pcx_name"]
        for row in rows
        if row["coverage_status"] == "shared_2700302b_op4_segment_rule"
    }
    unresolved_names = {row["normalized_pcx_name"] for row in rows if row["coverage_status"] == "unresolved"}
    eligible_raw = [row for row in raw_promotions if row.get("coverage_eligible") == "yes"]
    eligible_field16 = [row for row in field16_promotions if row.get("coverage_eligible") == "yes"]
    eligible_branch = [row for row in branch_promotions if row.get("coverage_eligible") == "yes"]
    eligible_shared_2700302b = [
        row for row in shared_2700302b_promotions if row.get("coverage_eligible") == "yes"
    ]
    return {
        "scope": "total",
        "reference_rows": str(len(rows)),
        "unique_likely_pcx": str(len(unique_names)),
        "exact_covered_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "exact")),
        "exact_covered_unique_pcx": str(len(exact_names)),
        "alias_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "alias")),
        "alias_unique_pcx": str(len(alias_names)),
        "alias_assets": str(len(aliases)),
        "decoded_material_reference_rows": str(
            sum(1 for row in rows if row["coverage_status"] == "decoded_material")
        ),
        "decoded_material_unique_pcx": str(len(decoded_names)),
        "decoded_material_assets": str(len(decoded_materials)),
        "raw_same_archive_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "raw_same_archive")),
        "raw_same_archive_unique_pcx": str(len(raw_names)),
        "raw_same_archive_assets": str(len(eligible_raw)),
        "field16_decoder_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "field16_decoder")),
        "field16_decoder_unique_pcx": str(len(field16_names)),
        "field16_decoder_assets": str(len(eligible_field16)),
        "branch_high_arg2_reference_rows": str(
            sum(1 for row in rows if row["coverage_status"] == "branch_high_arg2")
        ),
        "branch_high_arg2_unique_pcx": str(len(branch_names)),
        "branch_high_arg2_assets": str(len(eligible_branch)),
        "shared_2700302b_op4_segment_rule_reference_rows": str(
            sum(1 for row in rows if row["coverage_status"] == "shared_2700302b_op4_segment_rule")
        ),
        "shared_2700302b_op4_segment_rule_unique_pcx": str(len(shared_2700302b_names)),
        "shared_2700302b_op4_segment_rule_assets": str(len(eligible_shared_2700302b)),
        "exact_or_alias_unique_pcx": str(len(exact_names | alias_names)),
        "exact_alias_or_decoded_unique_pcx": str(len(exact_names | alias_names | decoded_names)),
        "exact_alias_decoded_or_raw_unique_pcx": str(len(exact_names | alias_names | decoded_names | raw_names)),
        "exact_alias_decoded_raw_or_field16_unique_pcx": str(
            len(exact_names | alias_names | decoded_names | raw_names | field16_names)
        ),
        "exact_alias_decoded_raw_field16_or_branch_unique_pcx": str(
            len(exact_names | alias_names | decoded_names | raw_names | field16_names | branch_names)
        ),
        "exact_alias_decoded_raw_field16_branch_or_shared2700302b_unique_pcx": str(
            len(exact_names | alias_names | decoded_names | raw_names | field16_names | branch_names | shared_2700302b_names)
        ),
        "unresolved_reference_rows": str(sum(1 for row in rows if row["coverage_status"] == "unresolved")),
        "unresolved_unique_pcx": str(len(unresolved_names)),
        "issue_rows": str(
            sum(1 for row in rows if row["issues"])
            + sum(1 for row in aliases if row["issues"])
            + sum(1 for row in decoded_materials if row.get("issues"))
            + sum(1 for row in eligible_raw if row.get("issues"))
            + sum(1 for row in eligible_field16 if row.get("issues"))
            + sum(1 for row in eligible_branch if row.get("issues"))
            + sum(1 for row in eligible_shared_2700302b if row.get("issues"))
        ),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    aliases: list[dict[str, str]],
    decoded_materials: list[dict[str, str]],
    raw_promotions: list[dict[str, str]],
    field16_promotions: list[dict[str, str]],
    branch_promotions: list[dict[str, str]],
    shared_2700302b_promotions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "references": rows,
        "aliases": aliases,
        "decoded_materials": decoded_materials,
        "raw_same_archive_promotions": raw_promotions,
        "field16_decoder_promotions": field16_promotions,
        "branch_high_arg2_promotions": branch_promotions,
        "shared_2700302b_op4_segment_rule_promotions": shared_2700302b_promotions,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("references.csv", output_dir / "references.csv"),
            ("aliases.csv", output_dir / "aliases.csv"),
            ("material_decodes.csv", output_dir / "material_decodes.csv"),
            ("raw_same_archive_promotions.csv", output_dir / "raw_same_archive_promotions.csv"),
            ("field16_decoder_promotions.csv", output_dir / "field16_decoder_promotions.csv"),
            ("branch_high_arg2_promotions.csv", output_dir / "branch_high_arg2_promotions.csv"),
            (
                "shared_2700302b_op4_segment_rule_promotions.csv",
                output_dir / "shared_2700302b_op4_segment_rule_promotions.csv",
            ),
        )
    )
    alias_rows = [row for row in rows if row["coverage_status"] == "alias"]
    decoded_rows = [row for row in rows if row["coverage_status"] == "decoded_material"]
    raw_rows = [row for row in rows if row["coverage_status"] == "raw_same_archive"]
    field16_rows = [row for row in rows if row["coverage_status"] == "field16_decoder"]
    branch_rows = [row for row in rows if row["coverage_status"] == "branch_high_arg2"]
    shared_2700302b_rows = [
        row for row in rows if row["coverage_status"] == "shared_2700302b_op4_segment_rule"
    ]
    unresolved_rows = [row for row in rows if row["coverage_status"] == "unresolved"]
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
  --warn: #f0b06a;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1200px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Exact unique</div><div class="value ok">{html.escape(summary['exact_covered_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Alias unique</div><div class="value">{html.escape(summary['alias_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Decodes materiaux</div><div class="value">{html.escape(summary['decoded_material_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Raw same-archive</div><div class="value">{html.escape(summary['raw_same_archive_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Field16 decoder</div><div class="value">{html.escape(summary['field16_decoder_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Branch high-arg2</div><div class="value">{html.escape(summary['branch_high_arg2_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">2700302b OP4</div><div class="value">{html.escape(summary['shared_2700302b_op4_segment_rule_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Couverts augmentes</div><div class="value">{html.escape(summary['exact_alias_decoded_raw_field16_branch_or_shared2700302b_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Restants</div><div class="value warn">{html.escape(summary['unresolved_unique_pcx'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Fichiers</h2>
    <div>{links}</div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References avec alias</h2>
    {render_table(alias_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References decodees materiaux</h2>
    {render_table(decoded_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References raw same-archive promues</h2>
    {render_table(raw_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References field16 decoder promues</h2>
    {render_table(field16_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References branch high-arg2 promues</h2>
    {render_table(branch_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References 2700302b OP4 par segment promues</h2>
    {render_table(shared_2700302b_rows, ROW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>References restantes</h2>
    {render_table(unresolved_rows, ROW_FIELDNAMES)}
  </section>
</main>
<script>
const TEX_AUGMENTED_COVERAGE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    references_path: Path,
    alias_pack_path: Path,
    material_decode_pack_path: Path,
    raw_same_archive_promoted_pack_path: Path,
    field16_decoder_promoted_pack_path: Path,
    branch_high_arg2_promoted_pack_path: Path,
    shared_2700302b_op4_segment_rule_promoted_pack_path: Path,
    title: str,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, aliases, decoded_materials, raw_promotions, field16_promotions, branch_promotions, shared_2700302b = build_rows(
        read_rows(references_path),
        read_rows(alias_pack_path),
        read_optional_rows(material_decode_pack_path),
        read_optional_rows(raw_same_archive_promoted_pack_path),
        read_optional_rows(field16_decoder_promoted_pack_path),
        read_optional_rows(branch_high_arg2_promoted_pack_path),
        read_optional_rows(shared_2700302b_op4_segment_rule_promoted_pack_path),
    )
    summary = summary_row(
        rows,
        aliases,
        decoded_materials,
        raw_promotions,
        field16_promotions,
        branch_promotions,
        shared_2700302b,
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "references.csv", ROW_FIELDNAMES, rows)
    write_csv(output_dir / "aliases.csv", ALIAS_FIELDNAMES, aliases)
    write_csv(output_dir / "material_decodes.csv", DECODED_MATERIAL_FIELDNAMES, decoded_materials)
    write_csv(output_dir / "raw_same_archive_promotions.csv", RAW_SAME_ARCHIVE_FIELDNAMES, raw_promotions)
    write_csv(output_dir / "field16_decoder_promotions.csv", FIELD16_DECODER_FIELDNAMES, field16_promotions)
    write_csv(output_dir / "branch_high_arg2_promotions.csv", BRANCH_HIGH_ARG2_FIELDNAMES, branch_promotions)
    write_csv(
        output_dir / "shared_2700302b_op4_segment_rule_promotions.csv",
        SHARED_2700302B_OP4_SEGMENT_RULE_FIELDNAMES,
        shared_2700302b,
    )
    (output_dir / "index.html").write_text(
        build_html(
            summary,
            rows,
            aliases,
            decoded_materials,
            raw_promotions,
            field16_promotions,
            branch_promotions,
            shared_2700302b,
            output_dir,
            title,
        )
    )
    return summary, rows, aliases, decoded_materials, raw_promotions, field16_promotions, branch_promotions, shared_2700302b


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine exact .tex reference coverage with alias candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    parser.add_argument("--alias-pack", type=Path, default=DEFAULT_ALIAS_PACK)
    parser.add_argument("--material-decode-pack", type=Path, default=DEFAULT_MATERIAL_DECODE_PACK)
    parser.add_argument("--raw-same-archive-promoted-pack", type=Path, default=DEFAULT_RAW_SAME_ARCHIVE_PROMOTED_PACK)
    parser.add_argument("--field16-decoder-promoted-pack", type=Path, default=DEFAULT_FIELD16_DECODER_PROMOTED_PACK)
    parser.add_argument("--branch-high-arg2-promoted-pack", type=Path, default=DEFAULT_BRANCH_HIGH_ARG2_PROMOTED_PACK)
    parser.add_argument(
        "--shared-2700302b-op4-segment-rule-promoted-pack",
        type=Path,
        default=DEFAULT_SHARED_2700302B_OP4_SEGMENT_RULE_PROMOTED_PACK,
    )
    parser.add_argument("--title", default="Lands of Lore II .tex Augmented Coverage")
    args = parser.parse_args()

    summary, _rows, _aliases, _decoded, _raw, _field16, _branch, _shared_2700302b = write_report(
        args.output,
        args.references,
        args.alias_pack,
        args.material_decode_pack,
        args.raw_same_archive_promoted_pack,
        args.field16_decoder_promoted_pack,
        args.branch_high_arg2_promoted_pack,
        args.shared_2700302b_op4_segment_rule_promoted_pack,
        args.title,
    )
    print(f"Unique likely PCX: {summary['unique_likely_pcx']}")
    print(
        "Exact/alias/decoded/raw/field16/branch/2700302b/unresolved unique: "
        f"{summary['exact_covered_unique_pcx']}/"
        f"{summary['alias_unique_pcx']}/"
        f"{summary['decoded_material_unique_pcx']}/"
        f"{summary['raw_same_archive_unique_pcx']}/"
        f"{summary['field16_decoder_unique_pcx']}/"
        f"{summary['branch_high_arg2_unique_pcx']}/"
        f"{summary['shared_2700302b_op4_segment_rule_unique_pcx']}/"
        f"{summary['unresolved_unique_pcx']}"
    )
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
