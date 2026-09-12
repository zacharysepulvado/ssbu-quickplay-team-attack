#!/usr/bin/env python3
"""Create a tiny original AArch64 TEST fixture, not any Nintendo game code."""
import argparse
import struct
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = bytearray(4096)
    # Synthetic serializer: constants/stores deliberately exercise the heuristic.
    serializer = [0xA9BF7BFD, 0x910003FD, 0xD2800F01, 0x3901A001, 0x39016001,
                  0xD28003E2, 0xB9004002, 0xA8C17BFD, 0xD65F03C0]
    caller = [0xA9BF7BFD, 0x910003FD, 0x97FFFFE6, 0xD503201F, 0xD2800023,
              0xA8C17BFD, 0xD65F03C0]
    for offset, words in [(0x20, serializer), (0x80, caller)]:
        struct.pack_into("<" + "I" * len(words), data, offset, *words)
    with args.output.open("xb") as destination:
        destination.write(data)
    print("Created synthetic fixture only; offsets are not game offsets.")


if __name__ == "__main__":
    main()
