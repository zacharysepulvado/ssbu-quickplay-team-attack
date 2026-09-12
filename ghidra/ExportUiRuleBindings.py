# Trace names obtained from the user's original UI scripts into native code.
# @category SSBU.Research
# @runtime PyGhidra
import json
import re
import struct
import time
import zlib
from collections import OrderedDict

EXPECTED_SHA = 'eb79e639e47d9a0c79bcfe2ec50fc807afa9601800226627b58bd6a1a83dc52d'
BASE = 0x7100000000
LABELS = [
    'set_battle_mode', 'set_battle_rule', 'set_rule_staminae',
    'set_rule_stock', 'set_rule_time', 'set_rule_stage', 'set_rule_item',
    'open_priority_sub_window', 'decided_priority_sub_window',
    'close_priority_sub_window', 'is_busy_priority_sub_window',
    'open_priority_window', 'decided_priority_window', 'close_priority_window',
    'PRIORITY_RULE', 'g_is_rule_priority', 'BATTLE_MODE', 'RULE_ITEM',
    'online_priority', 'online_any', 'online_parallel',
    'SEQUENCE_ONLINE_MELEE_ANYONE', 'SEQUENCE_ONLINE_MELEE_WAIT_PARALLEL',
    'team_attack',  # Previously observed positive control only.
]
CHUNK = 1024 * 1024
OVERLAP = 128
MAX_BYTES = 192 * 1024 * 1024
MAX_SECONDS = 240
SCAN_SECONDS = 100
MAX_REPORT = 6000000
MAX_HITS_PER_LABEL = 20
MAX_FUNCTIONS = 36
MAX_WINDOWS = 100
ADDRESS_PATTERN = re.compile(b'[\x10\x30\x50\x70\x90\xb0\xd0\xf0]')


def hash40(label):
    raw = label.encode('ascii')
    return len(raw) << 32 | zlib.crc32(raw) & 0xffffffff


def byte_buffer(value):
    try:
        return memoryview(value).cast('B').tobytes()
    except (TypeError, ValueError):
        return bytes(int(v) & 255 for v in value)


def address_seed(word, pc):
    """Exact ADR/ADRP immediate decoding; not arbitrary address dataflow."""
    op = word & 0x9f000000
    if op not in (0x10000000, 0x90000000) or word & 31 == 31:
        return None
    immediate = ((word >> 5) & 0x7ffff) << 2 | ((word >> 29) & 3)
    if immediate & 0x100000:
        immediate -= 0x200000
    return (word & 31, (pc & ~0xfff) + (immediate << 12)
            if op == 0x90000000 else pc + immediate, op == 0x90000000)


def add_immediate(word, register):
    if word & 0xff800000 != 0x91000000 or (word >> 5) & 31 != register:
        return None
    if word & 31 == 31:
        return None
    return (word & 31, ((word >> 10) & 0xfff) << (12 if word & (1 << 22) else 0))


def move_wide(word):
    op = word & 0x7f800000
    if op not in (0x52800000, 0x72800000) or word & 31 == 31:
        return None
    width = 64 if word & 0x80000000 else 32
    shift = ((word >> 21) & 3) * 16
    if shift >= width:
        return None
    return op == 0x52800000, word & 31, (word >> 5) & 0xffff, shift, width


