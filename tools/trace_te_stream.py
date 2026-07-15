#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

try:
    from export_te_guided_decoders import load_catalog, payload_after_name
    from export_te_span_previews import source_payload
except ModuleNotFoundError:
    load_catalog = None
    payload_after_name = None
    source_payload = None


DEFAULT_NAMES = [
    "L10_DC/hdstn1h.pcx",
    "L10_DC/imrbwl02.pcx",
    "L17_HC/ductdmg2.pcx",
    "L7_DH/beamhorz.pcx",
    "L12_CM/newmtn3.pcx",
]


def advance(x, y, width, amount):
    x += amount
    rows = 0
    while x >= width:
        x -= width
        y += 1
        rows += 1
    return x, y, rows


def signed_byte(value):
    return value - 256 if value >= 128 else value


def clamp_cursor(x, y, width, height):
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def get_arg(payload, pos, offset):
    index = pos + offset
    if index >= len(payload):
        return None
    return payload[index]


def hex_byte(value):
    if value is None:
        return ""
    return f"{value:02x}"


def load_choices(path):
    choices = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            key = (row["level"], row["name"])
            choices[key] = {
                "source": row["source"],
                "mode": row["mode"],
                "width": int(row["width"]),
                "height": int(row["height"]),
                "extra": None if row["extra"] == "" else int(row["extra"]),
                "start": None if row["start"] == "" else int(row["start"]),
                "score": float(row.get("score", 0.0)),
                "filled": float(row.get("filled", 0.0)),
            }
    return choices


def wanted_keys(values):
    keys = set()
    for value in values:
        if "/" not in value:
            raise SystemExit(f"--name must use LEVEL/name.pcx form: {value}")
        level, name = value.split("/", 1)
        keys.add((level, name))
    return keys


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
    ) and "_cmd20_arg2_" in mode


def op4_signature_skip_args(mode):
    prefix = mode.split("_cmd20_arg2_", 1)[0]
    if prefix.endswith("s2"):
        return 2
    if prefix.endswith("s4"):
        return 4
    return 3


def is_cmd20_signature(arg1, arg2, arg3):
    return is_cmd20_zero_signature(arg1, arg2, arg3) or is_cmd20_high_arg2_signature(arg1, arg2, arg3)


def arg2_threshold(mode):
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
        return y - dy, -dy
    return y + dy, dy


def parse_suffix_int(mode, marker):
    return int(mode.rsplit(marker, 1)[1])


