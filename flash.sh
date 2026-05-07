#!/bin/bash

# =====================================================================
# Command Helper / Usage Guide
#
# Purpose:
# Automates erasing and flashing MicroPython firmware to ESP boards.
# Supports different chip architectures and automatically adjusts
# the flash address, default port, and binary file path.
#
# Usage:
# ./flash.sh [chip_type] [target_port]
#
# Parameters:
# chip_type   : Architecture of the board (esp32 or esp32c3). Defaults to esp32c3.
# target_port : Optional serial port override.
#
# Examples:
#
# Default deployment (esp32c3 on standard port):
# ./flash.sh
#
# Specify legacy board:
# ./flash.sh esp32
#
# Specify legacy board on a custom port:
# ./flash.sh esp32 /dev/ttyUSB_custom
# =====================================================================

# Handle input parameters with default fallback
CHIP=${1:-"esp32c3"}

# Configure variables based on the selected chip architecture
if [ "$CHIP" == "esp32c3" ]; then
    DEFAULT_PORT="/dev/ttyACM0"
    FLASH_ADDR="0x0"
    BIN_FILE="./config/iso/ESP32_GENERIC_C3-20260406-v1.28.0.bin"
elif [ "$CHIP" == "esp32" ]; then
    DEFAULT_PORT="/dev/ttyUSB0"
    FLASH_ADDR="0x1000"
    BIN_FILE="./config/iso/ESP32_GENERIC-20240222-v1.22.2.bin"
else
    echo "❌ Error: Unsupported chip type '$CHIP'."
    echo "Valid options are: esp32, esp32c3"
    exit 1
fi

# Allow overriding the default port with an additional argument
PORT=${2:-$DEFAULT_PORT}

echo "🔍 Detected available ports:"
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | sed 's/^/   - /'

echo "-----------------------------------"
echo "🛠️  Target Chip   : $CHIP"
echo "🔌 Target Port   : $PORT"
echo "📍 Flash Address : $FLASH_ADDR"
echo "📦 Firmware File : $BIN_FILE"
echo "-----------------------------------"

# Verify firmware file existence before proceeding
if [ ! -f "$BIN_FILE" ]; then
    echo "❌ Error: Firmware file '$BIN_FILE' not found."
    exit 1
fi

# Erase current image from the microcontroller
echo "🧹 Erasing current flash memory..."
if ! uvx esptool --chip "$CHIP" --port "$PORT" erase-flash; then
    echo "❌ Error: Failed to access port $PORT or erase flash memory."
    echo "Make sure the port is correct and not used by another program."
    exit 1
fi

# Flash new MicroPython image
echo "⚡ Flashing new MicroPython image..."
if ! uvx esptool --chip "$CHIP" --port "$PORT" --baud 460800 write-flash -z "$FLASH_ADDR" "$BIN_FILE"; then
    echo "❌ Error: Failed to write firmware to the board."
    exit 1
fi

echo "✅ Firmware flashed successfully!"
