#!/usr/bin/env python3
"""Run all local Goemon reverse-engineering tests without GitHub Actions.

Add --native to compile/run original N64 memory and collision C++20 tests.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


def run_native(root: Path) -> int:
    compiler = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++") or shutil.which("cl")
    if not compiler:
        print("ERROR: no C++20 compiler found in PATH", file=sys.stderr)
        return 2
    source_dir = root / "re" / "tests"
    sources = [source_dir / "test_original_memory.cpp",
               source_dir / "test_original_collision.cpp",
               source_dir / "test_original_character_init.cpp",
               source_dir / "test_goemon_capture_gate.cpp",
               source_dir / "test_original_jump.cpp",
               source_dir / "test_original_horizontal.cpp",
               source_dir / "test_original_motion_adapter.cpp",
               source_dir / "test_original_animation_rates.cpp",
               source_dir / "test_original_yaw.cpp",
               source_dir / "test_original_action_phase.cpp",
               source_dir / "test_original_steering.cpp",
               source_dir / "test_original_steered_motion.cpp",
               source_dir / "test_original_vector_acceleration.cpp",
               source_dir / "test_original_vector_controller.cpp"]
    for source in sources:
        if not source.is_file():
            print(f"ERROR: native test source missing: {source}", file=sys.stderr)
            return 2
    with tempfile.TemporaryDirectory(prefix="goemon-native-test-") as temp:
        for source in sources:
            executable = Path(temp) / (
                source.stem + (".exe" if sys.platform == "win32" else "")
            )
            if Path(compiler).stem.lower() == "cl":
                command = [
                    compiler, "/nologo", "/std:c++20", "/W4", "/WX", "/EHsc",
                    "/I" + str(root.parents[1]), str(source),
                    "/Fe:" + str(executable),
                ]
            else:
                command = [
                    compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                    "-pedantic", "-I", str(root.parents[1]),
                    str(source), "-o", str(executable),
                ]
            for arguments in (command, [str(executable)]):
                result = subprocess.run(arguments, check=False, timeout=120)
                if result.returncode != 0:
                    return result.returncode
            print(f"Goemon C++20 native {source.stem}: PASS")
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--native", action="store_true", help="compile/run native C++20 original-memory and collision tests")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent
    folders = (
        root / "tests",
        root / "reference_probe" / "tests",
        root / "re" / "tests",
    )
    loader = unittest.TestLoader()
    all_tests = unittest.TestSuite()
    for folder in folders:
        if folder.is_dir():
            all_tests.addTests(loader.discover(str(folder), pattern="test_*.py"))
    count = all_tests.countTestCases()
    if not count:
        print("ERROR: no Goemon tests found", file=sys.stderr)
        return 2
    result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(all_tests)
    print(f"Goemon tools: {result.testsRun}/{count} tests run, "
          f"failures={len(result.failures)}, errors={len(result.errors)}")
    if not result.wasSuccessful():
        return 1
    return run_native(root) if args.native else 0


if __name__ == "__main__":
    sys.exit(main())
