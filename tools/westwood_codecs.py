"""Small Westwood asset codecs shared by the LOLG tooling."""


def lcw_literal_encoded_size(size):
    if size < 0:
        raise ValueError("size must be non-negative")
    return size + ((size + 62) // 63) + 1


def lcw_compress_literal(source):
    """Encode a valid LCW/Format80 stream using literal packets only."""

    data = bytes(source)
    output = bytearray()
    offset = 0
    while offset < len(data):
        count = min(63, len(data) - offset)
        output.append(0x80 | count)
        output.extend(data[offset : offset + count])
        offset += count
    output.append(0x80)
    return bytes(output)


def _emit_lcw_literal(output, literal):
    offset = 0
    while offset < len(literal):
        count = min(63, len(literal) - offset)
        output.append(0x80 | count)
        output.extend(literal[offset : offset + count])
        offset += count


def _lcw_match_length(data, source, target, limit):
    limit = min(limit, target - source)
    length = 0
    while length < limit and target + length < len(data):
        if data[source + length] != data[target + length]:
            break
        length += 1
    return length


def _lcw_match_length_overlapping(data, source, target, limit):
    length = 0
    while length < limit and target + length < len(data):
        if data[source + length] != data[target + length]:
            break
        length += 1
    return length


def _lcw_key(data, offset):
    return (data[offset] << 16) | (data[offset + 1] << 8) | data[offset + 2]


def lcw_compress(source, search_depth=32):
    """Encode an LCW/Format80 stream with literals and copy commands.

    This is a conservative greedy encoder intended for generated assets. It
    emits only command forms shared by the local decoders: 63-byte literals,
    short relative copies, and short absolute copies. It intentionally avoids
    the 0xFE/0xFF extended commands because older local tools disagree about
    their meaning.
    """

    data = bytes(source)
    if not data:
        return b"\x80"

    output = bytearray()
    literal = bytearray()
    recent = {}
    offset = 0

    def flush_literal():
        if literal:
            _emit_lcw_literal(output, literal)
            literal.clear()

    def remember(start, count):
        end = min(len(data) - 2, start + count)
        for pos in range(start, end):
            key = _lcw_key(data, pos)
            bucket = recent.setdefault(key, [])
            bucket.append(pos)
            if len(bucket) > 96:
                del bucket[: len(bucket) - 96]

    def best_copy(target):
        if target + 2 >= len(data):
            return 0, 0, ""
        candidates = recent.get(_lcw_key(data, target), [])
        best_length = 0
        best_source = 0
        best_kind = ""
        checked = 0
        for source_pos in reversed(candidates):
            if source_pos >= target:
                continue
            distance = target - source_pos
            if distance <= 0:
                continue
            if checked >= search_depth:
                break
            checked += 1
            if distance <= 0x0FFF:
                length = _lcw_match_length(data, source_pos, target, 10)
                if length >= 3 and (length - 2, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "short"
            if source_pos <= 0xFFFF:
                length = _lcw_match_length(data, source_pos, target, 64)
                if length >= 4 and (length - 3, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "absolute"
        return best_length, best_source, best_kind

    while offset < len(data):
        copy_length, copy_source, copy_kind = best_copy(offset)
        copy_cost = 2 if copy_kind == "short" else 3
        copy_score = copy_length - copy_cost if copy_kind else -1

        if copy_score >= 0:
            flush_literal()
            if copy_kind == "short":
                distance = offset - copy_source
                output.append(((copy_length - 3) << 4) | ((distance >> 8) & 0x0F))
                output.append(distance & 0xFF)
            else:
                output.append(0xC0 | (copy_length - 3))
                output.extend((copy_source & 0xFF, (copy_source >> 8) & 0xFF))
            remember(offset, copy_length)
            offset += copy_length
            continue

        literal.append(data[offset])
        remember(offset, 1)
        offset += 1
        if len(literal) == 63:
            flush_literal()

    flush_literal()
    output.append(0x80)
    literal_size = lcw_literal_encoded_size(len(data))
    if len(output) >= literal_size:
        return lcw_compress_literal(data)
    return bytes(output)


def lcw_compress_extended(source, search_depth=96, max_match=0xFFFF):
    """Encode LCW/Format80 using long copy and fill commands when profitable."""

    data = bytes(source)
    if not data:
        return b"\x80"

    output = bytearray()
    literal = bytearray()
    recent = {}
    offset = 0

    def flush_literal():
        if literal:
            _emit_lcw_literal(output, literal)
            literal.clear()

    def remember(start, count):
        end = min(len(data) - 2, start + count)
        for pos in range(start, end):
            key = _lcw_key(data, pos)
            bucket = recent.setdefault(key, [])
            bucket.append(pos)
            if len(bucket) > 160:
                del bucket[: len(bucket) - 160]

    def fill_length(target):
        value = data[target]
        end = min(len(data), target + 0xFFFF)
        pos = target + 1
        while pos < end and data[pos] == value:
            pos += 1
        return pos - target

    def best_copy(target):
        if target + 2 >= len(data):
            return 0, 0, ""
        candidates = recent.get(_lcw_key(data, target), [])
        best_length = 0
        best_source = 0
        best_kind = ""
        checked = 0
        limit = min(0xFFFF, max_match, len(data) - target)
        for source_pos in reversed(candidates):
            if source_pos >= target:
                continue
            distance = target - source_pos
            if distance <= 0:
                continue
            if checked >= search_depth:
                break
            checked += 1
            if distance <= 0x0FFF:
                length = _lcw_match_length_overlapping(data, source_pos, target, min(10, limit))
                if length >= 3 and (length - 2, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "short"
            if source_pos <= 0xFFFF:
                length = _lcw_match_length_overlapping(data, source_pos, target, min(64, limit))
                if length >= 4 and (length - 3, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "absolute"
                length = _lcw_match_length_overlapping(data, source_pos, target, limit)
                if length >= 8 and length - 5 > best_length - (2 if best_kind == "short" else 3):
                    best_length = length
                    best_source = source_pos
                    best_kind = "long"
        return best_length, best_source, best_kind

    while offset < len(data):
        run_length = fill_length(offset)
        copy_length, copy_source, copy_kind = best_copy(offset)

        fill_score = run_length - 4 if run_length >= 4 else -1
        copy_cost = 2 if copy_kind == "short" else 3 if copy_kind == "absolute" else 5
        copy_score = copy_length - copy_cost if copy_kind else -1

        if fill_score >= copy_score and fill_score >= 0:
            flush_literal()
            count = min(run_length, 0xFFFF)
            output.append(0xFE)
            output.extend((count & 0xFF, (count >> 8) & 0xFF, data[offset]))
            remember(offset, count)
            offset += count
            continue

        if copy_score >= 0:
            flush_literal()
            if copy_kind == "short":
                distance = offset - copy_source
                output.append(((copy_length - 3) << 4) | ((distance >> 8) & 0x0F))
                output.append(distance & 0xFF)
            elif copy_kind == "absolute":
                output.append(0xC0 | (copy_length - 3))
                output.extend((copy_source & 0xFF, (copy_source >> 8) & 0xFF))
            else:
                output.append(0xFF)
                output.extend(
                    (
                        copy_length & 0xFF,
                        (copy_length >> 8) & 0xFF,
                        copy_source & 0xFF,
                        (copy_source >> 8) & 0xFF,
                    )
                )
            remember(offset, copy_length)
            offset += copy_length
            continue

        literal.append(data[offset])
        remember(offset, 1)
        offset += 1
        if len(literal) == 63:
            flush_literal()

    flush_literal()
    output.append(0x80)
    compact = bytes(output)
    literal_size = lcw_literal_encoded_size(len(data))
    if len(compact) >= literal_size:
        return lcw_compress_literal(data)
    return compact


def lcw_compress_vqa_extended(source, search_depth=96, max_match=0xFFFF):
    """Encode VQA LCW with the command meanings used by ``lolg_vqa_decode``.

    For non-pointer VQA chunks, the local VQA decoder and original LOCALLNG
    profiles use 0xFF for fill and 0xFE for long absolute copy. Keep this
    separate from ``lcw_compress_extended``, which preserves an older local
    helper dialect.
    """

    data = bytes(source)
    if not data:
        return b"\x80"

    output = bytearray()
    literal = bytearray()
    recent = {}
    offset = 0

    def flush_literal():
        if literal:
            _emit_lcw_literal(output, literal)
            literal.clear()

    def remember(start, count):
        end = min(len(data) - 2, start + count)
        for pos in range(start, end):
            key = _lcw_key(data, pos)
            bucket = recent.setdefault(key, [])
            bucket.append(pos)
            if len(bucket) > 160:
                del bucket[: len(bucket) - 160]

    def fill_length(target):
        value = data[target]
        end = min(len(data), target + 0xFFFF)
        pos = target + 1
        while pos < end and data[pos] == value:
            pos += 1
        return pos - target

    def best_copy(target):
        if target + 2 >= len(data):
            return 0, 0, ""
        candidates = recent.get(_lcw_key(data, target), [])
        best_length = 0
        best_source = 0
        best_kind = ""
        checked = 0
        limit = min(0xFFFF, max_match, len(data) - target)
        for source_pos in reversed(candidates):
            if source_pos >= target:
                continue
            distance = target - source_pos
            if distance <= 0:
                continue
            if checked >= search_depth:
                break
            checked += 1
            if distance <= 0x0FFF:
                length = _lcw_match_length_overlapping(data, source_pos, target, min(10, limit))
                if length >= 3 and (length - 2, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "short"
            if source_pos <= 0xFFFF:
                length = _lcw_match_length_overlapping(data, source_pos, target, min(64, limit))
                if length >= 4 and (length - 3, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "absolute"
                length = _lcw_match_length_overlapping(data, source_pos, target, limit)
                if length >= 8 and length - 5 > best_length - (2 if best_kind == "short" else 3):
                    best_length = length
                    best_source = source_pos
                    best_kind = "long"
        return best_length, best_source, best_kind

    while offset < len(data):
        run_length = fill_length(offset)
        copy_length, copy_source, copy_kind = best_copy(offset)

        fill_score = run_length - 4 if run_length >= 4 else -1
        copy_cost = 2 if copy_kind == "short" else 3 if copy_kind == "absolute" else 5
        copy_score = copy_length - copy_cost if copy_kind else -1

        if fill_score >= copy_score and fill_score >= 0:
            flush_literal()
            count = min(run_length, 0xFFFF)
            output.append(0xFF)
            output.extend((count & 0xFF, (count >> 8) & 0xFF, data[offset]))
            remember(offset, count)
            offset += count
            continue

        if copy_score >= 0:
            flush_literal()
            if copy_kind == "short":
                distance = offset - copy_source
                output.append(((copy_length - 3) << 4) | ((distance >> 8) & 0x0F))
                output.append(distance & 0xFF)
            elif copy_kind == "absolute":
                output.append(0xC0 | (copy_length - 3))
                output.extend((copy_source & 0xFF, (copy_source >> 8) & 0xFF))
            else:
                output.append(0xFE)
                output.extend(
                    (
                        copy_length & 0xFF,
                        (copy_length >> 8) & 0xFF,
                        copy_source & 0xFF,
                        (copy_source >> 8) & 0xFF,
                    )
                )
            remember(offset, copy_length)
            offset += copy_length
            continue

        literal.append(data[offset])
        remember(offset, 1)
        offset += 1
        if len(literal) == 63:
            flush_literal()

    flush_literal()
    output.append(0x80)
    compact = bytes(output)
    literal_size = lcw_literal_encoded_size(len(data))
    if len(compact) >= literal_size:
        return lcw_compress_literal(data)
    return compact


def lcw_compress_windowed_pointer(source, search_depth=192, max_match=0xFFFF, base_address=0x8200):
    """Encode VPTZ-style LCW using the original 64K window commands.

    VQA pointer chunks in the game data are decoded against a 64K rolling
    window. This variant uses the command meanings handled by
    ``decode_lcw_windowed_pointer``: 0xFE is a long window copy and 0xFF is a
    fill. Copy sources are emitted as 16-bit window addresses, so matches must
    be within the previous 64K of output.
    """

    data = bytes(source)
    if not data:
        return b"\x80"

    output = bytearray()
    literal = bytearray()
    recent = {}
    offset = 0

    def flush_literal():
        if literal:
            _emit_lcw_literal(output, literal)
            literal.clear()

    def remember(start, count):
        end = min(len(data) - 2, start + count)
        for pos in range(start, end):
            key = _lcw_key(data, pos)
            bucket = recent.setdefault(key, [])
            bucket.append(pos)
            if len(bucket) > 512:
                del bucket[: len(bucket) - 512]

    def fill_length(target):
        value = data[target]
        end = min(len(data), target + 0xFFFF)
        pos = target + 1
        while pos < end and data[pos] == value:
            pos += 1
        return pos - target

    def best_copy(target):
        if target + 2 >= len(data):
            return 0, 0, ""
        candidates = recent.get(_lcw_key(data, target), [])
        best_length = 0
        best_source = 0
        best_kind = ""
        checked = 0
        limit = min(0xFFFF, max_match, len(data) - target)
        for source_pos in reversed(candidates):
            if source_pos >= target:
                continue
            distance = target - source_pos
            if distance <= 0 or distance > 0x10000:
                continue
            if checked >= search_depth:
                break
            checked += 1
            if distance <= 0x0FFF:
                length = _lcw_match_length_overlapping(data, source_pos, target, min(10, limit))
                if length >= 3 and (length - 2, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                    best_length = length
                    best_source = source_pos
                    best_kind = "short"
            length = _lcw_match_length_overlapping(data, source_pos, target, min(64, limit))
            if length >= 4 and (length - 3, length) > (best_length - (2 if best_kind == "short" else 3), best_length):
                best_length = length
                best_source = source_pos
                best_kind = "window"
            length = _lcw_match_length_overlapping(data, source_pos, target, limit)
            if length >= 8 and length - 5 > best_length - (2 if best_kind == "short" else 3):
                best_length = length
                best_source = source_pos
                best_kind = "long_window"
        return best_length, best_source, best_kind

    while offset < len(data):
        run_length = fill_length(offset)
        copy_length, copy_source, copy_kind = best_copy(offset)

        fill_score = run_length - 4 if run_length >= 4 else -1
        copy_cost = 2 if copy_kind == "short" else 3 if copy_kind == "window" else 5
        copy_score = copy_length - copy_cost if copy_kind else -1

        if fill_score >= copy_score and fill_score >= 0:
            flush_literal()
            count = min(run_length, 0xFFFF)
            output.append(0xFF)
            output.extend((count & 0xFF, (count >> 8) & 0xFF, data[offset]))
            remember(offset, count)
            offset += count
            continue

        if copy_score >= 0:
            flush_literal()
            if copy_kind == "short":
                distance = offset - copy_source
                output.append(((copy_length - 3) << 4) | ((distance >> 8) & 0x0F))
                output.append(distance & 0xFF)
            elif copy_kind == "window":
                output.append(0xC0 | (copy_length - 3))
                source = (base_address + copy_source) & 0xFFFF
                output.extend((source & 0xFF, (source >> 8) & 0xFF))
            else:
                output.append(0xFE)
                source = (base_address + copy_source) & 0xFFFF
                output.extend(
                    (
                        copy_length & 0xFF,
                        (copy_length >> 8) & 0xFF,
                        source & 0xFF,
                        (source >> 8) & 0xFF,
                    )
                )
            remember(offset, copy_length)
            offset += copy_length
            continue

        literal.append(data[offset])
        remember(offset, 1)
        offset += 1
        if len(literal) == 63:
            flush_literal()

    flush_literal()
    output.append(0x80)
    compact = bytes(output)
    literal_size = lcw_literal_encoded_size(len(data))
    if len(compact) >= literal_size:
        return lcw_compress_literal(data)
    return compact


def lcw_decompress(source, expected_size=None):
    src = memoryview(source)
    sp = 0
    dest = bytearray()
    relative = False
    if src and src[0] == 0:
        relative = True
        sp = 1

    def read_word(offset):
        return src[offset] | (src[offset + 1] << 8)

    def copy_from(position, count):
        if position < 0:
            raise ValueError("LCW copy points before output buffer")
        cursor = position
        for _ in range(count):
            if cursor >= len(dest):
                raise ValueError("LCW copy points beyond output buffer")
            dest.append(dest[cursor])
            cursor += 1

    while sp < len(src):
        command = src[sp]
        sp += 1
        if command & 0x80 == 0:
            if sp >= len(src):
                raise ValueError("truncated LCW command 2")
            count = ((command & 0x70) >> 4) + 3
            position = len(dest) - (((command & 0x0F) << 8) | src[sp])
            sp += 1
            copy_from(position, count)
        elif command & 0x40 == 0:
            count = command & 0x3F
            if count == 0:
                break
            dest.extend(src[sp : sp + count])
            sp += count
        else:
            count = command & 0x3F
            if count < 0x3E:
                if sp + 2 > len(src):
                    raise ValueError("truncated LCW command 3")
                count += 3
                raw_position = read_word(sp)
                sp += 2
                position = len(dest) - raw_position if relative else raw_position
                copy_from(position, count)
            elif count == 0x3E:
                if sp + 3 > len(src):
                    raise ValueError("truncated LCW command 4")
                repeat_count = read_word(sp)
                value = src[sp + 2]
                sp += 3
                dest.extend([value] * repeat_count)
            else:
                if sp + 4 > len(src):
                    raise ValueError("truncated LCW command 5")
                copy_count = read_word(sp)
                raw_position = read_word(sp + 2)
                sp += 4
                position = len(dest) - raw_position if relative else raw_position
                copy_from(position, copy_count)

        if expected_size is not None and len(dest) > expected_size:
            raise ValueError("LCW output exceeded expected size")

    if expected_size is not None and len(dest) != expected_size:
        raise ValueError(f"LCW output size {len(dest)} != expected {expected_size}")
    return bytes(dest)
