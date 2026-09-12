#!/usr/bin/env python3
"""Summarize one 0.2.3 offline session; never infer Quickplay or match phases."""
import argparse
import hashlib
import json
from pathlib import Path


def summarize(path):
    raw = path.read_bytes()
    lines = raw.decode('utf-8-sig').splitlines()
    headers = {}
    for line in lines:
        if line.startswith('# ') and '=' in line and ':' not in line.split('=', 1)[0]:
            key, value = line[2:].split('=', 1)
            if key in headers:
                raise ValueError('Duplicate header: ' + key)
            headers[key] = value
    if headers.get('observer_version') != '0.2.3' or headers.get('game_version') != '13.0.5':
        raise ValueError('Expected observer 0.2.3 / game 13.0.5')
    if headers.get('observe_rule_codec') != 'true':
        raise ValueError('Codec observation was not enabled')
    events, counts, watch = [], [], []
    for line in lines:
        for prefix, target in [('# codec_event: ', events), ('# codec_counts: ', counts), ('# watch: ', watch)]:
            if line.startswith(prefix):
                target.append(dict(item.split(':', 1) for item in line[len(prefix):].split()))
    states = [line.split(': ', 1)[1] for line in lines if line.startswith('# observer_status: ')]
    failures = [s for s in states if 'FAIL' in s]
    transitions = []
    for row in watch:
        if row.get('initialized') == '1' and (not transitions or transitions[-1]['value'] != row['team_attack_global']):
            transitions.append({'elapsed_ms': int(row['elapsed_ms']), 'value': row['team_attack_global']})
    tests = {}
    for phase in ['before', 'after']:
        prefix = 'codec_private_selftest_' + phase + '_hooks_PASS:'
        matches = [s for s in states if s.startswith(prefix)]
        tests[phase + '_hooks'] = 'PASS' if len(matches) == 1 else 'MISSING_OR_DUPLICATE'
    return {
        'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
        'run_label': headers.get('run_label'), 'private_selftests': tests,
        'recorded_failures': failures, 'live_codec_event_count': len(events),
        'last_live_counts': counts[-1] if counts else None,
        'live_events': sorted(events, key=lambda e: (int(e['elapsed_ms']), int(e['sequence']))),
        'global_transitions': transitions,
        'note': 'Synthetic checks are separate from live counters. Zero live calls is a valid coverage result. Menu/match phases and damage outcomes require the operator note; no online or mutation conclusion.'
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(args.log), indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
