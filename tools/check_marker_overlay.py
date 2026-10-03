#!/usr/bin/env python3
"""Exercise the compiled marker draw callback with a stubbed graphics host.

Requires pyelftools and unicorn. This verifies callback control flow and labels,
not rendering on a Switch or the loader's order of plugin initialization.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X30, UC_ARM64_REG_PC, UC_ARM64_REG_SP

BASE, STACK, STUB = 0x10000000, 0x20000000, 0x30000000
END, GET_CONTEXT, TICK = STUB, STUB + 0x100, 1000


def run(path):
    data = Path(path).read_bytes()
    with open(path, 'rb') as stream:
        elf = ELFFile(stream)
        segments = [(s['p_vaddr'], s['p_memsz'], s.data()) for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        imports = [s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx'] == 'SHN_UNDEF']
        assert not any('imgui' in name.lower() for name in imports), 'mandatory renderer import'
        external = {}
        relocations = []
        for section in elf.iter_sections():
            if section['sh_type'] != 'SHT_RELA':
                continue
            table = elf.get_section(section['sh_link'])
            for r in section.iter_relocations():
                symbol = table.get_symbol(r['r_info_sym'])
                if r['r_info_type'] == 1027:
                    value = BASE + r['r_addend']
                elif r['r_info_type'] in (257, 1025, 1026):
                    if symbol['st_shndx'] != 'SHN_UNDEF':
                        value = BASE + symbol['st_value'] + r['r_addend']
                    else:
                        value = external.setdefault(symbol.name, STUB + 0x200 + 16 * len(external))
                else:
                    raise AssertionError(('unhandled relocation', r['r_info_type']))
                relocations.append((BASE + r['r_offset'], value))

    def find(module, suffix):
        matches = [BASE + v for n, v in symbols.items() if module in n and n.endswith(suffix)]
        assert len(matches) == 1, (module, suffix, matches)
        return matches[0]

    draw = find('marker_overlay', '4draw')
    getter = find('marker_overlay', '11GET_CONTEXT.0')
    snapshot = find('marker_state', '8SNAPSHOT.0')
    functions = {BASE + symbols[name]: name for name in [
        'igSetCurrentContext', 'igSetNextWindowPos', 'igSetNextWindowBgAlpha',
        'igBegin', 'igTextColored', 'igEnd',
    ]}
    ext_names = {v: k for k, v in external.items()}
    tests = [
        ('missing_host', False, 1, 2, TICK, True, None),
        ('null_context', True, 0, 2, TICK, True, None),
        ('unknown', True, 1, 0, TICK, True, None),
        ('on', True, 1, 2, TICK, True, 'TEAM ATTACK: ON (selected)'),
        ('off', True, 1, 1, TICK, True, 'TEAM ATTACK: OFF (selected)'),
        ('expired', True, 1, 2, TICK + 90 * 19_200_000 + 1, True, None),
        ('future', True, 1, 2, TICK - 1, True, None),
        ('clipped', True, 1, 2, TICK, False, None),
    ]
    for name, host, context, status, now, begin, expected in tests:
        u = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        size = (max(a + n for a, n, _ in segments) + 4095) & ~4095
        u.mem_map(BASE, size)
        u.mem_map(STACK, 0x10000)
        u.mem_map(STUB, 0x10000)
        for address, _, content in segments:
            if content:
                u.mem_write(BASE + address, content)
        for address, value in relocations:
            u.mem_write(address, struct.pack('<Q', value))
        u.mem_write(getter, struct.pack('<Q', GET_CONTEXT if host else 0))
        u.mem_write(snapshot, struct.pack('<Q', (TICK << 2) | status))
        u.reg_write(UC_ARM64_REG_SP, STACK + 0xf000)
        u.reg_write(UC_ARM64_REG_X30, END)
        calls, labels = [], []

        def hook(emulator, address, size, unused):
            if address == GET_CONTEXT:
                calls.append('get_context')
                emulator.reg_write(UC_ARM64_REG_X0, context)
            elif address in ext_names:
                assert 'GetSystemTick' in ext_names[address], ext_names[address]
                emulator.reg_write(UC_ARM64_REG_X0, now)
            elif address in functions:
                function = functions[address]
                calls.append(function)
                if function == 'igSetCurrentContext':
                    assert emulator.reg_read(UC_ARM64_REG_X0) == context
                elif function == 'igBegin':
                    emulator.reg_write(UC_ARM64_REG_X0, int(begin))
                elif function == 'igTextColored':
                    pointer = emulator.reg_read(UC_ARM64_REG_X0)
                    labels.append(bytes(emulator.mem_read(pointer, 64)).split(b'\0')[0].decode())
            else:
                return
            emulator.reg_write(UC_ARM64_REG_PC, emulator.reg_read(UC_ARM64_REG_X30))

        u.hook_add(UC_HOOK_CODE, hook)
        u.emu_start(draw, END, count=10000)
        assert u.reg_read(UC_ARM64_REG_PC) == END, name
        assert labels == ([] if expected is None else [expected]), (name, labels)
        assert calls.count('igBegin') == calls.count('igEnd'), (name, calls)
        if name in ('missing_host', 'null_context'):
            assert not any(c.startswith('ig') for c in calls), (name, calls)
    return {'result': 'PASS', 'cases': len(tests), 'mandatory_imgui_imports': 0,
            'release_elf_sha256': hashlib.sha256(data).hexdigest(),
            'scope': 'AArch64 draw control flow with stubbed host; Switch rendering and pre-match timing still unverified.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('elf')
    print(json.dumps(run(parser.parse_args().elf), indent=2))
