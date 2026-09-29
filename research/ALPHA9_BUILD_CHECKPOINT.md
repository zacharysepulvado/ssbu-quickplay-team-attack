# Alpha.9 build checkpoint

The GitHub `main` branch remains the published v0.3.1 source. This work branch
contains experimental alpha.9 source. Its install ZIP was compiled and saved
separately for hardware testing; it is not a published GitHub release.

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

## Restored build environment and verification

The previous build cache reports `rustc 1.95.0-nightly (a423f68a0
2026-02-13)`. The matching official archive is `nightly-2026-02-14`.
Rustup 1.29.1 and cargo-skyline 3.5.0 were installed in this workspace.
Because `cargo skyline update-std` failed its GitHub API lookup, its documented
steps were performed manually: copy `nightly-2026-02-15` into the custom
Skyline toolchain, clone `skyline-rs/rust-src` branch `skyline` with submodules,
and `rustup toolchain link skyline-v3` to that directory. The custom standard
library source has the latest bors commit dated 2026-02-14. The archive base
nightly and source branch therefore match by date. The old build cache and
the new build do not use byte-identical compiler toolchains.

The repository intentionally omits seven reviewed `.bin` excerpts and the
generated `src/codec_bytes.rs`; rebuild them locally from a lawful SSBU 13.0.5
dump as described in `src/reviewed/README.md`. Do not add them to GitHub.

Verification completed: 36 Rust host tests; strict host and Switch Clippy;
129 compiled AArch64 callback scenarios; NRO structure; ZIP integrity and
content checks. The Python analyzer reproduces the selection counts above.
The compiled NRO SHA-256 is
`e6dcf77b998989282889e3cd371cd682ba33e89a5f541e2f1ab7d1cf9532f3df`.
The install ZIP SHA-256 is
`7e4def97e31fe2a83e6cb24095646648e4f281730a46ab13301d9728133b1d65`.
Use `tools/package_alpha9.py` to repackage only a freshly compiled and
validated alpha.9 NRO. No live alpha.9 result has been claimed.

The local TA ON/OFF versus-screen marker is a separate later experiment; it
is not implemented here.
