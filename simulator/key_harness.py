#!/usr/bin/env python3
"""Exercise simulator keyboard input paths and verify raw key codes."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


SIMULATOR_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIMULATOR_DIR.parent
RUNNER = SIMULATOR_DIR / "run.py"
VIEWER_SOURCE = SIMULATOR_DIR / "viewer" / "sdl_fb_viewer.c"
TRACE_RE = re.compile(r"^\[sim:key\]\s+(\d+)\s*$", re.MULTILINE)

BASE_CMD = [
    "micropython",
    str(RUNNER),
    "--headless",
    "--frames",
    "2",
    "--speed",
    "fast",
    "--audio",
    "silent",
    "--network",
    "offline",
]

NAMED_KEY_CASES = [
    ("up", [0xB5]),
    ("down", [0xB6]),
    ("left", [0xB4]),
    ("right", [0xB7]),
    ("escape", [0xB1]),
    ("back", [0xB1]),
    ("break", [0xD0]),
    ("insert", [0xD1]),
    ("backspace", [0x08]),
    ("enter", [0x0D]),
    ("tab", [0x09]),
    ("home", [0xD2]),
    ("delete", [0xD4]),
    ("end", [0xD5]),
    ("pageup", [0xD6]),
    ("pagedown", [0xD7]),
    ("ctrl-up", [0xC2]),
    ("ctrl-down", [0xC3]),
    ("f1", [0x81]),
    ("f2", [0x82]),
    ("f3", [0x83]),
    ("f4", [0x84]),
    ("f5", [0x85]),
    ("f6", [0x86]),
    ("f7", [0x87]),
    ("f8", [0x88]),
    ("f9", [0x89]),
    ("f10", [0x90]),
]

ALIAS_CASES = [
    ("esc", [0xB1]),
    ("ins", [0xD1]),
    ("bs", [0x08]),
    ("return", [0x0D]),
    ("center", [0x0D]),
    ("newline", [0x0D]),
    ("del", [0xD4]),
    ("page-up", [0xD6]),
    ("pgup", [0xD6]),
    ("page-down", [0xD7]),
    ("pgdn", [0xD7]),
    ("ctrlup", [0xC2]),
    ("ctrldown", [0xC3]),
]

TEXT_CASES = [
    ("whitespace", " \t\n", [0x20, 0x09, 0x0D]),
    ("digits", "0123456789", [ord(ch) for ch in "0123456789"]),
    ("lowercase", "abcdefghijklmnopqrstuvwxyz", [ord(ch) for ch in "abcdefghijklmnopqrstuvwxyz"]),
    ("uppercase", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", [ord(ch) for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]),
    ("symbols", r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""", [ord(ch) for ch in r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""]),
]

VIEWER_EXPECTED_SNIPPETS = [
    ("SDLK_UP", "return 0xB5;"),
    ("SDLK_DOWN", "return 0xB6;"),
    ("SDLK_LEFT", "return 0xB4;"),
    ("SDLK_RIGHT", "return 0xB7;"),
    ("SDLK_ESCAPE", "return 0xB1;"),
    ("SDLK_PAUSE", "return 0xD0;"),
    ("SDLK_INSERT", "return 0xD1;"),
    ("SDLK_BACKSPACE", "return 8;"),
    ("SDLK_RETURN", "return 13;"),
    ("SDLK_TAB", "return 9;"),
    ("SDLK_HOME", "return 0xD2;"),
    ("SDLK_DELETE", "return 0xD4;"),
    ("SDLK_END", "return 0xD5;"),
    ("SDLK_PAGEUP", "return 0xD6;"),
    ("SDLK_PAGEDOWN", "return 0xD7;"),
    ("SDLK_F1", "return 0x81;"),
    ("SDLK_F10", "return 0x90;"),
    ("KMOD_CTRL", "code = 0xC2;"),
    ("KMOD_CTRL", "code = 0xC3;"),
]

