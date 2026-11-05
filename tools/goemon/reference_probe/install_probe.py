#!/usr/bin/env python3
"""Install/remove the exploratory MNSG render-state probe in a local Goemon64Recomp checkout.

Only changes patches/main.c and patches/goemon_trace_probe.c in the supplied
working copy. No GitHub workflow, source ROM or upstream repository is modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


DECLARATION = "void GoemonReferenceProbe_CaptureRenderFrame(void);"
CALL = "    GoemonReferenceProbe_CaptureRenderFrame();"
ANCHOR_INCLUDE = '#include "ui_funcs.h"'
ANCHOR_CALL = "    recomp_run_ui_callbacks();"


def install(root: Path, remove: bool) -> None:
    patches = root / "patches"
    main = patches / "main.c"
    destination = patches / "goemon_trace_probe.c"
    source = Path(__file__).with_name("goemon_probe.c")

    if not main.is_file() or not (patches / "Makefile").is_file():
        raise ValueError(f"{root} is not a Goemon64Recomp source checkout")
    # Preserve Windows CRLF and Unix LF exactly, including mixed-line files.
    with main.open("r", encoding="utf-8", newline="") as stream:
        original = stream.read()
    newline = "\r\n" if "\r\n" in original else "\n"
    probe = source.read_bytes()

    if remove:
        if DECLARATION not in original and CALL not in original and not destination.exists():
            print("Probe already absent")
            return
        if original.count(DECLARATION) != 1 or original.count(CALL) != 1:
            raise ValueError("Unexpected main.c patch state; refusing incomplete removal")
        if not destination.is_file() or destination.read_bytes() != probe:
            raise ValueError("Probe C source changed; refusing to delete a modified file")
        changed = original.replace(DECLARATION + newline, "", 1)
        changed = changed.replace(CALL + newline, "", 1)
        with main.open("w", encoding="utf-8", newline="") as stream:
            stream.write(changed)
        destination.unlink()
        print("Removed Goemon reference probe")
        return

    if destination.exists() and destination.read_bytes() != probe:
        raise ValueError("Existing goemon_trace_probe.c differs; refusing overwrite")

    if DECLARATION in original or CALL in original:
        if original.count(DECLARATION) == 1 and original.count(CALL) == 1:
            if not destination.exists():
                destination.write_bytes(probe)
            print("Probe already installed")
            return
        raise ValueError("Unexpected main.c patch state; refusing partial overwrite")

    if original.count(ANCHOR_INCLUDE) != 1 or original.count(ANCHOR_CALL) != 1:
        raise ValueError("Goemon64Recomp main.c changed; cannot find unique insertion points")

    changed = original.replace(ANCHOR_INCLUDE, ANCHOR_INCLUDE + newline + DECLARATION, 1)
    changed = changed.replace(ANCHOR_CALL, ANCHOR_CALL + newline + CALL, 1)
    # Write probe first; main.c remains unmodified if source installation fails.
    destination.write_bytes(probe)
    with main.open("w", encoding="utf-8", newline="") as stream:
        stream.write(changed)
    print("Installed Goemon reference probe")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goemon_checkout", type=Path)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)
    try:
        install(args.goemon_checkout, args.remove)
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
