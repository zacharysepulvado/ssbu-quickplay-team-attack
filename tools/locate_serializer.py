#!/usr/bin/env python3
"""Rank structural leads exported by Ghidra; never generate an approved offset."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

REFERENCE_OFFSET = 0x16E2DF0  # 13.0.4 only; used to select a reference record.


def read_features(path: Path) -> tuple[dict, list[dict]]:
    metadata, functions, ended = None, [], False
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            if ended:
                raise ValueError(f"{path}:{line_number}: data after end marker")
            record = json.loads(line)
            kind = record.get("type")
            if kind == "metadata" and metadata is None and not functions:
                if record.get("schema") != 1:
                    raise ValueError("unsupported feature schema")
                metadata = record
            elif kind == "function" and metadata is not None:
                if not isinstance(record.get("offset"), int) or not isinstance(record.get("mnemonics"), list):
                    raise ValueError("invalid function record")
                functions.append(record)
            elif kind == "end" and metadata is not None:
                if record.get("function_count") != len(functions):
                    raise ValueError("truncated feature export")
                ended = True
            else:
                raise ValueError(f"{path}:{line_number}: unexpected record")
    if not ended or not functions:
        raise ValueError("export is incomplete or contains no functions")
    if len({f["offset"] for f in functions}) != len(functions):
        raise ValueError("duplicate function offsets")
    return metadata, functions


def score(function: dict, reference: dict | None = None) -> tuple[float, list[str]]:
    constants = set(function.get("constants", []))
    stores = set(function.get("store_displacements", []))
    reasons, points = [], 0.0
    for value, weight in [(0x78, 4), (0x1F, 2), (0x40, 1)]:
        if value in constants:
            points += weight
            reasons.append(f"scalar {value:#x}")
    matched = stores & {0x30, 0x34, 0x3C, 0x40, 0x48, 0x50, 0x58, 0x5C, 0x60, 0x68}
    points += len(matched)
    reasons.append(f"{len(matched)} store-displacement leads (bases unproven)")
    size = function.get("size", 0)
    if 256 <= size <= 1536:
        points += 2
    if reference:
        similarity = SequenceMatcher(None, reference["mnemonics"], function["mnemonics"], autojunk=False).ratio()
        points += 30 * similarity
        lhs, rhs = Counter(reference["mnemonics"]), Counter(function["mnemonics"])
        union = sum((lhs | rhs).values())
        points += 10 * sum((lhs & rhs).values()) / max(union, 1)
        reasons.append(f"reference mnemonic similarity {similarity:.3f} (not independent proof)")
    return round(points, 3), reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--reference", type=Path, help="optional 13.0.4 feature export from your own dump")
    parser.add_argument("--reference-offset", type=lambda value: int(value, 0), default=REFERENCE_OFFSET)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    try:
        metadata, functions = read_features(args.target)
        if metadata.get("game_version") != "13.0.5":
            raise ValueError("target must be labelled 13.0.5")
        if not 1 <= args.top <= 100:
            raise ValueError("--top must be 1..100")
        reference = None
        if args.reference:
            reference_meta, records = read_features(args.reference)
            if reference_meta.get("game_version") != "13.0.4":
                raise ValueError("reference must be labelled 13.0.4")
            reference = next((f for f in records if f["offset"] == args.reference_offset), None)
            if reference is None:
                raise ValueError("reference function missing; check base and Ghidra analysis")
        ranked = sorted(((score(f, reference), f) for f in functions), key=lambda pair: (-pair[0][0], pair[1]["offset"]))[:args.top]
        print(json.dumps({"status": "UNVERIFIED_CANDIDATES", "target": metadata, "candidates": [
            {"offset": hex(f["offset"]), "name": f.get("name"), "size": f.get("size"), "score": result[0], "reasons": result[1], "calls": f.get("calls", []), "data_references": f.get("data_references", [])}
            for result, f in ranked
        ], "warning": "Scores rank inspection work, not confidence. No candidate satisfies ABI, layout, version, or network-path proof automatically."}, indent=2))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
