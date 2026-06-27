#!/usr/bin/env python3
"""Exercise simulator capability shims beyond keyboard input."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


SIMULATOR_DIR = Path(__file__).resolve().parent
REPO_ROOT = SIMULATOR_DIR.parent
JPEG_FIXTURE = REPO_ROOT / "src" / "MicroPython" / "JPEGDEC" / "perf.jpg"


JPEG_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import sd_mp
sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    False,
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
from picoware.gui.draw import Draw
import jpegdec

draw = Draw()
data = sd_mp.read("fixture.jpg")
dec = jpegdec.JPEGDecoder()
info = dec.getinfo(data)
print("jpeg_info", int(info[0]), info[1], info[2])
print("jpeg_open_ram", int(dec.open_RAM(data)))
before = sum(draw._buffer)
print("jpeg_decode_buffer", int(dec.decode(0, 0, 8)))
print("jpeg_frame_changed", int(before != sum(draw._buffer)))

dec2 = jpegdec.JPEGDecoder()
print("jpeg_open_path", int(dec2.open_file("fixture.jpg")))
before_path = sum(draw._buffer)
print("jpeg_decode_path", int(dec2.decode(4, 4, 8)))
print("jpeg_path_changed", int(before_path != sum(draw._buffer)))

bad = jpegdec.JPEGDecoder()
bad_info = bad.getinfo(b"not-jpeg")
print("jpeg_bad_info", int(bad_info[0]), bad_info[1], bad_info[2])
print("jpeg_bad_open", int(bad.open_RAM(b"not-jpeg")))
print("jpeg_bad_decode", int(bad.decode(0, 0, 1)))
"""


PSRAM_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import picoware_psram
import sd_mp

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    False,
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

p = picoware_psram.PSRAM()
print("psram_size", p.size(), picoware_psram.SIZE, picoware_psram.HEAP_START_ADDR)
p.write(0, b"abcd")
print("psram_read", p.read(0, 4))
p.write8(10, 0x12)
p.write16(12, 0x3456)
p.write32(16, 0x789ABCDE)
print("psram_scalars", p.read8(10), hex(p.read16(12)), hex(p.read32(16)))
print("psram_bulk_write", p.write32_bulk(32, [1, 2, 3]))
print("psram_bulk_read", p.read32_bulk(32, 3))
print("psram_fill", p.fill(64, 0xAA, 4), p.read(64, 4))
print("psram_fill32", p.fill32(80, 0x11223344, 2), [hex(x) for x in p.read32_bulk(80, 2)])
p.copy(80, 96, 8)
print("psram_copy", [hex(x) for x in p.read32_bulk(96, 2)])
buf = bytearray(4)
print("psram_read_into", p.read_into(0, buf), bytes(buf))
try:
    p.read(picoware_psram.SIZE, 1)
    print("psram_bounds", 0)
except ValueError:
    print("psram_bounds", 1)

before = p.mem_free()
obj = p.alloc_object(b"payload")
addr = obj.addr()
after_alloc = p.mem_free()
obj.__del__()
after_free = p.mem_free()
collected = p.collect()
obj2 = p.alloc_object(b"xx")
print("psram_alloc", int(after_alloc < before), int(after_free > after_alloc), int(obj2.addr() == addr), collected)

sd_mp.create_directory("tmp")
f = sd_mp.file_open("tmp/large-write.bin")
chunk = b"x" * 4096
for _ in range(140):
    sd_mp.file_write(f, chunk)
sd_mp.file_close(f)
print("sd_large_write", sd_mp.get_file_size("tmp/large-write.bin"))
"""


MACHINE_SCRIPT = r"""
import sys
sys.path.insert(0, "simulator/hardware")
from machine import I2C, SPI, ADC, Timer, WDT
import time

I2C.set_device(0x42, b"abc")
i2c = I2C(0)
print("machine_i2c_scan", i2c.scan())
print("machine_i2c_read", i2c.readfrom(0x42, 4))
i2c.writeto_mem(0x42, 2, b"XY")
print("machine_i2c_mem", i2c.readfrom_mem(0x42, 0, 5))
buf = bytearray(3)
i2c.readfrom_into(0x42, buf)
print("machine_i2c_into", bytes(buf))

spi = SPI(0)
spi.write(b"hi")
print("machine_spi_read", spi.read(3, 0xEE))
rx = bytearray(4)
spi.write_readinto(b"AB", rx)
print("machine_spi_rw", bytes(rx))

ADC.set_value(26, 12345)
print("machine_adc", ADC(26).read_u16())

events = []
one = Timer(7)
one.init(mode=Timer.ONE_SHOT, period=1, callback=lambda t: events.append(("one", t.id)))
time.sleep(0.003)
Timer.poll_all()
Timer.poll_all()
periodic = Timer(8)
periodic.init(mode=Timer.PERIODIC, period=1, callback=lambda t: events.append(("periodic", t.id)))
time.sleep(0.003)
Timer.poll_all()
time.sleep(0.003)
Timer.poll_all()
periodic.deinit()
print("machine_timer", events)