def classify_command(payload, pos, byte, mode):
    arg1 = get_arg(payload, pos, 0)
    arg2 = get_arg(payload, pos, 1)
    arg3 = get_arg(payload, pos, 2)

    if mode.startswith("cmd20_high_arg2_skip") and byte == 0x20:
        skip = parse_suffix_int(mode, "skip")
        matched = is_cmd20_high_arg2_signature(arg1, arg2, arg3)
        return "cmd20", "sig_skip" if matched else "sig_noop", skip if matched else 0, matched, False
    if mode.startswith("cmd20_sig_xskip") and byte == 0x20:
        skip = parse_suffix_int(mode, "xskip")
        matched = is_cmd20_signature(arg1, arg2, arg3)
        return "cmd20", "sig_xskip" if matched else "sig_noop", skip if matched else 0, matched, True
    if mode.startswith("cmd20_xskip") and byte == 0x20:
        return "cmd20", "xskip", parse_suffix_int(mode, "xskip"), True, True
    if mode.startswith("cmd20_sig_skip") and byte == 0x20:
        skip = parse_suffix_int(mode, "skip")
        matched = is_cmd20_signature(arg1, arg2, arg3)
        return "cmd20", "sig_skip" if matched else "sig_noop", skip if matched else 0, matched, False
    if mode.startswith("cmd20_skip") and byte == 0x20:
        return "cmd20", "skip", parse_suffix_int(mode, "skip"), True, False

    if mode.startswith("op4_cmd20_sig_xskip") and byte == 0x20:
        skip = parse_suffix_int(mode, "xskip")
        matched = is_cmd20_signature(arg1, arg2, arg3)
        return "cmd20", "sig_xskip" if matched else "sig_noop", skip if matched else 0, matched, True
    if mode.startswith("op4_cmd20_xskip") and byte == 0x20:
        return "cmd20", "xskip", parse_suffix_int(mode, "xskip"), True, True
    if mode.startswith("op4_cmd20_sig_skip") and byte == 0x20:
        skip = parse_suffix_int(mode, "skip")
        matched = is_cmd20_signature(arg1, arg2, arg3)
        return "cmd20", "sig_skip" if matched else "sig_noop", skip if matched else 0, matched, False
    if mode.startswith("op4_cmd20_skip") and byte == 0x20:
        return "cmd20", "skip", parse_suffix_int(mode, "skip"), True, False

    if mode in {"low_skip", "zero_skip", "low_newline", "cmd20_y", "cmd20_xy"}:
        return None, None, 0, False, False

    if mode in {"op4_skip1", "op4_cmd20_skip1"} and is_op4_candidate(byte):
        return "op4", "skip", 1, True, False
    if mode in {"op4_skip2", "op4_cmd20_skip2"} and is_op4_candidate(byte):
        return "op4", "skip", 2, True, False
    if mode in {"op4_cmd20_skip3", "op4_cmd20_skip4"} and is_op4_candidate(byte):
        return "op4", "skip", 3, True, False
    if mode == "op4_xarg" and is_op4_candidate(byte):
        return "op4", "xarg", 1, arg1 is not None, False
    if mode == "op4_yarg" and is_op4_candidate(byte):
        return "op4", "yarg", 1, arg1 is not None, False
    if mode == "op4_small_skip1" and is_op4_candidate(byte) and arg1 is not None and arg1 < 0x20:
        return "op4", "small_skip", 1, True, False
    if mode == "op4_small_skip2" and is_op4_candidate(byte) and arg1 is not None and arg1 < 0x20:
        return "op4", "small_skip", 2, True, False
    if mode == "op4_zero_skip1" and is_op4_candidate(byte) and arg1 == 0:
        return "op4", "zero_skip", 1, True, False
    if mode in {"op4_cmd20_sig_skip2"} and is_op4_candidate(byte):
        return "op4", "skip", 2, arg2 is not None, False
    if mode in {"op4_cmd20_sig_skip3", "op4_cmd20_sig_skip4", "op4_cmd20_xskip3", "op4_cmd20_sig_xskip3"} and is_op4_candidate(byte):
        return "op4", "skip", 3, True, False
    if (
        mode.startswith("op4_cmd20_arg2_dy_skip")
        or mode.startswith("op4_cmd20_arg2_e0_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_f0_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_f8_safe_dy_skip")
        or mode.startswith("op4_cmd20_arg2_fc_safe_dy_skip")
    ) and is_op4_candidate(byte):
        return "op4", "skip", 3, True, False
    if is_op4_signature_safe_mode(mode) and is_op4_candidate(byte):
        matched = op4_signature_matches(mode, arg1, arg2, arg3)
        return "op4", "sig_skip" if matched else "sig_noop", op4_signature_skip_args(mode) if matched else 0, matched, False
    if mode.startswith("op4_emit1_cmd20_skip") and is_op4_candidate(byte):
        return "op4", "emit_arg1_skip", 3, True, False
    if mode.startswith("op4_emit1_cmd20_sig_skip") and is_op4_candidate(byte):
        return "op4", "emit_arg1_skip", 3, True, False

    return None, None, 0, False, False


