# Alpha.10.1 local marker test

This is a rebuilt experimental display candidate for SSBU 13.0.5. The desired
gameplay baseline is Alpha.6. The available buildable source is Alpha.9-derived:
it retains the guarded local proposal and serializer mutation paths and adds
passive diagnostics. It is not a byte-identical rebuild of Alpha.6. No received
opponent rule or final selected rule is changed by the marker.

## Changes since the failed Alpha.10 startup test

- Resolve `imgui_get_context_export` and the draw-registration function through
  `nn::ro::LookupSymbol`. If either is missing, disable the display and retain
  the existing proposal behavior. The compiled ELF has no undefined ImGui
  imports. This addresses the observed missing-host dependency, but the prior
  generic crash screen did not establish an exact exception location.
- Obtain the host's current context on each render callback, before using
  ImGui. A null context causes an immediate return. This handles context
  creation before or after registration without relying on a missed one-shot
  post-initialization callback.
- Publish the selected state and timestamp in one atomic word, preventing the
  render thread from combining different selections. Unknown, invalid, future,
  and expired observations cannot produce an ON label.
- Use version `0.3.2-alpha.10.1` and run label `SELECTED_MARKER_ALPHA10_1_01`.

The host must be loaded when the Team Attack plugin registers. There is no
late background registration retry: if the host is absent then, the marker
stays disabled for that Smash process. Close and relaunch after installing it.

## Display meaning and hardware test

Green `TEAM ATTACK: ON (selected)` and red `TEAM ATTACK: OFF (selected)` reflect
the local selected Quickplay co-op rule byte. They do not certify agreement
on remote consoles or guarantee teammate damage. Unknown state is hidden.
The label clears at the next selection and expires 90 seconds after its
observation; it can remain into the match. Exact versus-board timing is still
unverified. This build is not a claim of 100% Team Attack success.

Install the matching upstream `libimgui_smash.nro` v1.0.0 separately alongside
the Team Attack NRO. Its SHA-256 is
`61e19e1b593826b1216228c6536cf2603b512154a8fecc548203e245bb86ed3e`.
It is not bundled in this package. The overlay produces local graphics and
does not send its text or status label to opponents. This does not establish
anything about platform enforcement.

First verify Smash launches and offline play works. Then check one Quickplay
co-op versus board: photograph the marker and record actual teammate damage.
Keep the newest capture log. If the label is absent, report a display failure,
not Team Attack OFF. Restore the backed-up Alpha.6 NRO/config if launch or
match errors recur. Keep the existing ExeFS stage patch installed; this package
contains no stage data, PRC overrides, or changes to the stage patch.

## Recovered build environment and checks

- Rust `nightly-2026-02-15`, compiler `a33907a7a`, cargo-skyline 3.5.0.
- Custom standard library `skyline-rs/rust-src` at
  `fabcf8e5bebc0d31e33717778a89df97d2b0e443`, with its pinned library/backtrace
  submodule; upstream Rust base bors commit `f8463896a9b36a04899c013bd8825a7fd29dd7a4`
  dated 2026-02-14. Linked as `skyline-v3`.
- imgui-api pinned at `9259902433138ec9c9ef9e4b152de01403f9456f`.
- Static developer archive SHA-256
  `6bd8c15d3aeda3d15da4e90cec94282fbffeb20d3bc7511ab78816a1d6f60e3d`.
- 37 Rust tests; host and Switch Clippy with warnings denied; release build.
- 129 compiled AArch64 application callback scenarios passed, including the
  two permitted mutation targets and inactive-logger path.
- Eight compiled marker callback scenarios passed: no host pointer, null
  context, unknown, ON, OFF, expired, future timestamp, and clipped window.
  Graphics calls are stubbed in this emulator test; it is not hardware proof.

Run `tools/check_application_callbacks.py` and `tools/check_marker_overlay.py`
against the release ELF. `tools/package_alpha10_1.py` checks its identity,
NRO structure, unchanged Alpha.6 config values except label, and ZIP integrity.
Private game excerpts and the static archive must remain outside public git.
