# B4 caller and bounded rule-owner mapping — observer 0.2.6

Static review of the SSBU 13.0.5 executable found four direct sites that build
command B4 with length D0 and call the common submit routine at 0x1685CB0:

| call | classified source |
| --- | --- |
| 0x1687FE8 | state/update participant record |
| 0x1690880 | record mapped from the primary local identity |
| 0x16F52D4 | explicit per-slot record publisher |
| 0x16FA0E4 | initial/current record using the primary local identity slot |

The helper at 0x16F6340 compares an identity pointer with sixteen table entries
spaced 0x78 bytes apart and returns the matching bounded slot or FF. Observer
0.2.6 mirrors only this comparison and records the slot number. It never records
the identity pointer. The submit callback also converts x30 into one of the four
reviewed caller labels; raw return addresses are not logged.

Capture 0013 showed one B4 submission near the beginning of each observed
matchmaking cycle, not four submissions in one cycle. Three cycles submitted
slot 1 and selected a freshly received slot-0 record; a later cycle submitted
slot 0 and selected a freshly received slot-1 record. That pattern strongly
suggests different local and selected records, but 0.2.5 did not retain the
local slot or the B4 caller. It is not enough to justify mutation.

Observer 0.2.6 adds `local_slot`, `selected_owner_slot`, and `submit_origin` to
the existing bounded event lines. All hooks remain passive. The next combined
test covers a first match, a rematch, and a fresh queue in one launch so caller
and owner behavior can be compared without separate redundant runs.

This evidence does not establish server acceptance, peer agreement, ban safety,
or a safe mutation point.
