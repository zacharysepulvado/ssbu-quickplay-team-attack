#!/usr/bin/env python3
"""Package a verified alpha.9 NRO over the known alpha.6 install layout."""
from pathlib import Path
import hashlib
import zipfile

from package_release import validate_nro

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "repo"
BASELINE = ROOT / "SSBU-Team-Attack-Receive-Correlation-0.3.2-alpha.6.zip"
OUTPUT = ROOT / "SSBU-Team-Attack-Receive-Transitions-0.3.2-alpha.9.zip"
NRO_PATH = "atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_quickplay_team_attack.nro"
CONFIG_PATH = "ultimate/quickplay_team_attack/config.toml"

nro = (REPO / "target/aarch64-skyline-switch/release/libssbu_quickplay_team_attack.nro").read_bytes()
validate_nro(nro)
assert b"0.3.2-alpha.9" in nro
with zipfile.ZipFile(BASELINE) as previous:
    assert previous.testzip() is None
    entries = {name: previous.read(name) for name in previous.namelist() if not name.endswith("/")}
    assert previous.read(NRO_PATH) != nro

config = entries[CONFIG_PATH].decode()
assert "RECEIVE_CORRELATION_ALPHA6_01" in config
config = config.replace("receive-correlation experiment 0.3.2-alpha.6", "receive-transition experiment 0.3.2-alpha.9")
config = config.replace("RECEIVE_CORRELATION_ALPHA6_01", "RECEIVE_TRANSITIONS_ALPHA9_01")
entries[NRO_PATH] = nro
entries[CONFIG_PATH] = config.encode()
entries["NRO_SHA256.txt"] = (hashlib.sha256(nro).hexdigest() + "  libssbu_quickplay_team_attack.nro\n").encode()
entries["BUILD_VALIDATION.txt"] = (
    "v0.3.2-alpha.9 diagnostic build for SSBU 13.0.5 only.\n"
    "Removed alpha.8's high-frequency chooser inline hook. Guarded alpha.6 proposal\n"
    "and serializer mutation paths are unchanged. Bounded receive/application\n"
    "events remain enabled for offline transition analysis.\n"
    "36 Rust host tests, strict host/Switch Clippy, and 129 compiled callback\n"
    "scenarios passed. NRO structure, ZIP integrity and SHA-256 verified.\n"
    "No alpha.9 hardware result or 100% Team Attack claim is made.\n"
).encode()
entries["TEST_INSTRUCTIONS.txt"] = (
    "Alpha.9 receive-transition test — SSBU 13.0.5 only\n\n"
    "Fully close Smash. Back up the current NRO and config. Extract this ZIP to\n"
    "the SD root and replace those two files, then launch Smash fresh. Do not\n"
    "run a second Team Attack plugin. The versus-screen marker is not in this build.\n\n"
    "This build removes alpha.8's frequent chooser observation and retains\n"
    "the alpha.6 guarded mutation behavior. It may still select Team Attack OFF\n"
    "on opponents' rules. It does not rewrite opponent-owned received records.\n\n"
    "Play normal Quickplay co-op, including opponents' rules and rematches.\n"
    "For each match note whether teammate damage worked, whose rules won,\n"
    "fresh/rematch, and communication errors. Stop if disconnects repeat.\n"
    "Logging runs for up to 90 minutes; guarded mutation continues until Smash\n"
    "exits. Send the newest capture-XXXX.log and your match notes afterward.\n\n"
    "Restore your backed-up NRO/config or reinstall alpha.6 to revert.\n"
    "Online modding has compatibility and enforcement risks.\n"
).encode()
assert not OUTPUT.exists(), f"refusing to overwrite {OUTPUT}"
with zipfile.ZipFile(OUTPUT, "x", zipfile.ZIP_DEFLATED) as archive:
    for name, data in entries.items():
        archive.writestr(name, data)
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    assert archive.read(NRO_PATH) == nro
    assert archive.read(CONFIG_PATH) == config.encode()
    assert len([name for name in archive.namelist() if name == NRO_PATH]) == 1
print(OUTPUT)
print("zip_sha256", hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
print("nro_sha256", hashlib.sha256(nro).hexdigest())
