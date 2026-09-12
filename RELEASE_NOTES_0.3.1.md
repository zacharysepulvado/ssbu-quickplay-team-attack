# v0.3.1 — persistent mutation lifecycle fix

Version 0.3.1 fixes a confirmed bug in v0.3.0 that stopped the Team Attack
mutation 20 minutes after the plugin started.

## Fix

- Diagnostic logging still stops after its bounded 20-minute capture window.
- Team Attack proposal mutation now remains active until Smash exits.
- Ending diagnostic recording no longer clears the armed matchmaking session.
- After recording stops, only the `rule_submit` and `local_copy` callbacks
  continue evaluating the existing guarded mutation path. The six passive-only
  application callbacks return immediately.
- The final capture status explicitly states that observation stopped while
  mutation remains active.

## Validation status

The regression suite verifies that experiment mutation remains enabled when
recording is inactive. All prior proposal, ownership, executable-signature,
configuration, capture, and codec tests remain in place.

This source and binary fix must still be tested on SSBU 13.0.5 hardware in a
single live session lasting longer than 20 minutes. Rule selection can still
produce Team Attack OFF before the timeout; v0.3.1 fixes the lifecycle cutoff,
not every matchmaking selection outcome.

## Installation

Download `SSBU-Team-Attack-ON-0.3.1.zip`, fully close Smash, and copy the
archive's `atmosphere` and `ultimate` folders to the SD-card root. Replace the
existing plugin and configuration when prompted.
