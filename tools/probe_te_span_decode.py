#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw

from export_shp import read_palette


def load_rows(catalog, level, names):
    wanted = {name.lower() for name in names or []}
    with catalog.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["ext"] != ".pcx" or row["name"].lower() == "palette.pcx":
                continue
            path = Path(row["source"])
            if level and path.parent.name.lower() != level.lower():
                continue
            if wanted and row["name"].lower() not in wanted:
                continue
            row["offset"] = int(row["offset"])
            yield row


def advance(x, y, width, amount):
    x += amount
    while x >= width:
        x -= width
        y += 1
    return x, y


def put_pixel(pixels, width, height, x, y, value):
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = value


def signed_byte(value):
    return value - 256 if value >= 128 else value


def clamp_cursor(x, y, width, height):
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def arg2_threshold_for_mode(mode):
    if "_fc_" in mode:
        return 0xFC
    if "_f8_" in mode:
        return 0xF8
    if "_f0_" in mode:
        return 0xF0
    if "_e0_" in mode:
        return 0xE0
    return 0xC0


def is_cmd20_arg2_safe_mode(mode):
    return (
        mode.startswith("cmd20_arg2_safe_dy_skip")
        or mode.startswith("cmd20_arg2_e0_safe_dy_skip")
        or mode.startswith("cmd20_arg2_f0_safe_dy_skip")
        or mode.startswith("cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("cmd20_arg2_f8_safe_x_dy_skip")
        or (mode.startswith("cmd20_arg2_f8_safe_x_z") and "_dy_skip" in mode)
        or (mode.startswith("cmd20_arg2_f8_safe_z") and "_dy_skip" in mode)
        or mode.startswith("cmd20_arg2_f8_safe_down_dy_skip")
        or mode.startswith("cmd20_arg2_fc_safe_dy_skip")
        or mode.startswith("cmd20_arg2_fc_safe_x_dy_skip")
        or (mode.startswith("cmd20_arg2_fc_safe_x_z") and "_dy_skip" in mode)
        or (mode.startswith("cmd20_arg2_fc_safe_z") and "_dy_skip" in mode)
        or mode.startswith("cmd20_arg2_fc_safe_down_dy_skip")
        or mode.startswith("op4_cmd20_arg2_e0_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_f0_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_f8_safe_x_dy_skip")
        or (mode.startswith("op4_cmd20_arg2_f8_safe_x_z") and "_dy_skip" in mode)
        or (mode.startswith("op4_cmd20_arg2_f8_safe_z") and "_dy_skip" in mode)
        or mode.startswith("op4_cmd20_arg2_f8_safe_down_dy_skip")
        or mode.startswith("op4_cmd20_arg2_fc_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_fc_safe_x_dy_skip")
        or (mode.startswith("op4_cmd20_arg2_fc_safe_x_z") and "_dy_skip" in mode)
        or (mode.startswith("op4_cmd20_arg2_fc_safe_z") and "_dy_skip" in mode)
        or mode.startswith("op4_cmd20_arg2_fc_safe_down_dy_skip")
        or mode.startswith("op4arg_setx_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4arg_setx_cmd20_arg2_fc_safe_dy_skip")
        or mode.startswith("op4arg_advance_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4arg_advance_cmd20_arg2_fc_safe_dy_skip")
        or mode.startswith("op4code_advance_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4code_advance_cmd20_arg2_fc_safe_dy_skip")
        or mode.startswith("op4code_advance1_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4code_advance1_cmd20_arg2_fc_safe_dy_skip")
    )


def safe_cmd20_x_ok(mode, arg1, width):
    return "safe_x" not in mode or arg1 < width


def safe_cmd20_arg3_ok(mode, arg3):
    if "safe_z" in mode:
        suffix = mode.split("safe_z", 1)[1].split("_", 1)[0]
        if suffix.isdigit():
            return arg3 <= int(suffix)
    return True


def safe_cmd20_next_y(mode, y, arg2):
    dy = signed_byte(arg2)
    if "safe_down_dy" in mode:
        return y - dy
    return y + dy


def is_op4_candidate(byte):
    return 0x40 <= byte <= 0x68 and byte % 4 == 0


def is_marker_pair(first, second):
    return 0x27 <= first <= 0x2B and second in {0x30, 0x31}


def is_known_marker_pair(first, second):
    return (first, second) in {
        (0x27, 0x30),
        (0x28, 0x30),
        (0x29, 0x30),
        (0x2A, 0x30),
        (0x2B, 0x30),
        (0x2B, 0x31),
    }


HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}