wdt = WDT(timeout=1)
print("machine_wdt_before", int(wdt.expired()))
time.sleep(0.003)
print("machine_wdt_after", int(wdt.expired()), len(WDT.check_all()))
wdt.feed()
print("machine_wdt_feed", int(wdt.expired()))
"""


USB_SCRIPT = r"""
import sys
sys.path.insert(0, "simulator/hardware")
from machine import USBDevice

events = []
dev = USBDevice()
dev.config(
    reset_cb=lambda: events.append("reset"),
    open_itf_cb=lambda itf: events.append(("open", itf)) or True,
    xfer_cb=lambda ep, res, n: events.append(("xfer", ep, res, n)),
    control_xfer_cb=lambda stage, req: b"report" if req[1] == 6 else True,
)
print("usb_inactive_submit", int(dev.submit_xfer(0x83, b"\0" * 8)))
dev.active(True)
print("usb_active", int(dev.active()), events)
print("usb_open", dev.host_open_interface(2), dev.opened_interfaces())
print("usb_control", dev.host_control(1, bytes([0x81, 0x06, 0, 0x22, 2, 0, 64, 0])))
print("usb_submit_keyboard", int(dev.submit_xfer(0x83, bytes([2, 0, 4, 0, 0, 0, 0, 0]))))
print("usb_submit_consumer", int(dev.submit_xfer(0x83, bytes([0xCD, 0]))))
last = dev.last_transfer()
print("usb_last", last["ep"], last["type"], last["data"])
dev.host_receive(1, b"host")
print("usb_recv", dev.recv_xfer(1))
print("usb_log_count", len(dev.transfer_log()), len(dev.control_transfers))
"""


BLUETOOTH_SCRIPT = r"""
import sys
sys.path.insert(0, "simulator/hardware")
import ubluetooth as bluetooth

bluetooth.sim_reset()
bluetooth.sim_clear_scan_devices()
target = b"\x02\x50\x43\x57\x55\x01"
blocked = b"\x02\x50\x43\x57\x55\x02"
bluetooth.sim_add_scan_device("Chat-A", target, rssi=-33, services=(bluetooth.UUID(0x180F),), connectable=True)
bluetooth.sim_add_scan_device("Blocked", blocked, rssi=-80, connectable=False)

events = []
ble = bluetooth.BLE()
ble.active(True)
ble.irq(lambda event, data: events.append((event, data)))
ble.gap_scan(100)
scan_results = [item for item in events if item[0] == bluetooth._IRQ_SCAN_RESULT]
print("bt_scan", len(scan_results), scan_results[0][1][1], scan_results[0][1][3])
ble.gap_connect(0, target)
print("bt_connect", [item[0] for item in events].count(bluetooth._IRQ_PERIPHERAL_CONNECT))
ble.gap_connect(0, blocked)
print("bt_blocked", [item[0] for item in events].count(bluetooth._IRQ_PERIPHERAL_DISCONNECT))
ble.gap_advertise(100000, adv_data=b"adv", resp_data=b"rsp", connectable=False)
ads = bluetooth.sim_advertisements()
print("bt_adv", len(ads), ads[-1]["adv_data"], ads[-1]["resp_data"], ads[-1]["connectable"])
ble.gattc_write(1, 5, b"hello")
print("bt_notify", ble.sim_notifications())
"""


WIFI_SCRIPT = r"""
import sys
sys.path.insert(0, "simulator/hardware")
import network

network.sim_reset()
network.sim_clear_aps()
network.sim_add_ap("Secure", passphrase="sim-passphrase", channel=9, rssi=-35, authmode=network.AUTH_WPA2_PSK)
network.sim_add_ap("Open", authmode=network.AUTH_OPEN, rssi=-60)

sta = network.WLAN(network.STA_IF)
sta.active(True)
print("wifi_scan", sta.scan())
sta.connect("Missing", "")
print("wifi_missing", sta.status(), int(sta.isconnected()))
sta.connect("Secure", "bad")
print("wifi_badpass", sta.status(), int(sta.isconnected()))
sta.connect("Secure", "sim-passphrase")
print("wifi_connected", sta.status(), int(sta.isconnected()), sta.status("rssi"), sta.config("channel"))

ap = network.WLAN(network.AP_IF)
ap.config(essid="Picoware-AP", passphrase="sim-ap-passphrase", channel=3, authmode=network.AUTH_WPA2_PSK)
ap.active(True)
ap.sim_ap_connect(b"\xaa\xbb\xcc\xdd\xee\xff")
print("wifi_ap", int(ap.isconnected()), ap.config("essid"), ap.config("channel"), ap.status("stations"))
"""


GHOULS_SCRIPT = r"""
import sys
sys.path.insert(0, "simulator/hardware")
import ghouls

