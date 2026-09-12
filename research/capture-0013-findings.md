# Capture 0013: B4 rule-message paths observed on the Switch

Reviewed 2026-09-10. The targeted observer 0.2.5 runtime capture is received.
Its three new sites all fired during co-op mode. No repeat of this capture,
offline toggle test, new installation or additional online match is requested
to establish this same coverage.

Input: `capture-0013.log`, 88,520 bytes, 846 lines, SHA-256
`be53a3f5281b96a454f4dea913d374c079e6e8b0db9860df0ee5be4ce357ec93`.
Observer 0.2.5; SSBU 13.0.5; label `RULE_MESSAGE_BATCH_01`.
The user later confirmed that multiple matches finished normally, that they
rematched after some matches and declined after others, and that no disconnect,
startup error or unusual behavior occurred. The exact match count is unknown.
These are operator observations; the log does not contain match-end markers.

## What is directly recorded

| Observation | Count | Team Attack |
|---|---:|---|
| Filtered B4/D0 submit-entry observations | 4 | OFF |
| B4 payload observations before the field copy | 18 | OFF |
| Participant-record observations after the original field store | 18 | OFF |
| Participant selection → ready → before apply → after apply | 7 sequences, 28 events | OFF at every site |
| Local-copy observations | 0 | No sample in this capture |
| Natural encoder / decoder calls | 8 / 0 | All encodes OFF |
| Compact serializer snapshots | 8 | OFF |
| Initialized global-watch observations | 239 | All OFF |
| Reported application / codec dropped events | 0 / 0 | — |

All 68 application/message events report co-op mode `07010102`, request `2`,
and an initialized global Team Attack byte. All eight inline sites report
successful installation verification. Seven sites actually fired here,
including all three newly added sites. The local-copy branch was observed
under 0.2.4 in capture 0012; that does not turn this run's zero local count
into a new 0.2.5 local-hook runtime sample.

The four submit events carry slot 1 three times and slot 0 once. The receive
and stored samples have eleven pairs for slot 0 and seven for slot 1. These
are bounded record indices, not console, player, sender or host identities.
In particular, the fact that early submits use slot 1 while early receives
and selections use slot 0 does not identify either slot's owner.

## Ordering and connection to selection

The logger drains independent event banks. Printed line order and sequence
numbers do not represent global chronological order. Sorting by captured
elapsed ticks gives eighteen adjacent receive-before / field-stored pairs,
each with matching slot, mode, request, preparation state and OFF value.
The paired observations are 17–73 ticks apart (about 0.89–3.80 microseconds),
including observation overhead. These times are not network latency or an
unperturbed measurement of the native field-copy duration.

Each of the seven participant selections has an immediately preceding
same-slot, same-value stored observation in the chronological event stream:

| Setup time after observer start | Selected slot | Store to selection observation gap |
|---|---|---:|
| 1:11.277 | 0 | 241 ticks / 12.552 microseconds |
| 4:09.543 | 0 | 408 ticks / 21.250 microseconds |
| 7:29.276 | 0 | 226 ticks / 11.771 microseconds |
| 10:10.326 | 0 | 283 ticks / 14.740 microseconds |
| 12:47.458 | 1 | 341 ticks / 17.760 microseconds |
| 16:19.241 | 1 | 307 ticks / 15.990 microseconds |
| 19:55.491 | 1 | 382 ticks / 19.896 microseconds |

For every four-event application sequence, the prepared flag is 0, 0, 1, 1.
The reviewed native code copies B4 payload Team Attack at `+0x11` into the
participant record at `session + slot*0x1350 + 0xB6A9`; selection reads that
layout, then application receives the selected record at `session+0x24638`
and copies its Team Attack byte to `main+0x530A981`.

The observed order and matching field layout support this local OFF path.
The logger does not retain session identities, message identities, sender
identities or full rule records. Same-slot temporal association therefore
does not prove per-message causal provenance across sessions or across the
network. Four submissions cannot be matched one-for-one to eighteen received
copies. A local dispatcher invocation can include local dispatch/loopback;
it is not by itself a verified packet from an unmodified opponent.

## Integrity and recording boundary

Both original codec private-buffer self-tests report PASS, with 512 calls
before hooks and 512 after hooks. They are separate from the eight natural
encodes, which all advance the stream cursor from 36 to 50. The compact
records each contain 105 slots and read only the configured Team Attack byte.

The reproducible review script checks final totals, unique event slots/ticks,
version-specific bank mapping, tick-to-millisecond conversion, complete
application sequences, prepared-state order, codec cursor changes, compact
lengths/read allowlist, final serializer totals, recorded drops, startup
verification and temporal receive/store pairing. All seventeen checks pass.
No observer failure status is present. That is not proof that the game never
disconnected or displayed an error; this logger has no such event stream.

There are 241 watch rows: two uninitialized, then 239 OFF starting at 12.753s.
The last watch row is at 1199.496s, the last codec count at 1199.760s, and the
file explicitly reports `watch_limit_reached_20_minutes_observation_stopped`.
The seventh rule setup is only about 4.5 seconds before the observation limit.
Seven setups must not be reported as seven completed matches. The game can
continue after recording stops. Zero calls to the instrumented general-rule
decoder do not mean zero reception; the B4 copy path demonstrably executed.

## Resolved checkpoint and next action

The outstanding 0.2.5 question—whether its filtered submit and B4 receive/store
sites naturally execute in co-op—is answered yes. Receive/store and subsequent
participant selection/application are now observed repeatedly with OFF on the
user's console. Startup and these seven sites have hardware evidence; this is
not a blanket compatibility or long-term stability certification.

Still unresolved: which submission caller and participant owner each sample
belongs to, whether a locally proposed ON value can become the selected rule,
what validation or later updates affect it, and whether all participating
consoles apply the same ON value. The private-buffer ON copy tests retained
with the source do not establish those network/gameplay claims. No mutation
build has been produced, and ban safety is not established.

The next engineering target is the B4 submission callers, slot ownership and
selection authority in the already supplied executable, followed by a
controlled peer-agreement experiment designed around those findings. Another
ordinary OFF co-op capture with this same observer is not requested. A future
experiment must add an observation or intervention that distinguishes these
questions, rather than repeating the completed baseline.

**Needed from the user now:** say whether the doubles matches finished normally
and whether there were any disconnects, startup errors or unusual behavior.
No exact count or recollection of every match is required. Keep the current
capture and installation files; no further SD-card swap is needed for this
review. That operator note closes the annotation gap, not the ON propagation
gap. No additional game dump or Ghidra export is requested.
