# 🚀 ESP32 MicroPython Development Guide

This repository provides source code and utility scripts to flash MicroPython firmware and deploy applications onto ESP32 and ESP32-C3 boards.

## 💻 Local Environment Setup

Follow these commands to prepare your local development environment :

```bash
# To install Python dependencies using uv
uv sync --dev

# To initialize codebase linters
uv run pre-commit install

# To run linters manually on all files
uv run pre-commit run -a
```

## ⚡ MicroPython Firmware Flashing

The automated `flash.sh` script erases the board memory and flashes the appropriate MicroPython version based on your chip architecture.

**Usage:** `./flash.sh [chip_type] [target_port]`

```bash
# To flash an ESP32-C3 (default chip, uses port /dev/ttyACM0)
./flash.sh

# To flash a standard ESP32 (uses port /dev/ttyUSB0)
./flash.sh esp32

# To flash a standard ESP32 on specific manual port
./flash.sh esp32 /dev/ttyUSB_custom
```

## 📡 Code Deployment and Environment Variables

The `upload.sh` script automates the deployment process by cleaning the board, generating a final `config.py` file from your secrets, and uploading the source files.

**Requirements:**
Ensure your application folder contains a `config.py.template` file using the `${VARIABLE}` syntax for your secrets.

**Usage:** `./upload.sh <source_directory> <environment_file> [target_port]`

```bash
# To deploy an application with a specific environment file
./upload.sh ./led-switch .env.device_1

# To deploy an application with a specific environment file on a custom serial port
./upload.sh ./led-switch .env.device_2 /dev/ttyUSB_custom
```

>  📝 **Note :** If the specified environment file is missing, the script will automatically create it from `./config/.env.example` environnement file template.

## ⌨️ Remote Console and Debugging

After deployment, you can interact directly with the board through the remote console :

```bash
# To open remote ESP 32 console
uvx mpremote
```

| Console Shortcut | Description |
| :--- | :--- |
| `CTRL + C` | 🛑 Stop the currently running Python program |
| `CTRL + D` | 🔄 Perform a soft reboot of the microcontroller |
| `CTRL + X` | 🚪 Safely exit the remote console |
