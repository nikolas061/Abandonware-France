#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw

from analyze_te_pcx_payloads import MARKERS
from export_shp import read_palette
from probe_te_span_decode import decode_span


def load_rows(catalog, level=None):
    with catalog.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["ext"] != ".pcx" or row["name"].lower() == "palette.pcx":
                continue
            source = Path(row["source"])
            if level and source.parent.name.lower() != level.lower():
                continue
            row["offset"] = int(row["offset"])
            row["source_path"] = source
            yield row


def first_marker_offset(payload, search):
    best = None
    for marker in MARKERS:
        pos = payload[:search].find(marker)
        if pos < 0:
            continue
        if best is None or pos < best:
            best = pos
    return best


def source_payload(row, skip, limit, align_marker, marker_extra, marker_search):
    data = row["source_path"].read_bytes()
    name = row["name"].encode("latin1")
    start = row["offset"] + len(name) + 1 + skip
    payload = data[start : start + limit]
    if align_marker:
        marker_offset = first_marker_offset(payload, marker_search)
        if marker_offset is not None:
            payload = payload[marker_offset + marker_extra :]
    return payload


def render_indexed(pixels, width, height, palette):
    image = Image.new("RGBA", (width, height))
    image.putdata([palette[index] for index in pixels])
    return image


def make_sheet(entries, out_path, columns, thumb_size):
    label_h = 18
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size, max(1, rows) * (thumb_size + label_h)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(entries):
        x = (index % columns) * thumb_size
        y = (index // columns) * (thumb_size + label_h)
        thumb = image.copy()
        thumb.thumbnail((thumb_size, thumb_size), Image.Resampling.NEAREST)
        sheet.paste(thumb.convert("RGB"), (x + (thumb_size - thumb.width) // 2, y))
        draw.text((x + 2, y + thumb_size), label[:24], fill=(230, 230, 230))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def visible_ratio(pixels):
    if not pixels:
        return 0.0
    return sum(1 for pixel in pixels if pixel) / len(pixels)


def main():
    parser = argparse.ArgumentParser(description="Export batch previews from the current best TE span-command probe.")
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("-p", "--palette", type=Path, default=Path("extracted/LOCAL/7231c8f9.pal"))
    parser.add_argument("-o", "--out", type=Path, default=Path("previews_te_span"))
    parser.add_argument("--sheet", type=Path, default=Path("previews/te_span_textures.png"))
    parser.add_argument("--report", type=Path, default=Path("reports/te_span_previews.tsv"))
    parser.add_argument("--level")
    parser.add_argument(
        "--mode",
        default="cmd20_y",
        choices=[
            "raw",
            "filter",
            "low_skip",
            "zero_skip",
            "low_newline",
            "cmd20_y",
            "cmd20_xy",
            "op4_skip1",
            "op4_skip2",
            "op4_xarg",
            "op4_yarg",
            "op4_small_skip1",
            "op4_small_skip2",
            "op4_zero_skip1",
            "cmd20_skip1",
            "cmd20_skip2",
            "cmd20_skip3",
            "cmd20_skip4",
            "cmd20_sig_skip2",
            "cmd20_sig_skip3",
            "cmd20_sig_skip4",
            "cmd20_xskip3",
            "cmd20_sig_xskip3",
            "op4_cmd20_skip1",
            "op4_cmd20_skip2",
            "op4_cmd20_skip3",
            "op4_cmd20_skip4",
            "op4_cmd20_sig_skip2",
            "op4_cmd20_sig_skip3",
            "op4_cmd20_sig_skip4",
            "op4_cmd20_xskip3",
            "op4_cmd20_sig_xskip3",
            "cmd20_setx_skip4",
            "cmd20_setx_line_skip4",
            "cmd20_arg2_dy_skip4",
            "cmd20_arg2_setx_skip4",
            "cmd20_arg2_f0_setx_skip4",
            "cmd20_arg2_safe_dy_skip4",
            "cmd20_arg2_e0_safe_dy_skip4",
            "cmd20_arg2_f0_safe_dy_skip4",
            "cmd20_arg2_f8_safe_dy_skip4",
            "cmd20_arg2_fc_safe_dy_skip4",
            "op4_cmd20_arg2_dy_skip4",
            "op4_cmd20_arg2_e0_safe_dy_skip4",
            "op4_cmd20_arg2_f0_safe_dy_skip4",
            "op4_cmd20_arg2_f8_safe_dy_skip4",
            "op4_cmd20_arg2_fc_safe_dy_skip4",
            "op4arg_setx_cmd20_skip4",
            "op4arg_advance_cmd20_skip4",
            "op4code_advance_cmd20_skip4",
            "op4_emit1_cmd20_skip4",
            "op4_emit1_cmd20_sig_skip4",
        ],
    )
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--limit", type=int, default=65536)
    parser.add_argument("--align-marker", action="store_true")
    parser.add_argument("--marker-extra", type=int, default=4)
    parser.add_argument("--marker-search", type=int, default=512)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--thumb-size", type=int, default=128)
    args = parser.parse_args()

    palette = read_palette(args.palette)
    args.out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    sheet_entries = []
    report_rows = []
    for row in load_rows(args.catalog, args.level):
        payload = source_payload(row, args.skip, args.limit, args.align_marker, args.marker_extra, args.marker_search)
        pixels = decode_span(payload, args.width, args.height, args.mode, args.low, args.high)
        image = render_indexed(pixels, args.width, args.height, palette)
        level = row["source_path"].parent.name
        safe_name = row["name"].replace("/", "_").replace("\\", "_")
        out_dir = args.out / level
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{row['offset']:08x}_{safe_name}.png"
        image.save(out_path)
        label = f"{level}/{row['name']}"
        sheet_entries.append((label, image))
        report_rows.append(
            {
                "level": level,
                "name": row["name"],
                "offset": f"{row['offset']:08x}",
                "out": str(out_path),
                "payload_bytes": len(payload),
                "visible_ratio": f"{visible_ratio(pixels):.4f}",
            }
        )

    with args.report.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            delimiter="\t",
            fieldnames=["level", "name", "offset", "out", "payload_bytes", "visible_ratio"],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    make_sheet(sheet_entries, args.sheet, args.columns, args.thumb_size)
    print(f"exported {len(sheet_entries)} TE span preview(s) to {args.out}")
    print(f"wrote {args.sheet} and {args.report}")


if __name__ == "__main__":
    main()
