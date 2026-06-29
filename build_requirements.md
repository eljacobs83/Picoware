# Build Requirements

Complete instructions for building Picoware firmware for all supported targets.

---

## Table of Contents

- [Repository layout](#repository-layout)
- [Target summary](#target-summary)
- [MicroPython – RP2 targets (UF2)](#micropython--rp2-targets-uf2)
- [MicroPython – Cardputer ADV (ESP32-S3)](#micropython--cardputer-adv-esp32-s3)
- [MicroPython – CrowPanel 10.1 (ESP32-P4)](#micropython--crowpanel-101-esp32-p4)
- [CircuitPython – RP2 targets (UF2)](#circuitpython--rp2-targets-uf2)
- [Compiling app bytecode (.mpy)](#compiling-app-bytecode-mpy)
- [Desktop simulator](#desktop-simulator)
- [Flashing devices](#flashing-devices)

---

## Repository layout

```
Picoware/
├── builds/
│   ├── MicroPython/          # output: *.uf2 and *.bin artifacts
│   └── CircuitPython/        # output: *.uf2 artifacts
├── src/
│   ├── MicroPython/          # firmware source (picoware package + C modules)
│   └── CircuitPython/        # firmware source (picoware package + C modules)
├── tools/                    # build helper scripts
└── simulator/                # desktop simulator source
```

---

## Target summary

| Output file | Firmware | Board / chip | Script |
|---|---|---|---|
| `builds/MicroPython/Picoware-PicoCalcPico.uf2` | MicroPython | RPI_PICO (RP2040) | `tools/micropython-picocalc-pico.sh` |
| `builds/MicroPython/Picoware-PicoCalcPicoW.uf2` | MicroPython | RPI_PICO_W (RP2040) | `tools/micropython-picocalc-pico-w.sh` |
| `builds/MicroPython/Picoware-PicoCalcPico2.uf2` | MicroPython | RPI_PICO2 (RP2350) | `tools/micropython-picocalc-pico2.sh` |
| `builds/MicroPython/Picoware-PicoCalcPico2W.uf2` | MicroPython | RPI_PICO2_W (RP2350) | `tools/micropython-picocalc-pico2-w.sh` |
| `builds/MicroPython/Picoware-PicoCalcPimoroni2W.uf2` | MicroPython | PIMORONI_PICO_PLUS2W_RP2350 | `tools/micropython-picocalc-pimoroni-2w.sh` |
| `builds/MicroPython/Picoware-Waveshare-1.28.uf2` | MicroPython | WAVESHARE_RP2350_TOUCH_LCD_1_28 | `tools/micropython-waveshare-1.28.sh` |
| `builds/MicroPython/Picoware-Waveshare-1.43.uf2` | MicroPython | WAVESHARE_RP2350_TOUCH_LCD_1_43 | `tools/micropython-waveshare-1.43.sh` |
| `builds/MicroPython/Picoware-Waveshare-3.49.uf2` | MicroPython | WAVESHARE_RP2350_TOUCH_LCD_3_49 | `tools/micropython-waveshare-3.49.sh` |
| `builds/MicroPython/Picoware-Cardputer.bin` + bootloader + partition-table | MicroPython | ESP32_GENERIC_S3 | `tools/micropython-cardputer.sh` |
| `builds/MicroPython/Picoware-CrowPanel-10.1.bin` + bootloader + partition-table | MicroPython | ESP32_GENERIC_P4 (C6_WIFI) | `tools/micropython-crowpanel.sh` |
| `builds/CircuitPython/Picoware-PicoCalcPico.uf2` | CircuitPython | raspberry_pi_pico | `tools/circuitpython-picocalc-pico.sh` |
| `builds/CircuitPython/Picoware-PicoCalcPicoW.uf2` | CircuitPython | raspberry_pi_pico_w | `tools/circuitpython-picocalc-pico_w.sh` |
| `builds/CircuitPython/Picoware-PicoCalcPico2.uf2` | CircuitPython | raspberry_pi_pico2 | `tools/circuitpython-picocalc-pico2.sh` |
| `builds/CircuitPython/Picoware-PicoCalcPico2W.uf2` | CircuitPython | raspberry_pi_pico2_w | `tools/circuitpython-picocalc-pico2-w.sh` |
| `builds/CircuitPython/Picoware-PicoCalcPimoroni2W.uf2` | CircuitPython | pimoroni_pico_plus2w | `tools/circuitpython-picocalc-pimoroni-2w.sh` |

To build every target in one shot:

```bash
bash tools/micropython-all.sh      # all MicroPython targets
bash tools/circuitpython-all.sh    # all CircuitPython targets
```

---

## MicroPython – RP2 targets (UF2)

### Prerequisites

| Requirement | Notes |
|---|---|
| Linux or macOS host | Windows via WSL2 works |
| `git` | For cloning repos and submodules |
| `cmake` ≥ 3.20 | `sudo apt install cmake` / `brew install cmake` |
| `gcc-arm-none-eabi` | `sudo apt install gcc-arm-none-eabi` / Arm GNU Toolchain |
| `make` | Standard build tool |
| Python 3 | Required by MicroPython's build system |

### 1. Clone MicroPython and initialise submodules

```bash
mkdir ~/pico && cd ~/pico
git clone https://github.com/micropython/micropython.git
cd micropython
git submodule update --init
```

### 2. Build mpy-cross

```bash
cd ~/pico/micropython
make -C mpy-cross
```

### 3. Set path variables in the build scripts

Open `tools/micropython-all.sh` (or the individual target script) and update:

```sh
micropython_dir="/path/to/micropython/ports/rp2"   # e.g. ~/pico/micropython/ports/rp2
picoware_dir="/path/to/Picoware"                    # root of this repository
```

> The individual per-target scripts (`tools/micropython-picocalc-pico.sh`, etc.) contain the same two variables and must be updated the same way.

### 4. Build

```bash
# All RP2 targets (PicoCalc + Waveshare)
bash tools/micropython-all.sh

# Or a single target, e.g. PicoCalc with a Raspberry Pi Pico
bash tools/micropython-picocalc-pico.sh
```

Output UF2 files are written to `builds/MicroPython/`.

### Custom board files

The Pimoroni and Waveshare boards require additional board definition files that are
not part of the upstream MicroPython repository. The build scripts copy these
automatically when the path variables are configured correctly:

- `src/MicroPython/boards/PIMORONI_PICO_PLUS2W_RP2350/` → `<micropython_dir>/boards/`
- `src/MicroPython/boards/WAVESHARE_RP2350_TOUCH_LCD_1_28/` → `<micropython_dir>/boards/`
- `src/MicroPython/boards/WAVESHARE_RP2350_TOUCH_LCD_1_43/` → `<micropython_dir>/boards/`
- `src/MicroPython/boards/WAVESHARE_RP2350_TOUCH_LCD_3_49/` → `<micropython_dir>/boards/`

The corresponding `.h` header for each board is also copied to:

```
<micropython_dir>/../../lib/pico-sdk/src/boards/include/boards/
```

### Build flags reference

| Target | BOARD | USER_C_MODULES cmake file | CFLAGS_EXTRA | MICROPY_HW_FLASH_STORAGE_BYTES |
|---|---|---|---|---|
| PicoCalc Pico | `RPI_PICO` | `PicoCalc/picoware_modules.cmake` | `-DPICOCALC` | 868352 |
| PicoCalc Pico W | `RPI_PICO_W` | `PicoCalc/picoware_modules.cmake` | `-DPICOCALC` | 442368 |
| PicoCalc Pico 2 | `RPI_PICO2` | `PicoCalc/picoware_modules.cmake` | `-DPICOCALC` | 2097152 |
| PicoCalc Pico 2W | `RPI_PICO2_W` | `PicoCalc/picoware_modules.cmake` | `-DPICOCALC` | 2097152 |
| PicoCalc Pimoroni 2W | `PIMORONI_PICO_PLUS2W_RP2350` | `PicoCalc/picoware_modules.cmake` | `-DPICOCALC` | _(default)_ |
| Waveshare 1.28 | `WAVESHARE_RP2350_TOUCH_LCD_1_28` | `Waveshare/RP2350-Touch-LCD-1.28/waveshare_modules.cmake` | `-DWAVESHARE_1_28` | _(default)_ |
| Waveshare 1.43 | `WAVESHARE_RP2350_TOUCH_LCD_1_43` | `Waveshare/RP2350-Touch-LCD-1.43/waveshare_modules.cmake` | `-DWAVESHARE_1_43` | _(default)_ |
| Waveshare 3.49 | `WAVESHARE_RP2350_TOUCH_LCD_3_49` | `Waveshare/RP2350-Touch-LCD-3.49/waveshare_modules.cmake` | `-DWAVESHARE_3_49` | _(default)_ |

---

## MicroPython – Cardputer ADV (ESP32-S3)

The Cardputer build produces three `.bin` files (firmware, bootloader, partition table)
rather than a single UF2.

### Prerequisites

| Requirement | Notes |
|---|---|
| Linux or macOS host | Windows via WSL2 works |
| ESP-IDF **v5.5.2** | Install via the [ESP-IDF install guide](https://docs.espressif.com/projects/esp-idf/en/v5.5.2/esp32s3/get-started/index.html) |
| Python 3 | Must match the version used by ESP-IDF |
| `git`, `cmake`, `make` | Standard build tools |
| Apple Silicon (optional) | Set `CARDPUTER_USE_ROSETTA=1` to force x86_64 build under Rosetta if the ESP-IDF Python env is x86-only |

### 1. Install ESP-IDF v5.5.2

```bash
mkdir -p ~/.espressif
cd ~/.espressif
git clone --branch v5.5.2 --depth 1 https://github.com/espressif/esp-idf.git v5.5.2/esp-idf
cd v5.5.2/esp-idf
./install.sh esp32s3
```

### 2. Clone MicroPython

```bash
mkdir ~/pico && cd ~/pico
git clone https://github.com/micropython/micropython.git
cd micropython
git submodule update --init
```

### 3. Configure environment variables

The Cardputer script reads three optional environment variables so you do not need to edit the script:

| Variable | Default (script) | Description |
|---|---|---|
| `MICROPYTHON_ESP32_PORT` | `/Users/user/pico/micropython/ports/esp32` | Path to MicroPython's `ports/esp32` |
| `MICROPYTHON_ROOT` | `/Users/user/pico/micropython` | Path to MicroPython root |
| `ESP_IDF_DIR` | `/Users/user/.espressif/v5.5.2/esp-idf` | Path to ESP-IDF root |
| `IDF_TOOLS_PATH` | `$HOME/.espressif` | Path to ESP-IDF tools |
| `CARDPUTER_USE_ROSETTA` | `0` | Set to `1` on Apple Silicon to force Rosetta |

Export these before running the script, or edit the defaults at the top of `tools/micropython-cardputer.sh`.

### 4. Build

```bash
bash tools/micropython-cardputer.sh
```

Artifacts are written to `builds/MicroPython/`:
- `Picoware-Cardputer.bin`
- `Picoware-Cardputer-bootloader.bin`
- `Picoware-Cardputer-partition-table.bin`

---

## MicroPython – CrowPanel 10.1 (ESP32-P4)

### Prerequisites

Same toolchain as Cardputer, but targeting ESP32-P4 instead of ESP32-S3.
The CrowPanel build always runs under Rosetta on Apple Silicon automatically.

| Requirement | Notes |
|---|---|
| ESP-IDF **v5.5.2** | Same install as Cardputer; run `./install.sh esp32p4` |
| MicroPython source | Same clone as Cardputer |
| ESP-IDF managed components | `esp_lcd_ek79007` and `esp_lcd_touch_gt911` — fetched automatically by CMake |

### 1. Install ESP-IDF target support (if not already done)

```bash
cd ~/.espressif/v5.5.2/esp-idf
./install.sh esp32p4
```

### 2. Configure environment variables

| Variable | Default (script) | Description |
|---|---|---|
| `MICROPYTHON_ESP32_PORT` | `/Users/user/pico/micropython/ports/esp32` | Path to MicroPython's `ports/esp32` |
| `MICROPYTHON_ROOT` | `/Users/user/pico/micropython` | Path to MicroPython root |
| `ESP_IDF_DIR` | `/Users/user/.espressif/v5.5.2/esp-idf` | Path to ESP-IDF root |

### 3. Build

```bash
bash tools/micropython-crowpanel.sh build
```

Artifacts are written to `builds/MicroPython/`:
- `Picoware-CrowPanel-10.1.bin`
- `Picoware-CrowPanel-bootloader.bin`
- `Picoware-CrowPanel-partition-table.bin`

---

## CircuitPython – RP2 targets (UF2)

### Prerequisites

| Requirement | Notes |
|---|---|
| Linux or macOS host | Windows via WSL2 works |
| `git` | For cloning repos and submodules |
| Python 3 + `venv` | Used to create the CircuitPython build environment |
| `gcc-arm-none-eabi` | Same as MicroPython RP2 builds |
| `cmake`, `make` | Standard build tools |
| `pioasm` | Compiled automatically from pico-sdk if not found in PATH |

### 1. Clone CircuitPython and set up the build environment

```bash
mkdir ~/pico && cd ~/pico
git clone https://github.com/adafruit/circuitpython.git
cd circuitpython

python3 -m venv venv
source venv/bin/activate
pip install --upgrade -r requirements-dev.txt
pip install --upgrade -r requirements-doc.txt

git checkout main

cd ports/raspberrypi
make fetch-port-submodules

cd ~/pico/circuitpython
make -C mpy-cross
```

### 2. Set path variables in the build scripts

Open `tools/circuitpython-all.sh` (or the individual target script) and update:

```sh
circuitpython_dir="/path/to/circuitpython"   # e.g. ~/pico/circuitpython
picoware_dir="/path/to/Picoware"             # root of this repository
```

### 3. Activate the CircuitPython virtual environment

```bash
source ~/pico/circuitpython/venv/bin/activate
```

### 4. Build

```bash
# All CircuitPython RP2 targets
bash tools/circuitpython-all.sh

# Or a single target, e.g. PicoCalc with a Raspberry Pi Pico
bash tools/circuitpython-picocalc-pico.sh
```

Output UF2 files are written to `builds/CircuitPython/`.

### pioasm

The scripts compile two PIO programs to C headers before invoking `make`:

- `src/CircuitPython/PicoCalc/shared-bindings/picoware_psram/psram_qspi.pio`
- `src/CircuitPython/PicoCalc/shared-bindings/picoware_lcd/st7789_lcd.pio`

`pioasm` is located by the scripts in this order:

1. `<micropython_dir>/ports/rp2/build-RPI_PICO/pioasm/pioasm` (from a prior MicroPython RP2 build)
2. `<pico-sdk>/tools/pioasm/build/pioasm`
3. `pioasm` in `PATH`
4. Built from pico-sdk automatically if none of the above exist

---

## Compiling app bytecode (.mpy)

App Python source lives in `builds/MicroPython/apps_unfrozen/` and
`builds/CircuitPython/apps_unfrozen/`. The `tools/freeze-all.sh` script compiles
every `.py` file into `.mpy` bytecode and places the results in `builds/MicroPython/apps/`
and `builds/CircuitPython/apps/` respectively.

### Prerequisites

| Requirement | Notes |
|---|---|
| `mpy-cross` in `PATH` | Built during MicroPython setup (`make -C mpy-cross`) |
| `~/pico/circuitpython/mpy-cross/build/mpy-cross` | Built during CircuitPython setup |

### Run

```bash
# Edit the path variables at the top of the script first
bash tools/freeze-all.sh
```

---

## Desktop simulator

The simulator runs Picoware on Windows, macOS, and Linux using SDL2. It requires
a small set of native helper binaries built from C/C++ sources in `simulator/`.

### Prerequisites

| Requirement | Notes |
|---|---|
| SDL2 development libraries | See install commands below |
| A C/C++ compiler (`cc` / `c++`) | `clang` or `gcc` |

**Install SDL2:**

```bash
# macOS
brew install sdl2

# Debian / Ubuntu
sudo apt install libsdl2-dev

# Fedora
sudo dnf install SDL2-devel

# Arch Linux
sudo pacman -S sdl2

# MSYS2 (Windows)
pacman -S mingw-w64-x86_64-SDL2
```

On Apple Silicon, if only an x86_64 SDL2 is installed (e.g. via Rosetta Homebrew),
the script automatically builds x86_64 binaries that run under Rosetta 2.

### Build

```bash
# Build all simulator native helpers
sh simulator/build.sh all

# Build only the framebuffer viewer
sh simulator/build.sh viewer

# Build audio sidecars
sh simulator/build.sh audio

# Build JPEG decoder
sh simulator/build.sh jpeg

# Build Game Boy runner
sh simulator/build.sh gameboy

# Force rebuild even if binaries are up to date
sh simulator/build.sh --force all

# Clean
sh simulator/build.sh --clean
```

---

## Flashing devices

### RP2-based targets (UF2)

Hold the **BOOT/BOOTSEL** button while connecting the device via USB. It mounts as a
mass-storage drive. Drag-and-drop (or `cp`) the `.uf2` file onto it; the device resets
automatically.

### Cardputer ADV (ESP32-S3)

Use the provided flash script after building:

```bash
bash tools/micropython-cardputer.sh flash --port /dev/cu.usbmodem11401

# Options
#   --port, -p   Serial port (required)
#   --baud, -b   Baud rate (default: 460800)
#   --no-erase   Skip full-chip erase
#   --no-verify  Skip post-flash readback verification

# Environment overrides
#   ESP_IDF_DIR, CARDPUTER_BUILD_DIR, CARDPUTER_PORT, CARDPUTER_BAUD
#   CARDPUTER_USE_ROSETTA=1   Force Rosetta on Apple Silicon
```

### CrowPanel 10.1 (ESP32-P4)

```bash
bash tools/micropython-crowpanel.sh flash --port /dev/cu.usbserial11401

# Options
#   --port, -p   Serial port
#   --baud, -b   Baud rate (default: 115200)

# Environment overrides
#   ESP_IDF_DIR, CROWPANEL_BUILD_DIR, CROWPANEL_PORT, CROWPANEL_BAUD
```
