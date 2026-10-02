# Local versus marker work in progress

This branch stages only the status source for a future local display. It does
not draw on the screen, does not produce an installable alpha.10 build, and
does not change the released alpha.9 ZIP.

The application `apply_after` observation reads the selected Team Attack byte.
The new `marker_state` module maps selected co-op rule byte `01` to ON and
`00` to OFF. It clears to UNKNOWN at the next selection and for any other
mode, request, or byte. The status continues updating after the diagnostic
logger's bounded capture interval. It never interprets a submitted proposal
as a selected outcome and never changes a network packet.

Before shipping an on-screen marker, identify and validate the SSBU 13.0.5
versus-board layout, a stable local-only text pane/draw hook, and the order
between `apply_after` and versus-board presentation. The previously collected
UI binding export covers rule controls; it does not establish those UI facts.
An ImGui backend is one option, but would add another Skyline plugin and
installation dependency. Do not publish a binary using an unreviewed hook.

Host validation: 37 Rust tests passed and Clippy with warnings denied passed.
The Switch UI path and hardware timing are pending. The alpha.9 install ZIP
remains the last compiled test build and has no marker.
