#!/usr/bin/env python3
"""Find repeatable candidate bits across at least three offline Off/On/Off cycles."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from compare_dumps import BUFFER_LEN, Payload, read_log


def candidate_bits(triplets: list[tuple[Payload, Payload, Payload]]) -> list[dict]:
    if len(triplets) < 3:
        raise ValueError("at least three independent Off/On/Off cycles are required")
    records = [payload for triple in triplets for payload in triple]
    if any(len(record) != BUFFER_LEN for record in records):
        raise ValueError("wrong payload length")
    masks = {tuple(value is not None for value in record) for record in records}
    if len(masks) != 1 or not any(next(iter(masks))):
        raise ValueError("all samples must have the same nonempty capture mask")
    candidates = []
    for offset in range(BUFFER_LEN):
        if records[0][offset] is None:
            continue
        off_values = [sample[offset] for triple in triplets for sample in (triple[0], triple[2])]
        on_values = [triple[1][offset] for triple in triplets]
        for bit in range(8):
            mask = 1 << bit
            off = {value & mask for value in off_values}
            on = {value & mask for value in on_values}
            if len(off) == len(on) == 1 and off != on:
                candidates.append({"offset": hex(offset), "mask": hex(mask), "off_bits": hex(next(iter(off))), "on_bits": hex(next(iter(on))), "status": "CORRELATION_ONLY"})
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--triplet", nargs=3, action="append", required=True, metavar=("OFF", "ON", "RETURN_OFF"), help="three log-path:sequence references; repeat at least three times")
    args = parser.parse_args()
    try:
        triplets, identities, log_cache, contexts = [], set(), {}, set()
        for refs in args.triplet:
            triple = []
            for ref in refs:
                path_text, sequence_text = ref.rsplit(":", 1)
                path, sequence = Path(path_text).resolve(), int(sequence_text)
                identity = (path, sequence)
                if identity in identities:
                    raise ValueError("each sample must be distinct; do not reuse a capture to manufacture repetitions")
                identities.add(identity)
                if path not in log_cache:
                    log_cache[path] = read_log(path)
                log = log_cache[path]
                keys = ("observer_version", "game_version", "serializer_text_offset", "caller_text_offset",
                        "compact_buffer_length", "reviewed_abi", "entry_signature", "caller_signature")
                if any(key not in log.metadata for key in keys):
                    raise ValueError("A/B analysis requires complete v0.2 session headers")
                contexts.add(tuple(log.metadata[key] for key in keys))
                triple.append(log.captures[sequence])
            triplets.append(tuple(triple))
        if len(contexts) != 1:
            raise ValueError("samples have different observer/version/hook contexts")
        print(json.dumps({"cycles": len(triplets), "candidates": candidate_bits(triplets), "conclusion": "Candidate correlations only. A disassembled rule consumer and actual network-path tracing are still required."}, indent=2))
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