def is_cmd20_high_arg2_signature(arg1, arg2, arg3):
    return arg1 is not None and arg2 in HIGH_ARG2_SIGNATURES and arg3 is not None


def is_cmd20_zero_signature(arg1, arg2, arg3):
    return (arg1, arg2, arg3) == (0, 0, 0)


def is_marker_symmetric_header(payload, first, pos):
    return (
        pos + 1 < len(payload)
        and is_known_marker_pair(first, payload[pos])
        and payload[pos + 1] == 0
        and pos + 2 < len(payload)
        and payload[pos + 2] == 0x52 - first
    )


def op4_signature_matches(mode, arg1, arg2, arg3):
    if arg1 is None or arg2 is None or arg3 is None:
        return False
    if mode.startswith("op4lo1_") or mode.startswith("op4lo1s"):
        return arg1 < 0x20
    if mode.startswith("op4lo3_") or mode.startswith("op4lo3s"):
        return arg3 < 0x20
    if mode.startswith("op4lo13_") or mode.startswith("op4lo13s"):
        return arg1 < 0x20 and arg3 < 0x20
    if mode.startswith("op4arg2op_") or mode.startswith("op4arg2ops"):
        return is_op4_candidate(arg2)
    if mode.startswith("op4lo1_arg2op_") or mode.startswith("op4lo1_arg2ops"):
        return arg1 < 0x20 and is_op4_candidate(arg2)
    return False


def is_op4_signature_safe_mode(mode):
    return (
        mode.startswith("op4lo1_cmd20_arg2_")
        or mode.startswith("op4lo3_cmd20_arg2_")
        or mode.startswith("op4lo13_cmd20_arg2_")
        or mode.startswith("op4arg2op_cmd20_arg2_")
        or mode.startswith("op4lo1_arg2op_cmd20_arg2_")
        or mode.startswith("op4lo1s")
        or mode.startswith("op4lo3s")
        or mode.startswith("op4lo13s")
        or mode.startswith("op4arg2ops")
        or mode.startswith("op4lo1_arg2ops")
        or mode.startswith("op4mix_")
    ) and "_cmd20_arg2_" in mode


def op4_signature_skip_args(mode):
    prefix = mode.split("_cmd20_arg2_", 1)[0]
    if prefix.endswith("s2"):
        return 2
    if prefix.endswith("s4"):
        return 4
    return 3


def op4_mix_skip_args(mode, arg1, arg2, arg3):
    if mode.startswith("op4mix_lo13s4_lo1s3_"):
        if op4_signature_matches("op4lo13_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4lo1_", arg1, arg2, arg3):
            return 3
        return 0
    if mode.startswith("op4mix_lo13s4_lo3s4_"):
        if op4_signature_matches("op4lo13_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4lo3_", arg1, arg2, arg3):
            return 4
        return 0
    if mode.startswith("op4mix_lo13s4_arg2ops3_"):
        if op4_signature_matches("op4lo13_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4arg2op_", arg1, arg2, arg3):
            return 3
        return 0
    if mode.startswith("op4mix_lo13s4_lo1s3_arg2ops3_"):
        if op4_signature_matches("op4lo13_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4lo1_", arg1, arg2, arg3):
            return 3
        if op4_signature_matches("op4arg2op_", arg1, arg2, arg3):
            return 3
        return 0
    if mode.startswith("op4mix_lo13s4_lo3s4_arg2ops3_"):
        if op4_signature_matches("op4lo13_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4lo3_", arg1, arg2, arg3):
            return 4
        if op4_signature_matches("op4arg2op_", arg1, arg2, arg3):
            return 3
        return 0
    return 0


