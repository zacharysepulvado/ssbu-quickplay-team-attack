# Reviewed code excerpts

This directory is populated locally during a source build. Seven `.bin` files
and the generated `src/codec_bytes.rs` module contain short excerpts of the
SSBU 13.0.5 executable used by the plugin's fail-closed runtime validation.
They are not redistributed in this repository or its source archive.

1. Dump `main` from your own SSBU 13.0.5 installation.
2. Run `python3 tools/extract_nso.py /private/main /private/nso-segments`.
3. Run `python3 tools/materialize_reviewed.py /private/nso-segments/text.bin`.
4. Build normally. `src/application.rs` includes the generated files and
   `src/codec_probe.rs` uses the generated codec module.

The materializer reads only the offsets listed in `manifest.json`, verifies
the SHA-256 digest of every excerpt, and refuses an unexpected game build or
an existing output file. Never commit or redistribute the generated `.bin`
files or codec module.
