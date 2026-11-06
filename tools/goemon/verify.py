#!/usr/bin/env python3
"""Run all local Goemon reverse-engineering tests without GitHub Actions.

Add --native to compile/run original N64 memory and collision C++20 tests.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


def windows_msvc() -> tuple[str, dict[str, str]] | None:
    """Use installed MSVC and its matching SDK, not an older standalone Clang."""
    if sys.platform != "win32":
        return None
    compiler = shutil.which("cl.exe")
    if compiler:
        return compiler, dict(os.environ)
    vsbase = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio"
    devcmds = sorted(vsbase.glob("*/*/Common7/Tools/VsDevCmd.bat"), reverse=True)
    if not devcmds:
        print(f"MSVC: no VS developer command prompt found under {vsbase}", file=sys.stderr)
        return None
    devcmd = devcmds[0]
    with tempfile.TemporaryDirectory(prefix="goemon-msvc-env-") as directory:
        launcher = Path(directory) / "load-msvc.cmd"
        launcher.write_text(
            '@echo off\ncall "' + str(devcmd) +
            '" -arch=x64 -host_arch=x64 >nul\nif errorlevel 1 exit /b %errorlevel%\nset\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher)],
            capture_output=True, text=True, check=False, timeout=90,
        )
    if result.returncode != 0:
        print(f"MSVC: VsDevCmd failed ({result.returncode}): {result.stderr[-800:]}",
              file=sys.stderr)
        return None
    environment = {key.upper(): value for key, value in os.environ.items()}
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            environment[key.upper()] = value
    compiler = shutil.which("cl.exe", path=environment.get("PATH"))
    if not compiler:
        print(f"MSVC: cl.exe missing after {devcmd}", file=sys.stderr)
        return None
    print(f"Goemon C++20 compiler: {compiler}")
    return compiler, environment


def run_native(root: Path) -> int:
    msvc = windows_msvc()
    environment = msvc[1] if msvc else dict(os.environ)
    compiler = (msvc[0] if msvc else
                shutil.which("clang++") or shutil.which("g++") or
                shutil.which("c++") or shutil.which("cl"))
    if not compiler:
        print("ERROR: no C++20 compiler found", file=sys.stderr)
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
               source_dir / "test_original_vector_controller.cpp",
               source_dir / "test_original_zelda_world_probe.cpp",
               source_dir / "test_original_zelda_actor_terrain.cpp",
               source_dir / "test_original_live_input.cpp",
               source_dir / "test_original_live_frame.cpp",
               source_dir / "test_original_pilot_camera.cpp",
               source_dir / "test_original_trace_replay.cpp"]
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
                result = subprocess.run(arguments, check=False, timeout=120, env=environment)
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
    # The dedicated self-hosted Goemon runner must validate the authentic
    # original ROM from its local filesystem, never from repository assets.
    if os.environ.get("RUNNER_NAME", "").lower() == "goemon-builder" and args.native:
        from real_rom_check import main as verify_real_rom
        real_result = verify_real_rom(["--graphics-scan"])
        if real_result:
            return real_result
    return run_native(root) if args.native else 0


if __name__ == "__main__":
    sys.exit(main())
