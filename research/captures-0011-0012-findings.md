# Captures 0011 and 0012: both selection branches observed

Reviewed 2026-09-09. Playing multiple matches supplied useful additional
coverage. Both files report observer **0.2.4**, SSBU 13.0.5 and run label
`APPLY_PATH_BATCH_01`. They cannot contain the three rule-message observations
added in 0.2.5. This identifies the builds that produced these logs, not what
is currently installed on the SD card.

## Inputs and operator account

| File | Bytes / lines | SHA-256 |
|---|---|---|
| capture-0011.log | 24,717 / 273 | 7a42bf90272b2435ccdbeda2a340c0a62817afa15f24196f8f66faa4c7aa06aa |
| capture-0012.log | 73,845 / 815 | 7eda2c3480c99389e317242ac20af1869fa067555fa3b6c26f5f15bc396da0cb |

The user associates these sessions with September 7 and 8, respectively. They
are uncertain what they did on the seventh and think they played doubles.
They confirm playing multiple doubles matches with a friend on the eighth.
The logs contain elapsed times, not calendar timestamps, match-end markers or
an authoritative completed-match count. No exact total or error-free completion
of every match is inferred from that account.

## Recorded coverage

| Observation | 0011 | 0012 |
|---|---:|---:|
| Last reported elapsed time | 5m 54.772s | 19m 58.518s |
| Explicit 20-minute recording-stop message | No | Yes |
| Rule-selection/application sequences | 2 | 6 |
| Local-copy branch | 1 | 4 |
| Participant-copy branch | 1 | 2 |
| Entry mode / request | 07010101 / 1 | 07010102 / 2 |
| Natural encoder / decoder calls | 7 / 0 | 22 / 0 |
| Compact snapshots | 6 | 7 |
| Application / codec dropped events | 0 / 0 | 0 / 0 |

07010101 is the single-entry Quickplay route; it does not specify whether the
actual match was teams or one-on-one. 07010102 is the two-local-player co-op
route. The user's uncertain seventh-day recollection is not treated as a
controlled test label or contradicted by an unsupported match-format inference.

All eight sequences are complete in tick order:
local_copy OR participant_copy → selection_ready → apply_before → apply_after.
The prepared flag is 0, 0, 1, 1. Rule and initialized global Team Attack are
00 (OFF) in every one of these events. Participant copies both use slot 0;
that is a record index, not an identified player, remote console or host.

| Capture | Elapsed seconds | Source branch |
|---|---:|---|
| 0011 | 83.751 | Participant |
| 0011 | 309.103 | Local |
| 0012 | 111.212 | Participant |
| 0012 | 331.278 | Participant |
| 0012 | 552.377 | Local |
| 0012 | 734.144 | Local |
| 0012 | 908.010 | Local |
| 0012 | 1122.859 | Local |

The four local-copy co-op sequences are new runtime coverage beyond capture
0009, which recorded only the participant branch. All five 0.2.4 observation
sites have now fired in co-op mode. This supports both reviewed OFF selection
routes through rule application on this console. It does not show an ON
application, a particular sender's ownership or synchronized rules on peers.

## Integrity and scope

Both native private-buffer codec self-tests report PASS before and after hooks
(512 calls in each phase), separate from natural call counts. Both startup
logs verify all five application sites. The review script checks event totals,
unique sequence IDs, capture-bank mapping, unique ticks and millisecond
conversion, complete four-event groups, prepared transitions, codec cursor
advancement, compact lengths/read allowlist, and final counts. All fifteen
checks pass for each file. No failure status or dropped events is recorded.
No new game or callback execution test was performed for this review.

Capture 0011 has 75 watch rows, 73 initialized: 70 OFF and 3 ON. Observed
transitions are OFF at 12.450s, ON at 36.172s, OFF at 49.222s. These poll times
do not reconstruct exact UI actions. Capture 0012 has 240 watch rows, 238
initialized, all OFF. All compact Team Attack bytes and natural encoder Team
Attack values are OFF. All encoders advance the cursor from 36 to 50.

The 0012 logger explicitly stops at its 20-minute limit. Later recreational
matches are outside this file; stopping the logger does not stop the game.
The earlier six setups remain useful, but are not six verified completed
matches. Capture 0011 ends without a stop-reason or match-end marker, so its
termination reason is unknown. Zero calls to the instrumented decoder do not
mean no network reception. Absence of B4 event names is expected in 0.2.4 and
must not be interpreted as proof that the native B4 paths did not execute.

## Next action

The remaining runtime question is whether the newly instrumented B4 submit and
receive-copy paths run during ordinary co-op, and how their field observations
relate to selected/applied rules. Observer 0.2.5 was already built for this;
its hardware status remains pending. A future ON propagation/peer-agreement
question also remains open. No rule-mutation build exists.

If an existing newer capture says observer_version=0.2.5, inspect it before
requesting another match. Otherwise install the existing 0.2.5 plugin and its
RULE_MESSAGE_BATCH_01 config, verify the two files on the SD card, and complete
one ordinary co-op match within the 20-minute recording window with both
players active. Skip the completed offline rule toggles/damage tests. Extra
recreational matches are optional; only the first 20 minutes are recorded.
Upload the newest log and report any errors or disconnects. No new dump,
Ghidra export or ARC update is needed.

The revised package changes instructions and adds a read-only Windows hash
check; NRO and config bytes remain identical to the 2026-09-08 0.2.5 release.
The checker compares both files on E: with the release hashes. Those expected
hashes were verified against the packaged bytes here; Windows execution of
the checker was not available in this environment. A PASS establishes these
two on-card files, not which boot environment or plugin actually runs. The new
log must still identify 0.2.5. Airplane mode provides an offline startup check;
it does not establish protection from bans.
