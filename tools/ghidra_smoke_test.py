#!/usr/bin/env python3
"""Exercise the Ghidra scripts on original synthetic code, never game content."""
from __future__ import annotations
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", required=True, type=Path)
    parser.add_argument("--work-directory", type=Path,
                        help="New directory; defaults to a retained temporary directory")
    args = parser.parse_args()
    if importlib.util.find_spec("pyghidra") is None:
        parser.error("Run with a Python interpreter that has Ghidra's PyGhidra package installed")
    if not (args.install_dir / "Ghidra/application.properties").is_file():
        parser.error("Ghidra installation not found")
    if args.work_directory:
        work = args.work_directory.resolve()
        work.mkdir(parents=True, exist_ok=False)
    else:
        work = Path(tempfile.mkdtemp(prefix="team-attack-ghidra-test-"))
    root = Path(__file__).resolve().parent.parent
    fixture = work / "synthetic-aarch64.bin"
    subprocess.run([sys.executable, str(root / "tools/make_synthetic_fixture.py"), str(fixture)], check=True)
    features, candidate = work / "features.jsonl", work / "candidate.json"
    launcher = [sys.executable, "-m", "pyghidra.ghidra_launch", "--install-dir",
                str(args.install_dir.resolve()), "ghidra.app.util.headless.AnalyzeHeadless",
                str(work), "synthetic-test"]
    command = launcher + [
        "-import", str(fixture), "-loader", "BinaryLoader",
        "-processor", "AARCH64:LE:64:v8A", "-loader-baseAddr", "7100000000",
        "-scriptPath", str(root / "ghidra"), "-preScript", "PrepareSyntheticFixture.py",
        "-postScript", "ExportFunctionFeatures.py", str(features), "7100000000", "13.0.5",
        "-postScript", "InspectSerializerCandidate.py", str(candidate), "7100000000", "0x20", "0x88", "16",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    log = result.stdout + result.stderr
    (work / "headless.log").write_text(log, encoding="utf-8")
    # Headless can exit zero after a script exception: inspect both output and products.
    if result.returncode or "ERROR " in log or not features.is_file() or not candidate.is_file():
        raise RuntimeError(f"Ghidra smoke test failed; inspect {work / 'headless.log'}")
    report = json.loads(candidate.read_text(encoding="utf-8"))
    assert report["status"] == "UNVERIFIED_CANDIDATE"
    assert report["serializer_text_offset"] == 0x20
    assert report["caller_text_offset"] == 0x88
    assert report["direct_bl_verified"] is True
    assert report["signatures_unique_in_imported_block"] is True
    assert report["evidence_reviewed"] is False
    assert len(report["expected_prologue"].split()) == 16
    ranked = subprocess.run([sys.executable, str(root / "tools/locate_serializer.py"),
                             str(features)], capture_output=True, text=True, check=True)
    ranking = json.loads(ranked.stdout)
    assert ranking["candidates"][0]["offset"] == "0x20"
    # A non-BL callsite must fail without producing even an unverified report.
    rejected = work / "must-not-exist.json"
    negative = subprocess.run(launcher + [
        "-process", fixture.name, "-noanalysis", "-readOnly",
        "-scriptPath", str(root / "ghidra"), "-postScript", "InspectSerializerCandidate.py",
        str(rejected), "7100000000", "0x20", "0x84", "16",
    ], capture_output=True, text=True, timeout=180)
    negative_log = negative.stdout + negative.stderr
    (work / "rejection.log").write_text(negative_log, encoding="utf-8")
    assert "Caller does not begin with direct AArch64 BL" in negative_log
    assert not rejected.exists()
    print(f"PASS: synthetic export, ranking, signature/BL checks and invalid-caller rejection. Logs: {work}")
    print("This tests Ghidra APIs only. No SSBU function, ABI, field, or offset was verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
