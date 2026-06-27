#!/usr/bin/env python3
"""Run the full simulator regression suite for this branch."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SIMULATOR_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIMULATOR_DIR.parent


class RegressionFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-key",
        action="store_true",
        help="Skip the key/text-editor harness.",
    )
    parser.add_argument(
        "--skip-viewer",
        action="store_true",
        help="Run capability modes individually and skip the SDL viewer smoke.",
    )
    return parser.parse_args()


def run_step(name: str, args: list[str]) -> None:
    print("[regression-harness:run]", name)
    result = subprocess.run(args, cwd=REPO_ROOT, text=True, check=False)
    if result.returncode != 0:
        raise RegressionFailure("{} failed with exit code {}".format(name, result.returncode))
    print("[regression-harness:pass]", name)


def run_capabilities(skip_viewer: bool) -> None:
    if not skip_viewer:
        run_step(
            "capabilities-all",
            [sys.executable, "simulator/capability_harness.py", "--mode", "all"],
        )
        return

    modes = (
        "jpeg",
        "psram",
        "machine",
        "usb",
        "bluetooth",
        "wifi",
        "ghouls",
        "gameboy",
        "engine",
    )
    for mode in modes:
        run_step(
            "capability-" + mode,
            [sys.executable, "simulator/capability_harness.py", "--mode", mode],
        )


def main() -> int:
    args = parse_args()
    run_step(
        "py-compile",
        [
            sys.executable,
            "-m",
            "py_compile",
            "simulator/capability_harness.py",
            "simulator/key_harness.py",
            "simulator/regression_harness.py",
            "simulator/hardware/engine.py",
            "simulator/hardware/gameboy.py",
            "simulator/hardware/ghouls.py",
            "simulator/hardware/jpegdec.py",
            "simulator/hardware/lcd.py",
            "simulator/hardware/machine.py",
            "simulator/hardware/network.py",
            "simulator/hardware/picoware_psram.py",
            "simulator/hardware/sim_runtime.py",
            "simulator/hardware/ubluetooth.py",
            "src/MicroPython/picoware/system/psram.py",
            "src/MicroPython/picoware/system/settings.py",
            "src/MicroPython/picoware/system/input.py",
            "src/MicroPython/picoware/applications/system/settings.py",
            "builds/MicroPython/apps_unfrozen/games/Flappy Bird.py",
        ],
    )
    run_capabilities(args.skip_viewer)
    if not args.skip_key:
        run_step("key-harness", [sys.executable, "simulator/key_harness.py"])
    run_step("diff-check", ["git", "diff", "--check"])
    print("[regression-harness:pass] all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