g = ghouls.Ghouls("tester", "sim-passphrase", False)
g.update_input(2)
g.update_input(1)
g.update_input(4)
for _ in range(6):
    g.update_draw()
snap = g.snapshot()
print("ghouls_state", snap["active"], snap["player"], snap["score"], snap["shots"], snap["enemies"], snap["frame"])
g.update_input(5)
print("ghouls_exit", g.snapshot()["active"])
"""


GAMEBOY_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    False,
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
import gameboy
import os
import time
from picoware.system.input import Input

gb = gameboy.GameBoy()
print("gameboy_start", int(gb.start("fixture.gb", "picoware/gameboy/test.sav")))
inp = Input()
mapped = []
for raw in (ord("z"), ord("x"), 13, 32):
    sim_runtime.push_key(raw)
    mapped.append(inp.button)
    inp.reset()
print("gameboy_inputmap", tuple(mapped))
gb.run(0)
gb.run(32)  # Picoware BUTTON_Z -> GameBoy B
gb.run(30)  # Picoware BUTTON_X -> GameBoy A
gb.run(4)   # Picoware BUTTON_CENTER / Enter -> GameBoy Start
gb.run(43)  # Picoware BUTTON_SPACE -> GameBoy Select
with open(sim_runtime.host_path("sim_gameboy_control.txt")) as handle:
    control = handle.read()
print("gameboy_control", int("button=54" in control))
time.sleep(0.08)
gb.run(-1)
snap = gb.snapshot()
print("gameboy_state", snap["running"], snap["rom_title"], snap["rom_size"], snap["frame"], snap["last_button"], snap["buttons_seen"])
frame_path = sim_runtime.host_path("sim_gameboy_frame.rgb565")
print("gameboy_native", int(getattr(gb, "_native", False)), int(os.stat(frame_path)[6] == 320 * 320 * 2))
gb.stop()
with open(sim_runtime.host_path("picoware/gameboy/test.sav")) as handle:
    saved = handle.read()
print("gameboy_saved", int("frame=6" in saved), int("title=SIMTEST" in saved))
try:
    gb.start("missing.gb")
    print("gameboy_missing", 0)
except OSError:
    print("gameboy_missing", 1)
"""


ENGINE_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")

from picoware.system.vector import Vector
from picoware.engine.camera import Camera
from picoware.engine.engine import GameEngine
from picoware.engine.entity import Entity, ENTITY_TYPE_PLAYER, ENTITY_TYPE_3D_SPRITE, SPRITE_3D_HOUSE
from picoware.engine.game import Game
from picoware.engine.level import Level
from picoware.engine.sprite3d import Sprite3D


class Input:
    def __init__(self):
        self.button = 4
        self.reset_count = 0

    def reset(self):
        self.reset_count += 1
        self.button = -1


class Draw:
    width = 160
    height = 120

    def __init__(self):
        self.calls = []

    def clear(self, color=0):
        self.calls.append(("clear", color))

    def fill_rectangle(self, pos, size, color):
        self.calls.append(("fill", pos.x, pos.y, size.x, size.y, color))

    def _fill_rectangle(self, x, y, w, h, color):
        self.calls.append(("fill", x, y, w, h, color))

    def _rectangle(self, x, y, w, h, color):
        self.calls.append(("rect", x, y, w, h, color))

    def _text(self, x, y, text, color):
        self.calls.append(("text", text))

    def swap(self):
        self.calls.append(("swap",))


events = []
draw = Draw()
inp = Input()
cam = Camera(Vector(0, 0, 0), Vector(1, 0, 0))
game = Game("sim-engine", Vector(160, 120), draw, inp, 0xFFFF, 0, cam)
level = Level("arena", Vector(16, 16), game)
game.level_add(level)

player = Entity(
    "player",
    ENTITY_TYPE_PLAYER,
    Vector(2, 2, 0),
    Vector(4, 4, 0),
    None,
    None,
    None,
    lambda entity: events.append(("start", entity.name)),
    lambda entity, g=None: events.append(("stop", entity.name)),
    lambda entity, g=None: events.append(("update", entity.name)),
    None,
    lambda entity, other, g=None: events.append(("collision", entity.name, other.name)),
    True,
    0,
    0,
)
enemy = Entity("enemy", 1, Vector(3, 3, 0), Vector(4, 4, 0))
wall = Entity("wall", ENTITY_TYPE_3D_SPRITE, Vector(6, 0, 0), Vector(1, 2, 0))
sprite = Sprite3D(SPRITE_3D_HOUSE, Vector(6, 0, 0), 2.0, 3.0, 0.25, 0x1234, None)
sprite.scale_factor = 2.5
wall.sprite_3d = sprite
wall.sprite_3d_color = 0x4321

