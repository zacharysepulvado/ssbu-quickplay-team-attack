# Observer 0.2.4: one combined test

This observes which rules are selected and applied. It does not enable Team
Attack or prove that another console will accept altered rules. Online ban
safety remains unverified. The new observer has compiled-code emulation checks,
but has not yet run on your Switch.

## Install

1. Fully power off the Switch. Put its SD card in your computer's card reader.
2. Back up the existing `libssbu_quickplay_team_attack.nro` and
   `ultimate/quickplay_team_attack/config.toml` to a folder on your PC. Keep the
   backup NRO outside the SD card's plugins folder.
3. Extract `ssbu-application-observer-0.2.4.zip` on your PC. Open its `SD_CARD`
   folder. Copy the two folders inside it, `atmosphere` and `ultimate`, to the
   SD card's top level, where those folders already exist. Merge folders and
   replace the two matching files. Do not copy the enclosing `SD_CARD` folder.
4. The resulting plugin path is
   `E:\atmosphere\contents\01006A800016E000\romfs\skyline\plugins\libssbu_quickplay_team_attack.nro`.
   The config path is `E:\ultimate\quickplay_team_attack\config.toml`.
   Use your SD card's actual drive letter if it changed. No configuration edits
   or new ARCropolis update are required for this test. Keep the other mods in
   the same state as capture-0007.
5. Eject the SD card, return it to the Switch, and boot using your normal
   Tegra/Hekate procedure. Start Smash with Airplane Mode on.

## Run everything in one Smash launch, within 20 minutes

1. Wait at the main menu for 15 seconds. If an observer error appears, photograph
   its message and Details, stop the test, and send those with the newest log.
2. Open your offline doubles rules. Set Team Attack **ON**, play a short offline
   team match for about 30 seconds, and deliberately hit your teammate once.
   Note whether it caused damage. Return to the offline rules and set Team
   Attack **OFF**. This checks that the new build launches and plays normally;
   it is not a repeat of the full previous Off/On/Off research batch.
3. Press HOME, turn Airplane Mode off through System Settings, then return to
   the same running Smash session. Open **Online → Smash → Quickplay → Co-op**.
4. Both players select fighters. Wait 15 seconds on that screen. Keep Preferred
   Rules unchanged from your previous online capture. Then play **one** doubles
   match with another person actively controlling player two throughout.
   Finish normally if possible. Do not start a second match just to collect
   more data. If nobody can play P2, stop after the offline check and send that
   log; do not repeat the unattended-P2 test.
5. Return to the main menu and wait 10 seconds. Close Smash, fully power off,
   then remove the SD card and use your card reader.
6. Open `E:\ultimate\quickplay_team_attack\captures` and upload the newest
   `capture-####.log`. Keep the older logs. If you relaunched Smash, send all
   logs created during this attempt.

With the log, tell me: offline teammate damage yes/no, online match completed
or interrupted, and whether Team Attack was OFF before entering Online. Note
any extra launches or route changes. Approximate menu and match times help;
there is no need to time the match precisely.

## What the capture can resolve

The new events distinguish a local copy, a participant-slot copy, the selected
record, and Team Attack immediately before/after the reviewed application call.
They include the mode code and request type. The co-op application samples have
their own capacity, so offline activity cannot exhaust that budget. Event
`sequence` identifies a reserved slot, not time order; sort by `elapsed_ticks`.

No new Ghidra export, game dump, or modification of game rule values is needed.
One capture may establish the branch taken in this match; it cannot establish
all possible participant-selection branches or remote acceptance of a future
override.
