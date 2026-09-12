# Validation — lifecycle fix 0.3.1

Date: 2026-09-12

Version 0.3.1 separates the process-scoped Team Attack mutation from the
bounded diagnostic-recording lifetime. It changes no SSBU offsets, signatures,
proposal guards, participant ownership checks, or permitted write addresses.

## Automated results

- Host Rust tests: 35 passed, 0 failed.
- Python project tests: 15 passed, 0 failed.
- Host Clippy: passed with warnings denied.
- Switch-target Skyline Clippy: passed with no warnings.
- Switch-target release build: passed with cargo-skyline 3.5.0 and Skyline
  0.6.0.
- Compiled AArch64 callback emulation: 129 passed. This includes two explicit
  regression cases with diagnostic recording inactive and experiment mutation
  active: guarded `rule_submit` still changes only proposal `+0x11`, and guarded
  `local_copy` still changes only the reviewed local Team Attack byte.
- NRO structure: valid `NRO0` header, declared length, aligned ordered segments,
  and in-bounds segment ranges.
- Release ZIP integrity: checked during deterministic packaging.

## Compiled identities

- NRO SHA-256:
  `b14811cb9e4d480fe0a0aa7010bf8b9bc71af12c50cd825cc6921d0f6a0200ac`
- Release ELF SHA-256:
  `a54886b0d2fc67c44a591e56155a7c1c1d6249437fa53e29fff4ab34900a0e8a`

## Remaining hardware requirement

This validation proves the compiled callback remains capable of guarded
mutation when diagnostic recording is inactive. It does not emulate Smash's
full 20-minute runtime or live matchmaking. Hardware verification should keep
one Smash process open past the log cutoff, then obtain at least one fresh
Quickplay co-op rule submission and match after the cutoff.

Rule selection can independently produce Team Attack OFF before or after the
timeout. Version 0.3.1 fixes the accidental lifecycle cutoff only; it does not
claim deterministic selection of the local ON proposal.