level.entity_add(player)
level.entity_add(enemy)
level.entity_add(wall)
level.start()
print("engine_sprite_alias", wall.has_3d_sprite(), wall.sprite_3d.scale_factor, wall.sprite_3d.color)
print("engine_collision", [item.name for item in level.collision_list(player)], level.has_collided(player), level.is_collision(player, enemy))
level.update()
eng = GameEngine(game, 0)
eng.update_game_input(2)
eng.run_async(False)
print("engine_game_input", game.input, inp.reset_count)
print("engine_draw", len(draw.calls) > 0, any(call[0] == "fill" for call in draw.calls), any(call[0] == "swap" for call in draw.calls))
print("engine_events", events)
print("engine_level", game.level_exists("arena"), game.level_switch("arena"), game.clamp(12, 1, 9), level.entity_count)
print("engine_remove", game.level_remove(level), game.current_level)
"""


WIKIREADER_HTTP_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
import sim_usocket
import sim_tls
sys.modules["usocket"] = sim_usocket
sys.modules["socket"] = sim_usocket
sys.modules["tls"] = sim_tls
sys.modules["ssl"] = sim_tls
from utime import sleep_ms

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "picocalc-pico2w",
    0,
    True,
    False,
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
    "network-fixtures",
    "",
)

from picoware.system.http import HTTP

headers = dict()
headers["User-Agent"] = "Picoware-WikiReader/Test"
headers["Accept-Encoding"] = "identity"
headers["Connection"] = "close"

def check_response(label, response, needle):
    print(label + "_status", response.status_code)
    print(label + "_needle", int(needle in response.text))
    response.close()

client = HTTP(chunk_size=128)
for term in ("Sex", "MicroPython", "Raspberry%20Pi"):
    url = "https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=15&srsearch=" + term + "&format=json&formatversion=2"
    response = client.get(url, headers=headers, timeout=5)
    check_response("wiki_search_" + term.replace("%20", "_"), response, '"search"')

article = client.get(
    "https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=true&redirects=1&pageids=3&format=json&formatversion=2",
    headers=headers,
    timeout=5,
)
check_response("wiki_article", article, "Picoware simulator fixture")

done = []
def callback(response=None, state=None, error=None):
    status = response.status_code if response else -1
    text = response.text if response else ""
    print("wiki_async_callback", status, state, error if error else "")
    print("wiki_async_needle", int('"search"' in text))
    if response:
        response.close()
    done.append(1)

client.callback = callback
started = client.get_async(
    "https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=15&srsearch=Sex&format=json&formatversion=2",
    headers=headers,
    timeout=5,
)
print("wiki_async_started", int(started))
for _ in range(200):
    if done:
        break
    sleep_ms(10)
print("wiki_async_done", int(bool(done)))

class FakeSocket:
    def __init__(self):
        self.data = b"HTTP/1.1 200 OK\r\nHeader: value\r\n\r\nbody"
        self.offset = 0
        self.sent = b""

    def read(self, count):
        if self.offset >= len(self.data):
            return b""
        end = min(len(self.data), self.offset + count)
        chunk = self.data[self.offset:end]
        self.offset = end
        return chunk

    def write(self, data):
        self.sent += data
        return len(data)

    def close(self):
        pass

compat = sim_tls._wrap_compat(FakeSocket())
print("wiki_tls_line", compat.readline())
print("wiki_tls_body", compat.read())
"""


FLAPPY_LOGIC_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
sys.path.insert(0, "builds/MicroPython/apps_unfrozen/games")

from picoware.system.vector import Vector
flappy = __import__("Flappy Bird")


class Draw:
    def __init__(self):
        self.size = Vector(320, 320)

    def scale(self, x, y):
        return int(x), int(y)

    def scale_x(self, value):
        return int(value)

    def scale_y(self, value):
        return int(value)


class Input:
    button = -1

    def reset(self):
        pass


class ViewManager:
    def __init__(self):
        self.draw = Draw()
        self.input_manager = Input()


vm = ViewManager()
print("flappy_start", int(flappy.start(vm)))
state = flappy._game_state
initial = sum(1 for p in state.pilars if p and p.visible)
for _ in range(45):
    state.bird.point.y = 120
    state.bird.gravity = 0
    flappy.__flappy_game_tick()
visible = sum(1 for p in state.pilars if p and p.visible)
spawned = sum(1 for p in state.pilars if p and getattr(p, "spawned_next", False))
print("flappy_pillars", initial, visible, state.pilars_count, spawned)
"""


TOUCH_BATTERY_SCRIPT = r"""
import sys
sys.path.insert(0, "src/MicroPython")
sys.path.insert(0, "simulator/hardware")
import sim_runtime
sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "waveshare-1.43-rp2350",
    0,
    True,
    False,
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
from picoware.system.input import Input
from picoware.system import buttons
import waveshare_battery

