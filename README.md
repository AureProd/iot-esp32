# ESP 32 base commands

## To setup local env

Here are the commands to install your development environment :

```bash
# To install Python dependencies
uv sync --dev

# To initialize codebase linters
uv run pre-commit install

# To run codebase linters
uv run pre-commit run -a
```

## To reset flashed image

```bash
# To list connected esp 32 port
ls /dev/ttyUSB* /dev/ttyACM*

# To errase current esp 32 image
uvx esptool --chip esp32 --port /dev/ttyUSB0 erase-flash
uvx esptool --chip esp32c3 --port /dev/ttyACM0 erase-flash

# To flash new esp 32 micropython image
uvx esptool --chip esp32 --port /dev/ttyUSB0 --baud 460800 write-flash -z 0x1000 ./config/iso/ESP32_GENERIC-20240222-v1.22.2.bin
uvx esptool --chip esp32c3 --port /dev/ttyACM0 --baud 460800 write-flash -z 0x0 ./config/iso/ESP32_GENERIC_C3-20260406-v1.28.0.bin
```

## To open remote console

```bash
# CTRL + X --> to quit console
# CTRL + D --> to soft reboot
uvx mpremote
```

## To upload new python files project

```bash
# To copy one file
uvx mpremote cp main.py :main.py

# To copy one folder
cd test_on_off
uvx mpremote fs cp -r . :

# To copy + reboot
uvx mpremote fs cp -r . : + soft-reset + repl
```
