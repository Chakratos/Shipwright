"""Deterministic tests for the standalone Goemon64Recomp probe tooling."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from install_probe import install
from log_to_csv import extract_lines


MAIN_SOURCE = (
    '#include "patches.h"\n'
    '#include "ui_funcs.h"\n'
    '\n'
    "void func_800012FC_1EFC(void) {\n"
    "    recomp_run_ui_callbacks();\n"
    "}\n"
)
SAMPLE_LOG = (
    "Unrelated engine output\n"
    "GOEMON_REF,0,17,1,3,1,32768,1.25,2.25,3.25,0,512,0,0.5,0,80,-80,1.0,-1.0\n"
)


class ProbeInstallerTests(unittest.TestCase):
    def test_install_idempotent_and_remove_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            patches = root / "patches"
            patches.mkdir()
            (patches / "main.c").write_text(MAIN_SOURCE, encoding="utf-8")
            (patches / "Makefile").write_text("C_SRCS := $(wildcard *.c)\n", encoding="utf-8")
            install(root, False)
            patched = (patches / "main.c").read_text(encoding="utf-8")
            self.assertEqual(patched.count("GoemonReferenceProbe_CaptureRenderFrame();"), 1)
            self.assertTrue((patches / "goemon_trace_probe.c").exists())
            install(root, False)
            self.assertEqual((patches / "main.c").read_text(encoding="utf-8"), patched)
            install(root, True)
            self.assertEqual((patches / "main.c").read_text(encoding="utf-8"), MAIN_SOURCE)
            self.assertFalse((patches / "goemon_trace_probe.c").exists())

    def test_unknown_source_is_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            patches = root / "patches"
            patches.mkdir()
            (patches / "Makefile").write_text("test\n", encoding="utf-8")
            (patches / "main.c").write_text("unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "insertion points"):
                install(root, False)
            self.assertFalse((patches / "goemon_trace_probe.c").exists())


class ProbeLogTests(unittest.TestCase):
    def test_parse_raw_record(self):
        result = extract_lines(SAMPLE_LOG.splitlines())
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 18)
        self.assertEqual(result[0][0], "0")
        self.assertEqual(result[0][10], "512")

    def test_skip_duplicate_frame(self):
        row = SAMPLE_LOG.splitlines()[1]
        with self.assertRaisesRegex(ValueError, "missing/duplicate"):
            extract_lines([row, row])

    def test_reject_nan(self):
        row = SAMPLE_LOG.splitlines()[1].replace("1.25", "nan")
        with self.assertRaisesRegex(ValueError, "bad root_pos_x"):
            extract_lines([row])


if __name__ == "__main__":
    unittest.main()
