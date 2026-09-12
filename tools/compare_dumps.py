#!/usr/bin/env python3
"""Strict comparison of observer captures; -- means unread, never zero."""
from __future__ import annotations
import argparse
import re
from dataclasses import dataclass
from pathlib import Path

BUFFER_LEN = 0x69
MAX_LOG_BYTES = 2 * 1024 * 1024
TOKEN = re.compile(r"(?:[0-9a-fA-F]{2}|--)")
DUMP = re.compile(r"dump\s+(\d+):\s*(.*)")
Payload = tuple[int | None, ...]

@dataclass
class CaptureLog:
    metadata: dict[str, str]
    captures: dict[int, Payload]


def read_log(path: Path) -> CaptureLog:
    with path.open("rb") as source:
        data = source.read(MAX_LOG_BYTES + 1)
    if len(data) > MAX_LOG_BYTES:
        raise ValueError(f"{path}: log exceeds 2 MiB")
    metadata: dict[str, str] = {}
    captures: dict[int, Payload] = {}
    for number, raw in enumerate(data.decode("utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            field = line[1:].strip()
            if "=" in field:
                key, value = field.split("=", 1)
                if key in metadata:
                    raise ValueError(f"{path}:{number}: duplicate header {key}")
                metadata[key] = value
            continue
        match = DUMP.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{number}: malformed capture line")
        sequence = int(match.group(1))
        if sequence in captures:
            raise ValueError(f"{path}:{number}: duplicate sequence {sequence}; do not concatenate logs")
        tokens = match.group(2).split()
        if len(tokens) != BUFFER_LEN or any(not TOKEN.fullmatch(token) for token in tokens):
            raise ValueError(f"{path}:{number}: require 105 byte tokens or -- markers")
        captures[sequence] = tuple(None if token == "--" else int(token, 16) for token in tokens)
    if not captures:
        raise ValueError(f"{path}: no captures")
    return CaptureLog(metadata, captures)


def read_dumps(path: Path) -> dict[int, Payload]:
    return read_log(path).captures


def choose_sequences(captures: dict[int, Payload], requested: list[int]) -> tuple[int, int]:
    if requested:
        if len(requested) != 2 or requested[0] == requested[1]:
            raise ValueError("provide two distinct sequence numbers")
        if any(sequence not in captures for sequence in requested):
            raise ValueError("requested sequence not found")
        return requested[0], requested[1]
    available = sorted(captures)
    if len(available) < 2:
        raise ValueError("log must contain at least two captures")
    return available[-2], available[-1]


def differences(left: Payload, right: Payload) -> list[tuple[int, int, int, int]]:
    if len(left) != BUFFER_LEN or len(right) != BUFFER_LEN:
        raise ValueError("wrong payload length")
    if tuple(x is not None for x in left) != tuple(x is not None for x in right):
        raise ValueError("capture masks differ; collect comparable samples")
    if all(x is None for x in left):
        raise ValueError("no observed bytes")
    return [(i, a, b, a ^ b) for i, (a, b) in enumerate(zip(left, right))
            if a is not None and b is not None and a != b]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("sequence", nargs="*", type=int)
    args = parser.parse_args()
    try:
        captures = read_dumps(args.log)
        left, right = choose_sequences(captures, args.sequence)
        changes = differences(captures[left], captures[right])
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    print(f"Comparing dump {left} -> dump {right}")
    print("offset  before  after   xor")
    for offset, before, after, xor in changes:
        print(f"0x{offset:02X}    0x{before:02X}    0x{after:02X}    0x{xor:02X}")
    print(f"Changed observed bytes: {len(changes)}; unread bytes were excluded.")
    print("A difference is not proof of a Team Attack field.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
