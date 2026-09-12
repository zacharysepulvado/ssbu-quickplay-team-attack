# Validation — experiment 0.3.0

- Rust formatting check: PASS.
- Host Rust tests: 34 PASS.
- Python project tests: 11 PASS.
- Host Clippy with warnings denied: PASS.
- Switch-target Skyline Clippy: PASS.
- Switch release build: PASS.
- NRO0 header, declared length, and segment alignment/bounds: PASS.
- Compiled AArch64 callback emulation: 127 PASS. This includes both permitted
  one-byte write targets, rejected slot/caller/state paths, the inert mode,
  capacity behavior, register preservation, and exact allowed reads.
- Original B4 receive/copy synthetic cases retained from 0.2.6: 51 PASS across
  all sixteen slots, OFF/ON/A5, oversize, and invalid-index cases.

Release NRO SHA-256:
`0c1239b11c0c1e6b3accb59b00d69ac8399145c8c46d7e2cd92632deefbb14a5`

Release ELF SHA-256:
`ddd500f711c9c2648277fcdd206c6137d31eb9fa5411149faf51d11f5e03730b`

These checks do not replace Switch hardware testing and do not prove server
acceptance, peer agreement, disconnect behavior, match behavior, or ban safety.

## Post-build hardware result

Capture 0015 subsequently recorded two separate fresh Quickplay co-op matches
against unmodified opponents. Both completed normally with teammate damage
working for the local and opposing teams. Match one selected Smashville and
match two selected Yoshi's Story from the user's modified Preferred Rules
stage pool. This is a two-match result, not proof for every matchmaking outcome
or of ban safety. See `../TECHNICAL_DEVELOPMENT.md` for the bounded conclusion.
