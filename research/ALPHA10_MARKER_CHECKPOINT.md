# Local versus marker work in progress

This branch adds a local ImGui overlay driven by the selected-rule status. The
overlay is experimental: its screen timing and gameplay behavior have not been
verified on hardware. The released alpha.9 ZIP is unchanged.

The application `apply_after` observation reads the selected Team Attack byte.
The new `marker_state` module maps selected co-op rule byte `01` to ON and
`00` to OFF. It clears to UNKNOWN at the next selection and for any other
mode, request, or byte. The status continues updating after the diagnostic
logger's bounded capture interval. It never interprets a submitted proposal
as a selected outcome and never changes a network packet.

The renderer uses the external `imgui-smash` v1.0.0 host plugin and its matching
`imgui-api` client commit 92599024. The host plugin must be installed separately
beside this NRO. The static developer archive stays local; do not commit or
redistribute its binary in this repository. The overlay touches only the local
render frame. It draws a noninteractive ON/OFF label for up to 90 seconds after
a recognized co-op selection. Unknown/unrecognized values show no label.

Still unverified: whether `apply_after` fires before the versus board is drawn,
whether the external host loads in this exact mod stack, and whether the
selected byte matches observed teammate damage in every match. A hardware
test must check all three. An absent marker should be recorded as a failed
display test, not treated as proof of Team Attack OFF.

Host validation: 37 Rust tests passed and Clippy with warnings denied passed.
The Switch target compiled an alpha.10 NRO and the Skyline-target Clippy pass
completed without warnings. The 129 compiled AArch64 callback scenarios passed
with the marker's additional timestamp read accounted for. The install ZIP and
NRO were structurally validated, and their SHA-256 values are:

- NRO: `9afab3db6463ae463e5e3a58107c5a84aa4624e9f881b4e6da8c38f62524fed0`
- ZIP: `3d99e20d5b7050fbd414306fd08335f659ab7909ba6d1b1b93db4e9a5de9eab1`

The upstream `libimgui_smash.nro` v1.0.0 has SHA-256
`61e19e1b593826b1216228c6536cf2603b512154a8fecc548203e245bb86ed3e`.
The UI path and match timing remain hardware pending.
