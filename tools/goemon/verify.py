#!/usr/bin/env python3
"""Run all Goemon tool tests locally without GitHub Actions or hosted CI."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
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
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
