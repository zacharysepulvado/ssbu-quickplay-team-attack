# Capture 0014 findings used by experiment 0.3.0

Input SHA-256: `2298f9c6a45260e7aabf88697a3e484130f6dc54a9fa8d9ada9e5b48c5a97935`.
Observer 0.2.6, SSBU 13.0.5, `RULE_OWNER_BATCH_01`.

The log contains nine B4 submissions. Every submitted record slot equals the
bounded local identity slot: two `01/01` and seven `00/00`. Reviewed submit
origins are four `state_update`, four `per_slot`, and one `initial_local`.

There are four rule selections. Exactly one used `local_copy` and reports local
slot 00 / selected owner 00. The other three used `participant_copy` and report
local/selected pairs 01/00, 00/01, and 01/00. All captured Team Attack values
were 00. This is the empirical basis for changing only a local-slot B4 proposal
and mirroring only at the local-copy branch.

The log does not identify accounts, prove network delivery, prove remote peer
agreement, establish completion boundaries for the four played matches, or
establish ban safety.
