# Compatibility assessment

No hardware or combined-plugin testing has been performed. No item below is
certified compatible. The observer's real hook remains unknown; consequently
there is no verified exact shared-target result yet.

| Component | Source-level assessment | Research action |
| --- | --- | --- |
| Skyline | Required loader; `A64HookFunction` changes code and creates a trampoline. No transactional rollback/pointer publication guarantee is exposed to this plugin. | Startup only; never hot-reload. |
| ARCropolis | Resource/mod loading does not by itself prove rule-hook compatibility. No dependency or resource hook is added by this observer. | Keep only what the local loader setup requires; test disabled loading first. |
| Smashline | Updates many code/data references and has cloning/CSS-related hooks. | Compare the eventual candidate and callsite with the exact installed build; test separately. |
| Online Deluxe 1.4.1 | Owns CSS, menu, stage, render, and network hooks. Examples below are from its source, not this plugin's offsets. | Remove for initial observation; do not import its context flags as proof of rule negotiation. |
| Training Modpack | Uses many game hooks; its runtime version query informed this observer's version check. Shared target cannot be established yet. | Disable for the first offline A/B captures so it does not change control conditions. |
| Delay/latency plugins | Exact files/versions not supplied; behavior and shared hooks may differ between implementations. | Identify exact repository and binary version before compatibility testing. |
| Legal-stage mods | Exact implementation not supplied; may be data-only or use code hooks. Either can change experimental conditions. | Hold stage settings constant; test with stage mods removed first. |

Online Deluxe source examples (13.0.5 support branch/release):

| Function | Text-relative offset in that mod |
| --- | --- |
| Main menu initialization | `0x235AAA0` |
| Online arena menu initialization | `0x22D9B50` |
| CSS update | `0x1A12F60` |
| CSS player pane count | `0x1A26200` |
| Stage pre-setup | `0x25D9288` |

An earlier-loaded patch affecting either configured signature causes this
observer to refuse installation. That is useful collision detection, not a
general compatibility guarantee. A later hook, an internal body patch, another
mod's mutable data, or load-order differences can still cause problems.

Primary source snapshots:

- [Skyline hook installer](https://github.com/skyline-dev/skyline/blob/2eb226fa9e4ab023dc00cb0db10ad4ec50ac4fa3/source/skyline/inlinehook/And64InlineHook.cpp)
- [Online Deluxe network hooks](https://github.com/saad-script/ssbu-online-deluxe/blob/c54c11684004e2d68fc1c519d046bb6793458b4d/src/net/mod.rs)
- [Smashline 13.0.5 changes](https://github.com/HDR-Development/smashline/compare/v1.6.6...v1.6.7)
- [Training Modpack runtime version query](https://github.com/jugeeya/UltimateTrainingModpack/blob/446eb549a08046e70fedf77020d80df147ee5d2e/src/common/events.rs)
- [ARCropolis source](https://github.com/Raytwo/ARCropolis)

The user should retain specific plugin versions and hashes with any eventual
compatibility report. Do not write "wifi-safe" or "ban-safe" based on one
successful game launch.