def decode_span(payload, width, height, mode, low, high, return_stats=False):
    markerpair_mode = mode.endswith("_markerpair")
    if markerpair_mode:
        mode = mode[: -len("_markerpair")]
    markerknownsymadv_mode = mode.endswith("_markerknownsymadv")
    if markerknownsymadv_mode:
        mode = mode[: -len("_markerknownsymadv")]
    markerknown0adv_mode = mode.endswith("_markerknown0adv")
    if markerknown0adv_mode:
        mode = mode[: -len("_markerknown0adv")]
    markerknownadv_mode = mode.endswith("_markerknownadv")
    if markerknownadv_mode:
        mode = mode[: -len("_markerknownadv")]
    markersymadv_mode = mode.endswith("_markersymadv")
    if markersymadv_mode:
        mode = mode[: -len("_markersymadv")]
    markerknown0_mode = mode.endswith("_markerknown0")
    if markerknown0_mode:
        mode = mode[: -len("_markerknown0")]
    markersym_mode = mode.endswith("_markersym")
    if markersym_mode:
        mode = mode[: -len("_markersym")]
    markerknown_mode = mode.endswith("_markerknown")
    if markerknown_mode:
        mode = mode[: -len("_markerknown")]
    pixels = bytearray(width * height)
    x = y = 0
    pos = 0
    emitted = 0
    high_arg2_skips = 0
    zero_signature_seen = 0
    zero_signature_skipped = 0
    markerknown_skips = 0

    def emit_pixel(value):
        nonlocal x, y, emitted
        put_pixel(pixels, width, height, x, y, value)
        x, y = advance(x, y, width, 1)
        emitted += 1

    while pos < len(payload) and y < height:
        b = payload[pos]
        pos += 1

        if mode == "raw":
            emit_pixel(b)
            continue

        if markerpair_mode and pos < len(payload) and is_marker_pair(b, payload[pos]):
            pos += 1
            continue

        if markerknown_mode and pos < len(payload) and is_known_marker_pair(b, payload[pos]):
            markerknown_skips += 1
            pos += 1
            continue

        if markerknownsymadv_mode and is_marker_symmetric_header(payload, b, pos):
            pos += 1
            x, y = advance(x, y, width, 1)
            continue

        if markerknownsymadv_mode and pos < len(payload) and is_known_marker_pair(b, payload[pos]):
            pos += 1
            continue

        if markerknownadv_mode and pos < len(payload) and is_known_marker_pair(b, payload[pos]):
            pos += 1
            x, y = advance(x, y, width, 1)
            continue

        if (
            markerknown0_mode
            and pos + 1 < len(payload)
            and is_known_marker_pair(b, payload[pos])
            and payload[pos + 1] == 0
        ):
            pos += 1
            continue

        if (
            markerknown0adv_mode
            and pos + 1 < len(payload)
            and is_known_marker_pair(b, payload[pos])
            and payload[pos + 1] == 0
        ):
            pos += 1
            x, y = advance(x, y, width, 1)
            continue

        if markersym_mode and is_marker_symmetric_header(payload, b, pos):
            pos += 1
            continue

        if markersymadv_mode and is_marker_symmetric_header(payload, b, pos):
            pos += 1
            x, y = advance(x, y, width, 1)
            continue

        if mode == "filter":
            if low <= b <= high:
                emit_pixel(b)
            continue

        if mode.startswith("cmd20_high_arg2_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if is_cmd20_high_arg2_signature(arg1, arg2, arg3):
                high_arg2_skips += 1
                pos = min(len(payload), pos + skip)
            elif is_cmd20_zero_signature(arg1, arg2, arg3):
                zero_signature_seen += 1
            continue

        if mode.startswith("cmd20_sig_xskip") and b == 0x20:
            skip = int(mode.rsplit("xskip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if (arg1, arg2, arg3) == (0, 0, 0) or arg2 in {0xFC, 0xFD, 0xFE, 0xFF, 0xE0}:
                x, y = advance(x, y, width, arg1 or 0)
                pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_xskip") and b == 0x20:
            skip = int(mode.rsplit("xskip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            x, y = advance(x, y, width, arg1)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_sig_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if (arg1, arg2, arg3) == (0, 0, 0) or arg2 in {0xFC, 0xFD, 0xFE, 0xFF, 0xE0}:
                pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_cmd20_sig_xskip") and b == 0x20:
            skip = int(mode.rsplit("xskip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if (arg1, arg2, arg3) == (0, 0, 0) or arg2 in {0xFC, 0xFD, 0xFE, 0xFF, 0xE0}:
                x, y = advance(x, y, width, arg1 or 0)
                pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_cmd20_xskip") and b == 0x20:
            skip = int(mode.rsplit("xskip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            x, y = advance(x, y, width, arg1)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_cmd20_sig_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if (arg1, arg2, arg3) == (0, 0, 0) or arg2 in {0xFC, 0xFD, 0xFE, 0xFF, 0xE0}:
                pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_cmd20_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            pos = min(len(payload), pos + skip)
            continue

        if (
            is_op4_signature_safe_mode(mode)
        ) and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if arg2 >= arg2_threshold_for_mode(mode):
                next_y = safe_cmd20_next_y(mode, y, arg2)
                if (
                    0 <= next_y < height
                    and safe_cmd20_x_ok(mode, arg1, width)
                    and safe_cmd20_arg3_ok(mode, arg3)
                ):
                    x, y = arg1 % max(1, width), next_y
            pos = min(len(payload), pos + skip)
            continue

        if (mode.startswith("op4arg_") or mode.startswith("op4code_")) and "cmd20_arg2_" in mode and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            if arg2 >= arg2_threshold_for_mode(mode):
                next_y = y + signed_byte(arg2)
                if 0 <= next_y < height:
                    x, y = arg1 % max(1, width), next_y
            pos = min(len(payload), pos + skip)
            continue

        if (mode.startswith("op4arg_") or mode.startswith("op4code_")) and b == 0x20:
            pos = min(len(payload), pos + 4)
            continue

        if mode.startswith("cmd20_setx_line_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            if pos < len(payload):
                x, y = clamp_cursor(payload[pos] % max(1, width), y + 1, width, height)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_setx_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            if pos < len(payload):
                x = payload[pos] % max(1, width)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_arg2_dy_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            if arg2 >= 0xC0:
                x, y = clamp_cursor(arg1 % max(1, width), y + signed_byte(arg2), width, height)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_arg2_setx_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            if arg2 >= 0xC0:
                x = arg1 % max(1, width)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_arg2_f0_setx_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            if arg2 >= 0xF0:
                x = arg1 % max(1, width)
            pos = min(len(payload), pos + skip)
            continue

        if is_cmd20_arg2_safe_mode(mode) and mode.startswith("cmd20_") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if arg2 >= arg2_threshold_for_mode(mode):
                next_y = safe_cmd20_next_y(mode, y, arg2)
                if (
                    0 <= next_y < height
                    and safe_cmd20_x_ok(mode, arg1, width)
                    and safe_cmd20_arg3_ok(mode, arg3)
                ):
                    x, y = arg1 % max(1, width), next_y
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("cmd20_arg2_safe_dy_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if arg2 >= 0xC0:
                next_y = safe_cmd20_next_y(mode, y, arg2)
                if 0 <= next_y < height and safe_cmd20_arg3_ok(mode, arg3):
                    x, y = arg1 % max(1, width), next_y
            pos = min(len(payload), pos + skip)
            continue

        if is_cmd20_arg2_safe_mode(mode) and mode.startswith("op4_cmd20_") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else 0
            if arg2 >= arg2_threshold_for_mode(mode):
                next_y = safe_cmd20_next_y(mode, y, arg2)
                if (
                    0 <= next_y < height
                    and safe_cmd20_x_ok(mode, arg1, width)
                    and safe_cmd20_arg3_ok(mode, arg3)
                ):
                    x, y = arg1 % max(1, width), next_y
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_cmd20_arg2_dy_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else 0
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else 0
            if arg2 >= 0xC0:
                x, y = clamp_cursor(arg1 % max(1, width), y + signed_byte(arg2), width, height)
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_emit1_cmd20_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            pos = min(len(payload), pos + skip)
            continue

        if mode.startswith("op4_emit1_cmd20_sig_skip") and b == 0x20:
            skip = int(mode.rsplit("skip", 1)[1])
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if (arg1, arg2, arg3) == (0, 0, 0) or arg2 in {0xFC, 0xFD, 0xFE, 0xFF, 0xE0}:
                pos = min(len(payload), pos + skip)
            continue

        if mode == "low_skip":
            if b < low:
                x, y = advance(x, y, width, b)
                continue
        elif mode == "zero_skip":
            if b == 0 and pos < len(payload):
                x, y = advance(x, y, width, payload[pos])
                pos += 1
                continue
            if b < low:
                continue
        elif mode == "low_newline":
            if b < low:
                y += 1
                x = b
                continue
        elif mode == "cmd20_y":
            if b == 0x20 and pos < len(payload):
                y = min(height - 1, payload[pos])
                x = 0
                pos += 1
                continue
            if b < low:
                continue
        elif mode == "cmd20_xy":
            if b == 0x20 and pos + 1 < len(payload):
                y = min(height - 1, payload[pos])
                x = min(width - 1, payload[pos + 1])
                pos += 2
                continue
            if b < low:
                continue
        elif mode == "op4_skip1":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload):
                pos += 1
                continue
        elif mode == "op4_skip2":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos + 1 < len(payload):
                pos += 2
                continue
        elif mode == "op4_xarg":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload):
                x = min(width - 1, payload[pos] % max(1, width))
                pos += 1
                continue
        elif mode == "op4_yarg":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload):
                y = min(height - 1, payload[pos])
                x = 0
                pos += 1
                continue
        elif mode == "op4_small_skip1":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload) and payload[pos] < 0x20:
                pos += 1
                continue
        elif mode == "op4_small_skip2":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos + 1 < len(payload) and payload[pos] < 0x20:
                pos += 2
                continue
        elif mode == "op4_zero_skip1":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload) and payload[pos] == 0:
                pos += 1
                continue
        elif mode == "op4_cmd20_skip1":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos < len(payload):
                pos += 1
                continue
        elif mode == "op4_cmd20_skip2":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos + 1 < len(payload):
                pos += 2
                continue
        elif mode == "op4_cmd20_skip3":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif mode == "op4_cmd20_skip4":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif mode == "op4_cmd20_sig_skip2":
            if 0x40 <= b <= 0x68 and b % 4 == 0 and pos + 1 < len(payload):
                pos += 2
                continue
        elif mode == "op4_cmd20_sig_skip3":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif mode == "op4_cmd20_sig_skip4":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif mode == "op4_cmd20_xskip3":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif mode == "op4_cmd20_sig_xskip3":
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                pos = min(len(payload), pos + 3)
                continue
        elif (
            mode.startswith("op4_cmd20_arg2_dy_skip")
            or mode.startswith("op4_cmd20_arg2_e0_safe_dy_skip")
            or mode.startswith("op4_cmd20_arg2_f0_safe_dy_skip")
            or mode.startswith("op4_cmd20_arg2_f8_safe_dy_skip")
            or mode.startswith("op4_cmd20_arg2_fc_safe_dy_skip")
        ):
            if is_op4_candidate(b):
                pos = min(len(payload), pos + 3)
                continue
        elif (
            is_op4_signature_safe_mode(mode)
        ):
            arg1 = payload[pos] if pos < len(payload) else None
            arg2 = payload[pos + 1] if pos + 1 < len(payload) else None
            arg3 = payload[pos + 2] if pos + 2 < len(payload) else None
            if is_op4_candidate(b):
                skip_args = op4_mix_skip_args(mode, arg1, arg2, arg3) if mode.startswith("op4mix_") else 0
                if skip_args == 0 and op4_signature_matches(mode, arg1, arg2, arg3):
                    skip_args = op4_signature_skip_args(mode)
                if skip_args:
                    pos = min(len(payload), pos + skip_args)
                    continue
        elif mode.startswith("op4arg_setx_cmd20_skip"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload):
                    x = payload[pos] % max(1, width)
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4arg_advance_cmd20_skip"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload):
                    x, y = advance(x, y, width, payload[pos])
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4code_advance_cmd20_skip"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                x, y = advance(x, y, width, (b - 0x40) // 4)
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4arg_setx_cmd20_arg2"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload):
                    x = payload[pos] % max(1, width)
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4arg_advance_cmd20_arg2"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload):
                    x, y = advance(x, y, width, payload[pos])
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4code_advance_cmd20_arg2"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                x, y = advance(x, y, width, (b - 0x40) // 4)
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4code_advance1_cmd20_arg2"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                x, y = advance(x, y, width, ((b - 0x40) // 4) + 1)
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4_emit1_cmd20_skip"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload) and low <= payload[pos] <= high:
                    emit_pixel(payload[pos])
                pos = min(len(payload), pos + 3)
                continue
        elif mode.startswith("op4_emit1_cmd20_sig_skip"):
            if 0x40 <= b <= 0x68 and b % 4 == 0:
                if pos < len(payload) and low <= payload[pos] <= high:
                    emit_pixel(payload[pos])
                pos = min(len(payload), pos + 3)
                continue

        if low <= b <= high:
            emit_pixel(b)
    result = bytes(pixels)
    if return_stats:
        return result, {
            "emitted": emitted,
            "overdraw": emitted / max(1, width * height),
            "final_x": x,
            "final_y": y,
            "high_arg2_skips": high_arg2_skips,
            "zero_signature_seen": zero_signature_seen,
            "zero_signature_skipped": zero_signature_skipped,
            "markerknown_skips": markerknown_skips,
        }
    return result


def render(pixels, width, height, palette, scale):
    image = Image.new("RGBA", (width, height))
    image.putdata([palette[index] for index in pixels])
    if scale > 1:
        image = image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    return image


def make_sheet(entries, out_path):
    thumb_w, thumb_h, label_h = 160, 120, 22
    columns = 4
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, max(1, rows) * (thumb_h + label_h)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(entries):
        x = (idx % columns) * thumb_w
        y = (idx // columns) * (thumb_h + label_h)
        thumb = image.copy()
        thumb.thumbnail((thumb_w, thumb_h), Image.Resampling.NEAREST)
        sheet.paste(thumb.convert("RGB"), (x + (thumb_w - thumb.width) // 2, y))
        draw.text((x + 2, y + thumb_h), label[:28], fill=(230, 230, 230))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main():
    parser = argparse.ArgumentParser(description="Probe simple span-command decoders for TE PCX records.")
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("-p", "--palette", type=Path, default=Path("extracted/LOCAL/7231c8f9.pal"))
    parser.add_argument("--level", default="L10_DC")
    parser.add_argument("--name", action="append", default=[])
    parser.add_argument("--sheet", type=Path, default=Path("previews/te_span_probe.png"))
    parser.add_argument("--widths", nargs="+", type=int, default=[64, 128, 256])
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--skips", nargs="+", type=int, default=[0, 4, 8, 12, 16, 24, 32])
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    args = parser.parse_args()

    palette = read_palette(args.palette)
    modes = [
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
    ]
    entries = []
    names = args.name or ["dirt.pcx", "sky01.pcx"]
    for row in load_rows(args.catalog, args.level, names):
        data = Path(row["source"]).read_bytes()
        name = row["name"].encode("latin1")
        base = row["offset"] + len(name) + 1
        for skip in args.skips:
            payload = data[base + skip : base + skip + 65536]
            for mode in modes:
                for width in args.widths:
                    pixels = decode_span(payload, width, args.height, mode, args.low, args.high)
                    image = render(pixels, width, args.height, palette, 1)
                    entries.append((f"{row['name']} s{skip} {mode} {width}", image))
    make_sheet(entries[:160], args.sheet)
    print(f"wrote {args.sheet} with {len(entries)} probe(s)")


if __name__ == "__main__":
    main()