TEXT_EDITOR_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import sd_mp
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.applications import text_editor

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    True,
    False,
    False,
    "",
    False,
    "",
    "",
    "offline",
    "virtual",
    "silent",
    "fast",
    0,
    "dev",
    "",
)

vm = ViewManager()
vm.add(View("text_editor", text_editor.run, text_editor.start, text_editor.stop))
vm.switch_to("text_editor")

sim_runtime.enqueue_key_names("enter")
sim_runtime.enqueue_text("note.txt")
sim_runtime.enqueue_key_names("center,back")
for _ in range(200):
    vm.run()
print("create_exists", int(sd_mp.exists("note.txt")))
sd_mp.write("sim_frame.rgb565", b"do-not-touch", True)

sim_runtime.push_key(182)  # down
vm.run()
sim_runtime.push_key(13)   # enter
vm.run()
sim_runtime.push_key(182)  # down
vm.run()
before_editor_frame = sum(vm.draw._buffer)
sim_runtime.push_key(13)   # center on note.txt in root
vm.run()
print("editor_has_draw", int(getattr(text_editor._textbox, "_draw", None) is vm.draw))
print("editor_frame_changed", int(before_editor_frame != sum(vm.draw._buffer)))
sim_runtime.push_key(122)  # z
vm.run()
sim_runtime.push_key(177)  # back/save
vm.run()

data = sd_mp.read("note.txt", 0, 0).decode("utf-8")
print("final_text", repr(data))
rgb = sd_mp.read("sim_frame.rgb565", 0, 0)
print("rgb_preserved", int(rgb == b"do-not-touch"))
"""

VISIBLE_KEYBOARD_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import sd_mp
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.applications import text_editor

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    True,
    False,
    False,
    "",
    False,
    "",
    "",
    "offline",
    "virtual",
    "silent",
    "fast",
    0,
    "dev",
    "",
)

vm = ViewManager()
vm.keyboard.show_keyboard = True
vm.add(View("text_editor", text_editor.run, text_editor.start, text_editor.stop))
vm.switch_to("text_editor")

sim_runtime.enqueue_key_names("enter")
sim_runtime.enqueue_text("note.txt")
sim_runtime.enqueue_key_names("center,back")
for _ in range(200):
    vm.run()

print("visible_exists", int(sd_mp.exists("note.txt")))
"""

FILE_MANAGER_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import sd_mp
from picoware.system.view_manager import ViewManager
from picoware.system.view import View
from picoware.applications import file_manager

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    True,
    False,
    False,
    "",
    False,
    "",
    "",
    "offline",
    "virtual",
    "silent",
    "fast",
    0,
    "dev",
    "",
)

sd_mp.write("sample.txt", b"hello", True)

vm = ViewManager()
vm.add(View("file_manager", file_manager.run, file_manager.start, file_manager.stop))
vm.switch_to("file_manager")
fb = file_manager._file_browser

