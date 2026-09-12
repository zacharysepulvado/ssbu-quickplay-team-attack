# Install and run — guarded experiment 0.3.0

This build intentionally performs a narrow online rule-proposal mutation. Its
network behavior and ban safety are unknown.

1. Fully close Smash and fully power off the Switch before removing the SD.
2. Back up the current plugin NRO and `ultimate/quickplay_team_attack/config.toml`.
3. Copy the `atmosphere` and `ultimate` folders from this ZIP's root to the SD
   root, merge folders, and replace the two matching files.
4. Boot Atmosphere with airplane mode on and launch Smash once. At the title
   screen, stop if an experiment error appears. Otherwise close Smash fully.
5. Turn airplane mode off while Smash is closed, relaunch, and go directly to
   Online > Smash > Co-op with an active second local player.
6. Play one match. Deliberately hit the local teammate once and record whether
   damage occurs. Do not rematch for the first experiment.
7. Record whether the match finished normally, whether a disconnect occurred,
   and whether the opponent appeared able to damage their teammate.
8. Close Smash, fully power off, and upload the newest capture log from
   `ultimate/quickplay_team_attack/captures`.

The new log should begin with version `0.3.0` and label
`LOCAL_B4_ON_EXPERIMENT_01`. Keep all older logs. Restore the backed-up passive
observer before ordinary online play if you do not want the experiment active.
