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
        for i in range(count):
            if position + i >= len(dest):
                raise ValueError("LCW copy points beyond output buffer")
            dest.append(dest[position + i])

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