sim_runtime.push_key(182)
vm.run()
sim_runtime.push_key(13)
vm.run()
print("menu_item", getattr(fb._context_menu, "current_item", None))
sim_runtime.push_key(13)
vm.run()
print("editing", int(fb._is_editing), "viewing", int(fb._is_viewing_text))
"""


class HarnessFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("all", "named", "aliases", "text", "viewer", "editor"),
        default="all",
        help="Subset of checks to run. The editor mode exercises source-level editor flows separately.",
    )
    parser.add_argument(
        "--keep-sd",
        action="store_true",
        help="Keep the temporary simulator SD directory for debugging.",
    )
    return parser.parse_args()


def extract_codes(output: str) -> list[int]:
    return [int(value) for value in TRACE_RE.findall(output)]


def run_case(name: str, extra_args: list[str], expected_codes: list[int], sd_root: Path) -> None:
    cmd = BASE_CMD + ["--sd", str(sd_root), "--trace-keys"] + extra_args
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "case {!r} failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                name, result.returncode, result.stdout, result.stderr
            )
        )

    actual_codes = extract_codes(result.stdout)
    if actual_codes != expected_codes:
        raise HarnessFailure(
            "case {!r} produced {} instead of {}\nstdout:\n{}".format(
                name, actual_codes, expected_codes, result.stdout
            )
        )

    print("[key-harness:pass]", name, actual_codes)


def check_micropython_available() -> None:
    if shutil.which("micropython") is None:
        raise HarnessFailure("micropython was not found in PATH")


def check_viewer_source() -> None:
    text = VIEWER_SOURCE.read_text()
    for anchor, expected in VIEWER_EXPECTED_SNIPPETS:
        if anchor not in text or expected not in text:
            raise HarnessFailure(
                "viewer mapping check failed: missing {!r} near {!r}".format(expected, anchor)
            )
    print("[key-harness:pass] viewer-source")


def run_named_cases(sd_root: Path) -> None:
    for key_name, expected in NAMED_KEY_CASES:
        run_case("named:" + key_name, ["--keys", key_name], expected, sd_root)


def run_alias_cases(sd_root: Path) -> None:
    for key_name, expected in ALIAS_CASES:
        run_case("alias:" + key_name, ["--keys", key_name], expected, sd_root)


def run_text_cases(sd_root: Path) -> None:
    for case_name, text, expected in TEXT_CASES:
        run_case("text:" + case_name, ["--keys-text", text], expected, sd_root)


def run_text_editor_regression(sd_root: Path) -> None:
    script = TEXT_EDITOR_SCRIPT.format(sd_root=str(sd_root))
    result = subprocess.run(
        ["micropython", "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "text editor regression failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if (
        "create_exists 1" not in result.stdout
        or "final_text 'z'" not in result.stdout
        or "rgb_preserved 1" not in result.stdout
        or "editor_has_draw 1" not in result.stdout
        or "editor_frame_changed 1" not in result.stdout
    ):
        raise HarnessFailure(
            "text editor regression produced unexpected output\nstdout:\n{}".format(
                result.stdout
            )
        )
    print("[key-harness:pass] text-editor")


def run_visible_keyboard_regression(sd_root: Path) -> None:
    script = VISIBLE_KEYBOARD_SCRIPT.format(sd_root=str(sd_root))
    result = subprocess.run(
        ["micropython", "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "visible keyboard regression failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if "visible_exists 1" not in result.stdout:
        raise HarnessFailure(
            "visible keyboard regression produced unexpected output\nstdout:\n{}".format(
                result.stdout
            )
        )
    print("[key-harness:pass] visible-keyboard")


def run_file_manager_regression(sd_root: Path) -> None:
    script = FILE_MANAGER_SCRIPT.format(sd_root=str(sd_root))
    result = subprocess.run(
        ["micropython", "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "file manager regression failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if "menu_item Edit" not in result.stdout or "editing 1 viewing 0" not in result.stdout:
        raise HarnessFailure(
            "file manager regression produced unexpected output\nstdout:\n{}".format(
                result.stdout
            )
        )
    print("[key-harness:pass] file-manager")


def main() -> int:
    args = parse_args()
    check_micropython_available()

    with tempfile.TemporaryDirectory(prefix="picoware-sim-keys-") as tmp:
        sd_root = Path(tmp)
        try:
            if args.mode in ("all", "viewer"):
                check_viewer_source()
            if args.mode in ("all", "named"):
                run_named_cases(sd_root)
            if args.mode in ("all", "aliases"):
                run_alias_cases(sd_root)
            if args.mode in ("all", "text"):
                run_text_cases(sd_root)
            if args.mode == "editor":
                run_text_editor_regression(sd_root)
            if args.mode == "editor":
                run_visible_keyboard_regression(sd_root)
                run_file_manager_regression(sd_root)
        except Exception:
            if args.keep_sd:
                debug_root = SIMULATOR_DIR / "sdcard" / "key-harness-debug"
                if debug_root.exists():
                    shutil.rmtree(debug_root)
                shutil.copytree(sd_root, debug_root)
                print("[key-harness:debug-sd]", debug_root)
            raise

    print("[key-harness:pass] mode=" + args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