def trace_payload(payload, width, height, mode, low, high, max_events):
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
    x = y = pos = 0
    event_index = 0
    emitted = 0
    row_transitions = 0
    counts = {"cmd20": 0, "op4": 0, "pixel": 0, "ignored_low": 0, "ignored_high": 0, "control": 0}

    while pos < len(payload) and y < height and event_index < max_events:
        event_pos = pos
        byte = payload[pos]
        pos += 1
        x0, y0 = x, y
        arg1 = get_arg(payload, pos, 0)
        arg2 = get_arg(payload, pos, 1)
        arg3 = get_arg(payload, pos, 2)
        kind = action = ""
        skip = 0
        emit = 0

        if mode == "raw":
            kind, action = "pixel", "raw_emit"
            emit = 1
            x, y, rows = advance(x, y, width, 1)
            emitted += 1
            row_transitions += rows
        elif markerpair_mode and pos < len(payload) and is_marker_pair(byte, payload[pos]):
            kind, action, skip = "control", "markerpair_skip", 1
            pos += 1
        elif markerknown_mode and pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            kind, action, skip = "control", "markerknown_skip", 1
            pos += 1
        elif markerknownsymadv_mode and is_marker_symmetric_header(payload, byte, pos):
            kind, action, skip = "control", "markerknownsymadv_advance", 1
            pos += 1
            x, y, rows = advance(x, y, width, 1)
            row_transitions += rows
        elif markerknownsymadv_mode and pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            kind, action, skip = "control", "markerknownsymadv_skip", 1
            pos += 1
        elif markerknownadv_mode and pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            kind, action, skip = "control", "markerknownadv_skip", 1
            pos += 1
            x, y, rows = advance(x, y, width, 1)
            row_transitions += rows
        elif (
            markerknown0_mode
            and pos + 1 < len(payload)
            and is_known_marker_pair(byte, payload[pos])
            and payload[pos + 1] == 0
        ):
            kind, action, skip = "control", "markerknown0_skip", 1
            pos += 1
        elif (
            markerknown0adv_mode
            and pos + 1 < len(payload)
            and is_known_marker_pair(byte, payload[pos])
            and payload[pos + 1] == 0
        ):
            kind, action, skip = "control", "markerknown0adv_skip", 1
            pos += 1
            x, y, rows = advance(x, y, width, 1)
            row_transitions += rows
        elif markersym_mode and is_marker_symmetric_header(payload, byte, pos):
            kind, action, skip = "control", "markersym_skip", 1
            pos += 1
        elif markersymadv_mode and is_marker_symmetric_header(payload, byte, pos):
            kind, action, skip = "control", "markersymadv_skip", 1
            pos += 1
            x, y, rows = advance(x, y, width, 1)
            row_transitions += rows
        elif mode == "filter":
            if low <= byte <= high:
                kind, action = "pixel", "emit"
                emit = 1
                x, y, rows = advance(x, y, width, 1)
                emitted += 1
                row_transitions += rows
            else:
                kind = "ignored_low" if byte < low else "ignored_high"
                action = "filter_drop"
        else:
            command_kind = command_action = None
            skip = 0
            matched = False
            xskip = False
            handled = False
            if mode.startswith("cmd20_setx_line_skip") and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                kind, action = "cmd20", "setx_line"
                if arg1 is not None:
                    x, y = clamp_cursor(arg1 % max(1, width), y + 1, width, height)
                    row_transitions += 1
                pos = min(len(payload), pos + skip)
                handled = True
            elif mode.startswith("cmd20_setx_skip") and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                kind, action = "cmd20", "setx"
                if arg1 is not None:
                    x = arg1 % max(1, width)
                pos = min(len(payload), pos + skip)
                handled = True
            elif mode.startswith("cmd20_arg2_dy_skip") and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                kind, action = "cmd20", "arg2_dy" if arg2 is not None and arg2 >= 0xC0 else "arg2_noop"
                if arg1 is not None and arg2 is not None and arg2 >= 0xC0:
                    old_y = y
                    x, y = clamp_cursor(arg1 % max(1, width), y + signed_byte(arg2), width, height)
                    row_transitions += abs(y - old_y)
                pos = min(len(payload), pos + skip)
                handled = True
            elif (
                is_cmd20_arg2_safe_mode(mode)
                or is_op4_signature_safe_mode(mode)
            ) and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                threshold = arg2_threshold(mode)
                next_y, dy = safe_cmd20_next_y(mode, y, arg2) if arg2 is not None else (y, 0)
                matched = (
                    arg1 is not None
                    and arg2 is not None
                    and arg3 is not None
                    and arg2 >= threshold
                    and 0 <= next_y < height
                    and safe_cmd20_x_ok(mode, arg1, width)
                    and safe_cmd20_arg3_ok(mode, arg3)
                )
                kind, action = "cmd20", "safe_dy" if matched else "safe_dy_noop"
                if matched:
                    x = arg1 % max(1, width)
                    y = next_y
                    row_transitions += abs(dy)
                pos = min(len(payload), pos + skip)
                handled = True
            elif mode.startswith("op4_emit1_cmd20_skip") and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                kind, action = "cmd20", "skip"
                pos = min(len(payload), pos + skip)
                handled = True
            elif mode.startswith("op4_emit1_cmd20_sig_skip") and byte == 0x20:
                skip = parse_suffix_int(mode, "skip")
                matched = is_cmd20_signature(arg1, arg2, arg3)
                kind, action = "cmd20", "sig_skip" if matched else "sig_noop"
                if matched:
                    pos = min(len(payload), pos + skip)
                handled = True
            else:
                command_kind, command_action, skip, matched, xskip = classify_command(payload, pos, byte, mode)

            if handled:
                pass
            elif command_kind and matched:
                kind, action = command_kind, command_action
                if xskip:
                    x, y, rows = advance(x, y, width, arg1 or 0)
                    row_transitions += rows
                pos = min(len(payload), pos + skip)
            elif command_kind:
                kind, action = command_kind, command_action
            elif mode == "low_skip" and byte < low:
                kind, action, skip = "control", "advance_low", byte
                x, y, rows = advance(x, y, width, byte)
                row_transitions += rows
            elif mode == "zero_skip" and byte == 0 and pos < len(payload):
                kind, action, skip = "control", "zero_advance", payload[pos]
                x, y, rows = advance(x, y, width, payload[pos])
                row_transitions += rows
                pos += 1
            elif mode == "zero_skip" and byte < low:
                kind, action = "ignored_low", "zero_drop_low"
            elif mode == "low_newline" and byte < low:
                kind, action = "control", "newline_low"
                y += 1
                x = byte
                row_transitions += 1
            elif mode == "cmd20_y" and byte == 0x20 and pos < len(payload):
                kind, action, skip = "cmd20", "set_y", 1
                y = min(height - 1, payload[pos])
                x = 0
                pos += 1
                row_transitions += 1
            elif mode == "cmd20_xy" and byte == 0x20 and pos + 1 < len(payload):
                kind, action, skip = "cmd20", "set_xy", 2
                y = min(height - 1, payload[pos])
                x = min(width - 1, payload[pos + 1])
                pos += 2
                row_transitions += 1
            elif mode in {"cmd20_y", "cmd20_xy"} and byte < low:
                kind, action = "ignored_low", "cmd20_drop_low"
            elif command_kind == "op4" and command_action == "emit_arg1_skip":
                kind, action = command_kind, command_action
                if arg1 is not None and low <= arg1 <= high:
                    emit = 1
                    x, y, rows = advance(x, y, width, 1)
                    emitted += 1
                    row_transitions += rows
                pos = min(len(payload), pos + skip)
            elif low <= byte <= high:
                kind, action = "pixel", "emit"
                emit = 1
                x, y, rows = advance(x, y, width, 1)
                emitted += 1
                row_transitions += rows
            else:
                kind = "ignored_low" if byte < low else "ignored_high"
                action = "drop"

        counts[kind] = counts.get(kind, 0) + 1
        yield {
            "event_index": event_index,
            "stream_pos": event_pos,
            "x": x0,
            "y": y0,
            "byte": byte,
            "kind": kind,
            "action": action,
            "skip": skip,
            "arg1": arg1,
            "arg2": arg2,
            "arg3": arg3,
            "emit": emit,
            "x_after": x,
            "y_after": y,
            "next8": payload[event_pos : event_pos + 8].hex(),
        }
        event_index += 1

    return {
        "events": event_index,
        "emitted": emitted,
        "row_transitions": row_transitions,
        "final_x": x,
        "final_y": y,
        **counts,
    }


