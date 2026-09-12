#!/usr/bin/env python3
"""Summarize three separately labelled launches without treating globals as packets."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from compare_dumps import BUFFER_LEN, DUMP, TOKEN, MAX_LOG_BYTES

WATCH = re.compile(r"# watch: elapsed_ms:(\d+) initialized:([01]) team_attack_global:([0-9A-F]{2}|--) serializer_calls:(\d+) stored_dumps:(\d+)")
CONTEXT = ("observer_version", "game_version", "serializer_text_offset", "caller_text_offset",
           "entry_signature", "caller_signature", "poll_global_team_attack", "global_text_offset",
           "global_init_guard_text_offset")

def read_session(path: Path) -> dict:
    with path.open('rb') as source:
        data = source.read(MAX_LOG_BYTES + 1)
    if len(data) > MAX_LOG_BYTES:
        raise ValueError(f"{path}: oversized log")
    metadata, rows, dumps, transitions, status = {}, [], {}, [], []
    for number, line in enumerate(data.decode('utf-8').splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if line.startswith('# watch:'):
            match = WATCH.fullmatch(line)
            if not match:
                raise ValueError(f"{path}:{number}: malformed watch row")
            elapsed, initialized, value, calls, stored = match.groups()
            row = dict(elapsed_ms=int(elapsed), initialized=initialized == '1',
                       value=None if value == '--' else int(value, 16),
                       calls=int(calls), stored=int(stored))
            if row['initialized'] != (row['value'] is not None):
                raise ValueError(f"{path}:{number}: uninitialized byte reported as data")
            if rows and any(row[key] < rows[-1][key] for key in ('elapsed_ms', 'calls', 'stored')):
                raise ValueError(f"{path}:{number}: clock/counter reversal; do not concatenate logs")
            if row['value'] is not None and (not transitions or transitions[-1]['value'] != row['value']):
                transitions.append(dict(elapsed_ms=row['elapsed_ms'], value=row['value']))
            rows.append(row)
        elif line.startswith('#'):
            if line.startswith('# observer_status: '):
                status.append(line.removeprefix('# observer_status: '))
            elif '=' in line:
                key, value = line[1:].strip().split('=', 1)
                if key in metadata:
                    raise ValueError(f"{path}:{number}: duplicate header")
                metadata[key] = value
        else:
            match = DUMP.fullmatch(line)
            if not match:
                raise ValueError(f"{path}:{number}: unknown data row")
            sequence, payload = match.groups()
            tokens = payload.split()
            if int(sequence) in dumps or len(tokens) != BUFFER_LEN or any(not TOKEN.fullmatch(t) for t in tokens):
                raise ValueError(f"{path}:{number}: malformed/duplicate dump")
            dumps[int(sequence)] = tokens
    if not metadata.get('observer_version'):
        raise ValueError(f"{path}: missing observer header")
    values = sorted({r['value'] for r in rows if r['value'] is not None})
    return dict(file=path.name, metadata=metadata, statuses=status,
                watch_rows=len(rows), last_elapsed_ms=rows[-1]['elapsed_ms'] if rows else None,
                largest_watch_gap_ms=max((b['elapsed_ms']-a['elapsed_ms'] for a,b in zip(rows,rows[1:])), default=None),
                initialized_global_values=values, contains_non_boolean_value=any(v not in (0,1) for v in values),
                global_transitions=transitions,
                serializer_calls=rows[-1]['calls'] if rows else None,
                serializer_dumps=len(dumps),
                watch_enabled=metadata.get('poll_global_team_attack') == 'true')

def summarize(paths: list[Path]) -> dict:
    if len(paths) != 3 or len({p.resolve() for p in paths}) != 3:
        raise ValueError('require three distinct launch logs in Off, On, Return-Off order')
    sessions = [read_session(p) for p in paths]
    reference = tuple(sessions[0]['metadata'].get(k) for k in CONTEXT)
    if any(tuple(s['metadata'].get(k) for k in CONTEXT) != reference for s in sessions[1:]):
        raise ValueError('observer/code/global contexts differ; these launches are not comparable')
    for label, session in zip(('OFF', 'ON', 'RETURN_OFF'), sessions):
        session['operator_reported_condition'] = label
    return dict(sessions=sessions, interpretation='Conditions are operator-reported. Global snapshots do not identify menu/match phases, effective battle rules, or Quickplay acceptance. Zero serializer dumps is distinct from zero global observations.')

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('off', type=Path)
    parser.add_argument('on', type=Path)
    parser.add_argument('return_off', type=Path)
    args = parser.parse_args()
    try:
        result = summarize([args.off, args.on, args.return_off])
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
