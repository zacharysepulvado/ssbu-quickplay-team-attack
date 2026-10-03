#!/usr/bin/env python3
"""Package the checked Alpha.10.1 marker candidate; never reuse Alpha.10."""
from pathlib import Path
import hashlib
import tomllib
import zipfile

from package_release import validate_nro, add_bytes

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / 'repo'
BASELINE = ROOT / 'SSBU-Team-Attack-Receive-Correlation-0.3.2-alpha.6.zip'
OUTPUT = ROOT / 'SSBU-Team-Attack-Marker-0.3.2-alpha.10.1.zip'
NRO_PATH = 'atmosphere/contents/01006A800016E000/romfs/skyline/plugins/libssbu_quickplay_team_attack.nro'
CONFIG_PATH = 'ultimate/quickplay_team_attack/config.toml'
NRO_SHA = '9007ce034864adbde50a12305ecb24f8250aa2d29f57ac73670b6c15811d0253'
ELF_SHA = 'c5dbf2e99589d0938fcb872aaed047a7f31a05162bb974278f16913570522906'
HOST_SHA = '61e19e1b593826b1216228c6536cf2603b512154a8fecc548203e245bb86ed3e'
HOST_URL = 'https://github.com/Coolsonickirby/imgui-smash/releases/tag/v1.0.0'

release = REPO / 'target/aarch64-skyline-switch/release'
nro = (release / 'libssbu_quickplay_team_attack.nro').read_bytes()
assert hashlib.sha256(nro).hexdigest() == NRO_SHA, 'NRO differs from checked build'
assert hashlib.sha256((release / 'libssbu_quickplay_team_attack.so').read_bytes()).hexdigest() == ELF_SHA
validate_nro(nro)
assert b'0.3.2-alpha.10.1' in nro
assert b'TEAM ATTACK: ON (selected)' in nro
assert b'TEAM ATTACK: OFF (selected)' in nro
assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == 'd306534b9f1a04f90f2f4892fdb70648a4735ca2f37ce725f19b45268f2c6dfb'
with zipfile.ZipFile(BASELINE) as archive:
    assert archive.testzip() is None
    old_config = archive.read(CONFIG_PATH).decode()
    assert archive.read(NRO_PATH) != nro
config = old_config.replace('receive-correlation experiment 0.3.2-alpha.6', 'local marker experiment 0.3.2-alpha.10.1')
config = config.replace('RECEIVE_CORRELATION_ALPHA6_01', 'SELECTED_MARKER_ALPHA10_1_01')
old_values, new_values = tomllib.loads(old_config), tomllib.loads(config)
old_values.pop('run_label')
assert new_values.pop('run_label') == 'SELECTED_MARKER_ALPHA10_1_01'
assert old_values == new_values, 'Alpha.6 gameplay configuration changed'

instructions = f'''Alpha.10.1 local Team Attack indicator — SSBU 13.0.5 only

INSTALL
1. Fully close Smash. Back up the currently working Alpha.6 Team Attack NRO
   and ultimate/quickplay_team_attack/config.toml.
2. Download libimgui_smash.nro from the upstream v1.0.0 release:
   {HOST_URL}
   Required SHA-256: {HOST_SHA}
   Put it beside the Team Attack plugin at:
   atmosphere/contents/01006A800016E000/romfs/skyline/plugins/
3. Extract this ZIP to the SD root, merging folders and replacing our NRO and
   config. Keep only one Team Attack NRO. Do not replace the entire atmosphere
   folder or remove other files. Keep your existing ExeFS stage patch.
4. Launch Smash and verify the main menu and offline play work first.
5. In Quickplay co-op, photograph the versus board and look near the upper
   left for green TEAM ATTACK: ON (selected) or red OFF (selected). Note whether
   it appears BEFORE gameplay and whether teammate damage agrees with it.
   Send the newest capture log plus the photo and match notes.

WHAT THIS BUILD DOES
Retains the guarded proposal/serializer behavior used as the Alpha.6 gameplay
baseline. It is rebuilt from Alpha.9-derived source with passive diagnostics,
not the original Alpha.6 binary. The marker reads the locally selected co-op
rule and draws only on your console. It does not transmit the label or change
opponents' received rules. It does not attempt to increase Team Attack success.

The matching ImGui host is a separate download and is NOT included here.
If its exports are missing at launch, the display stays disabled until the next
Smash launch; the proposal path remains enabled. A missing label means UNKNOWN
or a display problem, not necessarily Team Attack OFF.

The marker may remain for up to 90 seconds after selection. Versus-screen
timing and hardware stability are still unverified. ON describes the selected
local rule, not proof that every console agrees or that damage is guaranteed.
The logger has a bounded window; marker updates and guarded mutation continue
after that window until Smash closes.

ROLLBACK
Fully close Smash, restore the backed-up Alpha.6 NRO and config, and remove
libimgui_smash.nro only if you installed it solely for this test. If launch
errors or repeated communication errors return, stop this test and roll back.
'''
entries = {
    NRO_PATH: nro,
    CONFIG_PATH: config.encode(),
    'TEST_INSTRUCTIONS.txt': instructions.encode(),
    'BUILD_VALIDATION.txt': (REPO / 'research/ALPHA10_1_MARKER_TEST.md').read_bytes(),
    'NRO_SHA256.txt': f'{NRO_SHA}  libssbu_quickplay_team_attack.nro\n'.encode(),
}
assert not OUTPUT.exists(), f'refusing to overwrite {OUTPUT}'
with zipfile.ZipFile(OUTPUT, 'x') as archive:
    for name, data in entries.items():
        add_bytes(archive, name, data)
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(entries)
    for name, data in entries.items():
        assert archive.read(name) == data
print(OUTPUT)
print('zip_sha256', hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
print('nro_sha256', NRO_SHA)
