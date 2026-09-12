# Quickplay Team Attack ON — SSBU 13.0.5

This Skyline plugin proposes Team Attack ON in Super Smash Bros. Ultimate
Quickplay co-op. It was built for game version 13.0.5 and tested in
online doubles matches against unmodified opponents. In the matches, both
teams could damage their own teammates.

Pair it with a legal-stage Preferred Rules mod if you want competitive stages
and Team Attack together. Cheesy doubles strategies that rely on teammates
being unable to hit each other should no longer be protected when the ON rule
is applied.

## What the plugin changes

The plugin changes one Team Attack field in the local command-B4 rule proposal
from `00` (OFF) to `01` (ON). It also has a guarded local mirror: after a local
proposal is changed, the local rule source is mirrored to ON only if Smash
selects the local-copy branch for that same runtime session.

It does not blindly force every rule structure to ON. The write is rejected
unless all reviewed SSBU 13.0.5 conditions match, including Quickplay co-op
mode, the expected request and preparation state, a valid local record slot,
the exact B4 command and payload length, an original OFF value, and one of four
known proposal callers. Incoming receive hooks and the participant-copy branch
remain read-only.

## Installation

Requirements:

- A modded Nintendo Switch running Atmosphere, Skyline, and SSBU 13.0.5.
- A backup of your current Skyline plugin and Team Attack configuration.

Steps:

1. Fully close Smash and power off the Switch.
2. Back up these existing files if present:
   - `atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_quickplay_team_attack.nro`
   - `ultimate/quickplay_team_attack/config.toml`
3. Extract the release ZIP on a computer.
4. Copy its `atmosphere` and `ultimate` folders to the root of the SD card.
5. Merge the folders and replace the two matching files when prompted.
6. Safely eject the SD card and boot Atmosphere normally.
7. Confirm Smash reports version 13.0.5. Do not use this build on another game
   version.

To uninstall, restore the backed-up NRO and configuration, or remove only this
plugin's NRO from the Skyline plugins folder while Smash is fully closed.

## Preferred Rules and selection behavior

When Smash chooses the user's modified Preferred Rules, the guarded mirror
keeps the local Team Attack proposal and applied rule consistent. Internally,
the first controlled test applied an ON participant record and the second used
the local-copy branch and mirror. Those internal branches do not by themselves
identify whose Preferred Rules won. Both matches selected stages from the
user's modified legal-stage pool, supporting that the user's Preferred Rules
were active. Two matches are not enough to promise ON for every matchmaking
outcome.

Recommended setup: enable your normal seven-minute team-battle Preferred Rules
and pair this plugin with the compatible legal-stage selection mod. Stage and
other rule behavior remain subject to Smash's normal Preferred Rules matching.

## Verified test result

The first hardware test used two separate fresh Quickplay co-op searches, not
rematches. Match one selected Smashville and match two selected Yoshi's Story,
both from the user's modified legal-stage Preferred Rules pool. Both matches
completed normally. The local team and the opposing team were each able to
inflict teammate damage.

The capture recorded:

- successful local B4 proposal mutations from OFF to ON;
- a participant-copy selection applying ON;
- a separate local-copy selection firing the guarded mirror;
- `apply_after` reporting the live Team Attack global as `01` in both cycles;
- the live Team Attack global remaining `01` during both match periods;
- zero dropped application or codec events.

## Risk warning

Online modding always carries risk. This project cannot guarantee protection
from account or console enforcement, disconnections, crashes, incompatibility
with other plugins, or future game updates. The plugin modifies an online rule
proposal and has only been tested on SSBU 13.0.5. Install and use it at your own
risk. Stop using it after any game update until the executable offsets and code
signatures have been reviewed again.

## Source and technical notes

The source archive and technical development history are included so the
community can audit the exact offsets, signatures, guards, callback behavior,
tests, and known limits. Reviewed game-code excerpts, including the generated
codec-byte module, are intentionally excluded from the public repository and
source archive. Builders can recreate them from a legally dumped SSBU 13.0.5 `main` using
`tools/materialize_reviewed.py`; the expected offsets, lengths, and SHA-256
digests are recorded in `src/reviewed/manifest.json`. See
`TECHNICAL_DEVELOPMENT.md`.
