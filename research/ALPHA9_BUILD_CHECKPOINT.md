# Alpha.9 build checkpoint (uncompiled)

The GitHub `main` branch remains the published v0.3.1 source. This work branch
contains an experimental alpha.9 source change only; there is no alpha.9 NRO
or Switch install package yet.

## What was changed

- Remove the alpha.8 chooser inline hook and its high-frequency counter.
- Keep the guarded local proposal and serializer mutation paths unchanged.
- Retain bounded rule-submit, receive, stored, and selected-rule observations.
- Add `tools/analyze_rule_transitions.py` for correlating those events offline.

The alpha.8 capture showed 17 online doubles selections: three local ON,
six participant ON, and eight participant OFF. Alpha.6 showed 14 local ON,
one participant ON, and two participant OFF. Because the ownership mix changed,
the overall rates do not establish that the chooser hook caused the difference.
Six participant ON selections in alpha.8 had an observed OFF-to-ON receive
transition before selection; the eight OFF selections did not.

## Build environment and remaining gates

The previous build cache reports `rustc 1.95.0-nightly (a423f68a0
2026-02-13)` and a custom Skyline target at
`/root/.cargo/skyline/toolchain/skyline`. The current execution environment
does not have `cargo`, `rustc`, or that target toolchain. The cached NRO in
`target/` is alpha.8 and must not be repackaged as alpha.9.

The repository intentionally omits seven reviewed `.bin` excerpts and the
generated `src/codec_bytes.rs`; rebuild them locally from a lawful SSBU 13.0.5
dump as described in `src/reviewed/README.md`. Do not add them to GitHub.

Once the matching toolchain is restored, run the Rust host tests, strict
Clippy checks, Switch release build, and compiled callback checker. Verify
the NRO header and package contents before hardware testing. The Python
analyzer currently passes syntax checks and reproduces the selection counts
above. No live alpha.9 result has been claimed.

The local TA ON/OFF versus-screen marker is a separate later experiment; it
is not implemented here.
