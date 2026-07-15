#!/usr/bin/env python3
import argparse
import csv
import struct
from collections import Counter
from pathlib import Path


MARKERS = (b"\x27\x30", b"\x28\x30", b"\x29\x30", b"\x2a\x30", b"\x2b\x30", b"\x2b\x31")


def load_rows(catalog, level=None):
    grouped = {}
    with catalog.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            source = Path(row["source"])
            if level and source.parent.name.lower() != level.lower():
                continue
            row["offset"] = int(row["offset"])
            row["source_path"] = source
            grouped.setdefault(source, []).append(row)
    for source_rows in grouped.values():
        source_rows.sort(key=lambda item: item["offset"])
        for index, row in enumerate(source_rows):
            row["next_offset"] = source_rows[index + 1]["offset"] if index + 1 < len(source_rows) else None
            yield row


def bounded_payload(row):
    data = row["source_path"].read_bytes()
    name = row["name"].encode("latin1")
    start = row["offset"] + len(name) + 1
    end = row["next_offset"] if row["next_offset"] is not None else len(data)
    return data[start:end]


def hex_bytes(data, limit):
    return data[:limit].hex(" ")


def marker_summary(data, limit):
    hits = []
    sample = data[:limit]
    for marker in MARKERS:
        pos = sample.find(marker)
        if pos >= 0:
            hits.append(f"{marker.hex()}@{pos}")
    return ",".join(hits)


def likely_u16s(data, limit):
    values = []
    for pos in range(0, min(len(data), limit) - 1, 2):
        value = struct.unpack_from("<H", data, pos)[0]
        if 0 < value <= 2048:
            values.append(f"{pos}:{value}")
    return ",".join(values[:24])


def byte_buckets(data, limit):
    sample = data[:limit]
    counts = Counter()
    for byte in sample:
        if byte == 0:
            counts["zero"] += 1
        elif byte < 0x20:
            counts["low"] += 1
        elif byte < 0x30:
            counts["cmd"] += 1
        elif byte <= 0xBF:
            counts["pixelish"] += 1
        else:
            counts["high"] += 1
    total = max(1, len(sample))
    return " ".join(f"{key}:{counts[key] / total:.3f}" for key in ("zero", "low", "cmd", "pixelish", "high"))


def write_report(rows, out_path, sample):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "level",
            "name",
            "offset",
            "payload_len",
            "first_bytes",
            "markers",
            "u16_candidates",
            "buckets",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            if row["ext"] != ".pcx" or row["name"].lower() == "palette.pcx":
                continue
            payload = bounded_payload(row)
            writer.writerow(
                {
                    "level": row["source_path"].parent.name,
                    "name": row["name"],
                    "offset": f"{row['offset']:08x}",
                    "payload_len": len(payload),
                    "first_bytes": hex_bytes(payload, 24),
                    "markers": marker_summary(payload, sample),
                    "u16_candidates": likely_u16s(payload, 48),
                    "buckets": byte_buckets(payload, sample),
                }
            )


def main():
    parser = argparse.ArgumentParser(description="Analyze bounded TE PCX payload bytes for command/header clues.")
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("-o", "--out", type=Path, default=Path("reports/te_pcx_payloads.tsv"))
    parser.add_argument("--level")
    parser.add_argument("--sample", type=int, default=512)
    args = parser.parse_args()

    rows = list(load_rows(args.catalog, args.level))
    write_report(rows, args.out, args.sample)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
