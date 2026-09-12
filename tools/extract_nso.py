#!/usr/bin/env python3
"""Extract and verify compressed NSO0 segments without external dependencies."""
import argparse
import hashlib
from pathlib import Path
import struct


def lz4_block(data, output_size):
    out = bytearray()
    cursor = 0
    while cursor < len(data):
        token = data[cursor]
        cursor += 1
        literal = token >> 4
        if literal == 15:
            while True:
                extra = data[cursor]
                cursor += 1
                literal += extra
                if extra != 255:
                    break
        out += data[cursor:cursor + literal]
        cursor += literal
        if cursor == len(data):
            break
        if cursor + 2 > len(data):
            raise ValueError('truncated match offset')
        offset = int.from_bytes(data[cursor:cursor + 2], 'little')
        cursor += 2
        if offset == 0 or offset > len(out):
            raise ValueError('invalid match offset')
        length = token & 15
        if length == 15:
            while True:
                extra = data[cursor]
                cursor += 1
                length += extra
                if extra != 255:
                    break
        length += 4
        for _ in range(length):
            out.append(out[-offset])
        if len(out) > output_size:
            raise ValueError('decompressed segment exceeds declared size')
    if cursor != len(data) or len(out) != output_size:
        raise ValueError(f'LZ4 size mismatch: input {cursor}/{len(data)}, output {len(out)}/{output_size}')
    return bytes(out)


def extract(path, destination):
    raw = path.read_bytes()
    if raw[:4] != b'NSO0':
        raise ValueError('not an NSO0 file')
    flags = struct.unpack_from('<I', raw, 0x0c)[0]
    compressed_sizes = struct.unpack_from('<III', raw, 0x60)
    names = ['text', 'rodata', 'data']
    result = []
    destination.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(names):
        file_offset, memory_offset, output_size = struct.unpack_from('<III', raw, 0x10 + index * 0x10)
        stored_size = compressed_sizes[index] if flags & (1 << index) else output_size
        stored = raw[file_offset:file_offset + stored_size]
        if len(stored) != stored_size:
            raise ValueError(f'truncated {name} segment')
        data = lz4_block(stored, output_size) if flags & (1 << index) else stored
        expected = raw[0xa0 + index * 0x20:0xc0 + index * 0x20]
        digest = hashlib.sha256(data).digest()
        if flags & (1 << (index + 3)) and digest != expected:
            raise ValueError(f'{name} SHA-256 mismatch')
        output = destination / f'{name}.bin'
        output.write_bytes(data)
        result.append((name, memory_offset, output_size, digest.hex(), output))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nso', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    for row in extract(args.nso, args.destination):
        print(*row)
