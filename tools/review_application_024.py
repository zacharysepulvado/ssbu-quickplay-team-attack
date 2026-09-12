#!/usr/bin/env python3
"""Review 0.2.4 event coverage; never infer completed matches or remote ownership."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def review(path):
    raw = path.read_bytes()
    lines = raw.decode('utf-8-sig').splitlines()
    headers = {}
    for line in lines:
        match = re.fullmatch(r'# (\w+)=(.*)', line)
        if match:
            key, value = match.groups()
            if key in headers:
                raise ValueError('Duplicate header: ' + key)
            headers[key] = value
    if (headers.get('observer_version'), headers.get('game_version')) != ('0.2.4', '13.0.5'):
        raise ValueError('This review supports only observer 0.2.4 / SSBU 13.0.5')
    def rows(name):
        prefix = '# ' + name + ': '
        return [dict(item.split(':', 1) for item in line[len(prefix):].split())
                for line in lines if line.startswith(prefix)]
    app = sorted(rows('application_event'), key=lambda e: int(e['elapsed_ticks']))
    codec = rows('codec_event')
    ac, cc, watch = rows('application_counts'), rows('codec_counts'), rows('watch')
    statuses = [s[len('# observer_status: '):] for s in lines if s.startswith('# observer_status: ')]
    dumps = []
    for line in lines:
        match = re.fullmatch(r'dump (\d+): (.*)', line)
        if match:
            seq, content = match.groups()
            values = content.split()
            dumps.append({'sequence': int(seq), 'length': len(values),
                          'read_bytes': {str(i): v for i, v in enumerate(values) if v != '--'}})
    kinds = ['local_copy', 'participant_copy', 'selection_ready', 'apply_before', 'apply_after']
    actual = Counter(e['kind'] for e in app)
    checks = {
        'application_counts_match': all(actual[k] == int(ac[-1][n]) for k, n in zip(kinds, ['local', 'participant', 'ready', 'before', 'after'])),
        'application_sequence_unique': len({e['sequence'] for e in app}) == len(app),
        'ticks_unique': len({e['elapsed_ticks'] for e in app}) == len(app),
        'tick_ms_consistent': all(int(e['elapsed_ticks']) // 19200 == int(e['elapsed_ms']) for e in app),
        'bank_ids_consistent': all(int(e['sequence']) // 64 == kinds.index(e['kind']) + (5 if e['mode'] == '07010102' else 0) for e in app),
        'codec_counts_match': all(sum(e['direction'] == k for e in codec) == int(cc[-1][k]) for k in ['encode', 'decode']),
        'codec_sequences_unique': len({e['sequence'] for e in codec}) == len(codec),
        'codec_cursor_advances_14': all(int(e['cursor_after']) - int(e['cursor_before']) == 14 and e['advanced_14'] == '1' for e in codec),
        'compact_lengths_and_read_allowlist': all(d['length'] == 105 and set(d['read_bytes']) == {'17'} for d in dumps),
        'compact_counts_match': len(dumps) == int(watch[-1]['stored_dumps']) == int(watch[-1]['serializer_calls']),
        'compact_sequences_contiguous': [d['sequence'] for d in dumps] == list(range(len(dumps))),
        'no_recorded_drops': all(int(c['dropped']) == 0 for c in ac + cc),
        'five_sites_installed': 'application_five_sites_installed_single_instruction_patches_verified' in statuses,
        'private_selftests_pass': all(sum(s == f'codec_private_selftest_{phase}_hooks_PASS: calls:512 roundtrips:128 decode_flag_values:256' for s in statuses) == 1 for phase in ['before', 'after']),
    }
    groups = []
    pending = []
    for event in app:
        pending.append(event)
        if event['kind'] == 'apply_after':
            groups.append(pending)
            pending = []
    checks['complete_application_groups'] = not pending and all(
        len(g) == 4 and g[0]['kind'] in kinds[:2]
        and [e['kind'] for e in g[1:]] == kinds[2:]
        and [e['prepared'] for e in g] == ['0', '0', '1', '1']
        and len({(e['mode'], e['request']) for e in g}) == 1 for g in groups)
    transitions = []
    for w in watch:
        if w['initialized'] == '1' and (not transitions or transitions[-1]['value'] != w['team_attack_global']):
            transitions.append({'elapsed_ms': int(w['elapsed_ms']), 'value': w['team_attack_global']})
    return {
        'file': path.name, 'bytes': len(raw), 'lines': len(lines),
        'sha256': hashlib.sha256(raw).hexdigest(), 'headers': headers,
        'checks': checks, 'all_checks_pass': all(checks.values()),
        'application_event_counts': dict(actual), 'application_groups': groups,
        'last_application_counts': ac[-1], 'codec_events': codec, 'last_codec_counts': cc[-1],
        'compact_dumps': dumps, 'watch_rows': len(watch),
        'initialized_watch_values': dict(Counter(w['team_attack_global'] for w in watch if w['initialized'] == '1')),
        'global_transitions': transitions, 'last_watch': watch[-1],
        'last_reported_elapsed_ms': max(int(w['elapsed_ms']) for w in ac + cc + watch),
        'statuses': statuses,
        'recording_limit_reached': 'watch_limit_reached_20_minutes_observation_stopped' in statuses,
        'recorded_failure_statuses': [s for s in statuses if re.search(r'fail|error', s, re.I)],
        'completed_match_count': None,
        'scope': 'Rule-application sequences are not completed-match markers. Mode is an entry route, not a complete battle format. Log rows and bank sequence IDs are not global event order. Zero codec decodes does not mean no network reception. B4 events are unavailable in 0.2.4.'
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps({'format': 'SSBU_APPLICATION_024_REVIEW_1',
                      'captures': [review(p) for p in args.logs]}, indent=2))
