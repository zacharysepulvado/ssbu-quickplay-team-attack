# Technical development history

## Public-source reconstruction note

The repository does not redistribute the reviewed instruction excerpts used by
`src/application.rs` and `src/codec_probe.rs`. Their text-relative offsets,
lengths, and SHA-256 digests are published in `src/reviewed/manifest.json`. Run
`tools/materialize_reviewed.py` against `text.bin` extracted from a legally
dumped SSBU 13.0.5 `main` before building. The script refuses any slice whose
digest does not match the reviewed build.

Raw capture-analysis JSON is also excluded from the public tree because it can
retain account/date inferences and detailed runtime traces. The reviewed,
human-readable findings and bounded validation summaries remain under
`research/`.

## 1. Establishing the executable identity

Development targeted a legally dumped SSBU 13.0.5 `main` executable with
SHA-256 `eb79e639e47d9a0c79bcfe2ec50fc807afa9601800226627b58bd6a1a83dc52d`.
Offsets are relative to Skyline's mapped main text region. Runtime startup
checks require display version 13.0.5, exact code signatures, unique aligned
signature matches, executable-region bounds, and reviewed data mappings.

## 2. Locating the compact rule serializer

Static analysis compared structural function features with the previously known
13.0.4 serializer. The 13.0.5 compact CSS serializer was identified at text
offset `0x16E2C50`. Its output is 0x69 bytes, and Team Attack is stored at byte
`+0x11`. A separate direct caller at `0x169462C` supplied an independent code
signature and calling-convention check.

Passive serializer observations and repeated offline OFF/ON/OFF tests connected
byte `+0x11` with Team Attack. A separately reviewed battle-rule consumer and
global value confirmed that this was an applied gameplay rule, not merely a UI
or profile flag.

## 3. Mapping rule selection and application

Five application points were reviewed around the local-copy branch,
participant-copy branch, selection-ready state, and the call that applies the
selected rule. Passive captures showed the selected rule's Team Attack byte
moving to the live global at `main+0x530A981`. The initialization guard is at
`main+0x53144D8`.

The co-op mode value observed in this path is `0x07010102`; the relevant request
value is `2`. The local rule source is at session `+0x21FA9`, and the selected
rule field is at session `+0x24649`.

## 4. Mapping B4 proposal submission and reception

The online rule record uses command `0xB4` with length `0xD0`. Its Team Attack
field is payload `+0x11`; its bounded participant slot is payload `+0xC8`.
Submission enters the common routine at `0x1685CB0`.

Four direct 13.0.5 B4 callsites were identified:

- `0x1687FE8` — state/update participant record
- `0x1690880` — record mapped from the primary local identity
- `0x16F52D4` — explicit per-slot publisher
- `0x16FA0E4` — initial/current record using the primary local identity slot

The receive dispatcher validates a slot from 0 through 15 and stores payload
byte `+0x11` into that participant's settings record. Passive hooks were placed
before reception, after the original field store, at submission, and throughout
selection/application.

## 5. Distinguishing local ownership

The native helper at `0x16F6340` compares the primary identity pointer against
sixteen entries separated by `0x78` bytes. The observer reproduced only that
bounded comparison and logged the resulting slot; it never logged identities or
raw pointers.

Capture 0014 contained nine B4 submissions. Every submitted payload slot
matched the local identity slot: two `01/01` and seven `00/00`. Its four rule
selections contained one local-copy selection and three participant-copy
selections. This supplied the ownership evidence required for a narrow
proposal experiment.

## 6. Guarded mutation design

Version 0.3.0 changes payload `+0x11` only when every condition below is true:

- explicit `proposal_experiment` configuration mode;
- live and configured version are both 13.0.5;
- all reviewed function bodies, hook instructions, callsites, and dispatch
  tables match;
- current mode equals `0x07010102` and request equals `2`;
- the session preparation byte is `0`;
- the live global is initialized and currently OFF;
- command is B4, length is D0, and the payload pointer is non-null;
- the local identity maps to a valid slot 00 through 0F;
- payload slot equals that local slot;
- proposal Team Attack is exactly `00`;
- return address classifies as one of the four reviewed B4 callers.

After a successful proposal write, the plugin stores the session address only
in a runtime atomic guard. If the reviewed local-copy branch later executes for
that same session, and its source remains OFF under the same co-op/global
guards, the source is changed to ON before the original copy continues. The
participant-copy and receive branches never call a write path.

## 7. Validation before hardware testing

The 0.3.0 release passed:

- 34 host Rust tests;
- 11 Python project tests;
- host Clippy with warnings denied;
- Switch-target Skyline Clippy;
- release compilation using cargo-skyline 3.5.0 and Skyline 0.6.0;
- NRO header, declared-length, segment-bound, and alignment checks;
- 127 compiled AArch64 callback-emulation cases using a Skyline-style register
  save/restore handler;
- retained native B4 dispatch/copy tests across all sixteen slots, OFF/ON/A5,
  oversize input, and invalid-index rejection.

The release NRO SHA-256 is
`0c1239b11c0c1e6b3accb59b00d69ac8399145c8c46d7e2cd92632deefbb14a5`.

## 8. Hardware result

Capture 0015 used observer/experiment 0.3.0 on SSBU 13.0.5. The operator played
two separate fresh Quickplay co-op matches against unmodified opponents. Both
matches completed with Team Attack active for both teams; these were not
rematches.

The first cycle recorded a local B4 proposal mutation, then received an ON
participant record, selected it through `participant_copy`, and applied global
Team Attack `01`. The second cycle recorded multiple guarded local proposals,
selected `local_copy`, executed `local_mirror_00_to_01`, and again applied
global `01`. These internal branches do not independently identify which
console's Preferred Rules won. The first match selected Smashville and the
second selected Yoshi's Story, both from the operator's modified legal-stage
pool, supporting that the modified Preferred Rules were active. The global
watcher remained at `01` during both match periods and returned to `00`
afterward. No application or codec events were dropped.

## 9. Limits

Two successful matches demonstrate the mechanism but do not prove behavior for
every region, ruleset, matchmaking topology, plugin combination, or future
version. The capture shows what the modded console proposed, received, selected,
and applied; the gameplay observation establishes teammate damage on both
consoles in these matches. It does not establish ban safety.
