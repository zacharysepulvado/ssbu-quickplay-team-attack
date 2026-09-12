#!/usr/bin/env python3
"""Package reviewed source and an optional v0.3.0 release NRO."""
from __future__ import annotations
import argparse
import hashlib
import shutil
import struct
import zipfile
from pathlib import Path

ROOT_FILES = {"Cargo.toml", "Cargo.lock", "README.md", "CONTRIBUTING.md", "LICENSE", ".gitignore", "BUILD_REPORT.md", "TECHNICAL_DEVELOPMENT.md", "RELEASE_NOTES_0.3.0.md"}
DIR_SUFFIXES = {"src": {".rs"}, "config": {".example"}, "research": {".md"}, "tools": {".py", ".sh"}, "ghidra": {".py", ".md"}}
REVIEWED_METADATA = {"README.md", "manifest.json"}
PLUGIN_NAME = "libssbu_quickplay_team_attack.nro"
PLUGIN_PATH = "atmosphere/contents/01006A800016E000/romfs/skyline/plugins/" + PLUGIN_NAME


def source_paths(root: Path) -> list[Path]:
    paths = []
    candidates = [root / name for name in ROOT_FILES]
    for directory in DIR_SUFFIXES:
        folder = root / directory
        if folder.is_dir() and not folder.is_symlink():
            candidates.extend(folder.iterdir())
    candidates.extend(root / "src/reviewed" / name for name in REVIEWED_METADATA)
    for path in sorted(candidates):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if len(relative.parts) == 1 and path.name in ROOT_FILES:
            paths.append(path)
        elif len(relative.parts) == 3 and relative.parts[:2] == ("src", "reviewed") and path.name in REVIEWED_METADATA:
            paths.append(path)
        elif (len(relative.parts) == 2
              and path.suffix in DIR_SUFFIXES.get(relative.parts[0], set())
              and relative.as_posix() != "src/codec_bytes.rs"):
            paths.append(path)
    if not {"Cargo.toml", "Cargo.lock", "README.md"}.issubset({p.name for p in paths}):
        raise ValueError("required source files missing")
    return paths


def validate_nro(data: bytes) -> None:
    if len(data) < 0x80 or data[0x10:0x14] != b"NRO0":
        raise ValueError("not an NRO0 file")
    size = struct.unpack_from("<I", data, 0x18)[0]
    if size != len(data):
        raise ValueError("NRO length/header mismatch")
    segments = [struct.unpack_from("<II", data, offset) for offset in (0x20, 0x28, 0x30)]
    last_end = 0
    for offset, length in segments:
        if offset < last_end or offset + length > size or offset % 0x1000 or length % 0x1000:
            raise ValueError("invalid NRO segment bounds/alignment")
        last_end = offset + length


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--nro", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output_directory.resolve()
    try:
        if output == root or root in output.parents:
            raise ValueError("output directory must be outside source tree")
        output.mkdir(parents=True, exist_ok=False)
        source = output / "ssbu-quickplay-team-attack-source.zip"
        with zipfile.ZipFile(source, "x") as archive:
            for path in source_paths(root):
                add_bytes(archive, root.name + "/" + path.relative_to(root).as_posix(), path.read_bytes())
        products = [source]
        report = output / "ssbu-team-attack-research-report.md"
        shutil.copyfile(root / "TECHNICAL_DEVELOPMENT.md", report)
        products.append(report)
        if args.nro:
            binary = args.nro.read_bytes()
            validate_nro(binary)
            nro = output / PLUGIN_NAME
            shutil.copyfile(args.nro, nro)
            install = output / "SSBU-Team-Attack-ON-0.3.0.zip"
            with zipfile.ZipFile(install, "x") as archive:
                add_bytes(archive, PLUGIN_PATH, binary)
                add_bytes(archive, "ultimate/quickplay_team_attack/config.toml", (root / "config/proposal_experiment_13_0_5.toml.example").read_bytes())
                add_bytes(archive, "README.md", (root / "README.md").read_bytes())
                add_bytes(archive, "BUILD_REPORT.md", (root / "BUILD_REPORT.md").read_bytes())
                add_bytes(archive, "TECHNICAL_DEVELOPMENT.md", (root / "TECHNICAL_DEVELOPMENT.md").read_bytes())
            products.extend([nro, install])
        for product in products:
            if product.suffix == ".zip":
                with zipfile.ZipFile(product) as archive:
                    if archive.testzip() is not None:
                        raise ValueError("archive integrity check failed")
        manifest = output / "SHA256SUMS.txt"
        with manifest.open("x", encoding="ascii") as destination:
            for product in products:
                digest = hashlib.sha256(product.read_bytes()).hexdigest()
                destination.write(f"{digest}  {product.name}\n")
                print(f"{digest}  {product.name}")
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