def payload_for_choice(row, choice, limit, marker_search):
    if choice["source"] == "width_field":
        return payload_after_name(row, choice["start"], limit)
    return source_payload(row, 0, limit, True, choice["extra"], marker_search)


def main():
    parser = argparse.ArgumentParser(description="Trace TE PCX stream interpretation event by event.")
    parser.add_argument("--choices", type=Path, default=Path("reports/te_guided_modes_skip4.tsv"))
    parser.add_argument("--catalog", type=Path, default=Path("reports/te_resources.tsv"))
    parser.add_argument("--out", type=Path, default=Path("reports/te_stream_trace.tsv"))
    parser.add_argument("--summary", type=Path, default=Path("reports/te_stream_trace_summary.tsv"))
    parser.add_argument("--name", action="append", default=[])
    parser.add_argument("--force-mode", help="Override the selected mode for all traced textures.")
    parser.add_argument("--limit", type=int, default=65536)
    parser.add_argument("--marker-search", type=int, default=512)
    parser.add_argument("--max-events", type=int, default=2048)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    choices = load_choices(args.choices)
    selected = wanted_keys(args.name or DEFAULT_NAMES)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    trace_fields = [
        "level",
        "name",
        "source",
        "mode",
        "width",
        "height",
        "event_index",
        "stream_pos",
        "x",
        "y",
        "byte",
        "kind",
        "action",
        "skip",
        "arg1",
        "arg2",
        "arg3",
        "emit",
        "x_after",
        "y_after",
        "next8",
    ]

    with args.out.open("w", encoding="utf-8", newline="") as out_fh:
        writer = csv.DictWriter(out_fh, delimiter="\t", fieldnames=trace_fields)
        writer.writeheader()
        for key in sorted(selected):
            choice = choices.get(key)
            row = catalog.get(key)
            if choice is None or row is None:
                summary_rows.append({"level": key[0], "name": key[1], "status": "missing"})
                continue
            if args.force_mode:
                choice = dict(choice)
                choice["mode"] = args.force_mode
            payload = payload_for_choice(row, choice, args.limit, args.marker_search)
            events = list(trace_payload(payload, choice["width"], choice["height"], choice["mode"], args.low, args.high, args.max_events))
            for event in events:
                output = {
                    "level": key[0],
                    "name": key[1],
                    "source": choice["source"],
                    "mode": choice["mode"],
                    "width": choice["width"],
                    "height": choice["height"],
                    **event,
                }
                for field in ["byte", "arg1", "arg2", "arg3"]:
                    output[field] = hex_byte(output[field])
                writer.writerow(output)
            if events:
                last = events[-1]
                counts = {}
                for event in events:
                    counts[event["kind"]] = counts.get(event["kind"], 0) + 1
                emitted = sum(event["emit"] for event in events)
                summary_rows.append(
                    {
                        "level": key[0],
                        "name": key[1],
                        "status": "ok",
                        "source": choice["source"],
                        "mode": choice["mode"],
                        "width": choice["width"],
                        "height": choice["height"],
                        "payload_bytes": len(payload),
                        "events": len(events),
                        "pixels": emitted,
                        "fill_ratio_in_trace": f"{emitted / max(1, choice['width'] * choice['height']):.4f}",
                        "cmd20": counts.get("cmd20", 0),
                        "op4": counts.get("op4", 0),
                        "control": counts.get("control", 0),
                        "ignored_low": counts.get("ignored_low", 0),
                        "ignored_high": counts.get("ignored_high", 0),
                        "final_x": last["x_after"],
                        "final_y": last["y_after"],
                    }
                )
            else:
                summary_rows.append({"level": key[0], "name": key[1], "status": "empty"})

    summary_fields = [
        "level",
        "name",
        "status",
        "source",
        "mode",
        "width",
        "height",
        "payload_bytes",
        "events",
        "pixels",
        "fill_ratio_in_trace",
        "cmd20",
        "op4",
        "control",
        "ignored_low",
        "ignored_high",
        "final_x",
        "final_y",
    ]
    with args.summary.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"wrote {args.out} and {args.summary}")


if __name__ == "__main__":
    main()
