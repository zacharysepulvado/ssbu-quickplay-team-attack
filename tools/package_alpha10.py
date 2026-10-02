#!/usr/bin/env python3
"""Package the freshly built local-marker plugin over verified alpha.9 layout.

The imgui-smash host plugin has its own upstream release and is not bundled.
"""
from pathlib import Path
import hashlib
import zipfile

from package_release import validate_nro

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "repo"
BASELINE = ROOT / "SSBU-Team-Attack-Receive-Transitions-0.3.2-alpha.9.zip"
OUTPUT = ROOT / "SSBU-Team-Attack-Marker-0.3.2-alpha.10.zip"
NRO_PATH = "atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_quickplay_team_attack.nro"
CONFIG_PATH = "ultimate/quickplay_team_attack/config.toml"
HOST_SHA256 = "61e19e1b593826b1216228c6536cf2603b512154a8fecc548203e245bb86ed3e"
HOST_URL = "https://github.com/Coolsonickirby/imgui-smash/releases/tag/v1.0.0"

nro = (REPO / "target/aarch64-skyline-switch/release/libssbu_quickplay_team_attack.nro").read_bytes()
validate_nro(nro)
assert b"0.3.2-alpha.10" in nro
assert b"TEAM ATTACK: ON (selected)" in nro
assert b"TEAM ATTACK: OFF (selected)" in nro
assert b"imgui_smash_add_on_draw_frame_wrapper" in nro
assert hashlib.sha256((REPO / "lib/libimgui_smash.a").read_bytes()).hexdigest() == (
    "6bd8c15d3aeda3d15da4e90cec94282fbffeb20d3bc7511ab78816a1d6f60e3d"
)

with zipfile.ZipFile(BASELINE) as previous:
    assert previous.testzip() is None
    entries = {name: previous.read(name) for name in previous.namelist() if not name.endswith("/")}
    assert previous.read(NRO_PATH) != nro

config = entries[CONFIG_PATH].decode()
assert "RECEIVE_TRANSITIONS_ALPHA9_01" in config
config = config.replace("receive-transition experiment 0.3.2-alpha.9", "selected-rule marker experiment 0.3.2-alpha.10")
config = config.replace("RECEIVE_TRANSITIONS_ALPHA9_01", "SELECTED_MARKER_ALPHA10_01")
entries[NRO_PATH] = nro
entries[CONFIG_PATH] = config.encode()
entries["NRO_SHA256.txt"] = (
    hashlib.sha256(nro).hexdigest() + "  libssbu_quickplay_team_attack.nro\n"
).encode()
entries["BUILD_VALIDATION.txt"] = (
    "0.3.2-alpha.10 test build for SSBU 13.0.5 only.\n"
    "37 Rust host tests and host Clippy passed; Switch release build and\n"
    "Switch Clippy passed; NRO and ZIP structure/checksums validated.\n"
    "The local ImGui indicator has not yet been tested on hardware.\n"
    "Alpha.9's guarded proposal path remains unchanged; no 100% claim.\n"
).encode()
entries["TEST_INSTRUCTIONS.txt"] = (
    "Alpha.10 local selected-rule marker test - SSBU 13.0.5 only\n\n"
    "This ZIP contains our plugin and config. It does not bundle the separate\n"
    "imgui-smash host plugin. First download libimgui_smash.nro from:\n"
    f"{HOST_URL}\n"
    f"Its SHA-256 must be: {HOST_SHA256}\n\n"
    "Fully close Smash. Back up your Team Attack NRO and config. Install the\n"
    "downloaded libimgui_smash.nro in:\n"
    "atmosphere/contents/01006A800016E000/romfs/skyline/plugins/\n"
    "Then extract this ZIP to the SD root and replace the Team Attack NRO and\n"
    "config. Do not run another copy of the Team Attack plugin. Boot Smash.\n\n"
    "In a Quickplay co-op match, look for a local green TEAM ATTACK: ON or red\n"
    "TEAM ATTACK: OFF label near the upper left of the versus/loading screen.\n"
    "It reports the locally selected rule, not a guarantee of actual damage\n"
    "or a peer-confirmed state. The label can remain briefly into the match and\n"
    "disappears 90 seconds after selection. If it never appears, record that\n"
    "as a marker failure; do not infer that Team Attack was OFF.\n\n"
    "Send a photo or short video of the versus board, whether the label\n"
    "appeared before the match, teammate-damage result, and newest capture\n"
    "log. Stop testing if errors or disconnects recur.\n\n"
    "To revert, fully close Smash, restore the backed-up NRO/config and\n"
    "remove libimgui_smash.nro if this test was your only reason to install it.\n"
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
