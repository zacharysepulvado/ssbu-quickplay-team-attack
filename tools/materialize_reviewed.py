#!/usr/bin/env python3
"""Recreate private reviewed code excerpts from a legally dumped 13.0.5 text segment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def checked_slice(text: bytes, item: dict[str, object], label: str,
                  parser: argparse.ArgumentParser) -> bytes:
    offset = int(str(item["offset"]), 0)
    length = int(item["length"])
    excerpt = text[offset:offset + length]
    if len(excerpt) != length:
        parser.error(f"text segment is too short for {label}")
    digest = hashlib.sha256(excerpt).hexdigest()
    if digest != item["sha256"]:
        parser.error(f"SSBU 13.0.5 digest mismatch for {label}")
    return excerpt


def rust_module(entries: list[tuple[str, bytes]]) -> bytes:
    lines = [
        "// Generated locally from a legally dumped SSBU 13.0.5 main; do not redistribute.\n",
        "// Runtime must match every byte before either native leaf may be called.\n",
    ]
    for name, data in entries:
        lines.append(f"pub const {name}: &[u8] = &[\n")
        for start in range(0, len(data), 16):
            row = ", ".join(f"0x{byte:02x}" for byte in data[start:start + 16])
            lines.append(f"    {row},\n")
        lines.append("];\n")
    return "".join(lines).encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", type=Path, help="decompressed main .text segment")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    reviewed = root / "src" / "reviewed"
    manifest = json.loads((reviewed / "manifest.json").read_text(encoding="utf-8"))
    text = args.text.read_bytes()

    pending: list[tuple[Path, bytes]] = []
    for item in manifest["files"]:
        destination = reviewed / item["name"]
        if destination.exists():
            parser.error(f"refusing to replace existing file: {destination}")
        pending.append((destination, checked_slice(text, item, item["name"], parser)))

    codec_destination = root / "src" / "codec_bytes.rs"
    if codec_destination.exists():
        parser.error(f"refusing to replace existing file: {codec_destination}")
    codec_entries = []
    for item in manifest["codec_module"]:
        name = str(item["rust_const"])
        codec_entries.append((name, checked_slice(text, item, name, parser)))
    pending.append((codec_destination, rust_module(codec_entries)))

    for destination, excerpt in pending:
        destination.write_bytes(excerpt)
        print(f"created {destination.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
