# Observer 0.2.3: codec batch — 2026-09-07

## Evidence and change

ssbu-rule-pipeline-trace.txt completed in 14 seconds: 29 selected/decompiled,
zero omissions, no reference cap. The complete 143-instruction encoder at
main+0x16A4920 and 137-instruction decoder at main+0x16A4B60 were recovered.
They are leaf routines using x0 (descriptor; rule pointer at +8) and x1
(stream pointer at +0, u32 cursor at +12). Neither accesses globals or calls
other functions. Both preserve x0 as the descriptor pointer; wrappers return
that value. Their dispatch slots are main+0x50831C0/+8.

The normal subrecord is 14 bytes: 13 scalar bytes and a flag byte. Team Attack
is rule+0x0D and bit 0x02 in the final encoded byte. Decoder reconstructs that
field as (flags >> 1) & 1. The encoder copies rule+9 without masking; isolation
assumes that base flag is canonical 0/1. No whole-network-packet offset or
Quickplay-specific classification is asserted.

Keystone reassembled all listed instructions; both first-32-byte prefixes
matched the independently exported raw signatures exactly. Unicorn executed
514 leaf calls: 128 canonical roundtrips, 256 decoder flag cases and two
noncanonical nonzero Team Attack encodes. All passed, including exact output,
cursor advance and private-page guard/write checks. This is simulation of
reconstructed code, not original binary execution or a Switch test.

## Native checks and observation

The optional observe_rule_codec flag defaults false. The prepared batch profile
sets it true and requires the existing bounded global watcher. Before any
native codec call or hook installation, the live game version must be 13.0.5,
all existing compact-entry/caller/global validations must pass, EVERY byte of
both live codec bodies must match the reconstruction (572/548 bytes), and both
relocated dispatch pointers must match. Kernel memory query validates readable,
non-executable module memory for the table, allowing RO or RW module sections.

The first native suite uses only owned arrays with guard bytes: 128 canonical
roundtrips and 256 flag-byte decoder cases (512 calls). It checks scalar and
Boolean values, untouched fields, cursor, descriptors, input and guard bytes.
Then two passive hooks are installed and the suite repeats through their entry
points and relocated originals. Synthetic calls run before live capture is
enabled and never consume live counters or slots. The after-hook test exercises
the passthrough/trampoline branch; its live logging branch is reviewed code,
not separately established by those synthetic calls.

Live hooks call the original exactly once with unchanged arguments and return
its x0 value. After return, bounded snapshots read descriptor rule bytes +9
and +0D and cursor +12 using machine reads, without Rust references to game
objects. The pre-call cursor is also sampled. The source reads the same fields,
never frees these objects, and does not change the descriptor. No packet bytes,
account identifiers or broad memory ranges are captured. Null/partial stream
paths are distinguished by advanced_14:0; only normal paths have length 14.

There are 256 single-use event slots shared by encode/decode; contention or
capacity exhaustion is counted as a dropped sample. Event times are post-call
monotonic times, not packet send/receive times. Events can drain out of order
under concurrency. Counters continue after slots fill. The writer flushes on
changes and at 5-second heartbeats, with the existing 20-minute limit. File
failures stop observation; installed hooks retain passthrough behavior. An
unexpected installation/trampoline or post-hook self-test failure fails closed
by aborting. Skyline hook publication is not transactional; startup-only
installation retains the existing narrow pointer-publication race limitation.

## Verification

- 26 host Rust tests passed, including native-suite test doubles plus deliberate
  neighbor-bit and guard corruption rejection, layout, config and existing tests.
- 15 existing Python tests passed.
- Host and Switch clippy passed with warnings denied.
- Switch release compiled with the existing pinned toolchain.
- Package NRO header, segments, lengths, contents and ZIP integrity checked.
- 0.2.3 hardware test: PENDING. No online test or mutation performed.

## Current project state

0.2.2 already worked on hardware: 104 initialized global observations and
user-confirmed No/Yes/No damage for Off/On/Return-Off. Its compact serializer
count stayed zero. This new batch validates additional hooks and performs all
three conditions in ONE game launch, covering within-process transitions.
Quickplay mode identification, negotiation/remote acceptance, effective
forced battle behavior and online safety remain unverified.