def hash_seed_pattern(targets):
    patterns = set()
    for value in targets:
        for shift in (0, 16, 32):
            imm = (value >> shift) & 0xffff
            if not imm:
                continue
            for width in (32, 64):
                if shift >= width:
                    continue
                word = (0xd2800000 if width == 64 else 0x52800000) | (shift // 16) << 21 | imm << 5
                raw = struct.pack('<I', word)
                patterns.add(b'(?:' + b'|'.join(re.escape(bytes([raw[0] | r])) for r in range(31)) + b')' + re.escape(raw[1:]))
    return re.compile(b'(?=(?:' + b'|'.join(sorted(patterns)) + b'))')


def hash_chain(raw, start, origin, targets, can_cross):
    move = move_wide(struct.unpack_from('<I', raw, start)[0])
    if not move or not move[0]:
        return None
    _, register, immediate, shift, width = move
    value = immediate << shift
    for index in range(16):
        pos = start + 4 * index
        if pos + 4 > len(raw):
            break
        if index:
            m = move_wide(struct.unpack_from('<I', raw, pos)[0])
            if m:
                zero, reg, imm, lane, bits = m
                if reg == register:
                    if zero:
                        break
                    value &= (1 << bits) - 1
                    value = (value & ~(0xffff << lane)) | imm << lane
            elif not can_cross(origin + pos, register):
                break
        if value in targets:
            return value, origin + pos
    return None


def address_uses(raw, origin, length, targets, can_cross, check):
    """ADR or ADRP followed by ADD within 16 instructions, with clobber checks."""
    pages = {v & ~0xfff for v in targets}
    for index, match in enumerate(ADDRESS_PATTERN.finditer(raw)):
        if index % 8192 == 0:
            check()
        pos = match.start() - 3
        if pos < 0 or pos >= length or (origin + pos) % 4:
            continue
        seed = address_seed(struct.unpack_from('<I', raw, pos)[0], origin + pos)
        if not seed:
            continue
        register, value, page = seed
        if not page:
            if value in targets:
                yield origin + pos, origin + pos, value, 'ADR'
            continue
        if value not in pages:
            continue
        for n in range(1, 17):
            at = pos + n * 4
            if at + 4 > len(raw):
                break
            add = add_immediate(struct.unpack_from('<I', raw, at)[0], register)
            if add and value + add[1] in targets:
                yield origin + pos, origin + at, value + add[1], 'ADRP_ADD'
            if not can_cross(origin + at, register):
                break


def code_addresses(raw, origin, can_cross, is_code):
    """Materialized code addresses in a small anchored window, not call pairs."""
    for pos in range(0, len(raw) - 3, 4):
        seed = address_seed(struct.unpack_from('<I', raw, pos)[0], origin + pos)
        if not seed:
            continue
        register, value, page = seed
        if not page:
            if is_code(value):
                yield origin + pos, value
            continue
        if not is_code(value):
            continue
        for n in range(1, 17):
            at = pos + n * 4
            if at + 4 > len(raw):
                break
            add = add_immediate(struct.unpack_from('<I', raw, at)[0], register)
            if add and is_code(value + add[1]):
                yield origin + at, value + add[1]
            if not can_cross(origin + at, register):
                break


def main():
    from ghidra.app.util import PseudoDisassembler
    from ghidra.app.decompiler import DecompInterface
    from ghidra.program.model.lang import Register

    if currentProgram is None:
        raise ValueError('Open the existing SSBU_13_0_5/main in CodeBrowser.')
    sha = str(currentProgram.getExecutableSHA256()).lower()
    if sha != EXPECTED_SHA or str(currentProgram.getLanguageID()) != 'AARCH64:LE:64:v8A':
        raise ValueError('Wrong program: use the same verified SSBU 13.0.5 main as before.')
    addr = lambda value: toAddr(hex(value))
    memory = currentProgram.getMemory()
    listing = currentProgram.getListing()
    fm = currentProgram.getFunctionManager()
    rm = currentProgram.getReferenceManager()
    text = memory.getBlock(addr(BASE))
    if text is None or not text.isExecute() or int(text.getStart().getOffset()) != BASE:
        raise ValueError('Expected executable text at 7100000000.')
    output = str(askFile('Save as ssbu-ui-rule-bindings.txt', 'Save').getAbsolutePath())
    if not output.lower().endswith('.txt'):
        output += '.txt'
    pseudo = PseudoDisassembler(currentProgram)
    started = time.monotonic()
    hits, issues, refs = [], [], []
    functions, sites, data_targets = OrderedDict(), OrderedDict(), OrderedDict()
    instructions, windows = {}, set()
    hit_counts, hit_seen, ref_seen = {}, set(), set()
    stats = {'literal_scan_bytes': 0, 'reference_scan_bytes': 0, 'hash_scan_bytes': 0,
             'literal_scan_complete': False, 'reference_scan_complete': False,
             'listing_instructions': 0, 'pseudo_instructions': 0, 'decode_failures': 0,
             'decompiled': 0}
    decompiler, stopped, written = None, None, 0

    def check():
        monitor.checkCancelled()
        if time.monotonic() - started >= MAX_SECONDS:
            raise TimeoutError('Overall time cap')

    def issue(kind, detail):
        if len(issues) < 300:
            issues.append({'kind': kind, 'detail': str(detail)})

    def read(value, length):
        raw = byte_buffer(getBytes(addr(value), length))
        if len(raw) != length:
            raise ValueError('Short read at ' + hex(value))
        return raw

    def instruction(value):
        if value in instructions:
            return instructions[value]
        check()
        ins = listing.getInstructionAt(addr(value))
        source = 'listing'
        if ins is None:
            source = 'pseudo'
            try:
                ins = pseudo.disassemble(addr(value))
            except Exception:
                check()
                ins = None
        if ins is None or int(ins.getLength()) != 4:
            stats['decode_failures'] += 1
            ins = None
        else:
            stats[source + '_instructions'] += 1
        instructions[value] = ins
        return ins

    def can_cross(value, register):
        ins = instruction(value)
        if ins is None:
            return False
        flow = ins.getFlowType()
        if not flow.isFallthrough() or flow.isCall() or flow.isJump() or flow.isTerminal():
            return False
        for obj in ins.getResultObjects():
            if isinstance(obj, Register):
                name = str(obj.getBaseRegister().getName()).lower()
                if name in ('x' + str(register), 'w' + str(register)):
                    return False
        return True

    def is_code(value):
        b = memory.getBlock(addr(value))
        return value % 4 == 0 and b is not None and b.isInitialized() and b.isExecute()

    def add_site(value, reason):
        if not is_code(value):
            return
        sites.setdefault(value, [])
        if reason not in sites[value]:
            sites[value].append(reason)

    def queue_function(value, reason):
        fn = fm.getFunctionContaining(addr(value))
        if fn is None or fn.isExternal() or fn.isThunk():
            return
        key = str(fn.getEntryPoint())
        if key in functions:
            if reason not in functions[key][1]:
                functions[key][1].append(reason)
        elif len(functions) < MAX_FUNCTIONS:
            functions[key] = [fn, [reason]]
        else:
            issue('function cap', key)

    blocks = [b for b in memory.getBlocks() if b.isInitialized() and not b.isOverlay()
              and b.getStart().getAddressSpace() == text.getStart().getAddressSpace()]
    blocks.sort(key=lambda b: (b.isExecute(), int(b.getStart().getOffset())))
    scan_state = {'complete': True}

    def chunks():
        scan_state['complete'] = True
        count = 0
        for b in blocks:
            cursor, end = int(b.getStart().getOffset()), int(b.getEnd().getOffset()) + 1
            while cursor < end:
                check()
                if time.monotonic() - started >= SCAN_SECONDS or count >= MAX_BYTES:
                    scan_state['complete'] = False
                    issue('scan cap; continuing with retained anchors', hex(cursor))
                    return
                size = min(CHUNK, end - cursor, MAX_BYTES - count)
                yield b, cursor, size, read(cursor, min(size + OVERLAP, end - cursor))
                count += size
                cursor += size

    with open(output, 'xb') as dest:
        def emit(label, data, final=False):
            nonlocal written
            body = data if isinstance(data, str) else json.dumps(data, indent=2)
            raw = ('\n=== ' + label + ' ===\n' + body + '\n').encode('utf-8')
            if not final and written + len(raw) > MAX_REPORT - 100000:
                raise OverflowError('Report cap')
            dest.write(raw)
            dest.flush()
            written += len(raw)

        def add_hit(label, kind, value, details=None):
            key = (label, kind, value)
            if key in hit_seen:
                return
            hit_seen.add(key)
            count_key = (label, kind)
            hit_counts[count_key] = hit_counts.get(count_key, 0) + 1
            if hit_counts[count_key] > MAX_HITS_PER_LABEL:
                if hit_counts[count_key] == MAX_HITS_PER_LABEL + 1:
                    issue('anchor hit cap', count_key)
                return
            row = {'label': label, 'kind': kind, 'address': hex(value), 'details': details,
                   'role': 'positive control' if label == 'team_attack' else 'unverified UI binding anchor'}
            hits.append(row)
            emit('ANCHOR', row)
            if kind != 'MOV_HASH40':
                data_targets.setdefault(value, []).append(label)
            if kind == 'MOV_HASH40' and label != 'team_attack':
                add_site(value, label + ': MOV hash anchor')

        def add_ref(site, target, kind, start=None):
            key = (site, target, kind)
            if key in ref_seen:
                return
            ref_seen.add(key)
            labels = data_targets.get(target, [])
            row = {'site': hex(site), 'target': hex(target), 'kind': kind, 'labels': labels}
            if start is not None:
                row['start'] = hex(start)
            refs.append(row)
            emit('REFERENCE CANDIDATE', row)
            if labels != ['team_attack']:
                add_site(site, ','.join(labels) + ': ' + kind)

        def window(value, reason, before=0x60, after=0x140):
            low, high = value - before, value + after
            if any(a <= low and high <= b for a, b in windows):
                return
            if len(windows) >= MAX_WINDOWS:
                issue('code window cap', hex(value))
                return
            windows.add((low, high))
            rows = []
            for pc in range(low, high, 4):
                if not is_code(pc):
                    continue
                ins = instruction(pc)
                row = {'address': hex(pc), 'word': read(pc, 4).hex(),
                       'instruction': str(ins) if ins is not None else None}
                if ins is not None:
                    row['flows'] = [str(a) for a in ins.getFlows()]
                rows.append(row)
            emit('CODE WINDOW', {'reason': reason, 'not_function_bounds': True, 'rows': rows})

        try:
            emit('METADATA', {'format': 'SSBU_UI_RULE_BINDINGS_1', 'sha256': sha,
                 'labels': {s: hex(hash40(s)) for s in LABELS},
                 'label_provenance': '86-file original UI export b0f12857c07dc75b1fe17a000cfdc13feb7609ec6eb87b8c2f9c20843ac31d05; team_attack is an earlier control',
                 'scope': 'Read-only program access. Exact ASCII substrings, literal u64 hashes, MOVZ/MOVK hash construction, database references, aligned absolute pointers, ADR and ADRP/ADD candidates. Pseudo-disassembly covers undefined Listing bytes.',
                 'limits': 'Names can be unused or belong to unrelated bindings. No automatic pairing of neighboring table pointers. No separate runtime modules, arbitrary dataflow, relative tables, or automatic function creation. No patch or hook approval.',
                 'caps': {'seconds': MAX_SECONDS, 'scan_seconds': SCAN_SECONDS, 'report_bytes': MAX_REPORT}})
            println('Finding original UI callback names and hashes...')
            hashes = {hash40(label): label for label in LABELS}
            patterns = [(s, 'ASCII', s.encode('ascii')) for s in LABELS]
            patterns += [(s, 'U64_HASH40', struct.pack('<Q', hash40(s))) for s in LABELS]
            seeds = hash_seed_pattern(hashes)
            for block, origin, size, raw in chunks():
                stats['literal_scan_bytes'] += size
                for label, kind, needle in patterns:
                    pos = raw.find(needle)
                    while 0 <= pos < size:
                        add_hit(label, kind, origin + pos,
                                {'surrounding_hex': raw[max(0, pos - 16):pos + len(needle) + 32].hex()})
                        if kind == 'ASCII':
                            # Paths may contain the target name after a prefix;
                            # references normally point at the entire C string.
                            begin = pos
                            while begin > max(0, pos - 128) and 32 <= raw[begin - 1] < 127:
                                begin -= 1
                            if begin < pos and begin > 0 and raw[begin - 1] == 0:
                                add_hit(label, 'ASCII_CONTAINER', origin + begin,
                                        {'matched_substring_address': hex(origin + pos),
                                         'prefix': raw[begin:pos].decode('ascii')})
                        pos = raw.find(needle, pos + 1)
                if block.isExecute():
                    stats['hash_scan_bytes'] += size
                    for match in seeds.finditer(raw):
                        pos = match.start()
                        if pos >= size or (origin + pos) % 4 or pos + 4 > len(raw):
                            continue
                        found = hash_chain(raw, pos, origin, hashes, can_cross)
                        if found:
                            add_hit(hashes[found[0]], 'MOV_HASH40', origin + pos,
                                    {'end': hex(found[1]), 'value': hex(found[0])})
            stats['literal_scan_complete'] = scan_state['complete']
            emit('ANCHOR SUMMARY', {'counts': len(hits), 'stats': stats})

            # Database references first; then raw reference scans for undefined code.
            for value in list(data_targets):
                it, count = rm.getReferencesTo(addr(value)), 0
                while it.hasNext() and count < 24:
                    check()
                    r = it.next()
                    add_ref(int(r.getFromAddress().getOffset()), value, 'database:' + str(r.getReferenceType()))
                    count += 1
                if it.hasNext():
                    issue('database reference cap', hex(value))
            println('Following callback names into code and registration tables...')
            # Only targets known before this pass; extra slots get DB references below.
            initial_targets = set(data_targets)
            pointer_patterns = [(target, struct.pack('<Q', target)) for target in initial_targets]
            pointer_slots = []
            for block, origin, size, raw in chunks():
                stats['reference_scan_bytes'] += size
                for target, needle in pointer_patterns:
                    pos = raw.find(needle)
                    while 0 <= pos < size:
                        if (origin + pos) % 8 == 0:
                            add_ref(origin + pos, target, 'possible absolute pointer')
                            if not block.isExecute():
                                pointer_slots.append((origin + pos, target))
                        pos = raw.find(needle, pos + 1)
                if block.isExecute() and initial_targets:
                    for start, site, target, kind in address_uses(raw, origin, size, initial_targets, can_cross, check):
                        add_ref(site, target, kind, start)
            stats['reference_scan_complete'] = scan_state['complete']

            # Preserve all anchor/reference records before bounded context expansion.
            for slot, target in pointer_slots[:48]:
                b = memory.getBlock(addr(slot))
                low = max(int(b.getStart().getOffset()), slot - 32)
                high = min(int(b.getEnd().getOffset()) + 1, slot + 48)
                raw = read(low, high - low)
                emit('POINTER TABLE CONTEXT', {'slot': hex(slot), 'anchor': hex(target), 'start': hex(low), 'bytes': raw.hex(),
                     'note': 'Neighboring code pointers are candidates, not confirmed name-handler pairs.'})
                if data_targets.get(target) == ['team_attack']:
                    continue
                for p in range((low + 7) & ~7, high - 7, 8):
                    v = struct.unpack_from('<Q', raw, p - low)[0]
                    if is_code(v):
                        add_site(v, 'possible callback pointer near slot ' + hex(slot))
                it, count = rm.getReferencesTo(addr(slot)), 0
                while it.hasNext() and count < 8:
                    r = it.next()
                    add_site(int(r.getFromAddress().getOffset()), 'references callback-name pointer slot ' + hex(slot))
                    count += 1
            if len(pointer_slots) > 48:
                issue('pointer table expansion cap', len(pointer_slots))

            priority = lambda row: (not any('set_' in reason for reason in row[1]), row[0])
            secondary = OrderedDict()
            primary_sites = sorted(sites.items(), key=priority)
            for value, reasons in primary_sites[:72]:
                queue_function(value, '; '.join(reasons))
                window(value, reasons)
                b = memory.getBlock(addr(value))
                low = max(int(b.getStart().getOffset()), value - 0x60)
                high = min(int(b.getEnd().getOffset()) + 1, value + 0x140)
                for site, target in code_addresses(read(low, high - low), low, can_cross, is_code):
                    if target not in sites and not low <= target < high:
                        secondary.setdefault(target, []).append({'site': hex(site), 'anchor_site': hex(value)})
            if len(primary_sites) > 72:
                issue('primary context cap', len(primary_sites))
            for target, evidence in list(secondary.items())[:24]:
                emit('MATERIALIZED CODE CANDIDATE', {'target': hex(target), 'evidence': evidence,
                     'note': 'Possible callback or unrelated code address; not a confirmed binding.'})
                queue_function(target, 'code address materialized near a UI anchor')
                window(target, 'possible callback body from materialized code address', before=0, after=0x400)
            if len(secondary) > 24:
                issue('materialized code expansion cap', len(secondary))

            emit('FUNCTION MODELS', [{'entry': k, 'reasons': v[1]} for k, v in functions.items()])
            if functions:
                decompiler = DecompInterface()
                decompiler.toggleCCode(True)
                decompiler.toggleSyntaxTree(False)
                if not decompiler.openProgram(currentProgram):
                    raise ValueError('Decompiler open failed; anchor and instruction records retained')
            for key, (fn, reasons) in functions.items():
                check()
                if int(fn.getBody().getNumAddresses()) > 65536:
                    issue('large function C skipped', key)
                    continue
                result = decompiler.decompileFunction(fn, min(6, max(1, int(MAX_SECONDS - time.monotonic() + started))), monitor)
                check()
                if result.decompileCompleted() and result.getDecompiledFunction() is not None:
                    c = str(result.getDecompiledFunction().getC())
                    if len(c) > 60000:
                        issue('C truncated', key)
                        c = c[:60000] + '\n/* TRUNCATED */'
                    emit('C CODE ' + key, c)
                    stats['decompiled'] += 1
                else:
                    issue('decompile failed', key + ': ' + str(result.getErrorMessage()))
        except Exception as error:
            stopped = str(error) or type(error).__name__
        finally:
            if decompiler is not None:
                decompiler.dispose()
            status = 'PARTIAL' if stopped or issues or stats['decode_failures'] or monitor.isCancelled() else 'FINISHED'
            emit('ISSUES', issues, final=True)
            emit('END REPORT', {'status': status, 'stop_reason': stopped, 'stats': stats,
                 'anchors': len(hits), 'reference_candidates': len(refs), 'code_windows': len(windows),
                 'existing_function_models': len(functions), 'elapsed_seconds': round(time.monotonic() - started, 1),
                 'note': 'A zero-hit or PARTIAL report is useful. FINISHED is collection status, not proof of a working override.'}, final=True)
    println('Saved ' + output)
    println('Status: ' + status + '. Upload the text report, including PARTIAL reports.')


if __name__ == '__main__':
    main()
