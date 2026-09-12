import json
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from analyze_ab import candidate_bits
from compare_dumps import BUFFER_LEN, choose_sequences, differences, read_log
from locate_serializer import read_features, score
from package_release import source_paths, validate_nro


def payload(value=0):
    result = [None] * BUFFER_LEN
    result[4] = value
    return tuple(result)


def line(sequence, values):
    return f"dump {sequence}: " + " ".join("--" if v is None else f"{v:02X}" for v in values) + "\n"


class CaptureTests(unittest.TestCase):
    def test_redacted_comparison(self):
        self.assertEqual(differences(payload(), payload(32)), [(4, 0, 32, 32)])
        self.assertEqual(differences(payload(32), payload(32)), [])

    def test_missing_is_not_zero(self):
        with self.assertRaises(ValueError):
            differences(payload(), tuple([None] * BUFFER_LEN))
        with self.assertRaises(ValueError):
            differences(tuple([None] * BUFFER_LEN), tuple([None] * BUFFER_LEN))

    def test_sequence_selection(self):
        data = {0: payload(), 3: payload(32), 5: payload()}
        self.assertEqual(choose_sequences(data, []), (3, 5))
        for requested in [[0], [0, 0], [1, 2]]:
            with self.assertRaises(ValueError):
                choose_sequences(data, requested)

    def test_parser_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.log"
            for contents in ["dump 0: AA\n", "dump 0: GG " * BUFFER_LEN, line(0, payload()) * 2, "# game_version=13.0.5\n" * 2 + line(0, payload()), "partial"]:
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_log(path)
            path.write_text("# run_label=A1_OFF\n" + line(0, payload()), encoding="utf-8")
            log = read_log(path)
            self.assertEqual(log.metadata["run_label"], "A1_OFF")
            self.assertEqual(log.captures[0], payload())

    def test_repeatable_bit_and_polarity(self):
        triplets = [(payload(), payload(32), payload())] * 3
        self.assertEqual(candidate_bits(triplets), [{"offset": "0x4", "mask": "0x20", "off_bits": "0x0", "on_bits": "0x20", "status": "CORRELATION_ONLY"}])
        reverse = [(payload(32), payload(), payload(32))] * 3
        self.assertEqual(candidate_bits(reverse)[0]["on_bits"], "0x0")

    def test_noise_and_failed_return_are_not_candidates(self):
        triplets = [(payload(), payload(32), payload())] * 2
        self.assertEqual(candidate_bits(triplets + [(payload(), payload(32), payload(32))]), [])
        with self.assertRaises(ValueError):
            candidate_bits(triplets)

    def test_cli_ab_context_and_distinctness(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.log"
            header = "# observer_version=0.2.0\n# game_version=13.0.5\n# serializer_text_offset=0x20\n# caller_text_offset=0x60\n# compact_buffer_length=0x69\n"
            header += "# reviewed_abi=void_u8_ptr_v1\n# entry_signature=AA00\n# caller_signature=94FF\n"
            path.write_text(header + "".join(line(i, payload(32 if i % 3 == 1 else 0)) for i in range(9)), encoding="utf-8")
            command = [sys.executable, str(Path(__file__).with_name("analyze_ab.py"))]
            for i in range(0, 9, 3):
                command += ["--triplet"] + [f"{path}:{j}" for j in range(i, i + 3)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["candidates"][0]["mask"], "0x20")
            result = subprocess.run(command + ["--triplet", f"{path}:0", f"{path}:1", f"{path}:2"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


class LocatorTests(unittest.TestCase):
    def test_structural_ranking_does_not_approve(self):
        function = {"offset": 32, "size": 560, "mnemonics": ["STP", "MOV", "STRB", "BL", "RET"], "constants": [0x78, 0x1f, 0x40], "store_displacements": [0x40, 0x58, 0x68]}
        unrelated = {"offset": 64, "size": 64, "mnemonics": ["RET"], "constants": [], "store_displacements": []}
        self.assertGreater(score(function, function)[0], score(unrelated, function)[0])
        self.assertNotIn("verified", function)

    def test_export_requires_end_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.jsonl"
            records = [{"type": "metadata", "schema": 1, "game_version": "13.0.5"}, {"type": "function", "offset": 32, "mnemonics": ["RET"]}]
            path.write_text("\n".join(map(json.dumps, records)), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_features(path)
            records.append({"type": "end", "function_count": 1})
            path.write_text("\n".join(map(json.dumps, records)), encoding="utf-8")
            self.assertEqual(len(read_features(path)[1]), 1)


class PackagingTests(unittest.TestCase):
    def test_nro_header_validation(self):
        data = bytearray(0x3000)
        data[0x10:0x14] = b"NRO0"
        struct.pack_into("<I", data, 0x18, len(data))
        for header, offset in [(0x20, 0), (0x28, 0x1000), (0x30, 0x2000)]:
            struct.pack_into("<II", data, header, offset, 0x1000)
        validate_nro(bytes(data))
        with self.assertRaises(ValueError):
            validate_nro(bytes(data[:-1]))
        struct.pack_into("<I", data, 0x28, 0x800)
        with self.assertRaises(ValueError):
            validate_nro(bytes(data))
        with self.assertRaises(ValueError):
            validate_nro(b"not a plugin")

    def test_source_allowlist_excludes_unrelated_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["Cargo.toml", "Cargo.lock", "README.md", "src/lib.rs", "src/codec_bytes.rs", "src/reviewed/README.md",
                     "src/reviewed/manifest.json", "src/reviewed/application.bin", "tools/locator.py",
                     "main", "prod.keys", "captures/capture.log", "target/plugin.nro",
                     "research/full-main.bin", "ghidra/main.gzf"]
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test fixture", encoding="utf-8")
            included = {path.relative_to(root).as_posix() for path in source_paths(root)}
            self.assertEqual(included, {"Cargo.toml", "Cargo.lock", "README.md", "src/lib.rs",
                                        "src/reviewed/README.md", "src/reviewed/manifest.json",
                                        "tools/locator.py"})


if __name__ == "__main__":
    unittest.main()