inp = Input()
sim_runtime.set_touch_point(440, 200, 6)
print("touch_button", inp.button, buttons.BUTTON_RIGHT, inp.point, int(inp.is_pressed()))
inp.reset()
sim_runtime.set_battery_percentage(42)
print("battery_runtime", inp.battery, waveshare_battery.get_percentage())

sim_runtime.configure(
    ".",
    {sd_root!r},
    "builds/MicroPython/apps_unfrozen",
    2,
    "crowpanel-10.1",
    0,
    True,
    False,
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
from picoware.system.input import Input as CrowInput
crow = CrowInput()
sim_runtime.set_touch_point(980, 300, 6)
print("crow_touch", crow.button, buttons.BUTTON_RIGHT, crow.point, int(crow.is_pressed()))
"""


class HarnessFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "all",
            "jpeg",
            "psram",
            "machine",
            "usb",
            "bluetooth",
            "wifi",
            "ghouls",
            "gameboy",
            "engine",
            "viewer",
            "flappy",
            "touch-battery",
            "settings",
            "wikireader",
        ),
        default="all",
        help="Subset of checks to run.",
    )
    parser.add_argument("--keep-sd", action="store_true")
    return parser.parse_args()


def check_micropython_available() -> None:
    if shutil.which("micropython") is None:
        raise HarnessFailure("micropython was not found in PATH")


def run_script(name: str, script: str, expected: tuple[str, ...], sd_root: Path) -> None:
    result = subprocess.run(
        ["micropython", "-c", script.format(sd_root=str(sd_root))],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "{} failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                name, result.returncode, result.stdout, result.stderr
            )
        )
    missing = [item for item in expected if item not in result.stdout]
    if missing:
        raise HarnessFailure(
            "{} missing expected output {}\nstdout:\n{}".format(
                name, missing, result.stdout
            )
        )
    print("[capability-harness:pass]", name)


def run_jpeg(sd_root: Path) -> None:
    shutil.copyfile(JPEG_FIXTURE, sd_root / "fixture.jpg")
    run_script(
        "jpeg",
        JPEG_SCRIPT,
        (
            "jpeg_info 1 1272 680",
            "jpeg_open_ram 1",
            "jpeg_decode_buffer 1",
            "jpeg_frame_changed 1",
            "jpeg_open_path 1",
            "jpeg_decode_path 1",
            "jpeg_path_changed 1",
            "jpeg_bad_info 0 0 0",
            "jpeg_bad_open 0",
            "jpeg_bad_decode 0",
        ),
        sd_root,
    )


def run_psram(sd_root: Path) -> None:
    run_script(
        "psram",
        PSRAM_SCRIPT,
        (
            "psram_size 8388608 8388608 0",
            "psram_read b'abcd'",
            "psram_scalars 18 0x3456 0x789abcde",
            "psram_bulk_write 12",
            "psram_bulk_read [1, 2, 3]",
            "psram_fill 4 b'\\xaa\\xaa\\xaa\\xaa'",
            "psram_fill32 8 ['0x11223344', '0x11223344']",
            "psram_copy ['0x11223344', '0x11223344']",
            "psram_read_into 4 b'abcd'",
            "psram_bounds 1",
            "psram_alloc 1 1 1",
            "sd_large_write 573440",
        ),
        sd_root,
    )


def run_machine(sd_root: Path) -> None:
    run_script(
        "machine",
        MACHINE_SCRIPT,
        (
            "machine_i2c_scan [66]",
            "machine_i2c_read b'abc\\x00'",
            "machine_i2c_mem b'abXY\\x00'",
            "machine_i2c_into b'abX'",
            "machine_spi_read b'hi\\xee'",
            "machine_spi_rw b'AB\\x00\\x00'",
            "machine_adc 12345",
            "('one', 7)",
            "('periodic', 8)",
            "machine_wdt_before 0",
            "machine_wdt_after 1 1",
            "machine_wdt_feed 0",
        ),
        sd_root,
    )


def run_usb(sd_root: Path) -> None:
    run_script(
        "usb",
        USB_SCRIPT,
        (
            "usb_inactive_submit 0",
            "usb_active 1 ['reset']",
            "usb_open True (2,)",
            "usb_control b'report'",
            "usb_submit_keyboard 1",
            "usb_submit_consumer 1",
            "usb_last 131 hid-consumer b'\\xcd\\x00'",
            "usb_recv b'host'",
            "usb_log_count 2 1",
        ),
        sd_root,
    )


def run_bluetooth(sd_root: Path) -> None:
    run_script(
        "bluetooth",
        BLUETOOTH_SCRIPT,
        (
            "bt_scan 2 b'\\x02PCWU\\x01' -33",
            "bt_connect 1",
            "bt_blocked 1",
            "bt_adv 1 b'adv' b'rsp' False",
            "bt_notify ((1, 3, b'echo:hello'),)",
        ),
        sd_root,
    )


def run_wifi(sd_root: Path) -> None:
    run_script(
        "wifi",
        WIFI_SCRIPT,
        (
            "wifi_scan [(b'Secure'",
            "wifi_missing -2 0",
            "wifi_badpass -3 0",
            "wifi_connected 3 1 -35 9",
            "wifi_ap 1 Picoware-AP 3 (b'\\xaa\\xbb\\xcc\\xdd\\xee\\xff',)",
        ),
        sd_root,
    )


def run_ghouls(sd_root: Path) -> None:
    run_script(
        "ghouls",
        GHOULS_SCRIPT,
        (
            "ghouls_state True (6, 6) 100 1 2 6",
            "ghouls_exit False",
        ),
        sd_root,
    )


def write_gameboy_fixture(sd_root: Path) -> None:
    data = bytearray(0x8000)
    data[0x100:0x104] = b"\x00\xC3\x00\x01"
    data[0x134:0x13B] = b"SIMTEST"
    data[0x147] = 0x00
    data[0x148] = 0x00
    data[0x149] = 0x00
    checksum = 0
    for value in data[0x134:0x14D]:
        checksum = (checksum - value - 1) & 0xFF
    data[0x14D] = checksum
    (sd_root / "fixture.gb").write_bytes(data)


def run_gameboy(sd_root: Path) -> None:
    write_gameboy_fixture(sd_root)
    run_script(
        "gameboy",
        GAMEBOY_SCRIPT,
        (
            "gameboy_start 1",
            "gameboy_inputmap (32, 30, 4, 43)",
            "gameboy_control 1",
            "gameboy_state True SIMTEST 32768 6 54 (0, 58, 59, 57, 54, 54)",
            "gameboy_native 1 1",
            "gameboy_saved 1 1",
            "gameboy_missing 1",
        ),
        sd_root,
    )


def run_engine(sd_root: Path) -> None:
    run_script(
        "engine",
        ENGINE_SCRIPT,
        (
            "engine_sprite_alias True 2.5 17185",
            "engine_collision ['enemy'] True True",
            "engine_game_input 4 1",
            "engine_draw True True True",
            "('collision', 'player', 'enemy')",
            "engine_level True True 9 3",
            "engine_remove True None",
        ),
        sd_root,
    )


def run_viewer(sd_root: Path) -> None:
    run_sd = sd_root / "viewer-smoke"
    screenshot = run_sd / "viewer.bmp"
    frame = run_sd / "sim_frame.rgb565"
    status = run_sd / "sim_frame.rgb565.status"
    error = run_sd / "sim_frame.rgb565.error"
    viewer_log = Path("/tmp/picoware-sim-viewer.log")
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = env.get("SDL_VIDEODRIVER", "dummy")
    result = subprocess.run(
        [
            "micropython",
            "simulator/run.py",
            "--viewer",
            "--exit-after-frames",
            "24",
            "--audio",
            "silent",
            "--network",
            "offline",
            "--sd",
            str(run_sd),
            "--reset-sd",
            "--sd-profile",
            "network-fixtures",
            "--screenshot",
            str(screenshot),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "viewer failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if error.exists():
        raise HarnessFailure("viewer wrote error file: {}".format(error.read_text()))
    if viewer_log.exists():
        log_text = viewer_log.read_text(errors="replace")
        if "SDL_Init failed" in log_text or "error" in log_text.lower():
            raise HarnessFailure("viewer log contains failure:\n{}".format(log_text))
    if not frame.exists() or frame.stat().st_size != 320 * 320 * 2:
        raise HarnessFailure("viewer frame missing or wrong size: {}".format(frame))
    frame_data = frame.read_bytes()
    if sum(frame_data) == 0 or len(set(frame_data)) < 2:
        raise HarnessFailure("viewer frame appears blank")
    if not screenshot.exists() or screenshot.stat().st_size <= 54:
        raise HarnessFailure("viewer screenshot missing or empty: {}".format(screenshot))
    bmp = screenshot.read_bytes()
    if bmp[:2] != b"BM":
        raise HarnessFailure("viewer screenshot is not a BMP")
    status_text = status.read_text(errors="replace") if status.exists() else ""
    required = ("Picoware Simulator", "Frames:", "Network: offline Audio: silent")
    missing = [item for item in required if item not in status_text]
    if missing:
        raise HarnessFailure("viewer status missing {}\n{}".format(missing, status_text))
    print("[capability-harness:pass] viewer")


def run_flappy(sd_root: Path) -> None:
    run_sd = sd_root / "flappy-smoke"
    screenshot = run_sd / "flappy.bmp"
    frame = run_sd / "sim_frame.rgb565"
    error = run_sd / "sim_frame.rgb565.error"
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = env.get("SDL_VIDEODRIVER", "dummy")
    result = subprocess.run(
        [
            "micropython",
            "simulator/run.py",
            "--viewer",
            "--game",
            "Flappy Bird",
            "--keys",
            "enter",
            "--exit-after-frames",
            "45",
            "--audio",
            "silent",
            "--network",
            "offline",
            "--sd",
            str(run_sd),
            "--reset-sd",
            "--sd-profile",
            "dev",
            "--screenshot",
            str(screenshot),
            "--trace-views",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "flappy viewer failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if error.exists():
        raise HarnessFailure("flappy viewer wrote error file: {}".format(error.read_text()))
    if "Imported Flappy Bird" not in result.stdout:
        raise HarnessFailure("flappy did not import requested game\nstdout:\n{}".format(result.stdout))
    if "Imported FlipWorld" in result.stdout:
        raise HarnessFailure("flappy launcher overshot into FlipWorld\nstdout:\n{}".format(result.stdout))
    if "[sim:engine] frame 0 game= Flappy Bird" not in result.stdout:
        raise HarnessFailure("flappy engine frames were not traced\nstdout:\n{}".format(result.stdout))
    if not frame.exists() or frame.stat().st_size != 320 * 320 * 2:
        raise HarnessFailure("flappy frame missing or wrong size: {}".format(frame))
    data = frame.read_bytes()
    pixels = [data[i] | (data[i + 1] << 8) for i in range(0, len(data), 2)]
    colors = set(pixels)
    required_colors = {0x07FF, 0x07E0, 0xFFFF, 0x0000}
    if len(colors) < 5 or not required_colors.issubset(colors):
        raise HarnessFailure("flappy frame does not contain expected game colors: {}".format(sorted(colors)))
    scene_colors = required_colors | {0x03E0, 0xFFE0}
    sprite_colors = colors - scene_colors
    if len(colors) < 12 or len(sprite_colors) < 5:
        raise HarnessFailure("flappy bird sprite still lacks RGB332 colors: {}".format(sorted(colors)))
    if all(pixel == 0xFFFF for pixel in pixels):
        raise HarnessFailure("flappy frame is all white")
    if not screenshot.exists() or screenshot.stat().st_size <= 54:
        raise HarnessFailure("flappy screenshot missing or empty: {}".format(screenshot))
    run_script(
        "flappy-logic",
        FLAPPY_LOGIC_SCRIPT,
        (
            "flappy_start 1",
            "flappy_pillars 1 2 2 1",
        ),
        sd_root,
    )
    print("[capability-harness:pass] flappy")


def run_touch_battery(sd_root: Path) -> None:
    run_script(
        "touch-battery",
        TOUCH_BATTERY_SCRIPT,
        (
            "touch_button",
            "battery_runtime 42 42",
            "crow_touch",
        ),
        sd_root,
    )


def run_settings(sd_root: Path) -> None:
    run_sd = sd_root / "settings-smoke"
    screenshot = run_sd / "settings.bmp"
    frame = run_sd / "sim_frame.rgb565"
    error = run_sd / "sim_frame.rgb565.error"
    settings_path = run_sd / "picoware" / "settings" / "picoware.json"
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = env.get("SDL_VIDEODRIVER", "dummy")
    result = subprocess.run(
        [
            "micropython",
            "simulator/run.py",
            "--viewer",
            "--open",
            "System",
            "--keys",
            "enter,down,enter,enter",
            "--exit-after-frames",
            "140",
            "--audio",
            "silent",
            "--network",
            "offline",
            "--sd",
            str(run_sd),
            "--reset-sd",
            "--sd-profile",
            "dev",
            "--screenshot",
            str(screenshot),
            "--trace-views",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "settings viewer failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if error.exists():
        raise HarnessFailure("settings viewer wrote error file: {}".format(error.read_text()))
    bad_text = ("Error running view", "__save_setting", "__fetch_setting")
    for text in bad_text:
        if text in result.stdout or text in result.stderr:
            raise HarnessFailure("settings emitted {}\nstdout:\n{}\nstderr:\n{}".format(text, result.stdout, result.stderr))
    if not settings_path.exists():
        raise HarnessFailure("settings file missing: {}".format(settings_path))
    import json

    settings = json.loads(settings_path.read_text())
    if settings.get("onscreen_keyboard") is not True:
        raise HarnessFailure("onscreen_keyboard was not saved true: {}".format(settings))
    if not frame.exists() or frame.stat().st_size != 320 * 320 * 2:
        raise HarnessFailure("settings frame missing or wrong size: {}".format(frame))
    if not screenshot.exists() or screenshot.stat().st_size <= 54:
        raise HarnessFailure("settings screenshot missing or empty: {}".format(screenshot))
    print("[capability-harness:pass] settings")


def run_wikireader_http(sd_root: Path) -> None:
    run_script(
        "wikireader-http",
        WIKIREADER_HTTP_SCRIPT,
        (
            "wiki_search_Sex_status 200",
            "wiki_search_Sex_needle 1",
            "wiki_search_MicroPython_status 200",
            "wiki_search_MicroPython_needle 1",
            "wiki_search_Raspberry_Pi_status 200",
            "wiki_search_Raspberry_Pi_needle 1",
            "wiki_article_status 200",
            "wiki_article_needle 1",
            "wiki_async_started 1",
            "wiki_async_callback 200 0",
            "wiki_async_needle 1",
            "wiki_async_done 1",
            "wiki_tls_line b'HTTP/1.1 200 OK\\r\\n'",
            "wiki_tls_body b'Header: value\\r\\n\\r\\nbody'",
        ),
        sd_root,
    )


def run_wikireader(sd_root: Path) -> None:
    run_wikireader_http(sd_root)

    run_sd = sd_root / "wikireader-smoke"
    screenshot = run_sd / "wikireader.bmp"
    frame = run_sd / "sim_frame.rgb565"
    error = run_sd / "sim_frame.rgb565.error"
    script = sd_root / "wikireader.script"
    script.write_text("app wikireader\nkeys 1\ntext Sex\nenter\n")
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = env.get("SDL_VIDEODRIVER", "dummy")
    result = subprocess.run(
        [
            "micropython",
            "simulator/run.py",
            "--viewer",
            "--script",
            str(script),
            "--exit-after-frames",
            "240",
            "--audio",
            "silent",
            "--network",
            "offline",
            "--sd",
            str(run_sd),
            "--reset-sd",
            "--sd-profile",
            "network-fixtures",
            "--screenshot",
            str(screenshot),
            "--trace-views",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessFailure(
            "wikireader viewer failed with exit code {}\nstdout:\n{}\nstderr:\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if error.exists():
        raise HarnessFailure("wikireader viewer wrote error file: {}".format(error.read_text()))
    bad_text = ("API Error", "Bad API Response", "Invalid API Response", "Error running view")
    for text in bad_text:
        if text in result.stdout or text in result.stderr:
            raise HarnessFailure("wikireader emitted {}\nstdout:\n{}\nstderr:\n{}".format(text, result.stdout, result.stderr))
    required_text = ("Imported wikireader", "[Keyboard] save from textbox response='Sex'", "(HTTP) started", "(HTTP) finished")
    for text in required_text:
        if text not in result.stdout:
            raise HarnessFailure("wikireader missing {}\nstdout:\n{}".format(text, result.stdout))
    if not frame.exists() or frame.stat().st_size != 320 * 320 * 2:
        raise HarnessFailure("wikireader frame missing or wrong size: {}".format(frame))
    data = frame.read_bytes()
    if sum(data) == 0 or len(set(data)) < 2:
        raise HarnessFailure("wikireader frame appears blank")
    if not screenshot.exists() or screenshot.stat().st_size <= 54:
        raise HarnessFailure("wikireader screenshot missing or empty: {}".format(screenshot))
    print("[capability-harness:pass] wikireader")


def main() -> int:
    args = parse_args()
    check_micropython_available()

    with tempfile.TemporaryDirectory(prefix="picoware-sim-cap-") as tmp:
        sd_root = Path(tmp)
        try:
            if args.mode in ("all", "jpeg"):
                run_jpeg(sd_root)
            if args.mode in ("all", "psram"):
                run_psram(sd_root)
            if args.mode in ("all", "machine"):
                run_machine(sd_root)
            if args.mode in ("all", "usb"):
                run_usb(sd_root)
            if args.mode in ("all", "bluetooth"):
                run_bluetooth(sd_root)
            if args.mode in ("all", "wifi"):
                run_wifi(sd_root)
            if args.mode in ("all", "ghouls"):
                run_ghouls(sd_root)
            if args.mode in ("all", "gameboy"):
                run_gameboy(sd_root)
            if args.mode in ("all", "engine"):
                run_engine(sd_root)
            if args.mode in ("all", "viewer"):
                run_viewer(sd_root)
            if args.mode == "flappy":
                run_flappy(sd_root)
            if args.mode in ("all", "touch-battery"):
                run_touch_battery(sd_root)
            if args.mode == "settings":
                run_settings(sd_root)
            if args.mode == "all":
                run_wikireader_http(sd_root)
            if args.mode == "wikireader":
                run_wikireader(sd_root)
        except Exception:
            if args.keep_sd:
                print("[capability-harness:sd]", sd_root)
            raise
    print("[capability-harness:pass] mode={}".format(args.mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
