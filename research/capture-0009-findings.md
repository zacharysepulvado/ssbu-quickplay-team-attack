# Capture 0009: co-op rule selection and application observed

Reviewed 2026-09-08. This capture closes the missing runtime observation of the
participant-record selection and rule-application path for an OFF value. It
does not establish an ON override or agreement across consoles. No repeat of
this baseline, new game dump or Ghidra export is requested.

Input: capture-0009.log; 23,458 bytes; 273 lines; observer 0.2.4; game 13.0.5;
label APPLY_PATH_BATCH_01. User-confirmed offline damage and a normally
completed online match complete the baseline annotation. SHA-256:
`60200a43dbe9bdc783255b721a218eabc1937a68bf4308805e571ad0d4546358`.

## Decisive sequence

All four events carry co-op mode 07010102 and request type 2. They were sampled
at approximately 281.225 seconds after observer start. Tick order resolves the
sequence despite identical displayed millisecond values.

| Order | Event | Tick | Prepared | Team Attack in rule / global |
| --- | --- | --- | --- | --- |
| 1 | Participant record copied, slot 0 | 5399533149 | 0 | OFF / OFF |
| 2 | Selected record ready | 5399533497 | 0 | OFF / OFF |
| 3 | Before original rule application | 5399533692 | 1 | OFF / OFF |
| 4 | After original rule application | 5399533811 | 1 | OFF / OFF |

The prepared transition from 0 to 1 matches the reviewed original instructions.
No local-copy event was recorded. Counters finish at local=0, participant=1,
ready=1, before=1, after=1, dropped=0. The separate capture-bank sequence numbers
384/448/512/576 identify slots; they do not imply missing events.

This is the participant-copy branch of main+0x169BEF0, through the call to
main+0x16E3EC0 at main+0x169EC0C, followed by the reviewed restore call to
main+0x16EB720 at main+0x169C938. For slot 0, the source Team Attack byte is
session+0xB6A9; the selected destination byte is session+0x24649; the general
rule global is main+0x530A981. The source record was already OFF before the
copy and application. This run did not submit ON to the application call.

Slot 0 is a session record index. This observer does not identify its console,
account, ownership or authority. It must not be described as a particular
opponent, host or proven remotely received record.

## Other checks

- Both native codec self-test batches passed: 512 owned-buffer calls before
  hooks and 512 after hooks, separate from live counts.
- All five application sites were installed and their single-instruction
  patches verified. Four sites fired; the local branch has no runtime sample.
- Two natural encodes at 268.209 and 268.411 seconds, Team Attack OFF; both
  advanced the stream cursor from 36 to 50. Natural decoder calls: zero.
- Three compact captures, each with Team Attack OFF; final serializer/dump
  totals agree. Codec and application drop counters are zero.
- 80 global-watch rows, 78 initialized: 54 OFF and 24 ON. Observed transitions
  were OFF at 12.524 s, ON at 54.625 s, OFF at 174.564 s. These are polling
  observations, not exact UI-action or gameplay timestamps.
- Last heartbeat: 395.697 seconds. No observer failure or 20-minute limit was
  recorded. Log termination alone does not prove a clean match completion.

Structural checks passed for event totals, unique slot IDs, strictly ordered
ticks, tick-to-millisecond conversion, prepared flags, compact-record lengths,
read allowlist and final counts. The log remained active about 114 seconds
beyond application; no exact match-end, result-screen or disconnect marker is
available. The zero decoder count does not imply zero network reception.

## Remaining code work and completed operator notes

The selected/apply OFF path is now observed on hardware. The next code question
is how the chosen participant settings record is populated and published, and
how a value becomes common across participating consoles. A write only after
selection would not by itself establish that agreement. No gameplay-mutation
build or additional online test is requested in this review.

The current observer stays observation-only. This capture does not prove
synchronized Team Attack ON, repeated match/results/rematch stability, or ban
safety. Use the supplied executable for further static work; collect another
live test only after a concrete additional observation is ready.

On 2026-09-08 the user confirmed that the offline teammate hit caused damage
and the online match finished normally. These are operator observations, not
values derived from a match-end or damage marker in the log. The combined
0.2.4 baseline is complete. No operator notes remain pending, and no repeat
baseline or new export is needed. This does not establish rematch behavior,
general online safety or Team Attack ON agreement across consoles.
