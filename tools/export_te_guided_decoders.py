#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from export_shp import read_palette
from export_te_span_previews import make_sheet, render_indexed, source_payload
from probe_te_span_decode import decode_span


def load_catalog(catalog):
    rows = {}
    with catalog.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["ext"] != ".pcx" or row["name"].lower() == "palette.pcx":
                continue
            source = Path(row["source"])
            row["offset"] = int(row["offset"])
            row["source_path"] = source
            rows[(source.parent.name, row["name"])] = row
    return rows


def load_baseline(path):
    choices = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            key = (row["level"], row["name"])
            choices[key] = {
                "source": "marker",
                "mode": row["mode"],
                "width": int(row["width"]),
                "height": int(row["height"]),
                "extra": int(row["extra"]),
                "start": None,
                "score": float(row["score"]),
                "filled": float(row["filled"]),
            }
    return choices


def apply_width_reports(choices, reports, tolerance, allowed_relations, min_width):
    for path in reports:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                key = (row["level"], row["name"])
                if key not in choices:
                    continue
                if int(row["width"]) < min_width:
                    continue
                relation = row.get("relation", "")
                if allowed_relations and relation and relation not in allowed_relations:
                    continue
                score = float(row["score"])
                if score <= choices[key]["score"] + tolerance:
                    choices[key] = {
                        "source": "width_field",
                        "mode": row["mode"],
                        "width": int(row["width"]),
                        "height": 128,
                        "extra": None,
                        "start": int(row["start"]),
                        "score": score,
                        "filled": float(row["filled"]),
                    }


def payload_after_name(row, start, limit):
    data = row["source_path"].read_bytes()
    name = row["name"].encode("latin1")
    base = row["offset"] + len(name) + 1 + start
    return data[base : base + limit]


def main():
    parser = argparse.ArgumentParser(description="Export TE previews using marker scoring plus width-field guided overrides.")
    parser.add_argument("--baseline", type=Path, default=Path("reports/te_best_decoder_all.tsv"))
    parser.add_argument("--width-report", action="append", type=Path, default=[])
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("-p", "--palette", type=Path, default=Path("extracted/LOCAL/7231c8f9.pal"))
    parser.add_argument("-o", "--out", type=Path, default=Path("previews_te_guided_decoder"))
    parser.add_argument("--sheet", type=Path, default=Path("previews/te_guided_decoder.png"))
    parser.add_argument("--report", type=Path, default=Path("reports/te_guided_decoder.tsv"))
    parser.add_argument("--limit", type=int, default=65536)
    parser.add_argument("--marker-search", type=int, default=512)
    parser.add_argument("--tolerance", type=float, default=0.0001)
    parser.add_argument("--relation", action="append", default=[])
    parser.add_argument("--min-width", type=int, default=1)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    args = parser.parse_args()

    reports = args.width_report or [
        Path("reports/te_width_start_exact.tsv"),
        Path("reports/te_width_start_half.tsv"),
        Path("reports/te_width_start_quarter.tsv"),
    ]
    catalog = load_catalog(args.catalog)
    choices = load_baseline(args.baseline)
    apply_width_reports(choices, reports, args.tolerance, set(args.relation), args.min_width)
    palette = read_palette(args.palette)
    args.out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    sheet_entries = []
    report_rows = []
    for key, choice in sorted(choices.items()):
        row = catalog.get(key)
        if row is None:
            continue
        if choice["source"] == "width_field":
            payload = payload_after_name(row, choice["start"], args.limit)
        else:
            payload = source_payload(row, 0, args.limit, True, choice["extra"], args.marker_search)
        pixels = decode_span(payload, choice["width"], choice["height"], choice["mode"], args.low, args.high)
        image = render_indexed(pixels, choice["width"], choice["height"], palette)
        level, name = key
        safe_name = name.replace("/", "_").replace("\\", "_")
        out_dir = args.out / level
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{row['offset']:08x}_{safe_name}.png"
        image.save(out_path)
        label = f"{level}/{name} {choice['source']} {choice['mode']}"
        sheet_entries.append((label, image))
        report_rows.append(
            {
                "level": level,
                "name": name,
                "source": choice["source"],
                "mode": choice["mode"],
                "width": choice["width"],
                "height": choice["height"],
                "extra": "" if choice["extra"] is None else choice["extra"],
                "start": "" if choice["start"] is None else choice["start"],
                "score": f"{choice['score']:.4f}",
                "filled": f"{choice['filled']:.4f}",
                "out": str(out_path),
            }
        )

    with args.report.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = ["level", "name", "source", "mode", "width", "height", "extra", "start", "score", "filled", "out"]
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    make_sheet(sheet_entries, args.sheet, 6, 128)
    print(f"exported {len(sheet_entries)} guided preview(s) to {args.out}")
    print(f"wrote {args.sheet} and {args.report}")


if __name__ == "__main__":
    main()
