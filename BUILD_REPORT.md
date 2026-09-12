# Build report — guarded local B4 proposal experiment 0.3.0

Built for Super Smash Bros. Ultimate 13.0.5 from observer 0.2.6 and capture
0014. The experiment changes only a reviewed command-B4 payload Team Attack
byte at `+0x11` from `00` to `01` when the payload's bounded slot equals the
current local identity slot.

The mutation fails closed unless all of these are true: exact game version and
code signatures; co-op mode `07010102`; request `2`; prepared byte `0`; valid
initialized global Team Attack state `00`; B4 command; D0 payload length;
non-null payload; local slot 00..0F; payload slot equals local slot; original
proposal byte `00`; and one of the four reviewed B4 submit callers.

After a proposal is changed, a runtime-only session guard is armed. The local
rule source is mirrored `00` to `01` only if the reviewed `local_copy` branch
runs for that same session. The `participant_copy` branch has no write path, so
an opponent-selected ruleset is not locally mirrored by this experiment.
Neither receive hook mutates data. Writes are limited to the proposal byte and
the local-copy source byte. Capture events label successful writes as
`proposal_00_to_01` or `local_mirror_00_to_01`.

Capture 0014 contained nine local B4 submissions and four selection cycles.
One cycle selected the local-copy branch (`00/00`); three selected participant
records (`01/00`, `00/01`, `01/00`). This supported the ownership gate before
the hardware experiment.

Capture 0015 recorded two separate fresh Quickplay co-op matches against
unmodified opponents, not rematches. Match one selected Smashville and match
two selected Yoshi's Story from the user's modified legal-stage Preferred
Rules pool. Both matches completed normally with teammate damage working for
the local and opposing teams. The first cycle applied an ON participant record;
the second selected the local-copy branch and fired the guarded mirror. The
live Team Attack global remained `01` during both match periods and no
application or codec events were dropped.

This is evidence from two successful matches, not a guarantee for every
matchmaking outcome, region, plugin combination, future game update, or ban
safety.

Validation performed for this release is recorded in
`research/VALIDATION_0_3_0.md`; release hashes are in `SHA256SUMS.txt` beside
the packaged files.
