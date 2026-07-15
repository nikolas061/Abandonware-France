#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from analyze_te_pcx_payloads import MARKERS


def load_rows(catalog, level=None, names=None):
    wanted = {name.lower() for name in names or []}
    with catalog.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["ext"] != ".pcx" or row["name"].lower() == "palette.pcx":
                continue
            source = Path(row["source"])
            if level and source.parent.name.lower() != level.lower():
                continue
            if wanted and row["name"].lower() not in wanted:
                continue
            row["offset"] = int(row["offset"])
            row["source_path"] = source
            yield row


def payload_after_name(row, limit):
    data = row["source_path"].read_bytes()
    name = row["name"].encode("latin1")
    start = row["offset"] + len(name) + 1
    return data[start : start + limit]


def marker_offset(payload, search):
    best = None
    for marker in MARKERS:
        pos = payload[:search].find(marker)
        if pos < 0:
            continue
        if best is None or pos < best:
            best = pos
    return best


def row_score(data, width, height):
    needed = width * height
    if len(data) < needed:
        return None
    sample = data[:needed]
    transitions = 0
    lowish = 0
    seam_delta = 0
    seam_count = 0
    for y in range(height):
        start = y * width
        row = sample[start : start + width]
        lowish += sum(1 for byte in row if byte < 0x20 or byte >= 0xC0)
        transitions += sum(abs(row[x] - row[x - 1]) for x in range(1, width))
        if y:
            prev = sample[start - width : start]
            seam_delta += sum(abs(row[x] - prev[x]) for x in range(width))
            seam_count += width
    intra = transitions / max(1, height * (width - 1))
    inter = seam_delta / max(1, seam_count)
    weird = lowish / needed
    return intra + inter * 0.65 + weird * 96.0


def main():
    parser = argparse.ArgumentParser(description="Score raw TE PCX layout guesses by simple row continuity metrics.")
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("--level")
    parser.add_argument("--name", action="append", default=[])
    parser.add_argument("--widths", nargs="+", type=int, default=[32, 48, 64, 80, 96, 112, 128, 160, 192, 256])
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--extras", nargs="+", type=int, default=list(range(0, 65, 4)))
    parser.add_argument("--limit", type=int, default=65536)
    parser.add_argument("--search", type=int, default=512)
    parser.add_argument("-o", "--out", type=Path, default=Path("reports/te_raw_layout_scores.tsv"))
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = ["level", "name", "marker_offset", "extra", "width", "height", "score"]
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        for row in load_rows(args.catalog, args.level, args.name):
            payload = payload_after_name(row, args.limit)
            marker = marker_offset(payload, args.search)
            base = marker if marker is not None else 0
            results = []
            for extra in args.extras:
                start = base + extra
                for width in args.widths:
                    score = row_score(payload[start:], width, args.height)
                    if score is None:
                        continue
                    results.append((score, extra, width))
            for score, extra, width in sorted(results)[:12]:
                writer.writerow(
                    {
                        "level": row["source_path"].parent.name,
                        "name": row["name"],
                        "marker_offset": "" if marker is None else marker,
                        "extra": extra,
                        "width": width,
                        "height": args.height,
                        "score": f"{score:.4f}",
                    }
                )
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
