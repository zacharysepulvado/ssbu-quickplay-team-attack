# Historical findings through 2026-09-07

This document preserves the pre-experiment investigation. It is superseded by
the verified two-match hardware result in the repository `README.md`,
`BUILD_REPORT.md`, and `TECHNICAL_DEVELOPMENT.md`.

The historical report below predates the user's three batch exports. Its
unknown-address statements are superseded here. The 13.0.5 compact serializer
at main+0x16e2c50 and caller at main+0x169462c have independently reviewed
instruction and caller evidence. Named team_attack lookup / loader writes lead
to global main+0x530a981, then compact buffer byte +0x11. Static provenance is
strong; runtime field correlation and Quickplay propagation remain unverified.

The user's 0.2.1 logs confirm log creation and hook installation but have no dump
samples, including the requested offline match run. 0.2.2 now adds independent
global watching for an offline Off/On/Return-Off batch. See
[OFFLINE_BATCH_0_2_2.md](OFFLINE_BATCH_0_2_2.md). No rule mutation exists.

## Historical findings before the user exports

# Research findings — 2026-09-06

## Result

**No verified 13.0.5 serializer offset or signature was found. No Team Attack
byte/mask/polarity or Quickplay propagation behavior has been established.**
This is a research gap, not proof that the desired behavior is impossible.

| Item | Evidence status |
| --- | --- |
| 13.0.5 serializer entry and ABI | Unverified; no real candidate shipped |
| 13.0.5 caller signature | Unverified |
| 0x69-byte layout on 13.0.5 | Working hypothesis from 13.0.4 reconstruction |
| Team Attack byte, bit, polarity | Unknown |
| Preferred Rules carries the field | Unknown |
| Final match rules preserve it | Unknown |
| Unmodified peers accept it | Unknown |
| Account/console safety | Cannot be guaranteed |

## Source assessment

The [decomp snapshot](https://github.com/sbergeron42/ssbu-decomp/tree/d55c91c94d18ee476bd7ffb596cedc3259c5e9f0)
targets 13.0.4. Its
[serializer reconstruction](https://github.com/sbergeron42/ssbu-decomp/blob/d55c91c94d18ee476bd7ffb596cedc3259c5e9f0/src/app/networking/state_serialize.cpp)
documents `css_read_state_to_compact_buffer` at text offset `0x16E2DF0`,
560 bytes long. It explicitly prioritizes readability over matching, omits
several assignments, and substitutes simplified accesses. Treat this as a
navigation lead, not a verified implementation or signature.

The accompanying
[CSSState header](https://github.com/sbergeron42/ssbu-decomp/blob/d55c91c94d18ee476bd7ffb596cedc3259c5e9f0/include/app/CSSState.h)
annotates a final field at `0x68` and a profile-data field at `0x60..0x67`.
Its prose says no profiles, contradicting that field label. Also, its C++
struct is not packed although annotated u64 fields begin at unaligned offsets.
Do not infer the exact original C++ layout from `sizeof` this reconstruction,
or read all 105 bytes as initialized data. Revision 0.2 uses selected bytes
only and excludes the profile region and annotated padding.

The [13.0.4 function table](https://github.com/sbergeron42/ssbu-decomp/blob/d55c91c94d18ee476bd7ffb596cedc3259c5e9f0/data/functions.csv)
names `is_team_battle_and_team_attack` at `0x15CFDD0`, size 224 bytes.
The separate 13.0.1 names CSV places that name at a different address; mixing
those tables would misidentify functions.

## Why old offsets cannot simply be shifted

[Online Deluxe 1.3.0 → 1.4.0](https://github.com/saad-script/ssbu-online-deluxe/compare/v1.3.0...v1.4.0)
moves main-menu initialization `0x235A650 → 0x235AAA0` and stage pre-setup
`0x25D8E38 → 0x25D9288` (+0x450), while its UI text helper moves
`0x37A22F0 → 0x37A28A0` (+0x5B0). Other hooks remain unchanged.
[Smashline 1.6.6 → 1.6.7](https://github.com/HDR-Development/smashline/compare/v1.6.6...v1.6.7)
also changes some fighter-path offsets by -0x40 and other references differently.
None supplies independent identity evidence for this project's serializer.

## Online behavior: do not conflate different layers

| Layer | What the research establishes |
| --- | --- |
| Offline CSS/save state | The reconstruction describes this area and a compact representation; actual 13.0.5 behavior still needs disassembly and observation |
| Arena rules | No traced caller chain from this candidate to final arena rules |
| Quickplay Preferred Rules | No demonstrated Team Attack field or serializer relationship |
| Matchmaking/final rule selection | No proven encode/decode or validation path for this bit |
| Per-peer battle state | No confirmation that unmodified peers would receive/apply it; a local-only write is not a solution |

[Online Deluxe's network source](https://github.com/saad-script/ssbu-online-deluxe/blob/c54c11684004e2d68fc1c519d046bb6793458b4d/src/net/mod.rs)
distinguishes connection/menu contexts, including arenas and Quickplay-related
states. These labels are useful search leads, but are not a Team Attack rule
schema or proof of Quickplay negotiation. We did not import its scene hooks
as an unverified context gate.

Nintendo's [13.0.5 update note](https://en-americas-support.nintendo.com/app/answers/detail/a_id/42809/~/how-to-update-super-smash-bros.-ultimate)
says invalid-data behavior in online battles was fixed. It does not disclose
a Team Attack validation rule, detection method, or ban threshold.
Online Deluxe's maintainer separately states its P2P changes have no newly
known 13.0.5 ban risk; that claim cannot validate a different rules mod.

## Search scope and next evidence

Additional reviewed primary sources include
[skyline-smash](https://github.com/ultimate-research/skyline-smash/tree/315e4e8bebb460ebb9f02f30f07b0f13883ba3d6),
[the PIA interface](https://github.com/project-ultelier/ssbu-pia-interface/tree/220b5aac0e66e5c577403e836ed296b06697dc07),
and the loader/runtime sources linked in the build and compatibility reports.
The skyline-smash common-parameter binding contains Team Attack shot/heal
rates; those are not evidence of a Team Attack toggle in Quickplay's serialized
rules. No verified serializer identity was recovered from these bindings.

Reviewed public repositories, release diffs, headers, symbols/function tables,
and targeted indexed searches for the serializer name, old offset, and 13.0.5
rule/Team Attack references. No independently verified public 13.0.5 candidate
was recovered. Private Discord posts, unindexed material, and missing binary
evidence may contain more information; absence from this search proves neither
nonexistence nor impossibility.

The next required input is a locally analyzed lawful 13.0.5 `main` dump.
Run the included Ghidra tools and share only a short candidate report plus
review notes. Do not publish the executable, keys, or full feature export.
