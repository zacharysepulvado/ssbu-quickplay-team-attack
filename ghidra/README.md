# Local serializer investigation

These tools locate **candidates**, not verified game functions. No real 13.0.5
offset or game-code signature is included. Keep the plugin disabled until
independent disassembly review satisfies the evidence checklist.

## Environment and lawful input

The scripts were executed on Ghidra **12.1.3**, PyGhidra **3.1.0**, Python 3.12,
and Java 21 using an original synthetic AArch64 program. This establishes API
compatibility on that setup only; no Nintendo executable was tested.

Use a `main` executable dumped from your own 13.0.5 installation. Record its
SHA-256 and how the version was established. Do not upload the executable,
Ghidra database, keys, tickets, certificates, or complete feature export.

Import the NSO with a compatible
[Switch loader](https://github.com/Adubbz/Ghidra-Switch-Loader), or use an already
correctly decompressed and mapped analysis database. A compressed NSO must not
be treated as a raw instruction stream. This project has not tested that
loader against Ghidra 12.1.3; use a compatible build and verify the memory map.
The synthetic smoke test needs no Switch loader.

Use little-endian `AARCH64:LE:64:v8A`, complete auto-analysis, and inspect the
memory map. The requested text base is the exact beginning of the initialized
executable **main .text block**, not an assumed image base, file offset, or
hard-coded `0x7100000000`. Map rodata/data correctly as well for cross-references.
These scripts currently require text to be one initialized executable block.
If the loader splits it, stop and adapt the block handling after review.

Launch Ghidra with PyGhidra enabled using its `support/pyghidraRun` launcher.
See the official
[PyGhidra setup](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.3_build/Ghidra/Features/PyGhidra/src/main/py/README.md).
The `@runtime PyGhidra` annotation is intentional; a Jython stub is insufficient.
Add this project's `ghidra` directory to Script Manager's script directories.

## 1. Export structural features

Open the analyzed program and run `ExportFunctionFeatures.py`. Supply a new
output filename, the actual text base, and `13.0.5`. The version is only your
label; the exporter does not authenticate a dump's version.

It exports function sizes, mnemonic sequences/histograms, small constants,
store operand scalars, calls, and data references. It exports no instruction
bytes. A completion marker prevents a canceled/partial export being ranked.
The filter retains functions 32..16384 bytes long; adjust it explicitly if
independent evidence requires a wider search.

Run from the source project on your computer:

```sh
python3 tools/locate_serializer.py /private/target-1305.jsonl
```

Optionally repeat the export on your own **13.0.4** dump and compare:

```sh
python3 tools/locate_serializer.py /private/target-1305.jsonl \
  --reference /private/reference-1304.jsonl
```

The reference offset defaults to `0x16E2DF0` only for the explicitly labeled
13.0.4 export. No relocation delta is used. The ranker considers the old
560-byte size as a soft lead, constants such as `0x78`/`0x1F`/`0x40`, store
displacements through `0x68`, and optional instruction similarity. Store
scalars may be stack offsets or unrelated fields; the exporter does not prove
that their base register is the output pointer. Scores are not probabilities.

## 2. Independently review candidates

For each promising entry, inspect instructions and the decompiler together:

- Follow the argument register through aliases and establish every write's
  actual base. Prove the function is a CSS-to-compact-buffer transformation,
  not its decoder or an unrelated struct copy.
- Establish the actual calling convention: x0 is the output pointer, no
  required additional/hidden arguments, and callers do not rely on a return
  value. A decompiler's guessed prototype is not proof.
- Check every caller allocation and prove at least 105 bytes of capacity,
  output lifetime after return, and initialization of each selected byte.
- Compare CSS globals, validation branches, DLC-related loops, and consumers
  with the reference. The public decomp is simplified/nonmatching, so do not
  treat its C++ struct offsets or omitted assignments as exact machine code.
- Identify a **separate** relevant caller/global/consumer relationship as the
  second semantic evidence category. Signature equality alone is insufficient.

If no candidate meets these conditions, retain an unverified finding. Do not
choose the highest-ranked address simply to get a capture.

## 3. Extract short identity signatures

Define the reviewed function and one separate direct caller in Ghidra. Run
`InspectSerializerCandidate.py` and provide the text base, candidate
text-relative entry, the text-relative address of the caller's **BL instruction**,
and a signature length (16..64 bytes, multiple of four).

The script checks executable bounds, defined function boundaries, separate
nonoverlapping signatures, a direct AArch64 BL to the entry, and uniqueness of
both signatures at aligned addresses in the imported text block. It exports
only the short signatures and context to `candidate.json`, with
`UNVERIFIED_CANDIDATE`, empty ABI/allowlist, and false review attestation.

It does not patch the database or executable, generate an enabled config,
identify Team Attack, or prove that live Skyline text is identical. Review the
report and write your evidence notes separately. On the Switch, the observer
rechecks runtime version, mapped bounds, exact signatures, uniqueness, and BL
target before installing the hook.

## Headless use on an existing analyzed project

Close the GUI first. Use the Python environment containing PyGhidra. The
following paths and text base are placeholders, not game offsets:

```sh
python3 -m pyghidra.ghidra_launch --install-dir /path/to/ghidra \
  ghidra.app.util.headless.AnalyzeHeadless /private/projects ProjectName \
  -process main -noanalysis -readOnly \
  -scriptPath /path/to/ssbu-quickplay-team-attack/ghidra \
  -postScript ExportFunctionFeatures.py /private/target-1305.jsonl ACTUAL_TEXT_BASE 13.0.5
```

For candidate inspection, replace the post-script clause with:

```text
-postScript InspectSerializerCandidate.py /private/candidate.json ACTUAL_TEXT_BASE ENTRY_OFFSET BL_OFFSET 16
```

Check logs as well as exit status: Ghidra headless can return zero after a
script exception. The exporter must end with a valid `end` record and the
candidate file must exist. Both scripts refuse an existing output filename.

## Synthetic integration test

From the project root, with Java 21 available and PyGhidra installed:

```sh
python3 tools/ghidra_smoke_test.py --install-dir /path/to/ghidra
```

The test generates an original 4096-byte AArch64 fixture in a new temporary
directory, imports it headlessly, prepares test functions, executes both
analysis scripts, runs the ranker, and checks invalid-caller rejection. Logs
and the synthetic database remain in the printed directory for inspection.
`PrepareSyntheticFixture.py` is test-only and rejects other program names and
shapes. Never run it on your game database. Synthetic offsets `0x20` and `0x88`
have no relationship to Smash and must never go into your plugin configuration.

## What to share next

Share only the short unverified candidate JSON and your version/ABI/layout/
caller review notes. Then follow the repeated offline A/B/A procedure in
[PORTING_PLAN.md](../research/PORTING_PLAN.md). Identifying an offline field
still does not prove that Preferred Rules, matchmaking, or every peer preserves
it. The present observer has no network or gameplay mutation capability.
