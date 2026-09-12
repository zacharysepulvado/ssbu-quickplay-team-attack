# Offline batch observer 0.2.2 — 2026-09-07

## Evidence prompting this revision

The user's capture-0000.log (menu startup) and capture-0001.log (the requested
offline match test) both identify observer 0.2.1 / Smash 13.0.5 and record
log_ready_before_hook and hook_installed. Neither contains a dump row.
This console-confirms the 0.2.1 creation repair and hook publication. It does
not prove the serializer executed, nor that it is exclusively an online path.
No repeated unchanged offline match tests are requested with 0.2.1.

## Change

0.2.2 retains the reviewed original-first serializer hook and selected byte 11.
An optional poll_global_team_attack flag adds a worker-thread observation of
main+0x530a981, with initialization guard main+0x53144d8. This is the statically
identified global source byte, not a packet or effective battle-rule consumer.
It never calls the serializer artificially and never writes a game rule.

Before reading, the usual live version / unique entry / unique caller / BL
validation runs. Additional instructions in the live serializer are checked:
ADRP/ADD global base, MOV W10 #0x2214, LDR X10, and its STUR at output+0x0c;
the initialized flag's ADRP/ADD are also checked. The projected source address
for output+0x11 is main+0x5308000+0x768+0x2214+5 = main+0x530a981.
Both absolute byte addresses must lie in kernel-reported readable/writable,
non-executable module data, above the module data start. Mapping checks run
before the hook is installed. There are no pointer-chain walks or heap reads.

The worker polls every 250 ms, emitting a watch row on a sampled change or
counter change and at least every five seconds while the worker is running.
Until guard bit 0 is set, the field is not read and is represented as --.
A value outside 0/1 is preserved as evidence, not silently normalized.
Calls entering the serializer are counted separately from written buffer dumps.
Elapsed milliseconds use GetSystemTick differences / 19200, avoiding an
absolute-tick multiplication overflow. Dump timing comments give writer-drain
time, not exact callback time. No GUI phase detector or automatic condition
labelling is claimed. Each game process gets its own incrementing capture file.
A 20-minute watch limit bounds output and disables observation for that launch;
the original serializer continues unchanged. Existing capture capacity remains
256, while global watching continues independently until the time limit.

## Validation and practical limits

- Host Rust tests: 23 passed, including the exact packaged batch profile.
- Host and Switch clippy: pass with warnings denied.
- Switch release build: pass on the same pinned toolchain as 0.2.1.
- Python tests: 15 passed, including separate global/dump accounting, backwards
  clock detection, uninitialized values, duplicate sessions and mixed-build refusal.
- Five fixed source instruction encodings independently decoded with Capstone
  and compared to the user's Ghidra disassembly; both ADRP targets also reviewed.
- Hardware test of 0.2.2: PENDING. No Quickplay or mutation test has occurred.
- Global reads are asynchronous byte snapshots, not an atomic game-state snapshot.
  Transitions shorter than the polling interval can be missed. The global may
  represent defaults, saved rules, or a different mode from local Smash.
- The config label OFFLINE_BATCH_01 names the whole batch. Individual Off/On/Off
  labels come from the operator's launch order, not from game-mode detection.

## Primary implementation references

Memory query ABI and 40-byte MemoryInfo layout:
https://github.com/switchbrew/libnx/blob/master/nx/include/switch/kernel/svc.h
SVC 0x06 register convention:
https://github.com/switchbrew/libnx/blob/master/nx/source/kernel/svc.s
Pinned tick implementation used for frequency verification:
https://github.com/skyline-rs/rust-src/blob/fabcf8e5bebc0d31e33717778a89df97d2b0e443/library/std/src/sys/time/switch.rs
Game addresses and field identity come from the user's ssbu-team-attack-trace.txt
and team-attack-candidate.json, not from those SDK sources.

## Batch analysis

Run tools/summarize_offline_batch.py OFF.log ON.log RETURN_OFF.log on three
distinct launch logs. It reports global transitions and serializer captures
separately and refuses incompatible observation contexts. Conditions are
operator-reported. It does not automatically approve a field, mutation or online
compatibility. A single triplet is a coverage/correlation screen; any useful
finding still requires independent confirmation before a gameplay change.
